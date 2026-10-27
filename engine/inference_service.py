"""Artifact-backed prediction. Missing evidence is an explicit unavailable state."""

import json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "research/artifacts"
SYMBOLS = {
    "TCS.NS": "India",
    "INFY.NS": "India",
    "SBIN.NS": "India",
    "AAPL": "US",
    "MSFT": "US",
    "NVDA": "US",
}


def _closed_history(symbol):
    import pandas as pd
    import yfinance as yf

    hist = yf.Ticker(symbol).history(period="6mo", auto_adjust=True)
    if len(hist):
        close = (
            hist.index[-1].normalize() + pd.Timedelta(hours=15, minutes=30)
            if symbol.endswith(".NS")
            else hist.index[-1].normalize() + pd.Timedelta(hours=16)
        )
        if pd.Timestamp.now(tz="UTC") < close.tz_convert("UTC"):
            hist = hist.iloc[:-1]
    return hist


def get_benchmark_results():
    runs = [json.loads(p.read_text()) for p in sorted(ART.glob("*_results.json"))]
    return {
        "status": "ready" if runs else "unavailable",
        "runs": runs,
        "protocol": "Chronological purged holdout; no trading return claims",
        "error": None if runs else "No verified experiments have completed.",
    }


def get_forecast_for_symbol(symbol):
    import numpy as np

    sym = symbol.upper().strip()
    sym = sym if sym in SYMBOLS else sym + ".NS"
    if sym not in SYMBOLS:
        return {
            "status": "out_of_scope",
            "symbol": sym,
            "error": "Symbol is outside the evaluated universe.",
        }
    market = SYMBOLS[sym]
    path = ART / f"{market}_gated_42.pt"
    if not path.exists():
        path = ART / f"{market}_technical_42.pt"
    if not path.exists():
        return {
            "status": "unavailable",
            "symbol": sym,
            "error": "No trained checkpoint available.",
        }
    try:
        import torch, yfinance as yf
        from .multimodal_model import ForecastModel
        from .technical_features import extract_technical_features
        from .sentiment_analyzer import FinancialSentimentEngine

        bundle = torch.load(path, map_location="cpu", weights_only=True)
        meta = bundle["metadata"]
        hist = _closed_history(sym)
        if len(hist) < 70:
            raise ValueError("Insufficient observed history")
        age_days = (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            - hist.index[-1].to_pydatetime()
        ).total_seconds() / 86400
        if age_days > 7:
            raise ValueError("Price history is stale (over seven calendar days)")
        f = extract_technical_features(hist)[meta["feature_order"]].values[-20:]
        x = torch.tensor(
            ((f - np.array(meta["mean"])) / np.array(meta["std"]))[None],
            dtype=torch.float32,
        )
        n = np.zeros(7, dtype=np.float32)
        items = []
        if meta["news_enabled"]:
            cutoff = hist.index[-1].date()
            try:
                for item in yf.Ticker(sym).news or []:
                    c = item.get("content", item)
                    title = c.get("title")
                    stamp = c.get("pubDate")
                    if not stamp:
                        continue
                    import pandas as pd

                    dt = pd.to_datetime(stamp, utc=True)
                    # Use only dated news available before the latest observed daily bar.
                    if title and dt.date() < cutoff and (cutoff - dt.date()).days <= 7:
                        items.append((title, float((cutoff - dt.date()).days * 24)))
                if items:
                    n = FinancialSentimentEngine(
                        str(ROOT / "research/sentiment_cache.json")
                    ).aggregate_sentiment(items[:2])
            except Exception:
                items = []
        model = ForecastModel(len(meta["feature_order"]), meta["mode"])
        model.load_state_dict(bundle["state_dict"])
        model.eval()
        with torch.no_grad():
            p = torch.softmax(model(x, torch.tensor(n[None])), 1)[0].numpy()
            removed = torch.softmax(model(x, torch.zeros((1, 7))), 1)[0].numpy()
        return {
            "status": "ready",
            "symbol": sym,
            "model_version": meta["version"],
            "model_mode": meta["mode"],
            "data_timestamp": hist.index[-1].isoformat(),
            "news_available": bool(items),
            "news_count": len(items[:2]),
            "forecast": {
                "prediction": ["Bearish", "Neutral", "Bullish"][int(p.argmax())],
                "probabilities": dict(
                    zip(["bearish", "neutral", "bullish"], map(float, p))
                ),
                "time_horizon": "3 trading sessions",
                "probability_note": "Uncalibrated model probabilities; not measured confidence",
            },
            "sensitivity": {
                "without_news_probability_change": dict(
                    zip(["bearish", "neutral", "bullish"], map(float, removed - p))
                ),
                "interpretation": "Input removal sensitivity, not causal attribution",
            },
        }
    except Exception as e:
        return {"status": "unavailable", "symbol": sym, "error": str(e)}


def simulate_forecast_whatif(symbol, simulated_polarity, headline_age_hours=2):
    # Scenarios must not masquerade as observed headlines or evidence.
    if not (-1 <= simulated_polarity <= 1) or not (0 <= headline_age_hours <= 168):
        return {
            "status": "invalid",
            "error": "Polarity must be in [-1,1], age in [0,168] hours.",
        }
    observed = get_forecast_for_symbol(symbol)
    if observed.get("status") != "ready":
        return {**observed, "simulation": True}
    if observed["model_mode"] != "gated":
        return {
            "status": "unavailable",
            "simulation": True,
            "error": "News simulation requires a trained gated model.",
        }
    try:
        import numpy as np
        import torch, yfinance as yf
        from .technical_features import extract_technical_features
        from .multimodal_model import ForecastModel

        sym = observed["symbol"]
        bundle = torch.load(
            ART / f"{SYMBOLS[sym]}_gated_42.pt", map_location="cpu", weights_only=True
        )
        meta = bundle["metadata"]
        hist = _closed_history(sym)
        f = extract_technical_features(hist)[meta["feature_order"]].values[-20:]
        x = torch.tensor(
            ((f - np.array(meta["mean"])) / np.array(meta["std"]))[None],
            dtype=torch.float32,
        )
        p = float(simulated_polarity)
        n = torch.tensor(
            [
                [
                    max(p, 0),
                    1 - abs(p),
                    max(-p, 0),
                    headline_age_hours / 168,
                    np.log(2),
                    0,
                    1,
                ]
            ],
            dtype=torch.float32,
        )
        model = ForecastModel(len(meta["feature_order"]), "gated")
        model.load_state_dict(bundle["state_dict"])
        model.eval()
        with torch.no_grad():
            probs = torch.softmax(model(x, n), 1)[0].tolist()
        return {
            "status": "ready",
            "simulation": True,
            "symbol": sym,
            "simulation_inputs": {"polarity": p, "age_hours": headline_age_hours},
            "forecast": {
                "prediction": ["Bearish", "Neutral", "Bullish"][int(np.argmax(probs))],
                "probabilities": dict(zip(["bearish", "neutral", "bullish"], probs)),
                "time_horizon": "3 trading sessions",
            },
            "interpretation": "Hypothetical sentiment probabilities through the trained model; not an observed headline or causal effect.",
        }
    except Exception as e:
        return {"status": "unavailable", "simulation": True, "error": str(e)}
