from dotenv import load_dotenv
load_dotenv()

from modules.modules import Chatterbot, FDCalculatorBot, SipChatterbot
from flask import Flask, render_template, request, jsonify
import yfinance as yf
import requests
import re
import traceback
import os
from market_data import get_market_indices, get_nifty_gainers, get_nifty_losers, get_nifty_volume, get_nifty_turnover

import sqlite3
import json
import hashlib
import time as _time

# ─── Portfolio DB (SQLite, file-based, persists across restarts) ───────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), 'portfolio_store.db')

def _db():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    with _db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                username  TEXT COLLATE NOCASE,
                symbol    TEXT,
                qty       REAL,
                avg_price REAL,
                added_at  INTEGER,
                PRIMARY KEY (username, symbol),
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
_init_db()
app = Flask(__name__)
app.secret_key = os.environ.get("9e45618318df240f85c0e4941f81ba48c08130d8406a8788ee6d1a3d1e0c9a23", "fallback-dev-key")
# ─── Portfolio API Routes ──────────────────────────────────────────────────────
@app.route('/api/portfolio/identify', methods=['POST'])
def portfolio_identify():
    """Register or login a user by username only (no password)."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username or len(username) < 2 or len(username) > 30:
        return jsonify({'error': 'Username must be 2-30 characters'}), 400
    # Only allow alphanumeric + underscore + hyphen
    import re as _re
    if not _re.match(r'^[A-Za-z0-9_\-]+$', username):
        return jsonify({'error': 'Only letters, numbers, _ and - allowed'}), 400
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
        user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return jsonify({'ok': True, 'username': user['username'], 'created_at': user['created_at']})

@app.route('/api/portfolio/load')
def portfolio_load():
    """Load all holdings for a user."""
    username = (request.args.get('username') or '').strip()
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    with _db() as c:
        rows = c.execute(
            "SELECT symbol, qty, avg_price, added_at FROM portfolios WHERE username=? ORDER BY added_at",
            (username,)
        ).fetchall()
    holdings = [{'symbol': r['symbol'], 'qty': r['qty'], 'avg': r['avg_price'], 'addedAt': r['added_at']} for r in rows]
    return jsonify({'holdings': holdings})

@app.route('/api/portfolio/save', methods=['POST'])
def portfolio_save():
    """Upsert a holding for a user."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    symbol   = (data.get('symbol') or '').strip().upper()
    qty      = data.get('qty')
    avg      = data.get('avg')
    added_at = data.get('added_at') or int(_time.time() * 1000)
    if not username or not symbol or qty is None or avg is None:
        return jsonify({'error': 'Missing fields'}), 400
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
        c.execute("""
            INSERT INTO portfolios (username, symbol, qty, avg_price, added_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(username, symbol) DO UPDATE SET qty=excluded.qty, avg_price=excluded.avg_price
        """, (username, symbol, float(qty), float(avg), int(added_at)))
    return jsonify({'ok': True})

@app.route('/api/portfolio/delete', methods=['POST'])
def portfolio_delete():
    """Remove a holding for a user."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    symbol   = (data.get('symbol') or '').strip().upper()
    if not username or not symbol:
        return jsonify({'error': 'Missing fields'}), 400
    with _db() as c:
        c.execute("DELETE FROM portfolios WHERE username=? AND symbol=?", (username, symbol))
    return jsonify({'ok': True})

@app.route('/api/portfolio/sync', methods=['POST'])
def portfolio_sync():
    """Full sync — replace all holdings for user with the provided list."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    holdings = data.get('holdings', [])
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
        c.execute("DELETE FROM portfolios WHERE username=?", (username,))
        for h in holdings:
            sym = (h.get('symbol') or '').strip().upper()
            if not sym: continue
            c.execute("""
                INSERT OR REPLACE INTO portfolios (username, symbol, qty, avg_price, added_at)
                VALUES (?,?,?,?,?)
            """, (username, sym, float(h.get('qty',0)), float(h.get('avg',0)), int(h.get('addedAt', _time.time()*1000))))
    return jsonify({'ok': True})





