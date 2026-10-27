"""
stock_service.py — yfinance backend with Twelve Data as primary quote source.

Key fixes (2026-04):
  - Twelve Data symbol format fixed: HDFCBANK.NS → HDFCBANK:NSE (Indian stocks)
  - _symbol_currency() infers USD/INR from symbol suffix — fixes US stocks showing ₹
  - get_quote() has 3-tier fallback: Twelve Data → yfinance .info → yfinance .history()
  - yfinance .history() is the most reliable tier — always works even when market is closed
  - ALL yf.Ticker().info calls consolidated via _get_ticker_data() (1 call, not 4)
  - Threading Event locks prevent duplicate concurrent fetches for the same symbol
  - Increased cache TTLs: quote 30s→120s, candles 60s→900s, news 300s→900s
"""

import time
import math
import threading
import os
import requests
from datetime import datetime, timezone
import yfinance as yf

# ── Cache ──────────────────────────────────────────────────────────────────────
_cache: dict = {}
_cache_lock = threading.Lock()

def _get(key):
    with _cache_lock:
        e = _cache.get(key)
    return e["data"] if e and time.time() - e["ts"] < e["ttl"] else None

def _set(key, data, ttl):
    with _cache_lock:
        _cache[key] = {"ts": time.time(), "data": data, "ttl": ttl}

def _safe(v, d=2):
    try:
        f = float(v)
        return round(f, d) if math.isfinite(f) else None
    except:
        return None


# ── Symbol helpers ─────────────────────────────────────────────────────────────

def _td_symbol(yf_symbol):
    """
    Convert yfinance symbol format to Twelve Data API format.
    HDFCBANK.NS  →  HDFCBANK:NSE   (Indian NSE stocks)
    TATASTEEL.BO →  TATASTEEL:BSE  (Indian BSE stocks)
    AAPL, MSFT   →  unchanged      (US stocks work as-is)
    """
    if yf_symbol.endswith('.NS'):
        return yf_symbol[:-3] + ':NSE'
    if yf_symbol.endswith('.BO'):
        return yf_symbol[:-3] + ':BSE'
    return yf_symbol


def _symbol_currency(symbol):
    """
    Infer currency from symbol suffix.
    Reliable fallback when yfinance .info doesn't return a currency field —
    which happens when the market is closed or the info dict is sparse.
    Fixes: US stocks (AAPL, MSFT) were showing ₹ instead of $.
    """
    if symbol.endswith('.NS') or symbol.endswith('.BO'):
        return 'INR'
    return 'USD'   # US, global stocks


# ── Twelve Data API ────────────────────────────────────────────────────────────
_TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")


def _twelve_data_quote(symbol):
    """
    Fetch quote from Twelve Data API (free tier: 800 req/day, no IP blocking).
    Converts yfinance symbol to Twelve Data format via _td_symbol() first.
    Returns dict compatible with get_quote(), or None on any failure.
    """
    if not _TWELVE_DATA_KEY:
        return None
    try:
        td_sym = _td_symbol(symbol)   # e.g. HDFCBANK.NS → HDFCBANK:NSE
        url = (
            f"https://api.twelvedata.com/quote"
            f"?symbol={td_sym}&apikey={_TWELVE_DATA_KEY}"
        )
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        d = r.json()
        # Error responses from Twelve Data have a "code" or "status":"error" field
        if "code" in d or ("status" in d and d.get("status") == "error"):
            return None
        cur  = _safe(d.get("close"))
        prev = _safe(d.get("previous_close"))
        if not cur or cur == 0:
            return None   # Empty/zero response — fall through to yfinance
        chg  = _safe((cur or 0) - (prev or 0))
        chgp = _safe(((chg / prev) * 100) if prev else 0)
        # currency from response; fall back to symbol-suffix inference
        currency = d.get("currency") or _symbol_currency(symbol)
        return {
            "symbol":      symbol,
            "current":     cur,
            "change":      chg,
            "change_pct":  chgp,
            "high":        _safe(d.get("high")),
            "low":         _safe(d.get("low")),
            "open":        _safe(d.get("open")),
            "prev_close":  prev,
            "volume":      int(d.get("volume", 0) or 0),
            "avg_volume":  None,
            "currency":    currency,
            "_source":     "twelvedata",
        }
    except Exception as e:
        print(f"  ⚠ Twelve Data quote failed for {symbol}: {e}")
        return None


# ── Deduplicating yf.Ticker().info fetch ──────────────────────────────────────
# Concurrent requests for the same symbol wait for the first fetch instead of
# all hitting Yahoo Finance simultaneously.
_inflight: dict = {}
_inflight_lock = threading.Lock()


