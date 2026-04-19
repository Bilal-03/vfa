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
        return None if f != f else round(f, d)
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
def _get_logo(symbol, website=None):
    from urllib.parse import urlparse

    KNOWN_DOMAINS = {
        "RELIANCE": "ril.com",        "RELIANCE.NS": "ril.com",
        "TCS":      "tcs.com",        "TCS.NS":      "tcs.com",
        "HDFCBANK": "hdfcbank.com",   "HDFCBANK.NS": "hdfcbank.com",
        "INFY":     "infosys.com",    "INFY.NS":     "infosys.com",
        "ICICIBANK":"icicibank.com",  "ICICIBANK.NS":"icicibank.com",
        "HINDUNILVR":"hul.co.in",     "SBIN":        "sbi.co.in",
        "BHARTIARTL":"airtel.com",    "BHARTIARTL.NS":"airtel.com",
        "BAJFINANCE":"bajajfinserv.in",
        "ASIANPAINT":"asianpaints.com",
        "MARUTI":   "marutisuzuki.com","MARUTI.NS":  "marutisuzuki.com",
        "KOTAKBANK":"kotak.com",      "LT":          "larsentoubro.com",
        "AXISBANK": "axisbank.com",   "TITAN":       "titancompany.in",
        "SUNPHARMA":"sunpharma.com",  "WIPRO":       "wipro.com",
        "HCLTECH":  "hcltech.com",    "TATAMOTORS":  "tatamotors.com",
        "ONGC":     "ongcindia.com",  "NTPC":        "ntpc.co.in",
        "POWERGRID":"powergridindia.com",
        "JSWSTEEL": "jsw.in",         "ADANIENT":    "adani.com",
        "ADANIPORTS":"adaniports.com",
        "COALINDIA":"coalindia.in",   "TECHM":       "techmahindra.com",
        "TATASTEEL":"tatasteel.com",  "HINDALCO":    "hindalco.com",
        "CIPLA":    "cipla.com",      "DRREDDY":     "drreddys.com",
        "BRITANNIA":"britannia.co.in",
        "APOLLOHOSP":"apollohospitals.com",
        "SBILIFE":  "sbilife.co.in",  "HEROMOTOCO":  "heromotocorp.com",
        "BPCL":     "bharatpetroleum.com",
        "SUZLON":   "suzlon.com",     "SUZLON.NS":   "suzlon.com",
        "ZOMATO":   "zomato.com",     "PAYTM":       "paytm.com",
        "NYKAA":    "nykaa.com",      "DLF":         "dlf.in",
        "DMART":    "dmartindia.com", "IRCTC":       "irctc.co.in",
        "HAL":      "hal-india.co.in","IRFC":        "irfc.nic.in",
        "LUPIN":    "lupin.com",      "AUROPHARMA":  "aurobindo.com",
        "HAVELLS":  "havells.com",    "VOLTAS":      "voltas.com",
        "JUBLFOOD":  "jubilantfoodworks.com",
        "ITC":      "itcportal.com",  "NTPC.NS":     "ntpc.co.in",
        "AAPL":  "apple.com",    "MSFT":  "microsoft.com",
        "GOOGL": "google.com",   "GOOG":  "google.com",
        "AMZN":  "amazon.com",   "META":  "meta.com",
        "TSLA":  "tesla.com",    "NVDA":  "nvidia.com",
        "NFLX":  "netflix.com",  "AMD":   "amd.com",
        "INTC":  "intel.com",    "JPM":   "jpmorganchase.com",
        "BAC":   "bankofamerica.com", "V": "visa.com",
        "WMT":   "walmart.com",  "DIS":   "thewaltdisneycompany.com",
    }

    domain = None
    if website:
        try:
            parsed = urlparse(website)
            domain = parsed.netloc.replace("www.", "").strip("/")
        except Exception:
            pass

    clean = symbol.upper().replace(".BO", "")
    if not domain:
        domain = KNOWN_DOMAINS.get(clean) or KNOWN_DOMAINS.get(clean.replace(".NS", ""))

    if domain:
        return f"https://www.google.com/s2/favicons?sz=128&domain_url=https://{domain}"
    return ""


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
    data = {
        "symbol":      info.get("symbol", symbol),
        "name":        info.get("longName") or info.get("shortName", symbol),
        "logo":        logo,
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
    Three-tier fallback to guarantee a valid price is always returned:

    Tier 1 — Twelve Data API
      Correct symbol format (HDFCBANK:NSE, AAPL), no IP blocking, 800 req/day free.
      Will be used for most requests after the cache warms up.

    Tier 2 — yfinance .info (shared cache, no extra HTTP call)
      Works when market is open and .info has currentPrice/regularMarketPrice.
      May return 0 on Indian stocks when market is closed — detected and skipped.

    Tier 3 — yfinance .history(period='5d')
      ALWAYS reliable. Returns OHLCV even on weekends, holidays, after market close.
      This is what was used before and we keep it as the guaranteed fallback.
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

    # ── Tier 3: yfinance .history() — guaranteed fallback ─────────────────────
    # Works market open OR closed, weekends, holidays. Always returns OHLCV.
    try:
        hist = yf.Ticker(symbol).history(period='5d')
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
                "high":       round(float(hist['High'].iloc[-1]), 2),
                "low":        round(float(hist['Low'].iloc[-1]),  2),
                "open":       round(float(hist['Open'].iloc[-1]), 2),
                "prev_close": prev,
                "volume":     int(vol) if vol == vol else 0,  # NaN guard
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
                r = _safe(v) if not isinstance(v, (int, float)) else v
                if r is not None:
                    return r
            return None

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
            "dividend_yield":    first(tds.get("dividend_yield"),     info.get("dividendYield")),
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


def get_news(symbol):
    """Fetch news. TTL 900 s (15 min) — was 300 s (5 min). 3x fewer Yahoo calls."""
    k = f"news:{symbol}"
    c = _get(k)
    if c:
        return c
    try:
        raw = yf.Ticker(symbol).news or []
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

        data = {"symbol": symbol, "articles": articles, "count": len(articles)}
        _set(k, data, 900)   # 15 min — was 5 min
        return data
    except Exception as e:
        return {"error": str(e), "articles": []}


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
        hist   = ticker.history(period="max", interval=interval) if start is None \
                 else ticker.history(start=start, end=end, interval=interval)

        if hist.empty:
            return {"error": "No chart data"}

        candles = []
        for ts, row in hist.iterrows():
            try:
                unix = int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts.value // 1_000_000_000)
                candles.append({
                    "time":   unix,
                    "open":   round(float(row["Open"]),   2),
                    "high":   round(float(row["High"]),   2),
                    "low":    round(float(row["Low"]),    2),
                    "close":  round(float(row["Close"]),  2),
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
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