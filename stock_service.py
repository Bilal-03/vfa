"""
stock_service.py — Clean rewrite using NSE API + Twelve Data.
No yfinance. Works perfectly on cloud servers (Render, AWS etc.)

Indian stocks (.NS / .BO) → NSE public API  (free, no key, never blocked)
US stocks                  → Twelve Data API (free, 800 req/day)
News                       → Twelve Data API (same key)
Charts                     → Twelve Data API (same key)

Setup: set environment variable TWELVE_DATA_KEY=your_key
Get free key at: https://twelvedata.com (takes 60 seconds)
"""
import os
import time
import requests
from datetime import datetime, timezone, date, timedelta

# ── API config ────────────────────────────────────────────────────────────────
TD_KEY  = os.environ.get("TWELVE_DATA_KEY", "")
TD_BASE = "https://api.twelvedata.com"

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get(key):
    e = _cache.get(key)
    return e["data"] if e and time.time() - e["ts"] < e["ttl"] else None

def _set(key, data, ttl):
    _cache[key] = {"ts": time.time(), "data": data, "ttl": ttl}

def _safe(v, d=2):
    try:
        f = float(v)
        return None if f != f else round(f, d)
    except:
        return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_indian(symbol: str) -> bool:
    return symbol.upper().endswith(".NS") or symbol.upper().endswith(".BO")

def _nse_sym(symbol: str) -> str:
    """RELIANCE.NS → RELIANCE"""
    return symbol.upper().replace(".NS", "").replace(".BO", "")

def _td_sym(symbol: str) -> str:
    """Convert symbol for Twelve Data: RELIANCE.NS → RELIANCE:NSE, AAPL → AAPL"""
    s = symbol.upper()
    if s.endswith(".NS"):  return s.replace(".NS", "") + ":NSE"
    if s.endswith(".BO"):  return s.replace(".BO", "") + ":BSE"
    return s

# ── NSE Session ───────────────────────────────────────────────────────────────
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

def _nse_session():
    s = requests.Session()
    s.headers.update(_NSE_HEADERS)
    try: s.get("https://www.nseindia.com", timeout=6)
    except: pass
    return s

def _nse_get(path: str) -> dict:
    try:
        s = _nse_session()
        r = s.get(f"https://www.nseindia.com/api/{path}", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"NSE error [{path}]: {e}")
        return {}