def _get_ticker_data(symbol):
    """
    Fetch yf.Ticker info ONCE and cache for 120 s.
    Used by get_profile(), get_metrics(), get_analyst() so they all share 1 HTTP call.
    """
    cache_key = f"ticker_data:{symbol}"
    cached = _get(cache_key)
    if cached:
        return cached

    with _inflight_lock:
        if symbol in _inflight:
            event = _inflight[symbol]
            is_leader = False
        else:
            event = threading.Event()
            _inflight[symbol] = event
            is_leader = True

    if not is_leader:
        event.wait(timeout=20)
        result = _get(cache_key)
        return result if result else {"info": {}, "error": "timeout waiting for fetch"}

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        data = {"info": info, "_ticker": symbol}
        _set(cache_key, data, 120)
        return data
    except Exception as e:
        return {"info": {}, "error": str(e)}
    finally:
        event.set()
        with _inflight_lock:
            _inflight.pop(symbol, None)


# ── Logo helper ────────────────────────────────────────────────────────────────
KNOWN_DOMAINS = {
    "RELIANCE": "ril.com",        "RELIANCE.NS": "ril.com",
    "TCS":      "tcs.com",        "TCS.NS":      "tcs.com",
    "HDFCBANK": "hdfcbank.com",   "HDFCBANK.NS": "hdfcbank.com",
    "INFY":     "infosys.com",    "INFY.NS":     "infosys.com",
    "ICICIBANK":"icicibank.com",  "ICICIBANK.NS":"icicibank.com",
    "HINDUNILVR":"hul.co.in",     "HINDUNILVR.NS":"hul.co.in",
    "SBIN":     "sbi.co.in",      "SBIN.NS":     "sbi.co.in",
    "BHARTIARTL":"airtel.com",    "BHARTIARTL.NS":"airtel.com",
    "BAJFINANCE":"bajajfinserv.in","BAJFINANCE.NS":"bajajfinserv.in",
    "ASIANPAINT":"asianpaints.com","ASIANPAINT.NS":"asianpaints.com",
    "MARUTI":   "marutisuzuki.com","MARUTI.NS":  "marutisuzuki.com",
    "KOTAKBANK":"kotak.com",      "KOTAKBANK.NS":"kotak.com",
    "LT":       "larsentoubro.com","LT.NS":       "larsentoubro.com",
    "AXISBANK": "axisbank.com",   "AXISBANK.NS": "axisbank.com",
    "TITAN":    "titancompany.in","TITAN.NS":    "titancompany.in",
    "SUNPHARMA":"sunpharma.com",  "SUNPHARMA.NS":"sunpharma.com",
    "WIPRO":    "wipro.com",      "WIPRO.NS":    "wipro.com",
    "HCLTECH":  "hcltech.com",    "HCLTECH.NS":  "hcltech.com",
    "TATAMOTORS":"tatamotors.com","TATAMOTORS.NS":"tatamotors.com",
    "ONGC":     "ongcindia.com",  "ONGC.NS":     "ongcindia.com",
    "NTPC":     "ntpc.co.in",     "NTPC.NS":     "ntpc.co.in",
    "POWERGRID":"powergridindia.com","POWERGRID.NS":"powergridindia.com",
    "JSWSTEEL": "jsw.in",         "JSWSTEEL.NS": "jsw.in",
    "ADANIENT": "adani.com",      "ADANIENT.NS": "adani.com",
    "ADANIPORTS":"adaniports.com","ADANIPORTS.NS":"adaniports.com",
    "COALINDIA":"coalindia.in",   "COALINDIA.NS":"coalindia.in",
    "TECHM":    "techmahindra.com","TECHM.NS":   "techmahindra.com",
    "TATASTEEL":"tatasteel.com",  "TATASTEEL.NS":"tatasteel.com",
    "HINDALCO": "hindalco.com",   "HINDALCO.NS": "hindalco.com",
    "CIPLA":    "cipla.com",      "CIPLA.NS":    "cipla.com",
    "DRREDDY":  "drreddys.com",   "DRREDDY.NS":  "drreddys.com",
    "BRITANNIA":"britannia.co.in","BRITANNIA.NS":"britannia.co.in",
    "APOLLOHOSP":"apollohospitals.com","APOLLOHOSP.NS":"apollohospitals.com",
    "SBILIFE":  "sbilife.co.in",  "SBILIFE.NS":  "sbilife.co.in",
    "HEROMOTOCO":"heromotocorp.com","HEROMOTOCO.NS":"heromotocorp.com",
    "BPCL":     "bharatpetroleum.com","BPCL.NS": "bharatpetroleum.com",
    "SUZLON":   "suzlon.com",     "SUZLON.NS":   "suzlon.com",
    "ZOMATO":   "zomato.com",     "ZOMATO.NS":   "zomato.com",
    "PAYTM":    "paytm.com",      "PAYTM.NS":    "paytm.com",
    "NYKAA":    "nykaa.com",      "NYKAA.NS":    "nykaa.com",
    "DLF":      "dlf.in",         "DLF.NS":      "dlf.in",
    "DMART":    "dmartindia.com", "DMART.NS":    "dmartindia.com",
    "IRCTC":    "irctc.co.in",    "IRCTC.NS":    "irctc.co.in",
    "HAL":      "hal-india.co.in","HAL.NS":      "hal-india.co.in",
    "IRFC":     "irfc.nic.in",    "IRFC.NS":     "irfc.nic.in",
    "LUPIN":    "lupin.com",      "LUPIN.NS":    "lupin.com",
    "AUROPHARMA":"aurobindo.com", "AUROPHARMA.NS":"aurobindo.com",
    "HAVELLS":  "havells.com",    "HAVELLS.NS":  "havells.com",
    "VOLTAS":   "voltas.com",     "VOLTAS.NS":   "voltas.com",
    "JUBLFOOD": "jubilantfoodworks.com","JUBLFOOD.NS":"jubilantfoodworks.com",
    "ITC":      "itcportal.com",  "ITC.NS":      "itcportal.com",
    "AAPL":     "apple.com",      "MSFT":        "microsoft.com",
    "GOOGL":    "google.com",     "GOOG":        "google.com",
    "AMZN":     "amazon.com",     "META":        "meta.com",
    "TSLA":     "tesla.com",      "NVDA":        "nvidia.com",
    "NFLX":     "netflix.com",    "AMD":         "amd.com",
    "INTC":     "intel.com",      "JPM":         "jpmorganchase.com",
    "BAC":      "bankofamerica.com", "V":        "visa.com",
    "WMT":      "walmart.com",    "DIS":         "thewaltdisneycompany.com",
}

