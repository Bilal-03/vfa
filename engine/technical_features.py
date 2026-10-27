"""
engine/technical_features.py — Quantitative Financial Feature Engineering

Extracts institutional-grade technical indicators from daily OHLCV equity data:
1. Momentum: 14-period RSI, Stochastic Oscillator (%K, %D).
2. Trend: MACD (12, 26, 9), EMA spans (9, 21, 50), Price-to-EMA ratios.
3. Volatility: Bollinger Bands (%B, Bandwidth), Normalized ATR (Average True Range).
4. Volume: On-Balance Volume (OBV), Volume Surges (Volume / 20-day SMA).
5. Statistical: Log returns, rolling annualized historical volatility.

Implements strict lookahead-bias prevention with rolling normalization.
"""

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Computes Wilder's smoothed Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0))
    loss = (-delta.where(delta < 0, 0.0))

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Computes Moving Average Convergence Divergence (MACD, Signal, Histogram)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Computes Bollinger Bands, %B, and Bandwidth."""
    sma = series.rolling(window=window).mean()
    rstd = series.rolling(window=window).std()
    upper = sma + (num_std * rstd)
    lower = sma - (num_std * rstd)

    # %B: 0 at lower band, 0.5 at middle band, 1.0 at upper band
    pct_b = (series - lower) / (upper - lower + 1e-9)
    bandwidth = (upper - lower) / (sma + 1e-9)
    return upper, lower, pct_b.fillna(0.5), bandwidth.fillna(0.0)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Computes 14-period Average True Range normalized by close price."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    norm_atr = (atr / (close + 1e-9)) * 100.0  # percentage of price
    return norm_atr.fillna(0.0)


def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
    """Computes Fast %K and Slow %D Stochastic Oscillator."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k_fast = 100.0 * ((close - lowest_low) / (highest_high - lowest_low + 1e-9))
    d_slow = k_fast.rolling(window=d_period).mean()
    return k_fast.fillna(50.0), d_slow.fillna(50.0)


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Computes On-Balance Volume normalized as cumulative trend."""
    direction = np.sign(close.diff().fillna(0.0))
    signed_vol = direction * volume
    obv = signed_vol.cumsum()
    # Normalize with 20-day standard deviation
    obv_norm = (obv - obv.rolling(20).mean()) / (obv.rolling(20).std() + 1e-9)
    return obv_norm.fillna(0.0)


def extract_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ingests raw OHLCV dataframe and extracts 12 normalized quantitative features.
    Required columns: ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    data = df.copy()
    close = data['Close'].astype(float)
    high = data['High'].astype(float)
    low = data['Low'].astype(float)
    vol = data['Volume'].astype(float)

    feat = pd.DataFrame(index=data.index)

    # 1. Normalized Log Returns
    feat['return_1d'] = np.log(close / close.shift(1)).fillna(0.0)
    feat['return_5d'] = np.log(close / close.shift(5)).fillna(0.0)

    # 2. RSI (Scaled to [-1, +1] around 50)
    rsi = compute_rsi(close, 14)
    feat['rsi_norm'] = (rsi - 50.0) / 50.0

    # 3. MACD and Signal normalized by price
    macd_line, sig_line, hist = compute_macd(close, 12, 26, 9)
    feat['macd_norm'] = macd_line / (close + 1e-9) * 100.0
    feat['macd_hist_norm'] = hist / (close + 1e-9) * 100.0

    # 4. Moving Average Ratios (Price / EMA - 1.0)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    feat['ema9_ratio'] = (close - ema9) / (ema9 + 1e-9)
    feat['ema21_ratio'] = (close - ema21) / (ema21 + 1e-9)
    feat['ema50_ratio'] = (close - ema50) / (ema50 + 1e-9)

    # 5. Bollinger Bands (%B centered at 0 in [-1, +1])
    _, _, pct_b, bandwidth = compute_bollinger_bands(close, 20, 2.0)
    feat['bollinger_pct_b'] = (pct_b - 0.5) * 2.0
    feat['bollinger_bandwidth'] = bandwidth

    # 6. Normalized ATR (Volatility)
    feat['norm_atr'] = compute_atr(high, low, close, 14) / 5.0  # scaled roughly [0, 1]

    # 7. Stochastic Oscillator (%K centered at 0 in [-1, +1])
    stoch_k, stoch_d = compute_stochastic(high, low, close, 14, 3)
    feat['stoch_k_norm'] = (stoch_k - 50.0) / 50.0

    # 8. Volume Ratio (Current volume vs 20-day moving average)
    vol_sma20 = vol.rolling(20).mean() + 1.0
    feat['volume_surge'] = np.clip((vol / vol_sma20) - 1.0, -2.0, 5.0)

    # 9. Rolling Annualized Historical Volatility (20-day)
    rolling_std = feat['return_1d'].rolling(20).std() * np.sqrt(252)
    feat['hist_volatility'] = rolling_std.fillna(0.0)

    # Clean any inf or NaNs safely
    feat = feat.replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
    return feat


def compute_feature_matrix(df: pd.DataFrame, window_size: int = 20) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Constructs 3D rolling tensor array of shape (N_samples, window_size, n_features)
    for sequence learning (BiLSTM / Cross-Attention).
    """
    feat_df = extract_technical_features(df)
    features_arr = feat_df.values
    n_samples = len(features_arr) - window_size + 1

    if n_samples <= 0:
        return np.empty((0, window_size, features_arr.shape[1])), feat_df

    sequences = []
    for i in range(n_samples):
        seq = features_arr[i : i + window_size]
        sequences.append(seq)

    tensor_3d = np.array(sequences, dtype=np.float32)
    return tensor_3d, feat_df


