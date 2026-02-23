"""
stock_service.py — Hybrid data backend.

Strategy to avoid Yahoo Finance 429 on cloud servers:
  1. NSE public API       → Indian stock quote (no auth, no IP block)
  2. yfinance .fast_info  → lightweight price fields (less blocked than .info)
  3. yfinance .history()  → price/candle data (rarely blocked)
  4. yfinance .info       → last resort for fundamentals, with retry + curl_cffi
"""
import time
import random
import requests
from datetime import datetime, timezone, timedelta, date

import yfinance as yf

# ── curl_cffi session ─────────────────────────────────────────────────────────
try:
    from curl_cffi import requests as curl_requests
    _YF_SESSION = curl_requests.Session(impersonate="chrome120")
    _YF_SESSION.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    print("✅ curl_cffi session active")
except ImportError:
    _YF_SESSION = None
    print("⚠️  curl_cffi not installed")

# ── In-memory cache ───────────────────────────────────────────────────────────
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

# ── Indian stock helpers ──────────────────────────────────────────────────────
def _is_indian(symbol: str) -> bool:
    return symbol.upper().endswith(".NS") or symbol.upper().endswith(".BO")

def _nse_symbol(symbol: str) -> str:
    return symbol.upper().replace(".NS", "").replace(".BO", "")

# ── NSE Public API ────────────────────────────────────────────────────────────
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

def _nse_session():
    s = requests.Session()
    s.headers.update(_NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except:
        pass
    return s

def _nse_quote(nse_sym: str) -> dict:
    """Fetch real-time quote from NSE public API — works from cloud servers."""
    try:
        s = _nse_session()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_sym}"
        r = s.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        d = r.json()
        pd_  = d.get("priceInfo", {})
        info = d.get("info", {})
        whl  = pd_.get("weekHighLow", {})
        return {
            "current":    _safe(pd_.get("lastPrice")),
            "open":       _safe(pd_.get("open")),
            "high":       _safe(pd_.get("intraDayHighLow", {}).get("max")),
            "low":        _safe(pd_.get("intraDayHighLow", {}).get("min")),
            "prev_close": _safe(pd_.get("previousClose")),
            "change":     _safe(pd_.get("change")),
            "change_pct": _safe(pd_.get("pChange")),
            "volume":     int(pd_.get("totalTradedVolume", 0) or 0),
            "week52_high":_safe(whl.get("max")),
            "week52_low": _safe(whl.get("min")),
            "name":       info.get("companyName", nse_sym),
            "isin":       info.get("isin", ""),
            "currency":   "INR",
        }
    except Exception as e:
        print(f"NSE quote error for {nse_sym}: {e}")
        return {}

# ── yfinance helpers ──────────────────────────────────────────────────────────
def _yf_ticker(symbol):
    return yf.Ticker(symbol, session=_YF_SESSION) if _YF_SESSION else yf.Ticker(symbol)

def _yf_fast_info(symbol) -> dict:
    """yfinance fast_info — lighter endpoint, less often blocked than .info."""
    try:
        fi = _yf_ticker(symbol).fast_info
        return {
            "current":    _safe(getattr(fi, "last_price", None)),
            "prev_close": _safe(getattr(fi, "previous_close", None)),
            "open":       _safe(getattr(fi, "open", None)),
            "high":       _safe(getattr(fi, "day_high", None)),
            "low":        _safe(getattr(fi, "day_low", None)),
            "volume":     int(getattr(fi, "three_month_average_volume", 0) or 0),
            "market_cap": getattr(fi, "market_cap", None),
            "week52_high":_safe(getattr(fi, "year_high", None)),
            "week52_low": _safe(getattr(fi, "year_low", None)),
            "currency":   getattr(fi, "currency", "INR"),
            "exchange":   getattr(fi, "exchange", ""),
        }
    except Exception as e:
        print(f"fast_info error {symbol}: {e}")
        return {}

def _yf_info_with_retry(symbol, retries=3, base_delay=3) -> dict:
    """Last-resort: fetch yfinance .info with exponential backoff."""
    last_err = None
    for attempt in range(retries):
        try:
            info = _yf_ticker(symbol).info or {}
            if info and len(info) > 5:
                return info
            raise ValueError("Empty info returned")
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if any(x in err_str for x in ["no data found", "delisted", "no timezone"]):
                break
            if attempt < retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1.5)
                print(f"⚠️  yfinance .info retry {attempt+1} for {symbol} in {delay:.1f}s: {e}")
                time.sleep(delay)
    return {}