US_KNOWN_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD",
    "INTC", "JPM", "BAC", "V", "MA", "WMT", "DIS", "UBER", "LYFT", "SNAP", "IBM",
    "ORCL", "CRM", "ADBE", "NOW", "PYPL", "SQ", "COIN", "HOOD", "SHOP", "SPOT",
    "ZM", "DOCU", "PLTR", "RBLX", "ABNB", "DASH", "RIVN", "LCID", "F", "GM",
    "GE", "BA", "CAT", "XOM", "CVX", "PFE", "JNJ", "MRK", "ABBV", "LLY", "UNH",
    "AMGN", "GILD", "MRNA", "GS", "MS", "C", "WFC", "AXP", "COF", "SCHW", "BLK",
    "KO", "PEP", "MCD", "SBUX", "NKE", "LULU", "TGT", "HD", "LOW", "COST", "ETSY", "EBAY"
}

def _get_logo(symbol, website=None):
    clean = symbol.upper().strip()
    if clean.endswith(".BO"):
        parqet_sym = clean.replace(".BO", ".NS")
    elif clean.endswith(".NS"):
        parqet_sym = clean
    elif clean in US_KNOWN_TICKERS:
        parqet_sym = clean
    else:
        # Default Indian stock without suffix
        parqet_sym = f"{clean}.NS"

    return f"https://assets.parqet.com/logos/symbol/{parqet_sym}"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_profile(symbol):
    k = f"profile:{symbol}"
    c = _get(k)
    if c:
        return c
    td   = _get_ticker_data(symbol)
    info = td.get("info", {})
    website = info.get("website", "")
    logo    = info.get("logo_url", "") or _get_logo(symbol, website)
    # CRITICAL: infer currency from symbol suffix when yf.info is sparse.
    # Prevents US stocks (AAPL, MSFT) from showing ₹ instead of $.
    currency         = info.get("currency") or _symbol_currency(symbol)
    default_country  = "India" if currency == "INR" else "USA"
    default_exchange = "NSE" if symbol.endswith(".NS") else ("BSE" if symbol.endswith(".BO") else "NASDAQ")

    # Extract domain from website or KNOWN_DOMAINS for fallback logo chain in frontend
    from urllib.parse import urlparse
    logo_domain = None
    if website:
        try:
            logo_domain = urlparse(website).netloc.replace("www.", "").strip("/")
        except Exception:
            pass
    if not logo_domain:
        clean_key = symbol.upper().replace(".BO", "").replace(".NS", "")
        logo_domain = KNOWN_DOMAINS.get(clean_key) or KNOWN_DOMAINS.get(symbol.upper())

    data = {
        "symbol":      info.get("symbol", symbol),
        "name":        info.get("longName") or info.get("shortName", symbol),
        "logo":        logo,
        "logo_domain": logo_domain or "",
        "exchange":    info.get("exchange", default_exchange),
        "industry":    info.get("industry", "N/A"),
        "sector":      info.get("sector", "N/A"),
        "country":     info.get("country", default_country),
        "currency":    currency,
        "web_url":     website,
        "description": (info.get("longBusinessSummary") or "")[:400],
        "employees":   info.get("fullTimeEmployees"),
        "market_cap":  info.get("marketCap"),
    }
    if "error" in td:
        data["error"] = td["error"]
    _set(k, data, 86400)
    return data


