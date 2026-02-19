from modules.modules import Chatterbot, FDCalculatorBot, SipChatterbot
from flask import Flask, render_template, request, jsonify
import yfinance as yf
import requests
import re
import traceback
from market_data import get_market_indices, get_nifty_gainers, get_nifty_losers, get_nifty_volume, get_nifty_turnover

app = Flask(__name__)

# Initialize bots
try:
    emi_bot = Chatterbot()
    fd_calculator = FDCalculatorBot()
    sip_bot = SipChatterbot()
    print("✅ All bots initialized successfully!")
except Exception as e:
    print(f"❌ Error initializing bots: {e}")
    traceback.print_exc()

# NIFTY 100 STOCK TICKERS (Top 100 by Market Cap)
STOCK_TICKERS = {
    # --- Top 10 Heavyweights ---
    "reliance": "RELIANCE.NS", "ril": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "hdfc": "HDFCBANK.NS", "hdfcbank": "HDFCBANK.NS",
    "icici": "ICICIBANK.NS", "icicibank": "ICICIBANK.NS",
    "infosys": "INFY.NS", "infy": "INFY.NS",
    "bharti": "BHARTIARTL.NS", "airtel": "BHARTIARTL.NS",
    "sbi": "SBIN.NS", "sbin": "SBIN.NS",
    "itc": "ITC.NS",
    "hul": "HINDUNILVR.NS", "hindunilvr": "HINDUNILVR.NS",
    "lt": "LT.NS", "larsen": "LT.NS",

    # --- Banking & Finance ---
    "kotak": "KOTAKBANK.NS", "kotakbank": "KOTAKBANK.NS",
    "axis": "AXISBANK.NS", "axisbank": "AXISBANK.NS",
    "indusind": "INDUSINDBK.NS",
    "bajajfinance": "BAJFINANCE.NS", "bajaj": "BAJFINANCE.NS",
    "bajajfinsv": "BAJAJFINSV.NS",
    "jiofin": "JIOFIN.NS",
    "sriram": "SHRIRAMFIN.NS", "shriramfin": "SHRIRAMFIN.NS",
    "chola": "CHOLAFIN.NS", "cholafin": "CHOLAFIN.NS",
    "muthoot": "MUTHOOTFIN.NS",
    "sbicard": "SBICARD.NS",
    "hdfclife": "HDFCLIFE.NS",
    "sbilife": "SBILIFE.NS",
    "icicipruli": "ICICIPRULI.NS",
    "icicigi": "ICICIGI.NS", "icicilombard": "ICICIGI.NS",
    "pfc": "PFC.NS",
    "rec": "REC.NS",
    "bajajhold": "BAJAJHLDNG.NS",
    "pnb": "PNB.NS",
    "bob": "BANKBARODA.NS", "bankbaroda": "BANKBARODA.NS",
    "canara": "CANBK.NS",
    "aubank": "AUBANK.NS",
    "idfcfirst": "IDFCFIRSTB.NS",

    # --- IT & Tech ---
    "hcl": "HCLTECH.NS", "hcltech": "HCLTECH.NS",
    "wipro": "WIPRO.NS",
    "techm": "TECHM.NS", "techmahindra": "TECHM.NS",
    "ltim": "LTIM.NS", "mindtree": "LTIM.NS",
    "ofss": "OFSS.NS", "oracle": "OFSS.NS",
    "mphasis": "MPHASIS.NS",
    "persistent": "PERSISTENT.NS",

    # --- Auto & Auto Comp ---
    "maruti": "MARUTI.NS",
    "tatamotors": "TATAMOTORS.NS",
    "mahindra": "M&M.NS", "m&m": "M&M.NS",
    "bajajauto": "BAJAJ-AUTO.NS",
    "eicher": "EICHERMOT.NS", "eichermot": "EICHERMOT.NS",
    "hero": "HEROMOTOCO.NS", "heromotoco": "HEROMOTOCO.NS",
    "tvs": "TVSMOTOR.NS", "tvsmotor": "TVSMOTOR.NS",
    "motherson": "MOTHERSON.NS", "samvardhana": "MOTHERSON.NS",
    "bosch": "BOSCHLTD.NS",
    "mrf": "MRF.NS",
    "balkrishna": "BALKRISIND.NS",

    # --- Energy, Oil & Gas ---
    "ongc": "ONGC.NS",
    "ntpc": "NTPC.NS",
    "powergrid": "POWERGRID.NS",
    "coalindia": "COALINDIA.NS",
    "bpcl": "BPCL.NS",
    "ioc": "IOC.NS",
    "gail": "GAIL.NS",
    "tatapower": "TATAPOWER.NS",
    "adanigreen": "ADANIGREEN.NS",
    "adanipower": "ADANIPOWER.NS",
    "adanienergy": "ADANIENSOL.NS", "adanitrans": "ADANIENSOL.NS",
    "atgl": "ATGL.NS", "adanigas": "ATGL.NS",
    "nhpc": "NHPC.NS",
    "jswenergy": "JSWENERGY.NS",

    # --- FMCG & Consumer ---
    "nestle": "NESTLEIND.NS",
    "britannia": "BRITANNIA.NS",
    "tataconsum": "TATACONSUM.NS",
    "titan": "TITAN.NS",
    "asianpaint": "ASIANPAINT.NS", "asian": "ASIANPAINT.NS",
    "berger": "BERGEPAINT.NS",
    "dabur": "DABUR.NS",
    "godrejcp": "GODREJCP.NS",
    "marico": "MARICO.NS",
    "colgate": "COLPAL.NS", "colpal": "COLPAL.NS",
    "varun": "VBL.NS", "vbl": "VBL.NS",
    "ubl": "UBL.NS", "unitedbreweries": "UBL.NS",
    "mcdowell": "MCDOWELL-N.NS", "unitedspirits": "MCDOWELL-N.NS",
    "zomato": "ZOMATO.NS",
    "avenue": "DMART.NS", "dmart": "DMART.NS",
    "trent": "TRENT.NS",
    "havells": "HAVELLS.NS",
    "pidilite": "PIDILITIND.NS",
    "page": "PAGEIND.NS",
    "eicher": "EICHERMOT.NS",

    # --- Pharma & Healthcare ---
    "sunpharma": "SUNPHARMA.NS",
    "cipla": "CIPLA.NS",
    "drreddy": "DRREDDY.NS",
    "divis": "DIVISLAB.NS", "divislab": "DIVISLAB.NS",
    "apollo": "APOLLOHOSP.NS", "apollohosp": "APOLLOHOSP.NS",
    "torrent": "TORNTPHARM.NS", "torntpharm": "TORNTPHARM.NS",
    "mankind": "MANKIND.NS",
    "zydus": "ZYDUSLIFE.NS", "zyduslife": "ZYDUSLIFE.NS",
    "lupin": "LUPIN.NS",
    "max": "MAXHEALTH.NS", "maxhealth": "MAXHEALTH.NS",
    "aurobindo": "AUROPHARMA.NS",

    # --- Metals & Mining ---
    "tatasteel": "TATASTEEL.NS",
    "jswsteel": "JSWSTEEL.NS",
    "hindalco": "HINDALCO.NS",
    "vedanta": "VEDL.NS", "vedl": "VEDL.NS",
    "jindalsteel": "JINDALSTEL.NS", "jindalstel": "JINDALSTEL.NS",
    "nmdec": "NMDC.NS", "nmdc": "NMDC.NS",

    # --- Infra, Capital Goods & Others ---
    "adani": "ADANIENT.NS", "adanient": "ADANIENT.NS",
    "adaniports": "ADANIPORTS.NS",
    "ultratech": "ULTRACEMCO.NS",
    "grasim": "GRASIM.NS",
    "ambuja": "AMBUJACEM.NS", "ambujacem": "AMBUJACEM.NS",
    "shree": "SHREECEM.NS", "shreecement": "SHREECEM.NS",
    "acc": "ACC.NS",
    "siemens": "SIEMENS.NS",
    "abb": "ABB.NS",
    "hal": "HAL.NS",
    "bel": "BEL.NS",
    "dlf": "DLF.NS",
    "macrotech": "LODHA.NS", "lodha": "LODHA.NS",
    "godrejprop": "GODREJPROP.NS",
    "irctc": "IRCTC.NS",
    "indigo": "INDIGO.NS", "interglobe": "INDIGO.NS",
    "naukri": "NAUKRI.NS", "infoedge": "NAUKRI.NS",
    "polycab": "POLYCAB.NS",
    "supreme": "SUPREMEIND.NS",
    "solar": "SOLARINDS.NS",
    "srf": "SRF.NS",
    "piind": "PIIND.NS"
}

