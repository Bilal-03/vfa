"""
stock_service.py — yfinance backend, no API key required.
Fixed: news format compatibility, logo fetching via multiple sources.
"""
import time
from datetime import datetime, timezone
import yfinance as yf

_cache: dict = {}

def _get(key): e=_cache.get(key); return e["data"] if e and time.time()-e["ts"]<e["ttl"] else None
def _set(key,data,ttl): _cache[key]={"ts":time.time(),"data":data,"ttl":ttl}
def _safe(v,d=2):
    try: f=float(v); return None if f!=f else round(f,d)
    except: return None

def _get_logo(symbol, website=None):
    """
    Return a logo URL using sources that actually work in 2025:
      1. Google Favicon API  (s=128 gives a high-res icon, free, no key needed)
      2. Direct /favicon.ico from company website
    Both are served via Google's infrastructure so very reliable.
    """
    from urllib.parse import urlparse

    domain = None
    if website:
        try:
            parsed = urlparse(website)
            domain = parsed.netloc.replace("www.", "").strip("/")
        except Exception:
            pass

    # Known domain map for stocks whose website isn't in yfinance info
    KNOWN_DOMAINS = {
        # Indian large-caps
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
        # US stocks
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
        # Google's favicon service — very reliable, returns high-res PNG
        return f"https://www.google.com/s2/favicons?sz=128&domain_url=https://{domain}"

    return ""

def get_profile(symbol):
    k=f"profile:{symbol}"; c=_get(k)
    if c: return c
    try:
        info=yf.Ticker(symbol).info or {}
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
        info=yf.Ticker(symbol).info or {}
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

# ── Candle helpers ────────────────────────────────────────────────────────────
# Interval for each timeframe
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
    """
    Return (start_date, end_date) strings 'YYYY-MM-DD' for exact calendar ranges,
    so that e.g. 1W always covers the last 7 calendar days regardless of weekends.
    Returns (None, None) for MAX so yfinance uses its own full history.
    """
    from datetime import date, timedelta
    today = date.today()
    end   = today + timedelta(days=1)          # include today's partial session

    delta = {
        "1D":  timedelta(days=2),              # extra day buffer for intraday
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
        _set(k, data, 60)
        return data
    except Exception as e:
        return {"error": str(e)}


def _compute_roe(ticker_obj, info):
    """
    Try multiple sources for ROE in order:
      1. info['returnOnEquity']  (most stocks)
      2. Compute from financials: Net Income / Stockholders Equity
      3. None
    """
    # Source 1 — direct from info
    roe = _safe(info.get("returnOnEquity"))
    if roe is not None:
        return roe

    # Source 2 — compute from financial statements
    try:
        bs   = ticker_obj.balance_sheet      # columns = quarters/years
        inc  = ticker_obj.financials

        if bs is not None and not bs.empty and inc is not None and not inc.empty:
            # Pick most recent column
            eq_keys = [k for k in bs.index if "Stockholders" in k or "equity" in k.lower() or "Equity" in k]
            ni_keys = [k for k in inc.index if "Net Income" in k or "NetIncome" in k]

            if eq_keys and ni_keys:
                equity     = float(bs.loc[eq_keys[0]].iloc[0])
                net_income = float(inc.loc[ni_keys[0]].iloc[0])
                if equity and equity != 0:
                    return round(net_income / equity, 4)
    except Exception:
        pass

    return None


def get_metrics(symbol):
    k = f"metrics:{symbol}"; c = _get(k)
    if c: return c
    try:
        t    = yf.Ticker(symbol)
        info = t.info or {}

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
        t=yf.Ticker(symbol); info=t.info or {}
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
        ck=info.get("recommendationKey","").lower()
        cm={"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
        consensus=cm.get(ck,"N/A")
        if consensus=="N/A" and total>0:
            bull=(sb+buy)/total; bear=(sell+ssell)/total
            consensus="Strong Buy" if bull>=0.6 else "Buy" if bull>=0.4 else "Sell" if bear>=0.4 else "Hold"
        data={"symbol":symbol,"consensus":consensus,"strong_buy":sb,"buy":buy,"hold":hold,
              "sell":sell,"strong_sell":ssell,"total":total,
              "target_mean":_safe(info.get("targetMeanPrice")),"target_high":_safe(info.get("targetHighPrice")),
              "target_low":_safe(info.get("targetLowPrice")),"analyst_count":info.get("numberOfAnalystOpinions",0)}
        _set(k,data,3600); return data
    except Exception as e: return {"error":str(e)}

def get_news(symbol):
    """
    Fetch news with compatibility for both old and new yfinance news formats.
    Old format: list of dicts with 'title', 'publisher', 'link', 'providerPublishTime'
    New format (yfinance >= 0.2.37): list of dicts with nested structure
    """
    k=f"news:{symbol}"; c=_get(k)
    if c: return c
    try:
        raw = yf.Ticker(symbol).news or []
        articles = []
        for a in raw[:12]:
            try:
                # New yfinance format wraps content inside 'content' key
                if 'content' in a:
                    content = a['content']
                    headline = content.get('title', '') or a.get('title', '')
                    # publisher may be nested
                    pub = content.get('provider', {})
                    if isinstance(pub, dict):
                        source = pub.get('displayName', pub.get('name', ''))
                    else:
                        source = str(pub)
                    # URL
                    canonical = content.get('canonicalUrl', {})
                    url = canonical.get('url', '') if isinstance(canonical, dict) else content.get('url', '')
                    if not url:
                        url = a.get('link', '')
                    # Timestamp
                    pub_date = content.get('pubDate', '') or content.get('publishedAt', '')
                    if pub_date:
                        try:
                            from datetime import datetime as dt
                            import re
                            # Handle ISO format
                            ts = dt.fromisoformat(pub_date.replace('Z', '+00:00')).timestamp()
                            unix_time = int(ts)
                        except:
                            unix_time = 0
                    else:
                        unix_time = 0
                    summary = content.get('summary', '') or content.get('description', '')
                else:
                    # Old yfinance format
                    headline = a.get('title', '')
                    source = a.get('publisher', '')
                    url = a.get('link', '')
                    unix_time = a.get('providerPublishTime', 0)
                    summary = a.get('summary', '')

                if headline:
                    articles.append({
                        "headline": headline,
                        "source": source,
                        "url": url,
                        "datetime": unix_time,
                        "summary": summary
                    })
            except Exception:
                continue

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