def get_quote(symbol):
    """
    Three-tier quote lookup; return unavailable if no usable price is found:

    Tier 1 — Twelve Data API
      Correct symbol format (HDFCBANK:NSE, AAPL), no IP blocking, 800 req/day free.
      Will be used for most requests after the cache warms up.

    Tier 2 — yfinance .info (shared cache, no extra HTTP call)
      Works when market is open and .info has currentPrice/regularMarketPrice.
      May return 0 on Indian stocks when market is closed — detected and skipped.

    Tier 3 — yfinance .history(period='5d')
      Uses the latest row with a finite positive close. Provider histories can
      contain empty placeholder rows even when earlier sessions are usable.
    """
    k = f"quote:{symbol}"
    c = _get(k)
    if c:
        return c

    # ── Tier 1: Twelve Data ────────────────────────────────────────────────────
    td_quote = _twelve_data_quote(symbol)
    if td_quote and (td_quote.get("current") or 0) > 0:
        _set(k, td_quote, 120)
        return td_quote

    # ── Tier 2: yfinance .info (from shared cache — no extra HTTP call) ───────
    try:
        td   = _get_ticker_data(symbol)
        info = td.get("info", {})
        cur  = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev = _safe(info.get("previousClose") or info.get("regularMarketPreviousClose"))
        if cur and cur > 0:
            chg  = _safe((cur or 0) - (prev or 0))
            chgp = _safe(((chg / prev) * 100) if prev else 0)
            data = {
                "symbol":     symbol,
                "current":    cur,
                "change":     chg,
                "change_pct": chgp,
                "high":       _safe(info.get("dayHigh") or info.get("regularMarketDayHigh")),
                "low":        _safe(info.get("dayLow")  or info.get("regularMarketDayLow")),
                "open":       _safe(info.get("open")    or info.get("regularMarketOpen")),
                "prev_close": prev,
                "volume":     info.get("volume", 0),
                "avg_volume": info.get("averageVolume"),
                "currency":   info.get("currency") or _symbol_currency(symbol),
                "_source":    "yfinance_info",
            }
            _set(k, data, 120)
            return data
    except Exception:
        pass

    # ── Tier 3: latest usable yfinance history row ────────────────────────────
    try:
        hist = yf.Ticker(symbol).history(period='5d')
        if not hist.empty:
            hist = hist.loc[hist['Close'].map(lambda v: (_safe(v, 8) or 0) > 0)].sort_index()
        if not hist.empty and len(hist) >= 1:
            cur  = round(float(hist['Close'].iloc[-1]), 2)
            prev = round(float(hist['Close'].iloc[-2]), 2) if len(hist) >= 2 else cur
            chg  = round(cur - prev, 2)
            chgp = round((chg / prev * 100) if prev else 0, 2)
            vol  = hist['Volume'].iloc[-1]
            data = {
                "symbol":     symbol,
                "current":    cur,
                "change":     chg,
                "change_pct": chgp,
                "high":       _safe(hist['High'].iloc[-1]),
                "low":        _safe(hist['Low'].iloc[-1]),
                "open":       _safe(hist['Open'].iloc[-1]),
                "prev_close": prev,
                "volume":     int(vol) if _safe(vol) is not None else None,
                "avg_volume": None,
                "currency":   _symbol_currency(symbol),
                "_source":    "yfinance_history",
            }
            _set(k, data, 120)
            return data
    except Exception as e:
        return {"error": str(e)}

    return {"error": f"No price data available for {symbol}"}

