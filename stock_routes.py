"""
stock_routes.py — Flask Blueprint for Stock Intelligence Dashboard.
"""
from flask import Blueprint, request, jsonify
import stock_service as ss

stock_bp = Blueprint("stock_intel", __name__)

def _sym():
    s = (request.args.get("symbol") or request.form.get("symbol") or "").upper().strip().lstrip("$")
    return s or None

@stock_bp.route("/si/dashboard")
def si_dashboard():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    data = ss.get_full_dashboard(sym)
    # Only 502 if there's a hard failure AND no price at all
    if "error" in data and not data.get("quote", {}).get("current"):
        return jsonify({"error": data["error"]}), 502
    return jsonify(data), 200

@stock_bp.route("/si/quote")
def si_quote():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    data = ss.get_quote(sym)
    return jsonify(data), (200 if data.get("current") is not None else 502)

@stock_bp.route("/si/candle")
def si_candle():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    tf = request.args.get("timeframe", "3M").upper()
    if tf not in {"1D","1W","1M","3M","6M","1Y","5Y","MAX"}:
        return jsonify({"error": "Invalid timeframe"}), 400
    data = ss.get_candles(sym, tf)
    return jsonify(data), (200 if data.get("candles") else 502)

@stock_bp.route("/si/profile")
def si_profile():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    return jsonify(ss.get_profile(sym))

@stock_bp.route("/si/metrics")
def si_metrics():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    return jsonify(ss.get_metrics(sym))

@stock_bp.route("/si/analyst")
def si_analyst():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    return jsonify(ss.get_analyst(sym))

@stock_bp.route("/si/news")
def si_news():
    sym = _sym()
    if not sym: return jsonify({"error": "Missing symbol"}), 400
    return jsonify(ss.get_news(sym))

@stock_bp.route("/si/cache/stats")
def si_cache_stats(): return jsonify(ss.cache_stats())

@stock_bp.route("/si/cache/clear")
def si_cache_clear(): return jsonify({"status": "ok", **ss.clear_cache(_sym())})