# ── Logo helper ───────────────────────────────────────────────────────────────
def _get_logo(symbol, website=None):
    from urllib.parse import urlparse
    domain = None
    if website:
        try:
            domain = urlparse(website).netloc.replace("www.", "").strip("/")
        except:
            pass
    KNOWN_DOMAINS = {
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
        "HINDUNILVR":"hul.co.in",
        "AAPL":"apple.com","MSFT":"microsoft.com","GOOGL":"google.com",
        "GOOG":"google.com","AMZN":"amazon.com","META":"meta.com",
        "TSLA":"tesla.com","NVDA":"nvidia.com","NFLX":"netflix.com",
        "AMD":"amd.com","INTC":"intel.com","JPM":"jpmorganchase.com",
        "BAC":"bankofamerica.com","V":"visa.com","WMT":"walmart.com",
    }
    clean = symbol.upper().replace(".NS","").replace(".BO","")
    if not domain:
        domain = KNOWN_DOMAINS.get(clean)
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
        # PRIMARY: NSE API — works from any cloud server, no Yahoo needed
        nse_data = _nse_quote(_nse_symbol(sym_up))
        if nse_data and nse_data.get("current"):
            data.update(nse_data)
            _set(k, data, 120)
            return data

    # FALLBACK 1: yfinance fast_info
    fi = _yf_fast_info(symbol)
    if fi and fi.get("current"):
        cur = fi.get("current"); prev = fi.get("prev_close")
        chg  = _safe(cur - prev) if cur and prev else None
        chgp = _safe(((cur - prev) / prev) * 100) if cur and prev else None
        data.update({**fi, "change": chg, "change_pct": chgp})
        _set(k, data, 180)
        return data

    # FALLBACK 2: yfinance history (last close)
    try:
        hist = _yf_ticker(symbol).history(period="2d")
        if not hist.empty:
            last    = hist.iloc[-1]
            prev_r  = hist.iloc[-2] if len(hist) > 1 else None
            cur     = round(float(last["Close"]), 2)
            prev    = round(float(prev_r["Close"]), 2) if prev_r is not None else cur
            chg     = _safe(cur - prev)
            chgp    = _safe(((cur - prev) / prev) * 100) if prev else None
            data.update({
                "current": cur, "open": _safe(last["Open"]),
                "high": _safe(last["High"]), "low": _safe(last["Low"]),
                "prev_close": prev, "change": chg, "change_pct": chgp,
                "volume": int(last["Volume"]) if last["Volume"] == last["Volume"] else 0,
            })
            _set(k, data, 180)
            return data
    except Exception as e:
        print(f"history fallback error {symbol}: {e}")

    return {"symbol": symbol, "error": "Could not fetch quote from any source"}


def get_profile(symbol):
    k = f"profile:{symbol}"; c = _get(k)
    if c: return c

    sym_up = symbol.upper()
    data = {
        "symbol": symbol, "exchange": "NSE", "currency": "INR",
        "country": "India", "industry": "N/A", "sector": "N/A",
        "name": _nse_symbol(sym_up), "description": "",
        "logo": _get_logo(symbol), "web_url": "", "employees": None, "market_cap": None,
    }

    if _is_indian(sym_up):
        nse_q = _nse_quote(_nse_symbol(sym_up))
        if nse_q.get("name"):
            data["name"] = nse_q["name"]
        # Try yfinance for sector/description — non-critical
        try:
            info = _yf_info_with_retry(symbol, retries=2, base_delay=2)
            if info:
                data.update({
                    "name":        info.get("longName") or info.get("shortName") or data["name"],
                    "sector":      info.get("sector", "N/A"),
                    "industry":    info.get("industry", "N/A"),
                    "description": (info.get("longBusinessSummary") or "")[:400],
                    "employees":   info.get("fullTimeEmployees"),
                    "market_cap":  info.get("marketCap"),
                    "web_url":     info.get("website", ""),
                    "logo":        info.get("logo_url") or _get_logo(symbol, info.get("website")),
                })
        except:
            pass
        _set(k, data, 86400)
        return data

    # US stocks
    fi = _yf_fast_info(symbol)
    if fi:
        data.update({"exchange": fi.get("exchange",""), "currency": fi.get("currency","USD"),
                     "market_cap": fi.get("market_cap"), "country": "US"})
    try:
        info = _yf_info_with_retry(symbol, retries=3, base_delay=3)
        if info:
            data.update({
                "name":        info.get("longName") or info.get("shortName", symbol),
                "sector":      info.get("sector", "N/A"),
                "industry":    info.get("industry", "N/A"),
                "description": (info.get("longBusinessSummary") or "")[:400],
                "employees":   info.get("fullTimeEmployees"),
                "market_cap":  info.get("marketCap") or fi.get("market_cap"),
                "web_url":     info.get("website", ""),
                "logo":        info.get("logo_url") or _get_logo(symbol, info.get("website")),
            })
    except Exception as e:
        data["error_detail"] = str(e)

    _set(k, data, 86400)
    return data


def _compute_roe(ticker_obj, info):
    roe = _safe(info.get("returnOnEquity")) if info else None
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
                if equity:
                    return round(net_income / equity, 4)
    except:
        pass
    return None


