"""
stock_service.py — Fast hybrid backend.

Indian stocks (.NS / .BO):
  - Quote + 52w    → NSE public API (instant, never blocked from cloud)
  - PE/EPS/PB      → NSE trade_info endpoint
  - Description    → yfinance .info with 6s thread timeout (non-blocking)
  - Chart          → yfinance .history() (rarely blocked)

US stocks:
  - All data       → yfinance .fast_info + .info with curl_cffi session

Key: yfinance .info NEVER blocks the page load — it runs in a thread with timeout.
"""
import time
import threading
import requests
from datetime import datetime, timezone, timedelta, date

import yfinance as yf

# ── curl_cffi session ─────────────────────────────────────────────────────────
try:
    from curl_cffi import requests as curl_requests
    _YF_SESSION = curl_requests.Session(impersonate="chrome120")
    _YF_SESSION.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    print("✅ curl_cffi session active")
except ImportError:
    _YF_SESSION = None
    print("⚠️  curl_cffi not installed")

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

def _nse_symbol(symbol: str) -> str:
    return symbol.upper().replace(".NS", "").replace(".BO", "")

def _yf_ticker(symbol):
    return yf.Ticker(symbol, session=_YF_SESSION) if _YF_SESSION else yf.Ticker(symbol)

def _yf_info_quick(symbol, timeout_sec=6) -> dict:
    """
    Fetch yfinance .info in a background thread with a hard timeout.
    Returns {} if Yahoo blocks or times out — never stalls the request.
    """
    result = {}
    def _fetch():
        try:
            info = _yf_ticker(symbol).info or {}
            if info and len(info) > 5:
                result.update(info)
        except:
            pass
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    return result

# ── NSE Public API ────────────────────────────────────────────────────────────
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
    try:
        s.get("https://www.nseindia.com", timeout=6)
    except:
        pass
    return s

def _nse_fetch(nse_sym: str) -> dict:
    """Single NSE API call — quote + 52w + sector/industry."""
    try:
        s = _nse_session()
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}", timeout=10)
        if r.status_code != 200:
            return {}
        d    = r.json()
        pi   = d.get("priceInfo", {})
        info = d.get("info", {})
        mds  = d.get("metadata", {})
        whl  = pi.get("weekHighLow", {})
        ih   = pi.get("intraDayHighLow", {})
        pdh  = pi.get("pdHighLow", {})
        ind  = d.get("industryInfo", {})

        return {
            "current":    _safe(pi.get("lastPrice")),
            "open":       _safe(pi.get("open")),
            "high":       _safe(ih.get("max") or pdh.get("max")),
            "low":        _safe(ih.get("min") or pdh.get("min")),
            "prev_close": _safe(pi.get("previousClose")),
            "change":     _safe(pi.get("change")),
            "change_pct": _safe(pi.get("pChange")),
            "volume":     int(float(pi.get("totalTradedVolume", 0) or 0)),
            "vwap":       _safe(pi.get("vwap")),
            "currency":   "INR",
            "week52_high":_safe(whl.get("max")),
            "week52_low": _safe(whl.get("min")),
            "name":       info.get("companyName", nse_sym),
            "isin":       info.get("isin", ""),
            "exchange":   "NSE",
            "sector":     ind.get("sector", "N/A"),
            "industry":   ind.get("industry", "") or ind.get("basicIndustry", "N/A"),
        }
    except Exception as e:
        print(f"NSE fetch error for {nse_sym}: {e}")
        return {}