from stock_routes import stock_bp
app.register_blueprint(stock_bp)

# Initialize bots
try:
    emi_bot = Chatterbot()
    fd_calculator = FDCalculatorBot()
    sip_bot = SipChatterbot()
    print("✅ All bots initialized successfully!")
except Exception as e:
    print(f"❌ Error initializing bots: {e}")
    traceback.print_exc()

STOCK_TICKERS = {
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
    "hcl": "HCLTECH.NS", "hcltech": "HCLTECH.NS",
    "wipro": "WIPRO.NS",
    "techm": "TECHM.NS", "techmahindra": "TECHM.NS",
    "ltim": "LTIM.NS", "mindtree": "LTIM.NS",
    "ofss": "OFSS.NS", "oracle": "OFSS.NS",
    "mphasis": "MPHASIS.NS",
    "persistent": "PERSISTENT.NS",
    "maruti": "MARUTI.NS",
    "tatamotors": "TATAMOTORS.NS",
    "mahindra": "M&M.NS", "m&m": "M&M.NS",
    "bajajauto": "BAJAJ-AUTO.NS",
    "eicher": "EICHERMOT.NS", "eichermot": "EICHERMOT.NS",
    "hero": "HEROMOTOCO.NS", "heromotoco": "HEROMOTOCO.NS",
    "tvs": "TVSMOTOR.NS", "tvsmotor": "TVSMOTOR.NS",
    "motherson": "MOTHERSON.NS",
    "bosch": "BOSCHLTD.NS",
    "mrf": "MRF.NS",
    "balkrishna": "BALKRISIND.NS",
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
    "nhpc": "NHPC.NS",
    "jswenergy": "JSWENERGY.NS",
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
    "ubl": "UBL.NS",
    "zomato": "ZOMATO.NS",
    "avenue": "DMART.NS", "dmart": "DMART.NS",
    "trent": "TRENT.NS",
    "havells": "HAVELLS.NS",
    "pidilite": "PIDILITIND.NS",
    "page": "PAGEIND.NS",
    "sunpharma": "SUNPHARMA.NS",
    "cipla": "CIPLA.NS",
    "drreddy": "DRREDDY.NS",
    "divis": "DIVISLAB.NS", "divislab": "DIVISLAB.NS",
    "apollo": "APOLLOHOSP.NS", "apollohosp": "APOLLOHOSP.NS",
    "torrent": "TORNTPHARM.NS",
    "mankind": "MANKIND.NS",
    "zydus": "ZYDUSLIFE.NS",
    "lupin": "LUPIN.NS",
    "max": "MAXHEALTH.NS", "maxhealth": "MAXHEALTH.NS",
    "aurobindo": "AUROPHARMA.NS",
    "tatasteel": "TATASTEEL.NS",
    "jswsteel": "JSWSTEEL.NS",
    "hindalco": "HINDALCO.NS",
    "vedanta": "VEDL.NS", "vedl": "VEDL.NS",
    "jindalsteel": "JINDALSTEL.NS",
    "nmdc": "NMDC.NS",
    "adani": "ADANIENT.NS", "adanient": "ADANIENT.NS",
    "adaniports": "ADANIPORTS.NS",
    "ultratech": "ULTRACEMCO.NS",
    "grasim": "GRASIM.NS",
    "ambuja": "AMBUJACEM.NS",
    "shree": "SHREECEM.NS",
    "acc": "ACC.NS",
    "siemens": "SIEMENS.NS",
    "abb": "ABB.NS",
    "hal": "HAL.NS",
    "bel": "BEL.NS",
    "dlf": "DLF.NS",
    "lodha": "LODHA.NS",
    "godrejprop": "GODREJPROP.NS",
    "irctc": "IRCTC.NS",
    "indigo": "INDIGO.NS",
    "naukri": "NAUKRI.NS",
    "polycab": "POLYCAB.NS",
    "supreme": "SUPREMEIND.NS",
    "srf": "SRF.NS",
    "piind": "PIIND.NS",
    "aapl": "AAPL", "apple": "AAPL",
    "msft": "MSFT", "microsoft": "MSFT",
    "googl": "GOOGL", "google": "GOOGL",
    "amzn": "AMZN", "amazon": "AMZN",
    "tsla": "TSLA", "tesla": "TSLA",
    "meta": "META",
    "nvda": "NVDA", "nvidia": "NVDA",
}

