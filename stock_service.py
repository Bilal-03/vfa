"""
stock_service.py — yfinance backend with cloud-server fix.

ONLY CHANGE from original: Yahoo Finance blocks .info on cloud IPs (Render/AWS).
Fix strategy:
  1. curl_cffi session  — impersonates Chrome, bypasses Yahoo bot detection
  2. NSE public API     — primary source for Indian stock quote + metrics (never blocked)
  3. yfinance in thread — 8s hard timeout so a Yahoo block never hangs the page
  
All field names, cache TTLs, and logic are IDENTICAL to the original.
"""
import time
import threading
from datetime import datetime, timezone, date, timedelta
import requests
import yfinance as yf

# ── curl_cffi session (bypasses Yahoo bot detection on cloud IPs) ─────────────
try:
    from curl_cffi import requests as curl_requests
    _SESSION = curl_requests.Session(impersonate="chrome120")
    _SESSION.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    print("✅ curl_cffi session active — Yahoo bot bypass enabled")
except ImportError:
    _SESSION = None
    print("⚠️  curl_cffi not installed")

# ── Cache (identical to original) ────────────────────────────────────────────
_cache: dict = {}

def _get(key): e=_cache.get(key); return e["data"] if e and time.time()-e["ts"]<e["ttl"] else None
def _set(key,data,ttl): _cache[key]={"ts":time.time(),"data":data,"ttl":ttl}
def _safe(v,d=2):
    try: f=float(v); return None if f!=f else round(f,d)
    except: return None

# ── yfinance ticker helper ─────────────────────────────────────────────────────
def _ticker(symbol):
    return yf.Ticker(symbol, session=_SESSION) if _SESSION else yf.Ticker(symbol)

def _info(symbol, timeout=8) -> dict:
    """
    Fetch yfinance .info in a background thread with a hard timeout.
    On Render, Yahoo sometimes blocks — this ensures the page never hangs waiting.
    Returns {} if blocked/timed-out (NSE data fills in for Indian stocks).
    """
    result = {}
    def _fetch():
        try:
            info = _ticker(symbol).info or {}
            if info and len(info) > 5:
                result.update(info)
        except: pass
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result

# ── NSE Public API (Indian stocks only, never blocked from cloud) ─────────────
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

def _nse_quote_raw(nse_sym: str) -> dict:
    """Fetch raw NSE quote-equity JSON. Returns {} on failure."""
    try:
        s = _nse_session()
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}", timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f"NSE error for {nse_sym}: {e}")
        return {}

def _nse_trade_info_raw(nse_sym: str) -> dict:
    """Fetch NSE trade_info section (has PE, EPS, market cap). Returns {} on failure."""
    try:
        s = _nse_session()
        r = s.get(
            f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}&section=trade_info",
            timeout=10
        )
        return r.json() if r.status_code == 200 else {}
    except: return {}

def _is_indian(symbol: str) -> bool:
    return symbol.upper().endswith(".NS") or symbol.upper().endswith(".BO")

def _nse_sym(symbol: str) -> str:
    return symbol.upper().replace(".NS","").replace(".BO","")

# ── Logo (identical to original) ──────────────────────────────────────────────
def _get_logo(symbol, website=None):
    from urllib.parse import urlparse
    domain = None
    if website:
        try:
            parsed = urlparse(website)
            domain = parsed.netloc.replace("www.", "").strip("/")
        except: pass

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
    clean = symbol.upper().replace(".BO", "")
    if not domain:
        domain = KNOWN_DOMAINS.get(clean) or KNOWN_DOMAINS.get(clean.replace(".NS", ""))
    if domain:
        return f"https://www.google.com/s2/favicons?sz=128&domain_url=https://{domain}"
    return ""

# ═════════════════════════════════════════════════════════════════════════════
# Public functions — same signatures and field names as original
# ═════════════════════════════════════════════════════════════════════════════

