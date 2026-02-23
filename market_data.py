import requests
import traceback
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz

# ─── NSE Session helper ───────────────────────────────────────────────────────
def _nse_session():
    """Return a requests.Session pre-warmed with NSE cookies."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    s = requests.Session()
    s.headers.update(headers)
    try:
        s.get('https://www.nseindia.com', timeout=8)
    except Exception:
        pass
    return s


def _fetch_nse_all_indices(session=None):
    """
    Fetch https://www.nseindia.com/api/allIndices
    Returns list of index dicts as returned by NSE, or [] on failure.
    Each dict has keys: indexSymbol, last, variation, percentChange, ...
    """
    if session is None:
        session = _nse_session()
    try:
        r = session.get(
            'https://www.nseindia.com/api/allIndices',
            timeout=12
        )
        r.raise_for_status()
        data = r.json()
        return data.get('data', [])
    except Exception as e:
        print(f"  ⚠ NSE allIndices failed: {e}")
        return []


def _yahoo_index(ticker_symbol, display_name):
    """Fetch a single index from Yahoo Finance. Returns dict or None."""
    try:
        hist = yf.Ticker(ticker_symbol).history(period='5d')
        if hist.empty or len(hist) < 2:
            return None
        current    = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2])
        change     = current - prev_close
        pct        = (change / prev_close * 100) if prev_close else 0
        return {
            'name':   display_name,
            'value':  round(current, 2),
            'change': round(change, 2),
            'pct':    round(pct, 2),
        }
    except Exception as e:
        print(f"  ⚠ Yahoo {ticker_symbol} failed: {e}")
        return None


# ─── Public: market indices ───────────────────────────────────────────────────
def get_market_indices():
    """
    Returns {'indices': [...], 'market_open': bool}
    Priority: NSE allIndices API -> Yahoo Finance fallback.
    Indices shown: NIFTY 50, NIFTY BANK, NIFTY IT, NIFTY AUTO,
                   NIFTY MIDCAP 100, NIFTY SMALLCAP 250, SENSEX (via Yahoo)
    """
    print("📊 Fetching market indices …")

    # Desired NSE index names -> display names
    WANT_NSE = {
        'NIFTY 50':           'NIFTY 50',
        'NIFTY BANK':         'NIFTY BANK',
        'NIFTY IT':           'NIFTY IT',
        'NIFTY AUTO':         'NIFTY AUTO',
        'NIFTY MIDCAP 100':   'NIFTY MIDCAP 100',
        'NIFTY SMALLCAP 250': 'NIFTY SMALLCAP 250',
    }

    session = _nse_session()
    nse_data = _fetch_nse_all_indices(session)

    result = []
    found_names = set()

    # Build lookup: indexSymbol (upper) -> row
    nse_lookup = {}
    for row in nse_data:
        key = row.get('indexSymbol', row.get('index', '')).upper()
        if key:
            nse_lookup[key] = row

    for nse_name, display in WANT_NSE.items():
        row = nse_lookup.get(nse_name.upper())
        if row:
            try:
                current = float(row.get('last', 0))
                change  = float(row.get('variation', 0))
                pct     = float(row.get('percentChange', 0))
                if current > 0:
                    result.append({
                        'name':   display,
                        'value':  round(current, 2),
                        'change': round(change, 2),
                        'pct':    round(pct, 2),
                    })
                    found_names.add(nse_name)
                    print(f"  ✓ {display}: ₹{current:,.2f} ({pct:+.2f}%) [NSE]")
            except Exception as e:
                print(f"  ⚠ Parse error for {nse_name}: {e}")

    # Fallback to Yahoo for any NSE index not found
    YAHOO_FALLBACK = {
        'NIFTY 50':           '^NSEI',
        'NIFTY BANK':         '^NSEBANK',
        'NIFTY IT':           '^CNXIT',
        'NIFTY AUTO':         '^CNXAUTO',
        'NIFTY MIDCAP 100':   '^CNXMDCP100',
        'NIFTY SMALLCAP 250': 'NIFTY_SMALLCAP_250.NS',
    }
    for nse_name, display in WANT_NSE.items():
        if nse_name not in found_names:
            ticker = YAHOO_FALLBACK.get(nse_name)
            if ticker:
                item = _yahoo_index(ticker, display)
                if item:
                    result.append(item)
                    found_names.add(nse_name)
                    print(f"  ✓ {display}: ₹{item['value']:,.2f} ({item['pct']:+.2f}%) [Yahoo]")
                else:
                    print(f"  ✗ {display}: no data from Yahoo either")

    # SENSEX - always from Yahoo (BSE index, not on NSE allIndices)
    sensex = _yahoo_index('^BSESN', 'SENSEX')
    if sensex:
        result.append(sensex)
        print(f"  ✓ SENSEX: ₹{sensex['value']:,.2f} ({sensex['pct']:+.2f}%) [Yahoo/BSE]")
    else:
        print("  ✗ SENSEX: unavailable")

    market_open = _is_market_open()
    print(f"✅ Fetched {len(result)} indices | Market: {'OPEN' if market_open else 'CLOSED'}")
    return {'indices': result, 'market_open': market_open}


# ─── Public: gainers / losers / volume / turnover ────────────────────────────
def get_nifty_gainers():
    """Top 5 NIFTY 50 gainers using NSE API first, Yahoo fallback."""
    print("📊 Fetching NIFTY 50 gainers …")
    stocks = _get_all_nifty50_data()
    gainers = sorted(
        [s for s in stocks if s['pChange'] > 0],
        key=lambda x: x['pChange'],
        reverse=True
    )[:5]
    print(f"✅ Top gainers: {[s['symbol'] for s in gainers]}")
    return gainers


def get_nifty_losers():
    """Top 5 NIFTY 50 losers using NSE API first, Yahoo fallback."""
    print("📊 Fetching NIFTY 50 losers …")
    stocks = _get_all_nifty50_data()
    losers = sorted(
        [s for s in stocks if s['pChange'] < 0],
        key=lambda x: x['pChange']
    )[:5]
    print(f"✅ Top losers: {[s['symbol'] for s in losers]}")
    return losers


def get_nifty_volume():
    """Top 5 NIFTY 50 by volume."""
    print("📊 Fetching top volume …")
    stocks = _get_all_nifty50_data()
    top = sorted(
        [s for s in stocks if s.get('volume', 0) > 0],
        key=lambda x: x['volume'],
        reverse=True
    )[:5]
    return [{'symbol': s['symbol'], 'price': s['price'], 'volume': s['volume']} for s in top]


def get_nifty_turnover():
    """Top 5 NIFTY 50 by turnover (price x volume)."""
    print("📊 Fetching top turnover …")
    stocks = _get_all_nifty50_data()
    for s in stocks:
        s['turnover'] = s.get('price', 0) * s.get('volume', 0)
    top = sorted(
        [s for s in stocks if s['turnover'] > 0],
        key=lambda x: x['turnover'],
        reverse=True
    )[:5]
    return [{'symbol': s['symbol'], 'price': s['price'], 'turnover': round(s['turnover'], 2)} for s in top]


# ─── Internal helpers ─────────────────────────────────────────────────────────
def _get_all_nifty50_data():
    """
    Fetch per-stock data for NIFTY 50 constituents.
    Tries NSE equity-stockIndices API first, falls back to Yahoo.
    Returns list of dicts: {symbol, price, change, pChange, volume}
    """
    result = []

    # Try NSE equity-stockIndices endpoint
    try:
        session = _nse_session()
        url = 'https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050'
        r = session.get(url, timeout=15)
        r.raise_for_status()
        data = r.json().get('data', [])
        # data[0] is the index summary row; skip it
        for row in data[1:]:
            sym = row.get('symbol', '')
            if not sym:
                continue
            try:
                result.append({
                    'symbol':  sym,
                    'price':   round(float(row.get('lastPrice', 0)), 2),
                    'change':  round(float(row.get('change', 0)), 2),
                    'pChange': round(float(row.get('pChange', 0)), 2),
                    'volume':  int(float(row.get('totalTradedVolume', 0))),
                })
            except Exception:
                continue
        if result:
            print(f"  ✓ NSE API returned {len(result)} stocks")
            return result
    except Exception as e:
        print(f"  ⚠ NSE equity-stockIndices failed: {e}")

    # Yahoo fallback
    print("  ↩ Falling back to Yahoo Finance for stock data …")
    for symbol in _get_nifty50_symbols():
        try:
            hist = yf.Ticker(f"{symbol}.NS").history(period='5d')
            if hist.empty or len(hist) < 2:
                continue
            current    = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2])
            change     = current - prev_close
            pct        = (change / prev_close * 100) if prev_close else 0
            volume     = int(hist['Volume'].iloc[-1])
            result.append({
                'symbol':  symbol,
                'price':   round(current, 2),
                'change':  round(change, 2),
                'pChange': round(pct, 2),
                'volume':  volume,
            })
        except Exception:
            continue
    print(f"  ✓ Yahoo returned {len(result)} stocks")
    return result


def _is_market_open():
    """True if NSE is currently open (Mon-Fri 09:15-15:30 IST)."""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        if now.weekday() >= 5:
            return False
        return dt_time(9, 15) <= now.time() <= dt_time(15, 30)
    except Exception:
        return datetime.now().weekday() < 5


def _get_nifty50_symbols():
    return [
        'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
        'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'BAJFINANCE',
        'ASIANPAINT', 'MARUTI', 'KOTAKBANK', 'LT', 'AXISBANK',
        'TITAN', 'SUNPHARMA', 'ULTRACEMCO', 'NESTLEIND', 'WIPRO',
        'HCLTECH', 'TATAMOTORS', 'ONGC', 'NTPC', 'M&M',
        'POWERGRID', 'JSWSTEEL', 'BAJAJFINSV', 'ADANIENT', 'ADANIPORTS',
        'COALINDIA', 'TECHM', 'INDUSINDBK', 'TATASTEEL', 'GRASIM',
        'HINDALCO', 'CIPLA', 'DRREDDY', 'EICHERMOT', 'DIVISLAB',
        'BRITANNIA', 'BAJAJ-AUTO', 'APOLLOHOSP', 'SBILIFE', 'HEROMOTOCO',
        'BPCL', 'TATACONSUM', 'LTIM', 'SHREECEM', 'UPL'
    ]