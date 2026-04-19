"""
stock_service.py — yfinance backend, no API key required (yfinance as fallback).
Twelve Data API used as primary quote source to reduce yfinance IP-rate-limiting.

Key fixes (2026-04):
  - ALL yf.Ticker().info calls consolidated into ONE fetch per symbol via _get_ticker_data()
  - Threading locks prevent duplicate concurrent fetches for the same symbol
  - Twelve Data API (free key, 800 req/day) used first for quotes — no IP blocking
  - Increased cache TTLs: quote 30s→120s, candles 60s→600s, news 300s→900s
  - get_full_dashboard() now triggers ~1 Yahoo call instead of 4+
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


# ── Twelve Data API (primary quote source — no IP-based throttling) ───────────
_TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")

def _twelve_data_quote(symbol):
    """
    Fetch real-time quote from Twelve Data API.
    Free tier: 800 requests/day, no IP blocking.
    Returns a dict compatible with get_quote(), or None on failure.
    """
    if not _TWELVE_DATA_KEY:
        return None
    try:
        url = (
            f"https://api.twelvedata.com/quote"
            f"?symbol={symbol}&apikey={_TWELVE_DATA_KEY}"
        )
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        d = r.json()
        # Twelve Data error responses contain a "code" field
        if "code" in d or "status" in d and d.get("status") == "error":
            return None
        cur  = _safe(d.get("close"))
        prev = _safe(d.get("previous_close"))
        chg  = _safe((cur or 0) - (prev or 0))
        chgp = _safe(((chg / prev) * 100) if prev else 0)
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
            "currency":    d.get("currency", "INR"),
            "_source":     "twelvedata",
        }
    except Exception as e:
        print(f"  ⚠ Twelve Data quote failed for {symbol}: {e}")
        return None


# ── Deduplicating ticker-info fetch ───────────────────────────────────────────
# Tracks in-flight fetches so concurrent requests for the same symbol
# wait for the first fetch instead of all hammering Yahoo Finance.
_inflight: dict = {}          # symbol → threading.Event
_inflight_lock = threading.Lock()

def _get_ticker_data(symbol):
    """
    Fetch yf.Ticker info ONCE and cache for 120 s.
    Concurrent requests for the same symbol wait for the first fetch to complete.
    This replaces 4 separate yf.Ticker(symbol).info calls with a single one.
    TTL 120 s: quotes change meaningfully only every 2+ minutes.
    """
    cache_key = f"ticker_data:{symbol}"
    cached = _get(cache_key)
    if cached:
        return cached

    # Check if another thread is already fetching this symbol
    with _inflight_lock:
        if symbol in _inflight:
            event = _inflight[symbol]
            is_leader = False
        else:
            event = threading.Event()
            _inflight[symbol] = event
            is_leader = True

    if not is_leader:
        # Wait for the leader thread (max 20 s), then return whatever got cached
        event.wait(timeout=20)
        result = _get(cache_key)
        return result if result else {"info": {}, "error": "timeout waiting for fetch"}

    # This thread is the leader — do the actual fetch
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        data = {"info": info, "_ticker": symbol}
        _set(cache_key, data, 120)
        return data
    except Exception as e:
        err = {"info": {}, "error": str(e)}
        return err
    finally:
        event.set()
        with _inflight_lock:
            _inflight.pop(symbol, None)


# ── Logo helper ───────────────────────────────────────────────────────────────
def _get_logo(symbol, website=None):
    from urllib.parse import urlparse

    KNOWN_DOMAINS = {
        "RELIANCE": "ril.com",       "RELIANCE.NS": "ril.com",
        "TCS":      "tcs.com",       "TCS.NS":      "tcs.com",
        "HDFCBANK": "hdfcbank.com",  "HDFCBANK.NS": "hdfcbank.com",
        "INFY":     "infosys.com",   "INFY.NS":     "infosys.com",
        "ICICIBANK":"icicibank.com", "ICICIBANK.NS":"icicibank.com",
        "HINDUNILVR":"hul.co.in",    "SBIN":        "sbi.co.in",
        "BHARTIARTL":"airtel.com",   "BHARTIARTL.NS":"airtel.com",
        "BAJFINANCE":"bajajfinserv.in",
        "ASIANPAINT":"asianpaints.com",
        "MARUTI":   "marutisuzuki.com","MARUTI.NS":  "marutisuzuki.com",
        "KOTAKBANK":"kotak.com",     "LT":          "larsentoubro.com",
        "AXISBANK": "axisbank.com",  "TITAN":       "titancompany.in",
        "SUNPHARMA":"sunpharma.com", "WIPRO":       "wipro.com",
        "HCLTECH":  "hcltech.com",   "TATAMOTORS":  "tatamotors.com",
        "ONGC":     "ongcindia.com", "NTPC":        "ntpc.co.in",
        "POWERGRID":"powergridindia.com",
        "JSWSTEEL": "jsw.in",        "ADANIENT":    "adani.com",
        "ADANIPORTS":"adaniports.com",
        "COALINDIA":"coalindia.in",  "TECHM":       "techmahindra.com",
        "TATASTEEL":"tatasteel.com", "HINDALCO":    "hindalco.com",
        "CIPLA":    "cipla.com",     "DRREDDY":     "drreddys.com",
        "BRITANNIA":"britannia.co.in",
        "APOLLOHOSP":"apollohospitals.com",
        "SBILIFE":  "sbilife.co.in", "HEROMOTOCO":  "heromotocorp.com",
        "BPCL":     "bharatpetroleum.com",
        "SUZLON":   "suzlon.com",    "SUZLON.NS":   "suzlon.com",
        "ZOMATO":   "zomato.com",    "PAYTM":       "paytm.com",
        "NYKAA":    "nykaa.com",     "DLF":         "dlf.in",
        "DMART":    "dmartindia.com","IRCTC":       "irctc.co.in",
        "HAL":      "hal-india.co.in","IRFC":       "irfc.nic.in",
        "LUPIN":    "lupin.com",     "AUROPHARMA":  "aurobindo.com",
        "HAVELLS":  "havells.com",   "VOLTAS":      "voltas.com",
        "JUBLFOOD":  "jubilantfoodworks.com",
        "ITC":      "itcportal.com", "NTPC.NS":     "ntpc.co.in",
        "AAPL":  "apple.com",   "MSFT":  "microsoft.com",
        "GOOGL": "google.com",  "GOOG":  "google.com",
        "AMZN":  "amazon.com",  "META":  "meta.com",
        "TSLA":  "tesla.com",   "NVDA":  "nvidia.com",
        "NFLX":  "netflix.com", "AMD":   "amd.com",
        "INTC":  "intel.com",   "JPM":   "jpmorganchase.com",
        "BAC":   "bankofamerica.com","V":  "visa.com",
        "WMT":   "walmart.com", "DIS":   "thewaltdisneycompany.com",
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


# ── Public API — all use _get_ticker_data() internally ────────────────────────

def get_profile(symbol):
    k = f"profile:{symbol}"
    c = _get(k)
    if c:
        return c
    td = _get_ticker_data(symbol)
    info = td.get("info", {})
    website = info.get("website", "")
    logo = info.get("logo_url", "") or _get_logo(symbol, website)
    data = {
        "symbol":      info.get("symbol", symbol),
        "name":        info.get("longName") or info.get("shortName", symbol),
        "logo":        logo,
        "exchange":    info.get("exchange", "NSE"),
        "industry":    info.get("industry", "N/A"),
        "sector":      info.get("sector", "N/A"),
        "country":     info.get("country", "India"),
        "currency":    info.get("currency", "INR"),
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
    Quote with Twelve Data as primary source, yfinance as fallback.
    TTL 120 s (was 30 s) — sufficient for display; auto-refresh handles freshness.
    """
    k = f"quote:{symbol}"
    c = _get(k)
    if c:
        return c

    # ── Primary: Twelve Data (no IP-based rate limiting) ──────────────────────
    td_quote = _twelve_data_quote(symbol)
    if td_quote:
        _set(k, td_quote, 120)
        return td_quote

    # ── Fallback: yfinance (shared ticker data — no extra HTTP call) ──────────
    try:
        td = _get_ticker_data(symbol)
        info = td.get("info", {})
        cur  = _safe(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0))
        prev = _safe(info.get("previousClose") or info.get("regularMarketPreviousClose", 0))
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
            "currency":   info.get("currency", "INR"),
            "_source":    "yfinance",
        }
        _set(k, data, 120)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_metrics(symbol):
    """Uses shared ticker data — no additional Yahoo request needed."""
    k = f"metrics:{symbol}"
    c = _get(k)
    if c:
        return c
    try:
        td   = _get_ticker_data(symbol)
        info = td.get("info", {})

        # ROE: try info first, then compute from financials
        roe = _safe(info.get("returnOnEquity"))
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

        data = {
            "symbol":            symbol,
            "pe_ratio":          _safe(info.get("trailingPE")),
            "pe_forward":        _safe(info.get("forwardPE")),
            "eps_ttm":           _safe(info.get("trailingEps")),
            "eps_forward":       _safe(info.get("forwardEps")),
            "gross_margins":     _safe(info.get("grossMargins")),
            "profit_margins":    _safe(info.get("profitMargins")),
            "operating_margins": _safe(info.get("operatingMargins")),
            "roe":               roe,
            "roa":               _safe(info.get("returnOnAssets")),
            "debt_equity":       _safe(info.get("debtToEquity")),
            "current_ratio":     _safe(info.get("currentRatio")),
            "quick_ratio":       _safe(info.get("quickRatio")),
            "dividend_yield":    _safe(info.get("dividendYield")),
            "week52_high":       _safe(info.get("fiftyTwoWeekHigh")),
            "week52_low":        _safe(info.get("fiftyTwoWeekLow")),
            "beta":              _safe(info.get("beta")),
            "price_to_book":     _safe(info.get("priceToBook")),
            "ev_ebitda":         _safe(info.get("enterpriseToEbitda")),
            "market_cap":        info.get("marketCap"),
            "free_cashflow":     info.get("freeCashflow"),
            "total_cash":        info.get("totalCash"),
            "total_debt":        info.get("totalDebt"),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_analyst(symbol):
    """Uses shared ticker data for info; only recommendations need a separate call (cached 1h)."""
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
                    if "strong buy" in g:                                         sb   += 1
                    elif any(x in g for x in ["buy","outperform","overweight"]):  buy  += 1
                    elif any(x in g for x in ["hold","neutral","equal"]):         hold += 1
                    elif any(x in g for x in ["strong sell","underperform","underweight"]): ssell += 1
                    elif "sell" in g:                                              sell += 1
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
            "symbol":         symbol,
            "consensus":      consensus,
            "strong_buy":     sb,
            "buy":            buy,
            "hold":           hold,
            "sell":           sell,
            "strong_sell":    ssell,
            "total":          total,
            "target_mean":    _safe(info.get("targetMeanPrice")),
            "target_high":    _safe(info.get("targetHighPrice")),
            "target_low":     _safe(info.get("targetLowPrice")),
            "analyst_count":  info.get("numberOfAnalystOpinions", 0),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_news(symbol):
    """
    Fetch news for a symbol. TTL raised to 900 s (15 min) — was 300 s (5 min).
    News doesn't update that frequently; this reduces Yahoo calls 3x.
    """
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
    TTL raised: intraday (1D/1W) = 300 s, longer timeframes = 900 s.
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
        if start is None:
            hist = ticker.history(period="max", interval=interval)
        else:
            hist = ticker.history(start=start, end=end, interval=interval)

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
        # Intraday charts need fresher data; longer timeframes are stable
        candle_ttl = 300 if tf in ("1D", "1W") else 900
        _set(k, data, candle_ttl)
        return data
    except Exception as e:
        return {"error": str(e)}


# ── Dashboard composite ────────────────────────────────────────────────────────
def get_full_dashboard(symbol):
    """
    Fetches all dashboard data.
    After fix: triggers _get_ticker_data() ONCE → ~1 Yahoo HTTP call instead of 4+.
    Twelve Data handles the quote; yfinance handles profile/metrics/analyst from cache.
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