def _twelve_data_statistics(symbol):
    """
    Fetch comprehensive fundamental statistics from Twelve Data API.
    Covers: PE, P/B, EV/EBITDA, beta, 52W high/low, margins, ROE, ROA,
    debt/equity, current ratio, dividend yield, market cap, cash flow.

    Twelve Data returns ratio/margin fields as DECIMALS matching yfinance format:
      profit_margin = 0.2430 (24.30%), ROE = 1.4593 (145.93%)
    so they slot directly into the existing display logic.

    Cached for 1 hour (same as get_metrics TTL) — no extra calls on re-render.
    """
    if not _TWELVE_DATA_KEY:
        return {}
    cache_key = f"td_stats:{symbol}"
    cached = _get(cache_key)
    if cached:
        return cached
    try:
        td_sym = _td_symbol(symbol)   # HDFCBANK.NS → HDFCBANK:NSE
        url = (
            f"https://api.twelvedata.com/statistics"
            f"?symbol={td_sym}&apikey={_TWELVE_DATA_KEY}"
        )
        r = requests.get(url, timeout=12)
        if r.status_code != 200:
            return {}
        d = r.json()
        if "code" in d or ("status" in d and d.get("status") == "error"):
            return {}

        stats = d.get("statistics", {})
        vm    = stats.get("valuations_metrics", {})
        ss    = stats.get("stock_statistics", {})
        fi    = stats.get("financials", {})
        inc   = fi.get("income_statement", {})
        bal   = fi.get("balance_sheet", {})
        cf    = fi.get("cash_flow", {})

        def sf(v):
            try:
                f = float(v)
                return None if (f != f) else f
            except:
                return None

        result = {
            # Valuation — absolute numbers, use as-is
            "market_cap":        sf(vm.get("market_capitalization")),
            "pe_ratio":          sf(vm.get("trailing_pe")),
            "pe_forward":        sf(vm.get("forward_pe")),
            "price_to_book":     sf(vm.get("price_to_book_mrq")),
            "ev_ebitda":         sf(vm.get("enterprise_to_ebitda")),
            # Per-share / ratio — safe to use as-is
            "eps_ttm":           sf(inc.get("eps_diluted_ttm") or ss.get("diluted_eps_ttm")),
            "beta":              sf(ss.get("beta")),
            "week52_high":       sf(ss.get("52_week_high")),
            "week52_low":        sf(ss.get("52_week_low")),
            "current_ratio":     sf(bal.get("current_ratio_mrq") or ss.get("current_ratio_mrq")),
            "debt_equity":       sf(bal.get("total_debt_to_equity_mrq") or ss.get("total_debt_to_equity_mrq")),
            # Decimal ratios (TD returns same decimal format as yfinance: 0.25 = 25%)
            "profit_margins":    sf(ss.get("profit_margin")),
            "operating_margins": sf(ss.get("operating_margin_ttm")),
            "roe":               sf(ss.get("return_on_equity_ttm")),
            "roa":               sf(ss.get("return_on_assets_ttm")),
            "dividend_yield":    sf(
                ss.get("forward_annual_dividend_yield")
                or ss.get("trailing_annual_dividend_yield")
            ),
            # Absolute cash/debt figures
            "total_cash":        sf(bal.get("total_cash_mrq") or ss.get("total_cash_mrq")),
            "total_debt":        sf(bal.get("total_debt_mrq") or ss.get("total_debt_mrq")),
            "free_cashflow":     sf(
                cf.get("levered_free_cash_flow_ttm")
                or ss.get("levered_free_cash_flow_ttm")
            ),
        }
        _set(cache_key, result, 3600)
        return result
    except Exception as e:
        print(f"  ⚠ Twelve Data statistics failed for {symbol}: {e}")
        return {}