# US symbols that must never get .NS appended
_US_SYMBOLS = {
    'AAPL','MSFT','GOOGL','GOOG','AMZN','META','TSLA','NVDA','NFLX','AMD',
    'INTC','QCOM','AVGO','TXN','MU','AMAT','LRCX','KLAC','JPM','BAC','WFC',
    'GS','MS','C','BLK','V','MA','PYPL','SQ','JNJ','PFE','MRK','ABBV','LLY',
    'BMY','AMGN','GILD','UNH','XOM','CVX','COP','EOG','SLB','WMT','HD','COST',
    'TGT','LOW','DIS','CMCSA','T','VZ','TMUS','GM','F','BA','LMT','RTX','GE',
    'HON','MMM','UBER','LYFT','ABNB','BKNG','COIN','HOOD','SCHW','CRM','NOW',
    'WDAY','ADBE','ORCL','INTU','ACM','AECOM','MTZ','PWR','SPY','QQQ','IWM',
    'GLD','SLV','SPGI','MCO','ICE','CME','RACE','NIO','LI','XPEV','RIVN',
}

def resolve_ticker(query):
    q = query.lower().strip().lstrip('$')
    upper = query.upper().strip().lstrip('$')

    # 1. Direct match in known ticker map
    if q in STOCK_TICKERS:
        return STOCK_TICKERS[q]

    # 2. Already has exchange suffix — use as-is
    if '.' in upper:
        return upper

    # 3. Known US symbol — never append .NS
    if upper in _US_SYMBOLS:
        return upper

    # 4. Fuzzy match in known ticker map
    best_match_val = None
    best_match_len = 0
    for key, val in STOCK_TICKERS.items():
        if key in q and len(key) > best_match_len:
            best_match_len = len(key)
            best_match_val = val
    if best_match_val:
        return best_match_val
    for key, val in STOCK_TICKERS.items():
        if q in key:
            return val

    # 5. Unknown symbol — mark for smart resolution in get_stock_full
    return f"__UNKNOWN__{upper}" 

def _clean_ticker(ticker):
    return ticker.lstrip('$').strip()

def get_stock_full(symbol_or_query):
    ticker_symbol = resolve_ticker(symbol_or_query)
    if not ticker_symbol:
        return {"error": f"Stock '{symbol_or_query}' not found. Try: INFY, TCS, RELIANCE, AAPL, MSFT etc."}

    # Unknown symbol: try as US stock first, then fall back to Indian .NS
    if isinstance(ticker_symbol, str) and ticker_symbol.startswith("__UNKNOWN__"):
        raw = ticker_symbol.replace("__UNKNOWN__", "")
        try:
            test = yf.Ticker(raw).history(period='2d')
            if not test.empty and len(test) > 0 and float(test['Close'].iloc[-1]) > 0:
                ticker_symbol = raw  # Valid US or global stock
            else:
                ticker_symbol = raw + '.NS'
        except Exception:
            ticker_symbol = raw + '.NS'

    ticker_symbol = _clean_ticker(ticker_symbol)
    symbol = ticker_symbol.replace('.NS', '').replace('.BO', '')
    result = {"symbol": symbol, "ticker": ticker_symbol}
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
    except Exception:
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
    try:
        user_input = request.form.get("msg", "").strip()
        if not user_input:
            return "Please type a message.", 200
        result = process_user_input(user_input)
        return result, 200
    except Exception as e:
        traceback.print_exc()
        return f"❌ Server error: {str(e)}", 200