def resolve_ticker(query):
    """
    Smart ticker resolution that prioritizes:
    1. Exact matches
    2. Longest key matches (prevents 'hdfc' from matching inside 'hdfclife')
    3. Partial matches
    """
    q = query.lower().strip().lstrip('$')
    
    # 1. Exact match (Highest Priority)
    if q in STOCK_TICKERS:
        return STOCK_TICKERS[q]
        
    # 2. Check if a Key is inside the Query (Longest key wins)
    # e.g. User types "hdfclife share" -> matches "hdfclife" (len 8) over "hdfc" (len 4)
    best_match_val = None
    best_match_len = 0
    
    for key, val in STOCK_TICKERS.items():
        if key in q:
            if len(key) > best_match_len:
                best_match_len = len(key)
                best_match_val = val
    
    if best_match_val:
        return best_match_val

    # 3. Check if Query is inside a Key (Autocomplete style)
    # e.g. User types "relian" -> matches "reliance"
    for key, val in STOCK_TICKERS.items():
        if q in key:
            return val
            
    # 4. Check reversed tickers (e.g. .NS check)
    direct = query.upper().strip()
    if not direct.endswith('.NS'):
        direct += '.NS'
    for val in STOCK_TICKERS.values():
        if val == direct:
            return val
            
    return None