def get_metrics(symbol):
    """
    Key fundamentals with three-source fallback so ANY available data is shown:

      Source 1 — Twelve Data statistics (comprehensive, reliable, no IP throttle)
        PE, P/B, beta, 52W high/low, margins, ROE/ROA, debt/equity, market cap, etc.

      Source 2 — yfinance fast_info (lightweight, always available)
        market_cap, year_high (52W high), year_low (52W low)

      Source 3 — yfinance .info (from shared _get_ticker_data cache)
        Fallback for any field not covered above.

      Source 4 — Computed from balance_sheet + financials (for ROE only)
        Most reliable for ROE — already shown to work.
    """
    k = f"metrics:{symbol}"
    c = _get(k)
    if c:
        return c
    try:
        # Source 1: Twelve Data statistics
        tds  = _twelve_data_statistics(symbol)

        # Source 2: yfinance fast_info (lightweight, no .info parsing needed)
        fi_data = {}
        try:
            fi = yf.Ticker(symbol).fast_info
            fi_data = {
                "market_cap":  getattr(fi, "market_cap",  None),
                "week52_high": getattr(fi, "year_high",   None),
                "week52_low":  getattr(fi, "year_low",    None),
            }
        except Exception:
            pass

        # Source 3: yfinance .info (shared cache — no extra HTTP call)
        td   = _get_ticker_data(symbol)
        info = td.get("info", {})

        # Source 4: ROE computed from balance_sheet if not available above
        roe = tds.get("roe") or _safe(info.get("returnOnEquity"))
        if roe is None:
            try:
                t   = yf.Ticker(symbol)
                bs  = t.balance_sheet
                inc = t.financials
                if bs is not None and not bs.empty and inc is not None and not inc.empty:
                    eq_keys = [k for k in bs.index if "Stockholders" in k or "equity" in k.lower() or "Equity" in k]
                    ni_keys = [k for k in inc.index if "Net Income" in k or "NetIncome" in k]
                    if eq_keys and ni_keys:
                        equity     = float(bs.loc[eq_keys[0]].iloc[0])
                        net_income = float(inc.loc[ni_keys[0]].iloc[0])
                        if equity and equity != 0:
                            roe = round(net_income / equity, 4)
            except Exception:
                pass

        def first(*vals):
            """Return the first non-None, non-NaN value from multiple sources."""
            for v in vals:
                r = v if isinstance(v, (int, float)) and math.isfinite(v) else _safe(v)
                if r is not None:
                    return r
            return None

        # Derive a fractional yield from explicit annual cash dividend and price.
        # Yahoo's dividendYield field may use percentage points and is ambiguous.
        annual_dividend = _safe(info.get("dividendRate"), 6)
        dividend_price = _safe(info.get("currentPrice") or info.get("regularMarketPrice"), 6)
        derived_yield = annual_dividend / dividend_price if annual_dividend is not None and dividend_price and dividend_price > 0 else None
        data = {
            "symbol":            symbol,
            # PE / valuation
            "pe_ratio":          first(tds.get("pe_ratio"),          info.get("trailingPE")),
            "pe_forward":        first(tds.get("pe_forward"),         info.get("forwardPE")),
            "eps_ttm":           first(tds.get("eps_ttm"),            info.get("trailingEps")),
            "eps_forward":       _safe(info.get("forwardEps")),
            "price_to_book":     first(tds.get("price_to_book"),      info.get("priceToBook")),
            "ev_ebitda":         first(tds.get("ev_ebitda"),          info.get("enterpriseToEbitda")),
            # Margins
            "gross_margins":     _safe(info.get("grossMargins")),     # not in TD stats
            "profit_margins":    first(tds.get("profit_margins"),     info.get("profitMargins")),
            "operating_margins": first(tds.get("operating_margins"),  info.get("operatingMargins")),
            # Return metrics
            "roe":               roe,
            "roa":               first(tds.get("roa"),                info.get("returnOnAssets")),
            # Risk / structure
            "beta":              first(tds.get("beta"),               info.get("beta")),
            "debt_equity":       first(tds.get("debt_equity"),        info.get("debtToEquity")),
            "current_ratio":     first(tds.get("current_ratio"),      info.get("currentRatio")),
            "quick_ratio":       _safe(info.get("quickRatio")),
            # Income / dividends
            "dividend_yield":    first(derived_yield, _safe(info.get("trailingAnnualDividendYield"), 6), tds.get("dividend_yield")),
            # 52-week range: TD stats → fast_info → .info
            "week52_high":       first(tds.get("week52_high"),        fi_data.get("week52_high"),  info.get("fiftyTwoWeekHigh")),
            "week52_low":        first(tds.get("week52_low"),         fi_data.get("week52_low"),   info.get("fiftyTwoWeekLow")),
            # Market cap: TD stats → fast_info → .info
            "market_cap":        first(tds.get("market_cap"),         fi_data.get("market_cap"),   info.get("marketCap")),
            # Cash flow
            "free_cashflow":     first(tds.get("free_cashflow"),      info.get("freeCashflow")),
            "total_cash":        first(tds.get("total_cash"),         info.get("totalCash")),
            "total_debt":        first(tds.get("total_debt"),         info.get("totalDebt")),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"error": str(e)}