def _nse_trade_info(nse_sym: str) -> dict:
    """NSE trade_info endpoint — PE, EPS, PB, market cap for Indian stocks."""
    try:
        s = _nse_session()
        r = s.get(
            f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}&section=trade_info",
            timeout=10
        )
        if r.status_code != 200:
            return {}
        d  = r.json()
        pi = d.get("priceInfo", {})
        ti = d.get("marketDeptOrderBook", {}).get("tradeInfo", {})

        result = {}
        if pi.get("pe"):        result["pe_ratio"]       = _safe(pi["pe"])
        if pi.get("eps"):       result["eps_ttm"]        = _safe(pi["eps"])
        if pi.get("pb"):        result["price_to_book"]  = _safe(pi["pb"])
        if pi.get("divYield"):  result["dividend_yield"] = _safe(pi["divYield"])
        if pi.get("bookValue"): result["book_value"]     = _safe(pi["bookValue"])
        if ti.get("totalMarketCap"):
            # NSE gives market cap in crores; convert to absolute
            result["market_cap"] = int(float(ti["totalMarketCap"]) * 1e7)
        if ti.get("ffmc"):
            result["market_cap_ff"] = int(float(ti["ffmc"]) * 1e7)
        return result
    except Exception as e:
        print(f"NSE trade_info error {nse_sym}: {e}")
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
        "LUPIN":"lupin.com","HAVELLS":"havells.com","ITC":"itcportal.com",
        "HINDUNILVR":"hul.co.in","DELHIVERY":"delhivery.com",
        "AAPL":"apple.com","MSFT":"microsoft.com","GOOGL":"google.com",
        "GOOG":"google.com","AMZN":"amazon.com","META":"meta.com",
        "TSLA":"tesla.com","NVDA":"nvidia.com","NFLX":"netflix.com",
        "AMD":"amd.com","INTC":"intel.com","JPM":"jpmorganchase.com",
        "BAC":"bankofamerica.com","V":"visa.com","WMT":"walmart.com",
    }
    clean = symbol.upper().replace(".NS","").replace(".BO","")
    if not domain: domain = KNOWN.get(clean)
    if domain:
        return f"https://www.google.com/s2/favicons?sz=128&domain_url=https://{domain}"
    return ""

# ── Public API ────────────────────────────────────────────────────────────────

def get_quote(symbol):
    k = f"quote:{symbol}"; c = _get(k)
    if c: return c
    sym_up = symbol.upper()
    data = {"symbol": symbol, "currency": "INR"}

    if _is_indian(sym_up):
        nse = _nse_fetch(_nse_symbol(sym_up))
        if nse and nse.get("current"):
            data.update(nse)
            # avg_volume not available from NSE — grab from fast_info (quick, non-blocking)
            try:
                fi = _yf_ticker(symbol).fast_info
                avg_vol = int(getattr(fi, "three_month_average_volume", 0) or 0)
                if avg_vol: data["avg_volume"] = avg_vol
            except: pass
            _set(k, data, 120)
            return data

    # US / fallback: fast_info
    try:
        fi   = _yf_ticker(symbol).fast_info
        cur  = _safe(getattr(fi, "last_price", None))
        prev = _safe(getattr(fi, "previous_close", None))
        if cur:
            chg  = _safe(cur - prev) if prev else None
            chgp = _safe(((cur - prev) / prev) * 100) if prev else None
            data.update({
                "current": cur, "prev_close": prev, "change": chg, "change_pct": chgp,
                "open":       _safe(getattr(fi, "open", None)),
                "high":       _safe(getattr(fi, "day_high", None)),
                "low":        _safe(getattr(fi, "day_low", None)),
                "volume":     int(getattr(fi, "last_volume", 0) or 0),
                "avg_volume": int(getattr(fi, "three_month_average_volume", 0) or 0),
                "market_cap":  getattr(fi, "market_cap", None),
                "week52_high": _safe(getattr(fi, "year_high", None)),
                "week52_low":  _safe(getattr(fi, "year_low", None)),
                "currency":    getattr(fi, "currency", "USD"),
            })
            _set(k, data, 180); return data
    except: pass

    # Last resort: history
    try:
        hist = _yf_ticker(symbol).history(period="2d")
        if not hist.empty:
            last = hist.iloc[-1]; pr = hist.iloc[-2] if len(hist)>1 else None
            cur  = round(float(last["Close"]),2)
            prev = round(float(pr["Close"]),2) if pr is not None else cur
            data.update({
                "current": cur, "prev_close": prev,
                "open": _safe(last["Open"]), "high": _safe(last["High"]), "low": _safe(last["Low"]),
                "change": _safe(cur-prev), "change_pct": _safe(((cur-prev)/prev)*100) if prev else None,
                "volume": int(last["Volume"]) if last["Volume"]==last["Volume"] else 0,
            })
            _set(k, data, 180); return data
    except: pass

    return {"symbol": symbol, "error": "Could not fetch quote"}