def get_metrics(symbol):
    k = f"metrics:{symbol}"; c = _get(k)
    if c: return c
    try:
        info = _yf_info_with_retry(symbol, retries=2, base_delay=3)
        t    = _yf_ticker(symbol)
        roe  = _compute_roe(t, info) if info else None
        data = {
            "symbol":            symbol,
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
        }
        # Fill week52 from NSE if yfinance failed
        if _is_indian(symbol) and not data["week52_high"]:
            nq = _nse_quote(_nse_symbol(symbol))
            data["week52_high"] = nq.get("week52_high")
            data["week52_low"]  = nq.get("week52_low")
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def get_analyst(symbol):
    k = f"analyst:{symbol}"; c = _get(k)
    if c: return c
    try:
        t    = _yf_ticker(symbol)
        info = _yf_info_with_retry(symbol, retries=2, base_delay=2)
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
        except:
            pass
        total     = sb + buy + hold + sell + ssell
        ck        = (info.get("recommendationKey","") if info else "").lower()
        cm        = {"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
        consensus = cm.get(ck, "N/A")
        if consensus == "N/A" and total > 0:
            bull = (sb + buy) / total; bear = (sell + ssell) / total
            consensus = "Strong Buy" if bull>=0.6 else "Buy" if bull>=0.4 else "Sell" if bear>=0.4 else "Hold"
        data = {
            "symbol": symbol, "consensus": consensus,
            "strong_buy": sb, "buy": buy, "hold": hold, "sell": sell, "strong_sell": ssell, "total": total,
            "target_mean":  _safe(info.get("targetMeanPrice") if info else None),
            "target_high":  _safe(info.get("targetHighPrice") if info else None),
            "target_low":   _safe(info.get("targetLowPrice")  if info else None),
            "analyst_count": (info.get("numberOfAnalystOpinions",0) if info else 0),
        }
        _set(k, data, 3600)
        return data
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def get_news(symbol):
    k = f"news:{symbol}"; c = _get(k)
    if c: return c
    try:
        raw = _yf_ticker(symbol).news or []
        articles = []
        for a in raw[:12]:
            try:
                if "content" in a:
                    content   = a["content"]
                    headline  = content.get("title","") or a.get("title","")
                    pub       = content.get("provider",{})
                    source    = pub.get("displayName", pub.get("name","")) if isinstance(pub,dict) else str(pub)
                    canonical = content.get("canonicalUrl",{})
                    url       = canonical.get("url","") if isinstance(canonical,dict) else content.get("url","")
                    if not url: url = a.get("link","")
                    pub_date  = content.get("pubDate","") or content.get("publishedAt","")
                    unix_time = 0
                    if pub_date:
                        try:
                            from datetime import datetime as dt
                            unix_time = int(dt.fromisoformat(pub_date.replace("Z","+00:00")).timestamp())
                        except: pass
                    summary   = content.get("summary","") or content.get("description","")
                else:
                    headline  = a.get("title","")
                    source    = a.get("publisher","")
                    url       = a.get("link","")
                    unix_time = a.get("providerPublishTime",0)
                    summary   = a.get("summary","")
                if headline:
                    articles.append({"headline":headline,"source":source,"url":url,
                                     "datetime":unix_time,"summary":summary})
            except:
                continue
        data = {"symbol":symbol,"articles":articles,"count":len(articles)}
        _set(k, data, 300)
        return data
    except Exception as e:
        return {"symbol":symbol,"error":str(e),"articles":[]}


# ── Candle data (yfinance history — rarely blocked) ───────────────────────────
_TF_INTERVAL = {
    "1D":"5m","1W":"15m","1M":"1h","3M":"1d","6M":"1d","1Y":"1d","5Y":"1wk","MAX":"1mo",
}

def _tf_dates(tf):
    today = date.today()
    end   = today + timedelta(days=1)
    delta = {
        "1D":timedelta(days=2),"1W":timedelta(days=7),
        "1M":timedelta(days=31),"3M":timedelta(days=92),
        "6M":timedelta(days=183),"1Y":timedelta(days=366),
        "5Y":timedelta(days=365*5+2),"MAX":None,
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
        ticker = _yf_ticker(symbol)
        hist   = ticker.history(period="max", interval=interval) if start is None \
                 else ticker.history(start=start, end=end, interval=interval)
        if hist.empty:
            return {"error": "No chart data"}
        candles = []
        for ts, row in hist.iterrows():
            try:
                unix = int(ts.timestamp()) if hasattr(ts,"timestamp") else int(ts.value//1_000_000_000)
                candles.append({
                    "time":   unix,
                    "open":   round(float(row["Open"]),2),
                    "high":   round(float(row["High"]),2),
                    "low":    round(float(row["Low"]),2),
                    "close":  round(float(row["Close"]),2),
                    "volume": int(row["Volume"]) if row["Volume"]==row["Volume"] else 0,
                })
            except:
                pass
        data = {"symbol":symbol,"timeframe":tf,"candles":candles,"count":len(candles)}
        _set(k, data, 60)
        return data
    except Exception as e:
        return {"error": str(e)}


def get_full_dashboard(symbol):
    quote   = get_quote(symbol)
    profile = get_profile(symbol)
    metrics = get_metrics(symbol)
    analyst = get_analyst(symbol)
    if "error" in quote:
        return {"symbol": symbol, "error": quote["error"], "quote": quote}
    return {
        "symbol":     symbol,
        "profile":    profile,
        "quote":      quote,
        "metrics":    metrics,
        "analyst":    analyst,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


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
        "keys": [{"key":k,"age_sec":round(now-v["ts"]),"ttl":v["ttl"]} for k,v in _cache.items()],
    }