def get_profile(symbol):
    k=f"profile:{symbol}"; c=_get(k)
    if c: return c
    try:
        info = _info(symbol, timeout=8)
        # If yfinance timed out and it's an Indian stock, fill name from NSE
        if not info and _is_indian(symbol):
            nse = _nse_quote_raw(_nse_sym(symbol))
            name = nse.get("info",{}).get("companyName", symbol)
            ind  = nse.get("industryInfo",{})
            data = {
                "symbol": symbol, "name": name, "logo": _get_logo(symbol),
                "exchange": "NSE", "industry": ind.get("industry","N/A"),
                "sector": ind.get("sector","N/A"), "country": "India",
                "currency": "INR", "web_url": "", "description": "",
                "employees": None, "market_cap": None,
            }
            _set(k,data,86400); return data
        # Original logic
        website = info.get("website","")
        logo = info.get("logo_url","") or _get_logo(symbol, website)
        data={"symbol":info.get("symbol",symbol),"name":info.get("longName") or info.get("shortName",symbol),
              "logo": logo,
              "exchange":info.get("exchange","NSE"),
              "industry":info.get("industry","N/A"),"sector":info.get("sector","N/A"),
              "country":info.get("country","India"),"currency":info.get("currency","INR"),
              "web_url": website,
              "description":(info.get("longBusinessSummary") or "")[:400],
              "employees":info.get("fullTimeEmployees"),"market_cap":info.get("marketCap")}
        _set(k,data,86400); return data
    except Exception as e: return {"error":str(e)}