def _clean_ticker(ticker):
    """
    Strip any leading $ that newer yfinance versions sometimes inject,
    and ensure the ticker is properly formatted.
    e.g. '$ZOMATO.NS' -> 'ZOMATO.NS'
    """
    return ticker.lstrip('$').strip()

def get_stock_full(symbol_or_query):
    ticker_symbol = resolve_ticker(symbol_or_query)
    if not ticker_symbol:
        return {"error": f"Stock '{symbol_or_query}' not found. Try: INFY, TCS, RELIANCE, HDFC, etc."}

    # Sanitize: strip any $ prefix that yfinance may inject internally
    ticker_symbol = _clean_ticker(ticker_symbol)
    symbol = ticker_symbol.replace('.NS', '').replace('.BO', '')
    result = {"symbol": symbol, "ticker": ticker_symbol}

    # Today: NSE
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com/'
        }
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=5)
        r = session.get(f"https://www.nseindia.com/api/quote-equity?symbol={symbol}", headers=headers, timeout=10)
        if r.status_code == 200 and 'priceInfo' in r.json():
            pi = r.json()['priceInfo']
            result['current']    = pi.get('lastPrice', 0)
            result['open']       = pi.get('open', 0)
            result['prev_close'] = pi.get('previousClose', 0)
            result['day_high']   = pi.get('intraDayHighLow', {}).get('max', 0)
            result['day_low']    = pi.get('intraDayHighLow', {}).get('min', 0)
            result['change']     = result['current'] - result['prev_close']
            result['change_pct'] = (result['change'] / result['prev_close'] * 100) if result['prev_close'] else 0
        else:
            raise Exception("NSE non-200")
    except Exception as e:
        # Fallback to Yahoo — use clean ticker to prevent $ injection
        try:
            clean_ticker = _clean_ticker(ticker_symbol)
            yf_data = yf.Ticker(clean_ticker).history(period='2d')
            if not yf_data.empty:
                result['current']    = float(yf_data['Close'].iloc[-1])
                result['open']       = float(yf_data['Open'].iloc[-1])
                result['day_high']   = float(yf_data['High'].iloc[-1])
                result['day_low']    = float(yf_data['Low'].iloc[-1])
                result['prev_close'] = float(yf_data['Close'].iloc[-2]) if len(yf_data) > 1 else result['open']
                result['change']     = result['current'] - result['prev_close']
                result['change_pct'] = (result['change'] / result['prev_close'] * 100) if result['prev_close'] else 0
        except Exception as e2:
            result['error_today'] = str(e2)

    # Weekly: Yahoo — use clean ticker to prevent $ injection
    try:
        clean_ticker = _clean_ticker(ticker_symbol)
        w = yf.Ticker(clean_ticker).history(period='5d')
        if not w.empty:
            result['week_open']   = float(w['Open'].iloc[0])
            result['week_close']  = float(w['Close'].iloc[-1])
            result['week_high']   = float(w['High'].max())
            result['week_low']    = float(w['Low'].min())
            result['week_change'] = result['week_close'] - result['week_open']
            result['week_pct']    = (result['week_change'] / result['week_open'] * 100) if result['week_open'] else 0
    except Exception as e:
        result['error_weekly'] = str(e)

    return result