@app.route("/market")
def market():
    return jsonify(get_market_indices())

@app.route("/top_gainers")
def top_gainers():
    return jsonify(get_nifty_gainers())

@app.route("/top_losers")
def top_losers():
    return jsonify(get_nifty_losers())

@app.route("/top_volume")
def top_volume():
    return jsonify(get_nifty_volume())

@app.route("/top_turnover")
def top_turnover():
    return jsonify(get_nifty_turnover())

@app.route("/currency")
def currency():
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=INR&to=USD,EUR,GBP,AED,SGD,JPY,CAD,AUD,CHF,CNY", timeout=8)
        r.raise_for_status()
        data = r.json()
        rates_from_inr = data.get("rates", {})
        currencies = {
            "USD": {"name": "US Dollar",       "symbol": "$",   "flag": "🇺🇸"},
            "EUR": {"name": "Euro",             "symbol": "€",   "flag": "🇪🇺"},
            "GBP": {"name": "British Pound",    "symbol": "£",   "flag": "🇬🇧"},
            "AED": {"name": "UAE Dirham",       "symbol": "د.إ", "flag": "🇦🇪"},
            "SGD": {"name": "Singapore Dollar", "symbol": "S$",  "flag": "🇸🇬"},
            "JPY": {"name": "Japanese Yen",     "symbol": "¥",   "flag": "🇯🇵"},
            "CAD": {"name": "Canadian Dollar",  "symbol": "C$",  "flag": "🇨🇦"},
            "AUD": {"name": "Australian Dollar","symbol": "A$",  "flag": "🇦🇺"},
            "CHF": {"name": "Swiss Franc",      "symbol": "Fr",  "flag": "🇨🇭"},
            "CNY": {"name": "Chinese Yuan",     "symbol": "¥",   "flag": "🇨🇳"},
        }
        result = []
        for code, meta in currencies.items():
            rate = rates_from_inr.get(code)
            if not rate:
                continue
            result.append({
                "code": code, "name": meta["name"], "symbol": meta["symbol"],
                "flag": meta["flag"], "inr_per_unit": round(1/rate, 4),
                "unit_per_inr": round(rate, 6),
            })
        return jsonify({"rates": result, "base": "INR", "date": data.get("date",""), "source": "ECB via Frankfurter"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/metals")
def metals():
    try:
        usd_inr = 84.0
        try:
            fx = requests.get("https://api.frankfurter.app/latest?from=USD&to=INR", timeout=6)
            usd_inr = fx.json()["rates"]["INR"]
        except Exception:
            pass
        TROY_OZ_TO_GRAM = 31.1035
        def fetch_metal(ticker_sym, name, unit_label, unit_factor):
            t = yf.Ticker(ticker_sym)
            hist = t.history(period="5d")
            if hist.empty:
                return None
            price_usd_oz  = float(hist["Close"].iloc[-1])
            prev_usd_oz   = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price_usd_oz
            price_inr_unit = (price_usd_oz / TROY_OZ_TO_GRAM) * usd_inr * unit_factor
            prev_inr_unit  = (prev_usd_oz / TROY_OZ_TO_GRAM) * usd_inr * unit_factor
            change = price_inr_unit - prev_inr_unit
            return {
                "name": name, "price_inr": round(price_inr_unit, 2),
                "prev_inr": round(prev_inr_unit, 2), "change": round(change, 2),
                "change_pct": round((change/prev_inr_unit*100) if prev_inr_unit else 0, 4),
                "price_usd_oz": round(price_usd_oz, 2), "unit": unit_label,
            }
        return jsonify({
            "gold": fetch_metal("GC=F", "Gold", "per 10g", 10),
            "silver": fetch_metal("SI=F", "Silver", "per kg", 1000),
            "usd_inr": round(usd_inr, 4), "source": "MCX Futures via Yahoo Finance"
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
    FEEDS = [
        ("https://economictimes.indiatimes.com/markets/stocks/rss.cms", "Economic Times", "#f97316"),
        ("https://economictimes.indiatimes.com/markets/rss.cms", "Economic Times", "#f97316"),
        ("https://www.moneycontrol.com/rss/MCtopnews.xml", "MoneyControl", "#ef4444"),
        ("https://www.moneycontrol.com/rss/marketreports.xml", "MoneyControl", "#ef4444"),
        ("https://www.moneycontrol.com/rss/latestnews.xml", "MoneyControl", "#ef4444"),
        ("https://www.livemint.com/rss/markets", "Mint", "#0ea5e9"),
        ("https://www.business-standard.com/rss/markets-106.rss", "Business Standard", "#8b5cf6"),
        ("https://www.financialexpress.com/market/feed/", "Financial Express", "#10b981"),
        ("https://feeds.feedburner.com/ndtvprofit-latest", "NDTV Profit", "#f59e0b"),
        ("https://feeds.reuters.com/reuters/INbusinessNews", "Reuters", "#dc2626"),
    ]
    REJECT = ["ramadan","eid","bollywood","cricket","ipl","movie","weather","horoscope","celebrity","fashion","covid","vaccine","election"]
    FINANCE = ["stock","share","market","nifty","sensex","bse","nse","rupee","rbi","sebi","ipo","fund","equity","invest","earning","profit","revenue","quarter","budget","economy","gdp","inflation","rate","bank","crore","lakh","billion","dividend","gold","silver","crude","forex"]
    hdrs = {"User-Agent": "Mozilla/5.0", "Accept": "application/xml"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    seen, all_articles = set(), []
    def fetch_feed(url, src, color):
        res = []
        try:
            r = requests.get(url, headers=hdrs, timeout=7)
            if r.status_code != 200: return res
            root = ET.fromstring(r.content)
            ch = root.find("channel")
            items = ch.findall("item") if ch is not None else root.findall("item")
            for item in items:
                title = html_lib.unescape(item.findtext("title","")).strip()
                if not title: continue
                tl = title.lower()
                if any(k in tl for k in REJECT): continue
                if not any(k in tl for k in FINANCE): continue
                pub_str = item.findtext("pubDate","")
                pub_dt = None
                try:
                    pub_dt = parsedate_to_datetime(pub_str)
                    if pub_dt < cutoff: continue
                except Exception: pass
                link = item.findtext("link","#").strip()
                if not link.startswith("http"):
                    guid = item.findtext("guid","").strip()
                    if guid.startswith("http"): link = guid
                res.append({"title": title, "source": src, "color": color, "link": link, "published": pub_str, "pub_dt": pub_dt})
        except Exception: pass
        return res
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed({ex.submit(fetch_feed, u, n, c): None for u,n,c in FEEDS}, timeout=12):
            try: all_articles.extend(f.result())
            except Exception: pass
    unique = []
    for a in all_articles:
        k = a["title"].lower()[:60]
        if k not in seen:
            seen.add(k); unique.append(a)
    unique.sort(key=lambda x: x["pub_dt"] if x["pub_dt"] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for a in unique: a.pop("pub_dt", None)
    return jsonify(unique[:50])

@app.route("/mf_list")
def mf_list():
    import time
    cache = getattr(mf_list, '_cache', None)
    if cache and (time.time() - cache['ts']) < 21600:
        return jsonify(cache['data'])
    CATS = [
        ("Liquid","Liquid"),("Overnight","Overnight"),("Ultra Short","Ultra Short Duration"),
        ("Low Duration","Low Duration"),("Short Duration","Short Duration"),("Short Term","Short Duration"),
        ("Medium Duration","Medium Duration"),("Long Duration","Long Duration"),("Dynamic Bond","Dynamic Bond"),
        ("Corporate Bond","Corporate Bond"),("Credit Risk","Credit Risk"),("Gilt","Gilt"),
        ("Floating Rate","Floating Rate"),("Money Market","Money Market"),("Banking and PSU","Banking & PSU"),
        ("Banking & PSU","Banking & PSU"),("Large & Mid Cap","Large & Mid Cap"),("Large and Mid Cap","Large & Mid Cap"),
        ("Large Cap","Large Cap"),("Mid Cap","Mid Cap"),("Midcap","Mid Cap"),("Small Cap","Small Cap"),
        ("Smallcap","Small Cap"),("Multi Cap","Multi Cap"),("Flexi Cap","Flexi Cap"),("Focused","Focused"),
        ("Value","Value / Contra"),("Contra","Value / Contra"),("Dividend Yield","Dividend Yield"),
        ("ELSS","ELSS (Tax Saving)"),("Tax Saver","ELSS (Tax Saving)"),("Infrastructure","Sectoral / Thematic"),
        ("Technology","Sectoral / Thematic"),("Pharma","Sectoral / Thematic"),("Banking","Sectoral / Thematic"),
        ("Nifty","Index Fund"),("Sensex","Index Fund"),("Index","Index Fund"),("ETF","ETF"),
        ("Gold","Gold / Commodities"),("International","International / FOF"),("Overseas","International / FOF"),
        ("Nasdaq","International / FOF"),("Fund of Fund","International / FOF"),("FOF","International / FOF"),
        ("Feeder","International / FOF"),("Balanced Advantage","Hybrid"),("Aggressive Hybrid","Hybrid"),
        ("Conservative Hybrid","Hybrid"),("Hybrid","Hybrid"),("Balanced","Hybrid"),("Arbitrage","Arbitrage"),
        ("Retirement","Retirement"),("Children","Children"),
    ]
    def cat(name):
        n = name.upper()
        for kw, c in CATS:
            if kw.upper() in n: return c
        return "Other"
    try:
        r = requests.get("https://api.mfapi.in/mf", timeout=15)
        r.raise_for_status()
        funds = []
        for f in r.json():
            name = f.get("schemeName","").strip()
            nu = name.upper()
            if "DIRECT" not in nu or "GROWTH" not in nu: continue
            if any(x in nu for x in ["IDCW","DIVIDEND","BONUS","PAYOUT","REINVEST","ANNUAL","MONTHLY","QUARTERLY","WEEKLY"]): continue
            funds.append({"code": f.get("schemeCode"), "name": name, "cat": cat(name)})
        result = {"funds": funds, "total": len(funds)}
        mf_list._cache = {"ts": time.time(), "data": result}
        return jsonify(result)
    except Exception as e:
        if cache: return jsonify(cache['data'])
        return jsonify({"error": str(e)}), 500

@app.route("/mf_search")
def mf_search():
    return jsonify([])

@app.route("/mf_detail/<int:scheme_code>")
def mf_detail(scheme_code):
    try:
        r = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10)
        r.raise_for_status()
        data = r.json()
        meta = data.get("meta", {})
        nav_data = data.get("data", [])
        if not nav_data:
            return jsonify({"error": "No NAV data found"}), 404
        def nav_on_date(days_ago):
            from datetime import datetime, timedelta
            target = datetime.now() - timedelta(days=days_ago)
            for entry in reversed(nav_data):
                try:
                    if datetime.strptime(entry["date"], "%d-%m-%Y") >= target:
                        return float(entry["nav"])
                except: pass
            return None
        latest_nav = float(nav_data[0]["nav"])
        def calc_return(days):
            old = nav_on_date(days)
            return round(((latest_nav - old) / old) * 100, 2) if old and old > 0 else None
        return jsonify({
            "schemeCode": scheme_code, "schemeName": meta.get("scheme_name",""),
            "fundHouse": meta.get("fund_house",""), "schemeType": meta.get("scheme_type",""),
            "schemeCategory": meta.get("scheme_category",""), "latestNAV": latest_nav,
            "navDate": nav_data[0]["date"], "return_1y": calc_return(365),
            "return_3y": calc_return(1095), "return_5y": calc_return(1825),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Groq AI Integration ───────────────────────────────────────────────────────
import re as _re
from groq import Groq as GroqClient

_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_groq_client = None

GROQ_SYSTEM_PROMPT = (
    "You are FinAssist, a smart Virtual Finance Assistant for Indian AND US markets. "
    "You specialise in NSE/BSE Indian stocks, US stocks (NYSE/NASDAQ), personal finance, "
    "mutual funds, banking, taxes, SIP, EMI, FD, and general economics. "
    "CRITICAL FORMATTING: Use <br> for line breaks, <strong> for bold, bullet points with •. "
    "NEVER use markdown (no **, ##, backticks). Use emojis for section headings. Be concise."
)


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        if not _GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set in .env file.")
        _groq_client = GroqClient(api_key=_GROQ_API_KEY)
    return _groq_client


def _md_to_html(text):
    text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = _re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    text = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = _re.sub(r'#{1,3}\s*(.+)', r'<strong>\1</strong>', text)
    text = text.replace('\n', '<br>')
    text = text.replace('`', '')
    return text.strip()


def _ask_groq(prompt):
    try:
        client = _get_groq_client()
        chat = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        return _md_to_html(chat.choices[0].message.content.strip())
    except Exception as e:
        err = str(e)
        print(f"⚠️ Groq error: {err}")
        if "429" in err or "rate_limit" in err.lower():
            return "⚠️ <strong>Groq rate limit reached.</strong><br>Please wait a moment and try again."
        if "401" in err or "invalid_api_key" in err.lower() or "GROQ_API_KEY not set" in err:
            return "❌ <strong>Invalid or missing Groq API key.</strong><br>Check your <code>.env</code> file."
        return f"❌ AI error: {err}"


def _stock_context_for_ai(query):
    try:
        d = get_stock_full(query)
        if 'error' not in d and d.get('current'):
            s = d.get('symbol', '')
            ticker = d.get('ticker', s)
            is_us = not ticker.endswith('.NS') and not ticker.endswith('.BO')
            cur = '$' if is_us else 'Rs.'
            ctx = (
                "[Live data for " + s + " (" + ('US' if is_us else 'NSE India') + ")] "
                "Price: " + cur + str(round(d.get('current',0),2)) + ", "
                "Change: " + str(round(d.get('change',0),2)) + " (" + str(round(d.get('change_pct',0),2)) + "%), "
                "Open: " + cur + str(round(d.get('open',0),2)) + ", "
                "High: " + cur + str(round(d.get('day_high',0),2)) + ", "
                "Low: " + cur + str(round(d.get('day_low',0),2)) + ", "
                "Prev Close: " + cur + str(round(d.get('prev_close',0),2))
            )
            if d.get('week_close'):
                ctx += (
                    ", Week High: " + cur + str(round(d.get('week_high',0),2)) +
                    ", Week Low: " + cur + str(round(d.get('week_low',0),2)) +
                    ", Week Change: " + str(round(d.get('week_pct',0),2)) + "%"
                )
            return ctx
    except Exception:
        pass
    return ""


def process_user_input(user_input):
    print(f"🔥 User Input: {user_input}")
    try:
        u = user_input.lower().strip()
        stock_ctx = ""
        has_stock_keyword = (
            any(w in u for w in ['price', 'stock', 'share', 'weekly', 'week',
                                  'today', 'current price', 'nse', 'bse', 'nasdaq', 'nyse'])
            or any(s in u for s in STOCK_TICKERS)
        )
        if has_stock_keyword:
            stock_ctx = _stock_context_for_ai(user_input)

        if stock_ctx:
            prompt = (
                "LIVE MARKET DATA (fetched right now): " + stock_ctx + "\n\n"
                "User question: " + user_input + "\n"
                "Present data in a clear structured format. Use $ for US stocks, Rs. for Indian stocks."
            )
        else:
            prompt = user_input

        return _ask_groq(prompt)
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        print(f"🚨 {error_msg}")
        traceback.print_exc()
        return error_msg

if __name__ == "__main__":
    app.run(debug=False)