def summarize_technical_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generates human-interpretable technical summary metrics and breakout signals
    for the latest trading session to support Explainable AI (XAI) outputs.
    """
    if len(df) < 25:
        return {
            "rsi": 50.0,
            "rsi_state": "Neutral",
            "macd_signal": "Neutral",
            "trend_regime": "Sideways",
            "volatility_regime": "Moderate",
            "signals": ["Insufficient historical price history for breakout detection"]
        }

    close = df['Close'].astype(float)
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    vol = df['Volume'].astype(float)

    rsi = float(compute_rsi(close, 14).iloc[-1])
    macd, sig, hist = compute_macd(close, 12, 26, 9)
    macd_val = float(macd.iloc[-1])
    sig_val = float(sig.iloc[-1])
    hist_val = float(hist.iloc[-1])
    hist_prev = float(hist.iloc[-2]) if len(hist) > 1 else 0.0

    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    curr_close = float(close.iloc[-1])

    signals = []

    # RSI Interpretation
    if rsi < 30.0:
        rsi_state = "Oversold"
        signals.append(f"RSI is oversold ({rsi:.1f}), signaling strong upside mean-reversion potential")
    elif rsi > 70.0:
        rsi_state = "Overbought"
        signals.append(f"RSI is overbought ({rsi:.1f}), cautioning against extended bullish exhaustion")
    else:
        rsi_state = "Balanced"
        signals.append(f"RSI is balanced ({rsi:.1f}) in healthy momentum equilibrium")

    # MACD Cross Check
    if hist_val > 0 and hist_prev <= 0:
        macd_signal = "Bullish Crossover"
        signals.append("MACD line crossed above the signal line (fresh bullish momentum impulse)")
    elif hist_val < 0 and hist_prev >= 0:
        macd_signal = "Bearish Crossover"
        signals.append("MACD line crossed below signal line (bearish continuation signal)")
    elif hist_val > 0:
        macd_signal = "Bullish Trend"
    else:
        macd_signal = "Bearish Trend"

    # Moving Average Trend Regime
    if curr_close > ema21 and ema21 > ema50:
        trend_regime = "Bullish Alignment (Price > EMA21 > EMA50)"
        signals.append("Golden short-term alignment: Price is cleanly positioned above EMA-21 and EMA-50")
    elif curr_close < ema21 and ema21 < ema50:
        trend_regime = "Bearish Alignment (Price < EMA21 < EMA50)"
        signals.append("Defensive trend: Price is trading beneath EMA-21 and EMA-50 moving averages")
    else:
        trend_regime = "Consolidation / Mixed"

    # Volume Surge
    vol_ratio = float(vol.iloc[-1] / (vol.rolling(20).mean().iloc[-1] + 1e-9))
    if vol_ratio > 1.75:
        signals.append(f"Institutional volume surge detected: current volume is {vol_ratio:.2f}x its 20-day average")

    return {
        "rsi": round(rsi, 2),
        "rsi_state": rsi_state,
        "macd": round(macd_val, 2),
        "macd_signal_line": round(sig_val, 2),
        "macd_signal": macd_signal,
        "curr_price": round(curr_close, 2),
        "ema21": round(ema21, 2),
        "ema50": round(ema50, 2),
        "trend_regime": trend_regime,
        "signals": signals[:3]
    }