def get_stock_price(query):
    d = get_stock_full(query)
    if 'error' in d:
        return f"❌ {d['error']}"
    s = d.get('symbol','')
    return (f"📊 <strong>{s}</strong><br>"
            f"💰 <strong>Current Price:</strong> ₹{d.get('current',0):.2f}<br>"
            f"📈 <strong>Change:</strong> {d.get('change',0):+.2f} ({d.get('change_pct',0):+.2f}%)<br>"
            f"📉 <strong>Day High:</strong> ₹{d.get('day_high',0):.2f}<br>"
            f"📊 <strong>Day Low:</strong> ₹{d.get('day_low',0):.2f}<br>"
            f"🔓 <strong>Open:</strong> ₹{d.get('open',0):.2f}<br>"
            f"🔒 <strong>Prev Close:</strong> ₹{d.get('prev_close',0):.2f}")

def get_stock_weekly(query):
    d = get_stock_full(query)
    if 'error' in d:
        return f"❌ {d['error']}"
    s = d.get('symbol','')
    return (f"📊 <strong>Weekly - {s}</strong><br><br>"
            f"🔓 <strong>Week Open:</strong> ₹{d.get('week_open',0):.2f}<br>"
            f"🔒 <strong>Week Close:</strong> ₹{d.get('week_close',0):.2f}<br>"
            f"📈 <strong>Week High:</strong> ₹{d.get('week_high',0):.2f}<br>"
            f"📉 <strong>Week Low:</strong> ₹{d.get('week_low',0):.2f}<br>"
            f"💹 <strong>Change:</strong> {d.get('week_change',0):+.2f} ({d.get('week_pct',0):+.2f}%)")

@app.route("/")
def index():
    return render_template('chat_enhanced.html')

@app.route("/get_stock", methods=["POST"])
def get_stock_endpoint():
    symbol = request.form.get("symbol", "")
    data = get_stock_full(symbol)
    return jsonify(data)

@app.route("/classic")
def classic():
    return render_template('chat.html')

@app.route("/get", methods=["POST"])
def get_response():
    user_input = request.form["msg"]
    return process_user_input(user_input)

@app.route("/market")
def market():
    data = get_market_indices()
    return jsonify(data)

@app.route("/top_gainers")
def top_gainers():
    data = get_nifty_gainers()
    return jsonify(data)

@app.route("/top_losers")
def top_losers():
    data = get_nifty_losers()
    return jsonify(data)

@app.route("/top_volume")
def top_volume():
    data = get_nifty_volume()
    return jsonify(data)

@app.route("/top_turnover")
def top_turnover():
    data = get_nifty_turnover()
    return jsonify(data)