def get_profile(symbol):
    k = f"profile:{symbol}"; c = _get(k)
    if c: return c
    sym_up = symbol.upper(); clean = _nse_symbol(sym_up)
    data = {
        "symbol": symbol, "name": clean, "exchange": "NSE", "currency": "INR",
        "country": "India", "industry": "N/A", "sector": "N/A",
        "description": "", "logo": _get_logo(symbol), "web_url": "",
        "employees": None, "market_cap": None,
    }
    if _is_indian(sym_up):
        nse = _nse_fetch(clean)
        if nse.get("name"):     data["name"]     = nse["name"]
        if nse.get("sector"):   data["sector"]   = nse["sector"]
        if nse.get("industry"): data["industry"] = nse["industry"]
        # Enrich with yfinance (non-blocking, 6s cap)
        info = _yf_info_quick(symbol, timeout_sec=6)
        if info:
            data.update({
                "name":        info.get("longName") or info.get("shortName") or data["name"],
                "sector":      info.get("sector") or data["sector"],
                "industry":    info.get("industry") or data["industry"],
                "description": (info.get("longBusinessSummary") or "")[:400],
                "employees":   info.get("fullTimeEmployees"),
                "market_cap":  info.get("marketCap"),
                "web_url":     info.get("website", ""),
                "logo":        info.get("logo_url") or _get_logo(symbol, info.get("website")),
            })
        _set(k, data, 86400); return data

    # US stocks
    info = _yf_info_quick(symbol, timeout_sec=10)
    if info:
        data.update({
            "name":        info.get("longName") or info.get("shortName", symbol),
            "sector":      info.get("sector", "N/A"),
            "industry":    info.get("industry", "N/A"),
            "description": (info.get("longBusinessSummary") or "")[:400],
            "employees":   info.get("fullTimeEmployees"),
            "market_cap":  info.get("marketCap"),
            "web_url":     info.get("website", ""),
            "logo":        info.get("logo_url") or _get_logo(symbol, info.get("website")),
            "exchange":    info.get("exchange", ""),
            "currency":    info.get("currency", "USD"),
            "country":     info.get("country", "US"),
        })
    _set(k, data, 86400); return data


def get_metrics(symbol):
    k = f"metrics:{symbol}"; c = _get(k)
    if c: return c
    sym_up = symbol.upper()
    data = {"symbol": symbol}

    if _is_indian(sym_up):
        clean = _nse_symbol(sym_up)
        # NSE for 52w + PE/EPS/PB/market cap
        nse = _nse_fetch(clean)
        ti  = _nse_trade_info(clean)
        data.update({
            "week52_high": nse.get("week52_high"),
            "week52_low":  nse.get("week52_low"),
        })
        data.update(ti)  # pe_ratio, eps_ttm, price_to_book, dividend_yield, market_cap

        # Enrich with yfinance (non-blocking, 6s cap)
        info = _yf_info_quick(symbol, timeout_sec=6)
        t    = _yf_ticker(symbol)
        if info:
            def _pick(yf_key, existing_key=None):
                return _safe(info.get(yf_key)) or data.get(existing_key or yf_key)
            data.update({
                "pe_ratio":          _pick("trailingPE", "pe_ratio"),
                "pe_forward":        _safe(info.get("forwardPE")),
                "eps_ttm":           _pick("trailingEps", "eps_ttm"),
                "eps_forward":       _safe(info.get("forwardEps")),
                "gross_margins":     _safe(info.get("grossMargins")),
                "profit_margins":    _safe(info.get("profitMargins")),
                "operating_margins": _safe(info.get("operatingMargins")),
                "roe":               _compute_roe(t, info),
                "roa":               _safe(info.get("returnOnAssets")),
                "debt_equity":       _safe(info.get("debtToEquity")),
                "current_ratio":     _safe(info.get("currentRatio")),
                "quick_ratio":       _safe(info.get("quickRatio")),
                "dividend_yield":    _pick("dividendYield", "dividend_yield"),
                "week52_high":       _safe(info.get("fiftyTwoWeekHigh")) or data.get("week52_high"),
                "week52_low":        _safe(info.get("fiftyTwoWeekLow"))  or data.get("week52_low"),
                "beta":              _safe(info.get("beta")),
                "price_to_book":     _pick("priceToBook", "price_to_book"),
                "ev_ebitda":         _safe(info.get("enterpriseToEbitda")),
                "market_cap":        info.get("marketCap") or data.get("market_cap"),
                "free_cashflow":     info.get("freeCashflow"),
                "total_cash":        info.get("totalCash"),
                "total_debt":        info.get("totalDebt"),
            })
        else:
            # yfinance timed out — compute ROE from financials directly (separate endpoint, less blocked)
            data["roe"] = _compute_roe(t, {})
        _set(k, data, 3600); return data

    # US stocks
    info = _yf_info_quick(symbol, timeout_sec=10)
    t    = _yf_ticker(symbol)
    roe  = _compute_roe(t, info) if info else None
    data.update({
        "pe_ratio":          _safe(info.get("trailingPE") if info else None),
        "pe_forward":        _safe(info.get("forwardPE") if info else None),
        "eps_ttm":           _safe(info.get("trailingEps") if info else None),
        "eps_forward":       _safe(info.get("forwardEps") if info else None),
        "gross_margins":     _safe(info.get("grossMargins") if info else None),
        "profit_margins":    _safe(info.get("profitMargins") if info else None),
        "operating_margins": _safe(info.get("operatingMargins") if info else None),
        "roe":               roe,
        "roa":               _safe(info.get("returnOnAssets") if info else None),
        "debt_equity":       _safe(info.get("debtToEquity") if info else None),
        "current_ratio":     _safe(info.get("currentRatio") if info else None),
        "quick_ratio":       _safe(info.get("quickRatio") if info else None),
        "dividend_yield":    _safe(info.get("dividendYield") if info else None),
        "week52_high":       _safe(info.get("fiftyTwoWeekHigh") if info else None),
        "week52_low":        _safe(info.get("fiftyTwoWeekLow") if info else None),
        "beta":              _safe(info.get("beta") if info else None),
        "price_to_book":     _safe(info.get("priceToBook") if info else None),
        "ev_ebitda":         _safe(info.get("enterpriseToEbitda") if info else None),
        "market_cap":        info.get("marketCap") if info else None,
        "free_cashflow":     info.get("freeCashflow") if info else None,
        "total_cash":        info.get("totalCash") if info else None,
        "total_debt":        info.get("totalDebt") if info else None,
    })
    _set(k, data, 3600); return data


