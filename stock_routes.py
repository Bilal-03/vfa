"""
stock_routes.py — Flask Blueprint for Stock Intelligence Dashboard.
Uses yfinance (stock_service.py). No API key required.

Add to app.py:
    from stock_routes import stock_bp
    app.register_blueprint(stock_bp)
"""
from flask import Blueprint, request, jsonify
import stock_service as ss

stock_bp = Blueprint("stock_intel", __name__)

def _sym():
    s=(request.args.get("symbol") or request.form.get("symbol") or "").upper().strip().lstrip("$")
    return s or None

@stock_bp.route("/si/dashboard")
def si_dashboard():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    data=ss.get_full_dashboard(sym)
    if "error" in data.get("quote",{}): return jsonify({"error":data["quote"]["error"]}),502
    return jsonify(data)

@stock_bp.route("/si/quote")
def si_quote():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    data=ss.get_quote(sym)
    return jsonify(data),(502 if "error" in data else 200)

@stock_bp.route("/si/candle")
def si_candle():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    tf=request.args.get("timeframe","3M").upper()
    if tf not in {"1D","1W","1M","3M","6M","1Y","5Y","MAX"}: return jsonify({"error":"Invalid timeframe"}),400
    data=ss.get_candles(sym,tf)
    return jsonify(data),(502 if "error" in data else 200)

@stock_bp.route("/si/profile")
def si_profile():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    return jsonify(ss.get_profile(sym))

@stock_bp.route("/si/metrics")
def si_metrics():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    return jsonify(ss.get_metrics(sym))

@stock_bp.route("/si/analyst")
def si_analyst():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    return jsonify(ss.get_analyst(sym))

@stock_bp.route("/si/news")
def si_news():
    sym=_sym()
    if not sym: return jsonify({"error":"Missing symbol"}),400
    return jsonify(ss.get_news(sym))

@stock_bp.route("/si/cache/stats")
def si_cache_stats(): return jsonify(ss.cache_stats())

@stock_bp.route("/si/cache/clear")
def si_cache_clear(): return jsonify({"status":"ok",**ss.clear_cache(_sym())})

# Read-only analytics. POST accepts holdings without persisting or logging them.
import insights_service as insights

@stock_bp.route('/si/insights/<kind>', methods=['GET', 'POST'])
def si_insight(kind):
    if kind not in {'movement', 'historical', 'portfolio-fit'}:
        return jsonify({'error': 'Unknown insight'}), 404
    if request.method == 'POST' and kind != 'portfolio-fit':
        return jsonify({'error': 'Use GET for this insight'}), 405
    try:
        payload = request.get_json(silent=True) if request.method == 'POST' else request.args
        if not isinstance(payload, dict) and request.method == 'POST':
            raise ValueError('A JSON object is required.')
        s = insights.symbol(payload.get('symbol'))
        investment = insights.amount(payload.get('amount', 10000))
        if kind == 'movement':
            data = insights.movement(s)
        elif kind == 'historical':
            months = int(payload.get('months', 3))
            if str(payload.get('months', 3)) != str(months) or months not in {1,3,6,12}:
                raise ValueError('Holding period must be 1, 3, 6 or 12 months.')
            data = insights.historical(s, investment, months)
        else:
            holdings = payload.get('holdings', [])
            if not isinstance(holdings, list) or len(holdings)>30:
                raise ValueError('Provide up to 30 holdings.')
            for h in holdings:
                if not isinstance(h, dict):
                    raise ValueError('Each holding must contain symbol and qty.')
                insights.symbol(h.get('symbol'))
                q = float(h.get('qty', 0))
                import math
                if not math.isfinite(q) or not 0 < q <= 1e12:
                    raise ValueError('Holding quantities must be positive and finite.')
            data = insights.portfolio_fit(s, holdings, investment)
        return jsonify(data)
    except (ValueError, TypeError, OverflowError):
        return jsonify({'status':'invalid_input', 'error':'Check the symbol, amount, holding period and holding quantities.'}), 400