# ── Twelve Data helper ────────────────────────────────────────────────────────
def _td_get(endpoint: str, params: dict) -> dict:
    if not TD_KEY:
        return {"status": "error", "message": "TWELVE_DATA_KEY not set"}
    try:
        params["apikey"] = TD_KEY
        r = requests.get(f"{TD_BASE}/{endpoint}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"Twelve Data error [{endpoint}]: {e}")
        return {}

# ── Logo ──────────────────────────────────────────────────────────────────────
def _get_logo(symbol, website=None):
    from urllib.parse import urlparse
    domain = None
    if website:
        try: domain = urlparse(website).netloc.replace("www.", "").strip("/")
        except: pass
    KNOWN = {
        "RELIANCE":"ril.com","TCS":"tcs.com","HDFCBANK":"hdfcbank.com",
        "INFY":"infosys.com","ICICIBANK":"icicibank.com","SBIN":"sbi.co.in",
        "BHARTIARTL":"airtel.com","BAJFINANCE":"bajajfinserv.in",
        "ASIANPAINT":"asianpaints.com","MARUTI":"marutisuzuki.com",
        "KOTAKBANK":"kotak.com","LT":"larsentoubro.com","AXISBANK":"axisbank.com",
        "TITAN":"titancompany.in","SUNPHARMA":"sunpharma.com","WIPRO":"wipro.com",
        "HCLTECH":"hcltech.com","TATAMOTORS":"tatamotors.com","ONGC":"ongcindia.com",
        "NTPC":"ntpc.co.in","POWERGRID":"powergridindia.com","JSWSTEEL":"jsw.in",
        "ADANIENT":"adani.com","ADANIPORTS":"adaniports.com","COALINDIA":"coalindia.in",
        "TECHM":"techmahindra.com","TATASTEEL":"tatasteel.com","HINDALCO":"hindalco.com",
        "CIPLA":"cipla.com","DRREDDY":"drreddys.com","BRITANNIA":"britannia.co.in",
        "APOLLOHOSP":"apollohospitals.com","SBILIFE":"sbilife.co.in",
        "HEROMOTOCO":"heromotocorp.com","BPCL":"bharatpetroleum.com",
        "SUZLON":"suzlon.com","ZOMATO":"zomato.com","PAYTM":"paytm.com",
        "NYKAA":"nykaa.com","DLF":"dlf.in","DMART":"dmartindia.com",
        "IRCTC":"irctc.co.in","HAL":"hal-india.co.in","IRFC":"irfc.nic.in",
        "LUPIN":"lupin.com","AUROPHARMA":"aurobindo.com","HAVELLS":"havells.com",
        "VOLTAS":"voltas.com","JUBLFOOD":"jubilantfoodworks.com",
        "ITC":"itcportal.com","HINDUNILVR":"hul.co.in","DELHIVERY":"delhivery.com",
        "AAPL":"apple.com","MSFT":"microsoft.com","GOOGL":"google.com",
        "GOOG":"google.com","AMZN":"amazon.com","META":"meta.com",
        "TSLA":"tesla.com","NVDA":"nvidia.com","NFLX":"netflix.com",
        "AMD":"amd.com","INTC":"intel.com","JPM":"jpmorganchase.com",
        "BAC":"bankofamerica.com","V":"visa.com","WMT":"walmart.com",
        "DIS":"thewaltdisneycompany.com",
    }
    clean = symbol.upper().replace(".NS","").replace(".BO","")
    if not domain: domain = KNOWN.get(clean)
    if domain:
        return f"https://www.google.com/s2/favicons?sz=128&domain_url=https://{domain}"
    return ""

# ═════════════════════════════════════════════════════════════════════════════
# get_quote
# ═════════════════════════════════════════════════════════════════════════════
def get_quote(symbol: str) -> dict:
    k = f"quote:{symbol}"; c = _get(k)
    if c: return c

    sym_up = symbol.upper()

    # ── Indian stocks → NSE API ───────────────────────────────────────────────
    if _is_indian(sym_up):
        d   = _nse_get(f"quote-equity?symbol={_nse_sym(sym_up)}")
        pi  = d.get("priceInfo", {})
        if pi.get("lastPrice"):
            ih  = pi.get("intraDayHighLow", {})
            pdh = pi.get("pdHighLow", {})
            cur  = _safe(pi["lastPrice"])
            prev = _safe(pi.get("previousClose", 0))
            chg  = _safe((cur or 0) - (prev or 0))
            chgp = _safe(((chg / prev) * 100) if prev else 0)
            data = {
                "symbol":     symbol,
                "current":    cur,
                "change":     chg,
                "change_pct": chgp,
                "high":       _safe(ih.get("max") or pdh.get("max")),
                "low":        _safe(ih.get("min") or pdh.get("min")),
                "open":       _safe(pi.get("open")),
                "prev_close": prev,
                "volume":     int(float(pi.get("totalTradedVolume", 0) or 0)),
                "avg_volume": None,
                "currency":   "INR",
            }
            _set(k, data, 30)
            return data

    # ── US stocks → Twelve Data ───────────────────────────────────────────────
    td = _td_get("quote", {"symbol": _td_sym(sym_up)})
    if td.get("close"):
        cur  = _safe(td["close"])
        prev = _safe(td.get("previous_close"))
        chg  = _safe(td.get("change"))
        chgp = _safe(td.get("percent_change"))
        data = {
            "symbol":     symbol,
            "current":    cur,
            "change":     chg,
            "change_pct": chgp,
            "high":       _safe(td.get("high")),
            "low":        _safe(td.get("low")),
            "open":       _safe(td.get("open")),
            "prev_close": prev,
            "volume":     int(float(td.get("volume", 0) or 0)),
            "avg_volume": int(float(td.get("average_volume", 0) or 0)) or None,
            "currency":   td.get("currency", "USD"),
        }
        _set(k, data, 30)
        return data

    return {"symbol": symbol, "error": "Could not fetch quote"}


# ═════════════════════════════════════════════════════════════════════════════
# get_profile
# ═════════════════════════════════════════════════════════════════════════════
def get_profile(symbol: str) -> dict:
    k = f"profile:{symbol}"; c = _get(k)
    if c: return c

    sym_up = symbol.upper()
    data = {
        "symbol": symbol, "name": _nse_sym(sym_up),
        "logo": _get_logo(symbol), "exchange": "NSE",
        "industry": "N/A", "sector": "N/A",
        "country": "India", "currency": "INR",
        "web_url": "", "description": "", "employees": None, "market_cap": None,
    }

    if _is_indian(sym_up):
        # Name + sector from NSE quote
        d   = _nse_get(f"quote-equity?symbol={_nse_sym(sym_up)}")
        info = d.get("info", {})
        ind  = d.get("industryInfo", {})
        if info.get("companyName"): data["name"]     = info["companyName"]
        if ind.get("sector"):       data["sector"]   = ind["sector"]
        if ind.get("industry") or ind.get("basicIndustry"):
            data["industry"] = ind.get("industry") or ind.get("basicIndustry")
        # Enrich with Twelve Data profile (description, employees, website)
        td = _td_get("profile", {"symbol": _td_sym(sym_up)})
        if td.get("name"):
            data["name"]        = td.get("name", data["name"])
            data["description"] = (td.get("description") or "")[:400]
            data["employees"]   = td.get("employees")
            data["web_url"]     = td.get("website", "")
            data["country"]     = td.get("country", "India")
            data["sector"]      = td.get("sector") or data["sector"]
            data["industry"]    = td.get("industry") or data["industry"]
            data["logo"]        = _get_logo(symbol, td.get("website")) or data["logo"]
        _set(k, data, 86400)
        return data

    # US stocks — Twelve Data profile
    td = _td_get("profile", {"symbol": _td_sym(sym_up)})
    if td.get("name"):
        data.update({
            "name":        td.get("name", symbol),
            "sector":      td.get("sector", "N/A"),
            "industry":    td.get("industry", "N/A"),
            "description": (td.get("description") or "")[:400],
            "employees":   td.get("employees"),
            "web_url":     td.get("website", ""),
            "country":     td.get("country", "US"),
            "currency":    td.get("currency", "USD"),
            "exchange":    td.get("exchange", ""),
            "logo":        _get_logo(symbol, td.get("website")),
        })
    _set(k, data, 86400)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# get_metrics
# ═════════════════════════════════════════════════════════════════════════════
def get_metrics(symbol: str) -> dict:
    k = f"metrics:{symbol}"; c = _get(k)
    if c: return c

    sym_up = symbol.upper()
    data   = {"symbol": symbol}

    if _is_indian(sym_up):
        # 52w high/low + PE/EPS/PB from NSE
        d   = _nse_get(f"quote-equity?symbol={_nse_sym(sym_up)}")
        pi  = d.get("priceInfo", {})
        whl = pi.get("weekHighLow", {})

        # Trade info for PE, EPS, market cap
        td_raw = _nse_get(f"quote-equity?symbol={_nse_sym(sym_up)}&section=trade_info")
        pi_ti  = td_raw.get("priceInfo", {})
        ti     = td_raw.get("marketDeptOrderBook", {}).get("tradeInfo", {})
        mkt_cap = int(float(ti["totalMarketCap"]) * 1e7) if ti.get("totalMarketCap") else None

        data.update({
            "pe_ratio":       _safe(pi_ti.get("pe")),
            "pe_forward":     None,
            "eps_ttm":        _safe(pi_ti.get("eps")),
            "eps_forward":    None,
            "dividend_yield": _safe(pi_ti.get("divYield")),
            "price_to_book":  _safe(pi_ti.get("pb")),
            "week52_high":    _safe(whl.get("max")),
            "week52_low":     _safe(whl.get("min")),
            "market_cap":     mkt_cap,
            "book_value":     _safe(pi_ti.get("bookValue")),
            # Fields below filled from Twelve Data statistics if available
            "gross_margins": None, "profit_margins": None,
            "operating_margins": None, "roe": None, "roa": None,
            "debt_equity": None, "current_ratio": None, "quick_ratio": None,
            "beta": None, "ev_ebitda": None,
            "free_cashflow": None, "total_cash": None, "total_debt": None,
        })

        # Enrich with Twelve Data statistics (has ROE, beta, debt/equity etc.)
        td = _td_get("statistics", {"symbol": _td_sym(sym_up)})
        vs = td.get("valuations_metrics", {})
        fs = td.get("financials", {})
        bs = fs.get("balance_sheet", {})
        is_ = fs.get("income_statement", {})
        st = td.get("stock_statistics", {})

        if td and td.get("symbol"):
            data.update({
                "pe_ratio":          _safe(vs.get("trailing_pe"))      or data["pe_ratio"],
                "pe_forward":        _safe(vs.get("forward_pe")),
                "price_to_book":     _safe(vs.get("price_to_book_mrq")) or data["price_to_book"],
                "ev_ebitda":         _safe(vs.get("enterprise_to_ebitda")),
                "beta":              _safe(st.get("beta")),
                "week52_high":       _safe(st.get("52_week_high"))      or data["week52_high"],
                "week52_low":        _safe(st.get("52_week_low"))       or data["week52_low"],
                "profit_margins":    _safe(is_.get("profit_margin")),
                "roe":               _safe(fs.get("return_on_equity_ttm")),
                "roa":               _safe(fs.get("return_on_assets_ttm")),
                "debt_equity":       _safe(bs.get("total_debt_to_equity_mrq")),
                "current_ratio":     _safe(bs.get("current_ratio_mrq")),
                "dividend_yield":    _safe(st.get("dividend_yield")) or data["dividend_yield"],
                "market_cap":        int(float(st["market_capitalization"])) if st.get("market_capitalization") else data["market_cap"],
            })

        _set(k, data, 3600)
        return data

    # US stocks — Twelve Data statistics
    td = _td_get("statistics", {"symbol": _td_sym(sym_up)})
    vs = td.get("valuations_metrics", {})
    fs = td.get("financials", {})
    bs = fs.get("balance_sheet", {})
    is_ = fs.get("income_statement", {})
    st  = td.get("stock_statistics", {})

    data.update({
        "pe_ratio":          _safe(vs.get("trailing_pe")),
        "pe_forward":        _safe(vs.get("forward_pe")),
        "eps_ttm":           _safe(st.get("eps_ttm")),
        "eps_forward":       None,
        "gross_margins":     None,
        "profit_margins":    _safe(is_.get("profit_margin")),
        "operating_margins": None,
        "roe":               _safe(fs.get("return_on_equity_ttm")),
        "roa":               _safe(fs.get("return_on_assets_ttm")),
        "debt_equity":       _safe(bs.get("total_debt_to_equity_mrq")),
        "current_ratio":     _safe(bs.get("current_ratio_mrq")),
        "quick_ratio":       None,
        "dividend_yield":    _safe(st.get("dividend_yield")),
        "week52_high":       _safe(st.get("52_week_high")),
        "week52_low":        _safe(st.get("52_week_low")),
        "beta":              _safe(st.get("beta")),
        "price_to_book":     _safe(vs.get("price_to_book_mrq")),
        "ev_ebitda":         _safe(vs.get("enterprise_to_ebitda")),
        "market_cap":        int(float(st["market_capitalization"])) if st.get("market_capitalization") else None,
        "free_cashflow":     None,
        "total_cash":        None,
        "total_debt":        None,
    })
    _set(k, data, 3600)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# get_analyst
# ═════════════════════════════════════════════════════════════════════════════
def get_analyst(symbol: str) -> dict:
    k = f"analyst:{symbol}"; c = _get(k)
    if c: return c

    td  = _td_get("analyst_ratings/light", {"symbol": _td_sym(symbol), "outputsize": 10})
    data = {
        "symbol": symbol, "consensus": "N/A",
        "strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0, "total": 0,
        "target_mean": None, "target_high": None, "target_low": None, "analyst_count": 0,
    }

    ratings = td.get("data", []) if isinstance(td.get("data"), list) else []
    sb = buy = hold = sell = ssell = 0
    for r in ratings:
        g = (r.get("rating") or r.get("action", "")).lower()
        if "strong buy"  in g: sb    += 1
        elif any(x in g for x in ["buy","outperform","overweight"]): buy   += 1
        elif any(x in g for x in ["hold","neutral","equal"]):        hold  += 1
        elif any(x in g for x in ["strong sell","underperform","underweight"]): ssell += 1
        elif "sell" in g: sell += 1

    total = sb + buy + hold + sell + ssell
    consensus = "N/A"
    if total > 0:
        bull = (sb + buy) / total; bear = (sell + ssell) / total
        consensus = "Strong Buy" if bull>=0.6 else "Buy" if bull>=0.4 else "Sell" if bear>=0.4 else "Hold"

    # Price targets from Twelve Data price_target endpoint
    pt = _td_get("price_target", {"symbol": _td_sym(symbol)})
    targets = pt.get("data", [])
    prices  = [_safe(t.get("price_target")) for t in targets if t.get("price_target")]
    prices  = [p for p in prices if p]

    data.update({
        "consensus":    consensus,
        "strong_buy":   sb, "buy": buy, "hold": hold,
        "sell":         sell, "strong_sell": ssell, "total": total,
        "target_mean":  round(sum(prices)/len(prices), 2) if prices else None,
        "target_high":  max(prices) if prices else None,
        "target_low":   min(prices) if prices else None,
        "analyst_count": total,
    })
    _set(k, data, 3600)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# get_news
# ═════════════════════════════════════════════════════════════════════════════
def get_news(symbol: str) -> dict:
    k = f"news:{symbol}"; c = _get(k)
    if c: return c

    td = _td_get("news", {"symbol": _td_sym(symbol), "outputsize": 12})
    articles = []
    for a in (td if isinstance(td, list) else []):
        try:
            pub_date = a.get("datetime", "") or a.get("published_utc", "")
            unix_time = 0
            if pub_date:
                try:
                    from datetime import datetime as dt
                    unix_time = int(dt.fromisoformat(pub_date.replace("Z","+00:00")).timestamp())
                except:
                    try: unix_time = int(pub_date)
                    except: pass
            headline = a.get("title","")
            if headline:
                articles.append({
                    "headline": headline,
                    "source":   a.get("source",""),
                    "url":      a.get("url",""),
                    "datetime": unix_time,
                    "summary":  (a.get("summary") or a.get("description",""))[:200],
                })
        except: continue

    data = {"symbol": symbol, "articles": articles, "count": len(articles)}
    _set(k, data, 300)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# get_candles
# ═════════════════════════════════════════════════════════════════════════════
_TF_CONFIG = {
    "1D":  {"interval": "5min",    "days": 2},
    "1W":  {"interval": "15min",   "days": 7},
    "1M":  {"interval": "1h",      "days": 31},
    "3M":  {"interval": "1day",    "days": 92},
    "6M":  {"interval": "1day",    "days": 183},
    "1Y":  {"interval": "1day",    "days": 366},
    "5Y":  {"interval": "1week",   "days": 365*5},
    "MAX": {"interval": "1month",  "days": 365*30},
}

def get_candles(symbol: str, tf: str = "3M") -> dict:
    k = f"candle:{symbol}:{tf}"; c = _get(k)
    if c: return c

    cfg      = _TF_CONFIG.get(tf, _TF_CONFIG["3M"])
    today    = date.today()
    start    = str(today - timedelta(days=cfg["days"]))
    end      = str(today + timedelta(days=1))

    td = _td_get("time_series", {
        "symbol":    _td_sym(symbol),
        "interval":  cfg["interval"],
        "start_date": start,
        "end_date":   end,
        "outputsize": 5000,
        "order":      "ASC",
    })

    values = td.get("values", [])
    if not values:
        return {"error": "No chart data"}

    candles = []
    for v in values:
        try:
            dt_str = v.get("datetime","")
            # Parse datetime to unix timestamp
            if ":" in dt_str:
                from datetime import datetime as dt
                unix = int(dt.strptime(dt_str, "%Y-%m-%d %H:%M:%S").timestamp())
            else:
                from datetime import datetime as dt
                unix = int(dt.strptime(dt_str, "%Y-%m-%d").timestamp())
            candles.append({
                "time":   unix,
                "open":   round(float(v["open"]),  2),
                "high":   round(float(v["high"]),  2),
                "low":    round(float(v["low"]),   2),
                "close":  round(float(v["close"]), 2),
                "volume": int(float(v.get("volume", 0) or 0)),
            })
        except: continue

    data = {"symbol": symbol, "timeframe": tf, "candles": candles, "count": len(candles)}
    _set(k, data, 60)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# get_full_dashboard
# ═════════════════════════════════════════════════════════════════════════════
def get_full_dashboard(symbol: str) -> dict:
    quote   = get_quote(symbol)
    profile = get_profile(symbol)
    metrics = get_metrics(symbol)
    analyst = get_analyst(symbol)
    if "error" in quote and not quote.get("current"):
        return {"symbol": symbol, "error": quote["error"], "quote": quote}
    return {
        "symbol":     symbol,
        "profile":    profile,
        "quote":      quote,
        "metrics":    metrics,
        "analyst":    analyst,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Cache utils
# ═════════════════════════════════════════════════════════════════════════════
def clear_cache(symbol=None):
    global _cache
    if symbol:
        keys = [k for k in _cache if f":{symbol}" in k]
        for k in keys: del _cache[k]
        return {"cleared": keys}
    n = len(_cache); _cache = {}
    return {"cleared_all": n}

def cache_stats():
    now = time.time()
    return {
        "entries": len(_cache),
        "keys": [{"key": k, "age_sec": round(now-v["ts"]), "ttl": v["ttl"]} for k,v in _cache.items()]
    }