def _compute_roe(ticker_obj, info):
    roe = _safe(info.get("returnOnEquity")) if info else None
    if roe is not None: return roe
    try:
        bs  = ticker_obj.balance_sheet
        inc = ticker_obj.financials
        if bs is not None and not bs.empty and inc is not None and not inc.empty:
            eq_keys = [k for k in bs.index if "Stockholders" in k or "equity" in k.lower()]
            ni_keys = [k for k in inc.index if "Net Income" in k]
            if eq_keys and ni_keys:
                equity = float(bs.loc[eq_keys[0]].iloc[0])
                ni     = float(inc.loc[ni_keys[0]].iloc[0])
                if equity: return round(ni / equity, 4)
    except: pass
    return None


def get_analyst(symbol):
    k = f"analyst:{symbol}"; c = _get(k)
    if c: return c
    try:
        t    = _yf_ticker(symbol)
        info = _yf_info_quick(symbol, timeout_sec=6)
        sb = buy = hold = sell = ssell = 0
        try:
            rdf = t.recommendations
            if rdf is not None and not rdf.empty:
                for _, row in rdf.tail(10).iterrows():
                    g = str(row.get("To Grade", row.get("Action",""))).lower()
                    if "strong buy" in g:  sb   += 1
                    elif any(x in g for x in ["buy","outperform","overweight"]): buy  += 1
                    elif any(x in g for x in ["hold","neutral","equal"]):        hold += 1
                    elif any(x in g for x in ["strong sell","underperform","underweight"]): ssell += 1
                    elif "sell" in g: sell += 1
        except: pass
        total = sb+buy+hold+sell+ssell
        ck    = (info.get("recommendationKey","") if info else "").lower()
        cm    = {"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
        consensus = cm.get(ck,"N/A")
        if consensus=="N/A" and total>0:
            bull=(sb+buy)/total; bear=(sell+ssell)/total
            consensus="Strong Buy" if bull>=0.6 else "Buy" if bull>=0.4 else "Sell" if bear>=0.4 else "Hold"
        data = {
            "symbol":symbol,"consensus":consensus,
            "strong_buy":sb,"buy":buy,"hold":hold,"sell":sell,"strong_sell":ssell,"total":total,
            "target_mean": _safe(info.get("targetMeanPrice") if info else None),
            "target_high": _safe(info.get("targetHighPrice") if info else None),
            "target_low":  _safe(info.get("targetLowPrice")  if info else None),
            "analyst_count": info.get("numberOfAnalystOpinions",0) if info else 0,
        }
        _set(k, data, 3600); return data
    except Exception as e:
        return {"symbol":symbol,"error":str(e)}


def get_news(symbol):
    k = f"news:{symbol}"; c = _get(k)
    if c: return c
    try:
        raw = _yf_ticker(symbol).news or []
        articles = []
        for a in raw[:12]:
            try:
                if "content" in a:
                    content  = a["content"]
                    headline = content.get("title","") or a.get("title","")
                    pub      = content.get("provider",{})
                    source   = pub.get("displayName",pub.get("name","")) if isinstance(pub,dict) else str(pub)
                    can      = content.get("canonicalUrl",{})
                    url      = can.get("url","") if isinstance(can,dict) else content.get("url","")
                    if not url: url = a.get("link","")
                    pd_      = content.get("pubDate","") or content.get("publishedAt","")
                    ts       = 0
                    if pd_:
                        try:
                            from datetime import datetime as dt
                            ts = int(dt.fromisoformat(pd_.replace("Z","+00:00")).timestamp())
                        except: pass
                    summary = content.get("summary","") or content.get("description","")
                else:
                    headline = a.get("title",""); source = a.get("publisher","")
                    url      = a.get("link",""); ts    = a.get("providerPublishTime",0)
                    summary  = a.get("summary","")
                if headline:
                    articles.append({"headline":headline,"source":source,"url":url,"datetime":ts,"summary":summary})
            except: continue
        data = {"symbol":symbol,"articles":articles,"count":len(articles)}
        _set(k,data,300); return data
    except Exception as e:
        return {"symbol":symbol,"error":str(e),"articles":[]}


_TF_INTERVAL = {"1D":"5m","1W":"15m","1M":"1h","3M":"1d","6M":"1d","1Y":"1d","5Y":"1wk","MAX":"1mo"}

def _tf_dates(tf):
    today=date.today(); end=today+timedelta(days=1)
    delta={"1D":timedelta(days=2),"1W":timedelta(days=7),"1M":timedelta(days=31),
           "3M":timedelta(days=92),"6M":timedelta(days=183),"1Y":timedelta(days=366),
           "5Y":timedelta(days=365*5+2),"MAX":None}.get(tf)
    if delta is None: return None,None
    return str(today-delta),str(end)

def get_candles(symbol, tf="3M"):
    k=f"candle:{symbol}:{tf}"; c=_get(k)
    if c: return c
    try:
        interval=_TF_INTERVAL.get(tf,"1d"); start,end=_tf_dates(tf)
        ticker=_yf_ticker(symbol)
        hist=ticker.history(period="max",interval=interval) if start is None \
             else ticker.history(start=start,end=end,interval=interval)
        if hist.empty: return {"error":"No chart data"}
        candles=[]
        for ts,row in hist.iterrows():
            try:
                unix=int(ts.timestamp()) if hasattr(ts,"timestamp") else int(ts.value//1_000_000_000)
                candles.append({"time":unix,"open":round(float(row["Open"]),2),
                    "high":round(float(row["High"]),2),"low":round(float(row["Low"]),2),
                    "close":round(float(row["Close"]),2),
                    "volume":int(row["Volume"]) if row["Volume"]==row["Volume"] else 0})
            except: pass
        data={"symbol":symbol,"timeframe":tf,"candles":candles,"count":len(candles)}
        _set(k,data,60); return data
    except Exception as e:
        return {"error":str(e)}


def get_full_dashboard(symbol):
    quote   = get_quote(symbol)
    profile = get_profile(symbol)
    metrics = get_metrics(symbol)
    analyst = get_analyst(symbol)
    if "error" in quote and not quote.get("current"):
        return {"symbol":symbol,"error":quote["error"],"quote":quote}
    return {"symbol":symbol,"profile":profile,"quote":quote,"metrics":metrics,
            "analyst":analyst,"fetched_at":datetime.now(timezone.utc).isoformat()}


def clear_cache(symbol=None):
    global _cache
    if symbol:
        keys=[k for k in _cache if f":{symbol}" in k]
        for k in keys: del _cache[k]
        return {"cleared":keys}
    n=len(_cache); _cache={}; return {"cleared_all":n}

def cache_stats():
    now=time.time()
    return {"entries":len(_cache),
            "keys":[{"key":k,"age_sec":round(now-v["ts"]),"ttl":v["ttl"]} for k,v in _cache.items()]}