def get_quote(symbol):
    k=f"quote:{symbol}"; c=_get(k)
    if c: return c
    try:
        # ── Indian stocks: NSE is primary (never blocked), yfinance is fallback ──
        if _is_indian(symbol):
            nse = _nse_quote_raw(_nse_sym(symbol))
            pi  = nse.get("priceInfo", {})
            if pi.get("lastPrice"):
                ih   = pi.get("intraDayHighLow", {})
                pdh  = pi.get("pdHighLow", {})
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
                    "avg_volume": None,   # filled below from fast_info
                    "currency":   "INR",
                }
                # avg_volume — fast_info is a lighter Yahoo endpoint, usually not blocked
                try:
                    fi = _ticker(symbol).fast_info
                    data["avg_volume"] = int(getattr(fi, "three_month_average_volume", 0) or 0) or None
                except: pass
                _set(k, data, 30)
                return data

        # ── US stocks (or NSE failed): original yfinance logic ──
        info = _info(symbol, timeout=8)
        if not info:
            return {"symbol": symbol, "error": "Rate limited. Try again shortly."}
        cur=_safe(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose",0))
        prev=_safe(info.get("previousClose") or info.get("regularMarketPreviousClose",0))
        chg=_safe((cur or 0)-(prev or 0)); chgp=_safe(((chg/prev)*100) if prev else 0)
        data={"symbol":symbol,"current":cur,"change":chg,"change_pct":chgp,
              "high":_safe(info.get("dayHigh") or info.get("regularMarketDayHigh")),
              "low":_safe(info.get("dayLow") or info.get("regularMarketDayLow")),
              "open":_safe(info.get("open") or info.get("regularMarketOpen")),
              "prev_close":prev,"volume":info.get("volume",0),"avg_volume":info.get("averageVolume"),
              "currency":info.get("currency","INR")}
        _set(k,data,30); return data
    except Exception as e: return {"error":str(e)}


# ── Candle helpers (identical to original, just uses _ticker() helper) ────────
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
    k = f"candle:{symbol}:{tf}"; c = _get(k)
    if c: return c
    try:
        interval = _TF_INTERVAL.get(tf, "1d")
        start, end = _tf_dates(tf)
        ticker = _ticker(symbol)
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
            except: pass
        data = {"symbol": symbol, "timeframe": tf, "candles": candles, "count": len(candles)}
        _set(k, data, 60)
        return data
    except Exception as e:
        return {"error": str(e)}


def _compute_roe(ticker_obj, info):
    """Identical to original — tries info first, then computes from financials."""
    roe = _safe(info.get("returnOnEquity"))
    if roe is not None:
        return roe
    try:
        bs  = ticker_obj.balance_sheet
        inc = ticker_obj.financials
        if bs is not None and not bs.empty and inc is not None and not inc.empty:
            eq_keys = [k for k in bs.index if "Stockholders" in k or "equity" in k.lower() or "Equity" in k]
            ni_keys = [k for k in inc.index if "Net Income" in k or "NetIncome" in k]
            if eq_keys and ni_keys:
                equity     = float(bs.loc[eq_keys[0]].iloc[0])
                net_income = float(inc.loc[ni_keys[0]].iloc[0])
                if equity and equity != 0:
                    return round(net_income / equity, 4)
    except: pass
    return None


def get_metrics(symbol):
    k = f"metrics:{symbol}"; c = _get(k)
    if c: return c
    try:
        t    = _ticker(symbol)
        info = _info(symbol, timeout=8)

        # For Indian stocks: if yfinance timed out, fill key metrics from NSE
        if not info and _is_indian(symbol):
            nse_sym = _nse_sym(symbol)
            nse_raw = _nse_quote_raw(nse_sym)
            ti_raw  = _nse_trade_info_raw(nse_sym)
            pi      = nse_raw.get("priceInfo", {})
            whl     = pi.get("weekHighLow", {})
            pi_ti   = ti_raw.get("priceInfo", {})
            ti      = ti_raw.get("marketDeptOrderBook", {}).get("tradeInfo", {})
            mkt_cap = int(float(ti["totalMarketCap"]) * 1e7) if ti.get("totalMarketCap") else None
            data = {
                "symbol":          symbol,
                "pe_ratio":        _safe(pi_ti.get("pe")),
                "pe_forward":      None,
                "eps_ttm":         _safe(pi_ti.get("eps")),
                "eps_forward":     None,
                "gross_margins":   None,
                "profit_margins":  None,
                "operating_margins": None,
                "roe":             _compute_roe(t, {}),
                "roa":             None,
                "debt_equity":     None,
                "current_ratio":   None,
                "quick_ratio":     None,
                "dividend_yield":  _safe(pi_ti.get("divYield")),
                "week52_high":     _safe(whl.get("max")),
                "week52_low":      _safe(whl.get("min")),
                "beta":            None,
                "price_to_book":   _safe(pi_ti.get("pb")),
                "ev_ebitda":       None,
                "market_cap":      mkt_cap,
                "free_cashflow":   None,
                "total_cash":      None,
                "total_debt":      None,
            }
            _set(k, data, 3600)
            return data

        # Original logic (works when yfinance responds)
        roe = _compute_roe(t, info)
        data = {
            "symbol":             symbol,
            "pe_ratio":           _safe(info.get("trailingPE")),
            "pe_forward":         _safe(info.get("forwardPE")),
            "eps_ttm":            _safe(info.get("trailingEps")),
            "eps_forward":        _safe(info.get("forwardEps")),
            "gross_margins":      _safe(info.get("grossMargins")),
            "profit_margins":     _safe(info.get("profitMargins")),
            "operating_margins":  _safe(info.get("operatingMargins")),
            "roe":                roe,
            "roa":                _safe(info.get("returnOnAssets")),
            "debt_equity":        _safe(info.get("debtToEquity")),
            "current_ratio":      _safe(info.get("currentRatio")),
            "quick_ratio":        _safe(info.get("quickRatio")),
            "dividend_yield":     _safe(info.get("dividendYield")),
            "week52_high":        _safe(info.get("fiftyTwoWeekHigh")),
            "week52_low":         _safe(info.get("fiftyTwoWeekLow")),
            "beta":               _safe(info.get("beta")),
            "price_to_book":      _safe(info.get("priceToBook")),
            "ev_ebitda":          _safe(info.get("enterpriseToEbitda")),
            "market_cap":         info.get("marketCap"),
            "free_cashflow":      info.get("freeCashflow"),
            "total_cash":         info.get("totalCash"),
            "total_debt":         info.get("totalDebt"),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_analyst(symbol):
    k=f"analyst:{symbol}"; c=_get(k)
    if c: return c
    try:
        t    = _ticker(symbol)
        info = _info(symbol, timeout=8)
        sb=buy=hold=sell=ssell=0
        try:
            rdf=t.recommendations
            if rdf is not None and not rdf.empty:
                for _,row in rdf.tail(10).iterrows():
                    g=str(row.get("To Grade",row.get("Action",""))).lower()
                    if "strong buy" in g: sb+=1
                    elif any(x in g for x in ["buy","outperform","overweight"]): buy+=1
                    elif any(x in g for x in ["hold","neutral","equal"]): hold+=1
                    elif any(x in g for x in ["strong sell","underperform","underweight"]): ssell+=1
                    elif "sell" in g: sell+=1
        except: pass
        total=sb+buy+hold+sell+ssell
        ck=(info.get("recommendationKey","") if info else "").lower()
        cm={"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
        consensus=cm.get(ck,"N/A")
        if consensus=="N/A" and total>0:
            bull=(sb+buy)/total; bear=(sell+ssell)/total
            consensus="Strong Buy" if bull>=0.6 else "Buy" if bull>=0.4 else "Sell" if bear>=0.4 else "Hold"
        data={"symbol":symbol,"consensus":consensus,"strong_buy":sb,"buy":buy,"hold":hold,
              "sell":sell,"strong_sell":ssell,"total":total,
              "target_mean":_safe(info.get("targetMeanPrice") if info else None),
              "target_high":_safe(info.get("targetHighPrice") if info else None),
              "target_low": _safe(info.get("targetLowPrice")  if info else None),
              "analyst_count":info.get("numberOfAnalystOpinions",0) if info else 0}
        _set(k,data,3600); return data
    except Exception as e: return {"error":str(e)}


def get_news(symbol):
    """Identical to original — compatible with both old and new yfinance news formats."""
    k=f"news:{symbol}"; c=_get(k)
    if c: return c
    try:
        raw = _ticker(symbol).news or []
        articles = []
        for a in raw[:12]:
            try:
                if 'content' in a:
                    content  = a['content']
                    headline = content.get('title', '') or a.get('title', '')
                    pub      = content.get('provider', {})
                    source   = pub.get('displayName', pub.get('name', '')) if isinstance(pub, dict) else str(pub)
                    canonical= content.get('canonicalUrl', {})
                    url      = canonical.get('url', '') if isinstance(canonical, dict) else content.get('url', '')
                    if not url: url = a.get('link', '')
                    pub_date = content.get('pubDate', '') or content.get('publishedAt', '')
                    unix_time = 0
                    if pub_date:
                        try:
                            from datetime import datetime as dt
                            unix_time = int(dt.fromisoformat(pub_date.replace('Z', '+00:00')).timestamp())
                        except: pass
                    summary = content.get('summary', '') or content.get('description', '')
                else:
                    headline  = a.get('title', '')
                    source    = a.get('publisher', '')
                    url       = a.get('link', '')
                    unix_time = a.get('providerPublishTime', 0)
                    summary   = a.get('summary', '')
                if headline:
                    articles.append({"headline":headline,"source":source,"url":url,
                                     "datetime":unix_time,"summary":summary})
            except: continue
        data = {"symbol": symbol, "articles": articles, "count": len(articles)}
        _set(k, data, 300)
        return data
    except Exception as e:
        return {"error": str(e), "articles": []}


def get_full_dashboard(symbol):
    return {"symbol":symbol,"profile":get_profile(symbol),"quote":get_quote(symbol),
            "metrics":get_metrics(symbol),"analyst":get_analyst(symbol),
            "fetched_at":datetime.now(timezone.utc).isoformat()}


def clear_cache(symbol=None):
    global _cache
    if symbol:
        keys=[k for k in _cache if f":{symbol}" in k]
        for k in keys: del _cache[k]
        return {"cleared":keys}
    n=len(_cache); _cache={}; return {"cleared_all":n}

def cache_stats():
    now=time.time()
    return {"entries":len(_cache),"keys":[{"key":k,"age_sec":round(now-v["ts"]),"ttl":v["ttl"]} for k,v in _cache.items()]}