def get_analyst(symbol):
    """Uses shared ticker info; recommendations fetched separately (cached 1h)."""
    k = f"analyst:{symbol}"
    c = _get(k)
    if c:
        return c
    try:
        td   = _get_ticker_data(symbol)
        info = td.get("info", {})

        sb = buy = hold = sell = ssell = 0
        try:
            t   = yf.Ticker(symbol)
            rdf = t.recommendations
            if rdf is not None and not rdf.empty:
                for _, row in rdf.tail(10).iterrows():
                    g = str(row.get("To Grade", row.get("Action", ""))).lower()
                    if "strong buy" in g:                                          sb    += 1
                    elif any(x in g for x in ["buy","outperform","overweight"]):   buy   += 1
                    elif any(x in g for x in ["hold","neutral","equal"]):          hold  += 1
                    elif any(x in g for x in ["strong sell","underperform","underweight"]): ssell += 1
                    elif "sell" in g:                                              sell  += 1
        except Exception:
            pass

        total     = sb + buy + hold + sell + ssell
        ck        = info.get("recommendationKey", "").lower()
        cm        = {"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
        consensus = cm.get(ck, "N/A")
        if consensus == "N/A" and total > 0:
            bull = (sb + buy) / total
            bear = (sell + ssell) / total
            consensus = "Strong Buy" if bull >= 0.6 else "Buy" if bull >= 0.4 else "Sell" if bear >= 0.4 else "Hold"

        data = {
            "symbol":        symbol,
            "consensus":     consensus,
            "strong_buy":    sb,
            "buy":           buy,
            "hold":          hold,
            "sell":          sell,
            "strong_sell":   ssell,
            "total":         total,
            "target_mean":   _safe(info.get("targetMeanPrice")),
            "target_high":   _safe(info.get("targetHighPrice")),
            "target_low":    _safe(info.get("targetLowPrice")),
            "analyst_count": info.get("numberOfAnalystOpinions", 0),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"error": str(e)}


def _parse_yahoo_news(raw):
    articles = []
    for a in raw[:12]:
        try:
            if "content" in a:
                content  = a["content"]
                headline = content.get("title", "") or a.get("title", "")
                pub      = content.get("provider", {})
                source   = pub.get("displayName", pub.get("name", "")) if isinstance(pub, dict) else str(pub)
                canonical = content.get("canonicalUrl", {})
                url  = canonical.get("url", "") if isinstance(canonical, dict) else content.get("url", "")
                if not url:
                    url = a.get("link", "")
                pub_date = content.get("pubDate", "") or content.get("publishedAt", "")
                if pub_date:
                    try:
                        from datetime import datetime as _dt
                        unix_time = int(_dt.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp())
                    except:
                        unix_time = 0
                else:
                    unix_time = 0
                summary = content.get("summary", "") or content.get("description", "")
            else:
                headline  = a.get("title", "")
                source    = a.get("publisher", "")
                url       = a.get("link", "")
                unix_time = a.get("providerPublishTime", 0)
                summary   = a.get("summary", "")

            if headline:
                articles.append({"headline": headline, "source": source,
                                 "url": url, "datetime": unix_time, "summary": summary})
        except Exception:
            continue

    return articles


def _google_stock_news(symbol):
    """Company-specific RSS search; only dated links from the preceding seven days."""
    import re
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    names = {'TCS': 'Tata Consultancy Services', 'INFY': 'Infosys',
             'SBIN': 'State Bank of India', 'AAPL': 'Apple',
             'MSFT': 'Microsoft', 'NVDA': 'Nvidia'}
    ticker = symbol.removesuffix('.NS').removesuffix('.BO')
    profile = _get(f'profile:{symbol}') or {}
    info = (_get(f'ticker_data:{symbol}') or {}).get('info', {})
    name = names.get(ticker) or profile.get('name') or info.get('longName') or ticker
    name = re.sub(r'\b(Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?)\b', '', name, flags=re.I).strip(' ,.')
    india = _symbol_currency(symbol) == 'INR'
    response = requests.get('https://news.google.com/rss/search', params={
        'q': f'"{name}" stock when:7d', 'hl': 'en-IN' if india else 'en-US',
        'gl': 'IN' if india else 'US', 'ceid': 'IN:en' if india else 'US:en',
    }, timeout=6, headers={'User-Agent': 'FinAssist/1.0'})
    response.raise_for_status()
    if len(response.content) > 2_000_000:
        raise ValueError('News response exceeds size limit')
    articles = []
    for item in ET.fromstring(response.content).findall('./channel/item'):
        try:
            stamp = int(parsedate_to_datetime(item.findtext('pubDate', '')).timestamp())
            title = item.findtext('title', '').strip()
            url = item.findtext('link', '').strip()
            source = item.findtext('source', '').strip()
            if source and title.endswith(' - '+source):
                title = title[:-len(source)-3]
            if title and url.startswith(('https://', 'http://')) and time.time()-7*86400 <= stamp <= time.time():
                articles.append(dict(headline=title, source=source, url=url, datetime=stamp, summary=''))
        except (ValueError, TypeError, OverflowError):
            continue
    return articles


def get_news(symbol):
    """Yahoo company news with an independently retrieved RSS fallback."""
    k = f'news:{symbol}'
    cached = _get(k)
    if cached is not None:
        return cached
    failed = False
    try:
        articles = _parse_yahoo_news(yf.Ticker(symbol).get_news(count=12, tab='news') or [])
        articles = [a for a in articles if a['url'].startswith(('https://', 'http://'))
                    and isinstance(a['datetime'], (int, float))
                    and time.time()-7*86400 <= a['datetime'] <= time.time()]
    except Exception:
        articles = []
        failed = True
    provider = 'Yahoo Finance'
    if not articles:
        try:
            articles = _google_stock_news(symbol)
            provider = 'Google News RSS'
            failed = False
        except Exception:
            failed = True
    unique = {}
    for article in articles:
        unique.setdefault(article['headline'].casefold().strip(), article)
    articles = sorted(unique.values(), key=lambda a: a['datetime'], reverse=True)[:12]
    status = 'ready' if articles else 'unavailable' if failed else 'empty'
    data = dict(symbol=symbol, articles=articles, count=len(articles), status=status,
                provider=provider, fetched_at=datetime.now(timezone.utc).isoformat())
    if status == 'unavailable':
        data['message'] = 'News providers are temporarily unavailable. Please retry shortly.'
    _set(k, data, 900 if articles else 60)
    return data


# ── Candle helpers ─────────────────────────────────────────────────────────────
_TF_INTERVAL = {
    "1D":  "5m",
    "1W":  "15m",
    "1M":  "1h",
    "3M":  "1d",
    "6M":  "1d",
    "1Y":  "1d",
    "5Y":  "1wk",
    "MAX": "1mo",
}

def _tf_dates(tf):
    from datetime import date, timedelta
    today = date.today()
    end   = today + timedelta(days=1)
    delta = {
        "1D":  timedelta(days=2),
        "1W":  timedelta(days=7),
        "1M":  timedelta(days=31),
        "3M":  timedelta(days=92),
        "6M":  timedelta(days=183),
        "1Y":  timedelta(days=366),
        "5Y":  timedelta(days=365*5+2),
        "MAX": None,
    }.get(tf)
    if delta is None:
        return None, None
    return str(today - delta), str(end)


def get_candles(symbol, tf="3M"):
    """
    TTL: intraday (1D/1W) = 300 s, longer timeframes = 900 s.
    Was 60 s for all — massive reduction in Yahoo calls.
    """
    k = f"candle:{symbol}:{tf}"
    c = _get(k)
    if c:
        return c
    try:
        interval = _TF_INTERVAL.get(tf, "1d")
        start, end = _tf_dates(tf)
        ticker = yf.Ticker(symbol)
        if tf == "5Y":
            hist = ticker.history(period="5y", interval="1wk")
        elif tf == "MAX":
            hist = ticker.history(period="max", interval="1mo")
        else:
            hist = ticker.history(period="max", interval=interval) if start is None \
                   else ticker.history(start=start, end=end, interval=interval)

        if hist.empty:
            return {"error": "No chart data"}

        # Drop any rows with NaN in core price series
        hist = hist.dropna(subset=["Open", "High", "Low", "Close"])
        if hist.empty:
            return {"error": "No chart data"}

        import math
        candles = []
        for ts, row in hist.iterrows():
            try:
                c = float(row["Close"])
                o = float(row["Open"])
                h = float(row["High"])
                l = float(row["Low"])
                if math.isnan(c) or math.isnan(o) or math.isnan(h) or math.isnan(l):
                    continue
                unix = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts.value // 1_000_000_000)
                v = row.get("Volume", 0)
                vol = int(v) if v == v and not math.isnan(float(v)) else 0
                candles.append({
                    "time":   unix,
                    "open":   round(o, 2),
                    "high":   round(h, 2),
                    "low":    round(l, 2),
                    "close":  round(c, 2),
                    "volume": vol,
                })
            except Exception:
                pass

        data = {"symbol": symbol, "timeframe": tf, "candles": candles, "count": len(candles)}
        candle_ttl = 300 if tf in ("1D", "1W") else 900
        _set(k, data, candle_ttl)
        return data
    except Exception as e:
        return {"error": str(e)}


# ── Dashboard composite ────────────────────────────────────────────────────────
def get_full_dashboard(symbol):
    """
    After fix: _get_ticker_data() is called ONCE → ~1 Yahoo HTTP call total
    (shared across profile, metrics, analyst). Quote uses Twelve Data first.
    """
    return {
        "symbol":     symbol,
        "profile":    get_profile(symbol),
        "quote":      get_quote(symbol),
        "metrics":    get_metrics(symbol),
        "analyst":    get_analyst(symbol),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Cache utilities ────────────────────────────────────────────────────────────
def clear_cache(symbol=None):
    global _cache
    with _cache_lock:
        if symbol:
            keys = [k for k in _cache if f":{symbol}" in k]
            for k in keys:
                del _cache[k]
            return {"cleared": keys}
        n = len(_cache)
        _cache = {}
        return {"cleared_all": n}


def cache_stats():
    now = time.time()
    with _cache_lock:
        entries = [
            {"key": k, "age_sec": round(now - v["ts"]), "ttl": v["ttl"]}
            for k, v in _cache.items()
        ]
    return {"entries": len(entries), "keys": entries}