@app.route("/currency")
def currency():
    """
    Exchange rates via Frankfurter API (ECB data, highly reliable, no key needed).
    Returns rates for major currencies relative to INR.
    """
    try:
        # Get rates with INR as base
        r = requests.get("https://api.frankfurter.app/latest?from=INR&to=USD,EUR,GBP,AED,SGD,JPY,CAD,AUD,CHF,CNY", timeout=8)
        r.raise_for_status()
        data = r.json()
        rates_from_inr = data.get("rates", {})

        # Build two-way table: how much 1 foreign unit = X INR
        currencies = {
            "USD": {"name": "US Dollar",         "symbol": "$",  "flag": "🇺🇸"},
            "EUR": {"name": "Euro",               "symbol": "€",  "flag": "🇪🇺"},
            "GBP": {"name": "British Pound",      "symbol": "£",  "flag": "🇬🇧"},
            "AED": {"name": "UAE Dirham",         "symbol": "د.إ","flag": "🇦🇪"},
            "SGD": {"name": "Singapore Dollar",   "symbol": "S$", "flag": "🇸🇬"},
            "JPY": {"name": "Japanese Yen",       "symbol": "¥",  "flag": "🇯🇵"},
            "CAD": {"name": "Canadian Dollar",    "symbol": "C$", "flag": "🇨🇦"},
            "AUD": {"name": "Australian Dollar",  "symbol": "A$", "flag": "🇦🇺"},
            "CHF": {"name": "Swiss Franc",        "symbol": "Fr", "flag": "🇨🇭"},
            "CNY": {"name": "Chinese Yuan",       "symbol": "¥",  "flag": "🇨🇳"},
        }

        result = []
        for code, meta in currencies.items():
            rate_from_inr = rates_from_inr.get(code)
            if not rate_from_inr:
                continue
            inr_per_unit = round(1 / rate_from_inr, 4)
            result.append({
                "code":        code,
                "name":        meta["name"],
                "symbol":      meta["symbol"],
                "flag":        meta["flag"],
                "inr_per_unit": inr_per_unit,       # 1 USD = X INR
                "unit_per_inr": round(rate_from_inr, 6),  # 1 INR = X USD
            })

        return jsonify({
            "rates": result,
            "base": "INR",
            "date": data.get("date", ""),
            "source": "European Central Bank via Frankfurter"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/metals")
def metals():
    """
    Gold & Silver prices via yfinance futures:
    GC=F = Gold (USD/troy oz), SI=F = Silver (USD/troy oz)
    Converted to INR using live USD/INR rate.
    Indian units: Gold per 10g, Silver per kg.
    """
    try:
        # Get live USD/INR rate
        usd_inr = 84.0  # fallback
        try:
            fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=INR", timeout=6)
            usd_inr = fx.json()["rates"]["INR"]
        except Exception:
            pass

        TROY_OZ_TO_GRAM = 31.1035  # 1 troy oz = 31.1035 grams

        def fetch_metal(ticker_sym, name, unit_label, unit_factor):
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="5d")
            if hist.empty:
                return None
            price_usd_oz   = float(hist["Close"].iloc[-1])
            prev_usd_oz    = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price_usd_oz
            price_usd_gram = price_usd_oz / TROY_OZ_TO_GRAM
            price_inr_gram = price_usd_gram * usd_inr
            price_inr_unit = price_inr_gram * unit_factor
            prev_inr_unit  = (prev_usd_oz / TROY_OZ_TO_GRAM) * usd_inr * unit_factor
            change         = price_inr_unit - prev_inr_unit
            change_pct     = (change / prev_inr_unit * 100) if prev_inr_unit else 0
            return {
                "name":        name,
                "price_inr":   round(price_inr_unit, 2),
                "prev_inr":    round(prev_inr_unit, 2),
                "change":      round(change, 2),
                "change_pct":  round(change_pct, 4),
                "price_usd_oz": round(price_usd_oz, 2),
                "unit":        unit_label,
            }

        gold   = fetch_metal("GC=F", "Gold",   "per 10g",  10)
        silver = fetch_metal("SI=F", "Silver",  "per kg",   1000)

        return jsonify({
            "gold":    gold,
            "silver":  silver,
            "usd_inr": round(usd_inr, 4),
            "source":  "MCX Futures via Yahoo Finance"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/news")
def news():
    import xml.etree.ElementTree as ET
    import html as html_lib
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone, timedelta
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # ── Feeds: dedicated market/finance sections only ─────────────────────────
    # Each entry: (url, display_name, color)
    FEEDS = [
        # Economic Times — markets & stocks sections
        ("https://economictimes.indiatimes.com/markets/stocks/rss.cms",             "Economic Times",    "#f97316"),
        ("https://economictimes.indiatimes.com/markets/rss.cms",                     "Economic Times",    "#f97316"),
        ("https://economictimes.indiatimes.com/markets/mutual-funds/rss.cms",        "Economic Times",    "#f97316"),
        # MoneyControl — multiple dedicated feeds for top news coverage
        ("https://www.moneycontrol.com/rss/MCtopnews.xml",                           "MoneyControl",      "#ef4444"),
        ("https://www.moneycontrol.com/rss/marketreports.xml",                       "MoneyControl",      "#ef4444"),
        ("https://www.moneycontrol.com/rss/latestnews.xml",                          "MoneyControl",      "#ef4444"),
        ("https://www.moneycontrol.com/rss/results.xml",                             "MoneyControl",      "#ef4444"),
        ("https://www.moneycontrol.com/rss/business.xml",                            "MoneyControl",      "#ef4444"),
        ("https://www.moneycontrol.com/rss/economy.xml",                             "MoneyControl",      "#ef4444"),
        # Mint — markets feed
        ("https://www.livemint.com/rss/markets",                                     "Mint",              "#0ea5e9"),
        ("https://www.livemint.com/rss/money",                                       "Mint",              "#0ea5e9"),
        # Business Standard — markets + economy
        ("https://www.business-standard.com/rss/markets-106.rss",                    "Business Standard", "#8b5cf6"),
        ("https://www.business-standard.com/rss/economy-policy-10301.rss",           "Business Standard", "#8b5cf6"),
        ("https://www.business-standard.com/rss/finance-155.rss",                    "Business Standard", "#8b5cf6"),
        # Financial Express — market news
        ("https://www.financialexpress.com/market/feed/",                             "Financial Express", "#10b981"),
        # NDTV Profit
        ("https://feeds.feedburner.com/ndtvprofit-latest",                           "NDTV Profit",       "#f59e0b"),
        # Reuters India
        ("https://feeds.reuters.com/reuters/INbusinessNews",                         "Reuters",           "#dc2626"),
    ]

    REJECT_KEYWORDS = [
        "ramadan","eid","wishes","whatsapp","greetings","festival","recipe",
        "bollywood","cricket","ipl","movie","film","song","weather","horoscope",
        "astrology","celebrity","actor","actress","wedding","divorce","baby",
        "pregnancy","fashion","lifestyle","sports","football","hockey","tennis",
        "covid","vaccine","health","hospital","political","election","government",
        "pakistan","china war","iran war","ukraine","military","army",
    ]

    FINANCE_KEYWORDS = [
        "stock","share","market","nifty","sensex","bse","nse","rupee","rbi",
        "sebi","ipo","fund","mutual","equity","invest","earning","profit",
        "revenue","quarter","fiscal","budget","economy","gdp","inflation",
        "rate","bank","target","buy","sell","rally","crash","gain","loss",
        "crore","lakh","billion","million","rs ","₹","dividend","futures",
        "options","commodity","gold","silver","crude","forex","fii","dii",
        "mcx","derivative","smallcap","midcap","largecap","bluechip","etf",
        "nav","aum","portfolio","hedge","arbitrage","demat","broker","trader",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    }

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)  # last 24h only
    seen   = set()
    all_articles = []

    def fetch_feed(feed_url, source_name, color):
        """Fetch and parse a single RSS feed, return list of article dicts."""
        results = []
        try:
            r = requests.get(feed_url, headers=headers, timeout=7)
            if r.status_code != 200:
                return results
            root    = ET.fromstring(r.content)
            channel = root.find("channel")
            items   = channel.findall("item") if channel is not None else root.findall("item")

            for item in items:
                title = html_lib.unescape(item.findtext("title", "")).strip()
                if not title:
                    continue

                tl = title.lower()
                if any(kw in tl for kw in REJECT_KEYWORDS):
                    continue
                if not any(kw in tl for kw in FINANCE_KEYWORDS):
                    continue

                # Parse publish date
                pub_str = item.findtext("pubDate", "")
                pub_dt  = None
                try:
                    pub_dt = parsedate_to_datetime(pub_str)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass  # no date → include anyway

                link = item.findtext("link", "#").strip()
                # Some feeds put link in <guid isPermaLink="true">
                if link == "#" or not link.startswith("http"):
                    guid = item.findtext("guid", "").strip()
                    if guid.startswith("http"):
                        link = guid

                results.append({
                    "title":     title,
                    "source":    source_name,
                    "color":     color,
                    "link":      link,
                    "published": pub_str,
                    "pub_dt":    pub_dt,
                })
        except Exception as e:
            print(f"Feed error [{source_name}] {feed_url}: {e}")
        return results

    # Fetch all feeds in parallel (max 6 workers)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_feed, url, name, color): (url, name)
                   for url, name, color in FEEDS}
        for future in as_completed(futures, timeout=12):
            try:
                all_articles.extend(future.result())
            except Exception:
                pass

    # Deduplicate by title, sort newest first
    unique = []
    for a in all_articles:
        key = a["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # Sort: articles with parsed dates first (newest), undated last
    unique.sort(key=lambda x: x["pub_dt"] if x["pub_dt"] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Strip pub_dt (not JSON serialisable) and return top 40
    for a in unique:
        a.pop("pub_dt", None)

    return jsonify(unique[:50])




@app.route("/mf_list")
def mf_list():
    """
    Returns ALL Direct Plan - Growth mutual funds from AMFI via mfapi.in.
    ~2,000 funds after filtering. Cached for 6 hours.
    Categories extracted from fund names.
    """
    import time

    cache = getattr(mf_list, '_cache', None)
    if cache and (time.time() - cache['ts']) < 21600:  # 6h
        return jsonify(cache['data'])

    CATEGORY_KEYWORDS = [
        ("Liquid",                "Liquid"),
        ("Overnight",             "Overnight"),
        ("Ultra Short",           "Ultra Short Duration"),
        ("Low Duration",          "Low Duration"),
        ("Short Duration",        "Short Duration"),
        ("Short Term",            "Short Duration"),
        ("Medium Duration",       "Medium Duration"),
        ("Long Duration",         "Long Duration"),
        ("Dynamic Bond",          "Dynamic Bond"),
        ("Corporate Bond",        "Corporate Bond"),
        ("Credit Risk",           "Credit Risk"),
        ("Gilt",                  "Gilt"),
        ("Floating Rate",         "Floating Rate"),
        ("Money Market",          "Money Market"),
        ("Banking and PSU",       "Banking & PSU"),
        ("Banking & PSU",         "Banking & PSU"),
        ("Large & Mid Cap",       "Large & Mid Cap"),
        ("Large and Mid Cap",     "Large & Mid Cap"),
        ("Large Cap",             "Large Cap"),
        ("Mid Cap",               "Mid Cap"),
        ("Midcap",                "Mid Cap"),
        ("Small Cap",             "Small Cap"),
        ("Smallcap",              "Small Cap"),
        ("Multi Cap",             "Multi Cap"),
        ("Multicap",              "Multi Cap"),
        ("Flexi Cap",             "Flexi Cap"),
        ("Flexicap",              "Flexi Cap"),
        ("Focused",               "Focused"),
        ("Value",                 "Value / Contra"),
        ("Contra",                "Value / Contra"),
        ("Dividend Yield",        "Dividend Yield"),
        ("ELSS",                  "ELSS (Tax Saving)"),
        ("Tax Saver",             "ELSS (Tax Saving)"),
        ("Long Term Equity",      "ELSS (Tax Saving)"),
        ("Infrastructure",        "Sectoral / Thematic"),
        ("Technology",            "Sectoral / Thematic"),
        ("Pharma",                "Sectoral / Thematic"),
        ("Healthcare",            "Sectoral / Thematic"),
        ("Banking",               "Sectoral / Thematic"),
        ("Financial Services",    "Sectoral / Thematic"),
        ("Consumption",           "Sectoral / Thematic"),
        ("Energy",                "Sectoral / Thematic"),
        ("Manufacturing",         "Sectoral / Thematic"),
        ("Defence",               "Sectoral / Thematic"),
        ("ESG",                   "Sectoral / Thematic"),
        ("Sectoral",              "Sectoral / Thematic"),
        ("Thematic",              "Sectoral / Thematic"),
        ("PSU",                   "Sectoral / Thematic"),
        ("Nifty",                 "Index Fund"),
        ("Sensex",                "Index Fund"),
        ("Index",                 "Index Fund"),
        ("ETF",                   "ETF"),
        ("Exchange Traded",       "ETF"),
        ("Gold",                  "Gold / Commodities"),
        ("Silver",                "Gold / Commodities"),
        ("Commodity",             "Gold / Commodities"),
        ("International",         "International / FOF"),
        ("Overseas",              "International / FOF"),
        ("Global",                "International / FOF"),
        ("World",                 "International / FOF"),
        ("US ",                   "International / FOF"),
        ("Nasdaq",                "International / FOF"),
        ("NYSE",                  "International / FOF"),
        ("Fund of Fund",          "International / FOF"),
        ("Fund of Funds",         "International / FOF"),
        ("FOF",                   "International / FOF"),
        ("Feeder",                "International / FOF"),
        ("Balanced Advantage",    "Hybrid"),
        ("Dynamic Asset",         "Hybrid"),
        ("Equity Savings",        "Hybrid"),
        ("Arbitrage",             "Arbitrage"),
        ("Aggressive Hybrid",     "Hybrid"),
        ("Conservative Hybrid",   "Hybrid"),
        ("Hybrid",                "Hybrid"),
        ("Balanced",              "Hybrid"),
        ("Retirement",            "Retirement"),
        ("Children",              "Children"),
        ("Child",                 "Children"),
    ]

    def extract_category(name):
        n = name.upper()
        for keyword, cat in CATEGORY_KEYWORDS:
            if keyword.upper() in n:
                return cat
        return "Other"

    try:
        r = requests.get("https://api.mfapi.in/mf", timeout=15)
        r.raise_for_status()
        raw = r.json()

        funds = []
        for f in raw:
            name = f.get("schemeName", "").strip()
            name_upper = name.upper()

            # Only Direct + Growth, exclude IDCW/Dividend/Payout variants
            if "DIRECT" not in name_upper:
                continue
            if "GROWTH" not in name_upper:
                continue
            if any(x in name_upper for x in [
                "IDCW", "DIVIDEND", "BONUS", "PAYOUT",
                "REINVEST", "ANNUAL", "MONTHLY", "QUARTERLY", "WEEKLY"
            ]):
                continue

            funds.append({
                "code": f.get("schemeCode"),
                "name": name,
                "cat":  extract_category(name),
            })

        result = {"funds": funds, "total": len(funds)}
        mf_list._cache = {"ts": time.time(), "data": result}
        return jsonify(result)

    except Exception as e:
        # Return stale cache if available
        if cache:
            return jsonify(cache['data'])
        return jsonify({"error": str(e)}), 500

@app.route("/mf_search")
def mf_search():
    """Kept for backward compat — client now uses /mf_list directly."""
    return jsonify([])


@app.route("/mf_detail/<int:scheme_code>")
def mf_detail(scheme_code):
    """
    Fetch NAV history for a scheme. Returns latest NAV + 1Y/3Y/5Y returns.
    """
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10)
        r.raise_for_status()
        data = r.json()
        meta = data.get("meta", {})
        nav_data = data.get("data", [])  # [{date, nav}] newest first

        if not nav_data:
            return jsonify({"error": "No NAV data found"}), 404

        def nav_on_date(days_ago):
            from datetime import datetime, timedelta
            target = datetime.now() - timedelta(days=days_ago)
            for entry in reversed(nav_data):  # oldest first
                try:
                    d = datetime.strptime(entry["date"], "%d-%m-%Y")
                    if d >= target:
                        return float(entry["nav"])
                except:
                    pass
            return None

        latest_nav = float(nav_data[0]["nav"])
        latest_date = nav_data[0]["date"]

        def calc_return(days):
            old = nav_on_date(days)
            if old and old > 0:
                return round(((latest_nav - old) / old) * 100, 2)
            return None

        return jsonify({
            "schemeCode":   scheme_code,
            "schemeName":   meta.get("scheme_name", ""),
            "fundHouse":    meta.get("fund_house", ""),
            "schemeType":   meta.get("scheme_type", ""),
            "schemeCategory": meta.get("scheme_category", ""),
            "latestNAV":    latest_nav,
            "navDate":      latest_date,
            "return_1y":    calc_return(365),
            "return_3y":    calc_return(1095),
            "return_5y":    calc_return(1825),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def process_user_input(user_input):
    print(f"🔥 User Input: {user_input}")
    try:
        user_input_lower = user_input.lower()
        bot_response = None
        
        if any(word in user_input_lower for word in ['emi', 'loan', 'calculate loan']):
            bot_response = emi_bot.respond(user_input)
        elif any(word in user_input_lower for word in ['fd', 'fixed deposit', 'calculate fd']):
            bot_response = fd_calculator.respond(user_input)
        elif any(word in user_input_lower for word in ['sip', 'systematic investment']):
            try:
                bot_response = sip_bot.respond(user_input)
            except Exception as e:
                bot_response = f"❌ SIP error: {str(e)}"
        elif 'week' in user_input_lower and any(word in user_input_lower for word in ['stock', 'share', 'data']):
            bot_response = get_stock_weekly(user_input)
        elif 'today' in user_input_lower and any(word in user_input_lower for word in ['stock', 'share']):
            bot_response = get_stock_price(user_input)
        elif any(word in user_input_lower for word in ['price', 'rate', 'current price', 'stock price']):
            bot_response = get_stock_price(user_input)
        elif any(stock in user_input_lower for stock in STOCK_TICKERS.keys()):
            bot_response = get_stock_price(user_input)
        else:
            bot_response = """
🤖 <strong>Virtual Finance Assistant</strong><br><br>
I can help you with:<br><br>
💰 <strong>Calculators:</strong><br>
  • EMI - "Calculate EMI for 500000 at 8% for 5 years"<br>
  • FD - "Calculate FD for 100000 at 7% for 2 years"<br>
  • SIP - "Calculate SIP 5000 monthly for 10 years at 12%"<br><br>
📈 <strong>Stock Information:</strong><br>
  • Price - "price of INFY" or "TCS stock"<br>
  • Weekly - "weekly data of RELIANCE"<br>
  • Today - "today's HDFC data"<br><br>
<em>💡 Tip: Use the Quick Actions menu on the left for easy access!</em>
"""
        if not bot_response:
            bot_response = "❌ Sorry, I couldn't process that. Try: 'price of INFY' or 'Calculate EMI for 500000 at 8% for 5 years'"
        return bot_response
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        print(f"🚨 {error_msg}")
        traceback.print_exc()
        return error_msg

if __name__ == "__main__":
    app.run(debug=False)