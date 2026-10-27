"""Deterministic Stock Insight calculations. Returns are fractions, not percentages."""
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

VERSION = 'stock-insights-1.0'
HORIZONS = {1: 21, 3: 63, 6: 126, 12: 252}
PARAMETERS = dict(regression_sessions=120, residual_sessions=60, alert_threshold=3.5,
                  volume_sessions=20, portfolio_min_returns=120, annual_sessions=252,
                  minimum_windows=30, horizons=HORIZONS)


def returns(frame):
    return frame['Close'].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)


def drawdown(prices):
    """Largest peak-to-trough decline; recovery to that peak, if observed."""
    p = pd.Series(prices).dropna()
    if p.empty:
        return None
    dd = p / p.cummax() - 1
    trough_pos = int(np.argmin(dd.to_numpy()))
    peak_pos = int(np.argmax(p.iloc[:trough_pos + 1].to_numpy()))
    recovery_positions = np.flatnonzero(p.iloc[trough_pos + 1:].to_numpy() >= p.iloc[peak_pos])
    recovery_pos = trough_pos + 1 + int(recovery_positions[0]) if len(recovery_positions) else None
    if float(dd.iloc[trough_pos]) == 0:
        recovery_pos = peak_pos = trough_pos = 0
    return dict(max_drawdown=float(dd.min()), peak_date=str(p.index[peak_pos])[:10],
                trough_date=str(p.index[trough_pos])[:10],
                recovery_date=str(p.index[recovery_pos])[:10] if recovery_pos is not None else None,
                sessions_peak_to_recovery=recovery_pos-peak_pos if recovery_pos is not None else None)


def historical(frame, amount, months):
    horizon = HORIZONS[months]
    p = frame['Close']
    # A window must contain every expected session; gaps never become zero returns.
    valid = p.notna().rolling(horizon + 1).sum() == horizon + 1
    outcomes = (p / p.shift(horizon) - 1).where(valid).dropna()
    base = dict(horizon_sessions=horizon, months=months, window_count=len(outcomes), amount=amount)
    if len(outcomes) < 30:
        return dict(base, status='insufficient_history', message='At least 30 complete historical windows are required.')
    quant = np.quantile(outcomes, [.1, .5, .9])
    counts, edges = np.histogram(outcomes, bins=min(16, max(5, int(np.sqrt(len(outcomes))))))
    return dict(base, status='ready', median_return=float(quant[1]), p10_return=float(quant[0]),
                p90_return=float(quant[2]), median_value=float(amount*(1+quant[1])),
                p10_value=float(amount*(1+quant[0])), p90_value=float(amount*(1+quant[2])),
                losing_fraction=float((outcomes < 0).mean()), worst_return=float(outcomes.min()),
                worst_value=float(amount*(1+outcomes.min())), drawdown=drawdown(p),
                distribution=[dict(low=float(edges[i]), high=float(edges[i+1]), count=int(n)) for i,n in enumerate(counts)],
                facts=['These overlapping historical windows are dependent observations, not future probabilities.',
                       'Adjusted prices account for splits and distributions; taxes, fees and inflation are excluded.'])


def robust_score(value, reference):
    reference = np.asarray(reference, dtype=float)
    median = float(np.median(reference))
    scale = float(1.4826 * np.median(np.abs(reference-median)))
    if scale < 1e-12:
        return None  # A constant reference cannot support a meaningful standardized score.
    return float((value-median)/scale)


def movement(frame, benchmark=None):
    sr = returns(frame)
    latest = frame.index[-1]
    current = sr.loc[latest]
    if not np.isfinite(current):
        return dict(status='insufficient_history', message='Latest session or preceding session price is missing.')
    past_vol = frame['Volume'].iloc[:-1].tail(20)
    median_vol = float(past_vol.median()) if len(past_vol.dropna()) == 20 else 0
    result = dict(status='partial', stock_return=float(current), benchmark_return=None,
                  abnormal_return=None, robust_score=None, unusual=None,
                  volume_multiple=float(frame['Volume'].iloc[-1]/median_vol)
                    if median_vol > 0 and np.isfinite(frame['Volume'].iloc[-1]) else None,
                  raw_robust_score=robust_score(current, sr.iloc[:-1].dropna().tail(60))
                    if len(sr.iloc[:-1].dropna()) >= 60 else None,
                  message='Market-adjusted assessment unavailable: benchmark or aligned history is insufficient.')
    if benchmark is None:
        return result
    aligned = pd.concat([sr.rename('stock'), returns(benchmark).rename('market')], axis=1).dropna()
    if len(aligned) < 181 or latest not in aligned.index or aligned.index[-1] != latest:
        return result
    # Each reference residual is itself an out-of-sample one-step residual.
    residuals = []
    for pos in range(len(aligned)-61, len(aligned)):
        prior = aligned.iloc[pos-120:pos]
        x = np.column_stack([np.ones(120), prior.market.to_numpy()])
        coef = np.linalg.lstsq(x, prior.stock.to_numpy(), rcond=None)[0]
        row = aligned.iloc[pos]
        residuals.append(float(row.stock - (coef[0]+coef[1]*row.market)))
    score = robust_score(residuals[-1], residuals[:-1])
    result.update(status='ready' if score is not None else 'partial',
                  benchmark_return=float(aligned.market.iloc[-1]), abnormal_return=residuals[-1],
                  robust_score=score, unusual=abs(score)>3.5 if score is not None else None,
                  regression_count=120, reference_count=60,
                  message=('Unusual market-adjusted movement.' if abs(score)>3.5 else 'Within the usual market-adjusted range.')
                    if score is not None else 'Residual variation is too small to standardize reliably.')
    return result


def portfolio(frames, quantities, sectors, candidate, amount):
    symbols = sorted(set(quantities) | {candidate})
    # Calculate individual one-session returns before aligning: never bridge a missing price.
    joined = pd.concat({s: returns(frames[s]) for s in symbols}, axis=1)
    valid = joined.dropna()
    if valid.empty:
        return dict(status='insufficient_history', message='No common daily returns are available.', aligned_returns=0)
    joined = joined.loc[:valid.index[-1]]
    gaps = np.flatnonzero(joined.isna().any(axis=1).to_numpy())
    aligned = joined.iloc[int(gaps[-1])+1:] if len(gaps) else joined
    # Compounded downside must never jump across unobserved portfolio sessions.
    if len(aligned) < 120:
        return dict(status='insufficient_history', message='At least 120 common daily returns are required.', aligned_returns=len(aligned))
    # All valuations are from the SAME latest common close, using unadjusted close when supplied.
    date = aligned.index[-1]
    values = np.array([quantities.get(s, 0)*float(frames[s].loc[date].get('RawClose', frames[s].loc[date, 'Close'])) for s in symbols])
    if not np.isfinite(values).all():
        return dict(status='unavailable', message='A holding has no valid unadjusted close for common-date valuation.')
    total = float(values.sum())
    if total <= 0:
        return dict(status='empty_portfolio', message='Add a holding to assess portfolio fit.')
    before = values / total
    after_values = values.copy()
    after_values[symbols.index(candidate)] += amount
    after = after_values / (total+amount)
    x = aligned.to_numpy()
    cov = LedoitWolf().fit(x).covariance_
    sample_cov = np.atleast_2d(np.cov(x, rowvar=False, ddof=1))
    def summary(weights):
        pr = x @ weights
        wealth = pd.Series(np.r_[1, np.cumprod(1+pr)], index=[aligned.index[0]-pd.Timedelta(days=1), *aligned.index])
        exposure = {}
        for s,w in zip(symbols, weights):
            sector = sectors.get(s) or 'Unknown'
            exposure[sector] = exposure.get(sector, 0)+float(w)
        return dict(weights=dict(zip(symbols, map(float, weights))), sector_exposure=exposure,
                    largest_stock_weight=float(weights.max()), concentration_hhi=float(weights@weights),
                    annualized_volatility=float(np.sqrt(max(0, weights@cov@weights)*252)),
                    sample_covariance_volatility=float(np.sqrt(max(0, weights@sample_cov@weights)*252)),
                    daily_return_p05=float(np.quantile(pr, .05)), historical_drawdown=drawdown(wealth))
    b,a = summary(before),summary(after)
    existing = x@before
    cr = x[:, symbols.index(candidate)]
    correlation = float(np.corrcoef(existing, cr)[0,1]) if np.std(existing)>1e-12 and np.std(cr)>1e-12 else None
    overlaps = []
    for i,s in enumerate(symbols):
        if before[i] <= 0:
            continue
        corr = float(np.corrcoef(x[:,i], cr)[0,1]) if np.std(x[:,i])>1e-12 and np.std(cr)>1e-12 else None
        overlaps.append(dict(symbol=s, weight=float(before[i]), correlation=corr,
                             weighted_overlap=float(before[i]*max(0,corr)) if corr is not None else None))
    overlaps.sort(key=lambda r: r['weighted_overlap'] if r['weighted_overlap'] is not None else -1, reverse=True)
    candidate_sector = sectors.get(candidate) or 'Unknown'
    sector_delta = a['sector_exposure'].get(candidate_sector,0)-b['sector_exposure'].get(candidate_sector,0)
    vol_delta = a['annualized_volatility']-b['annualized_volatility']
    def direction(v):
        return 'increases' if v>1e-8 else 'decreases' if v < -1e-8 else 'is unchanged'
    facts = [f"{candidate_sector} exposure {direction(sector_delta)} by {abs(sector_delta)*100:.2f} percentage points.",
             f"Estimated annualized historical volatility {direction(vol_delta)} by {abs(vol_delta)*100:.2f} percentage points.",
             'Hypothetical portfolio using current close-value weights, rebalanced daily to keep those weights fixed.',
             'Risk history uses the latest uninterrupted common return period; earlier gaps or listing dates can shorten it.']
    return dict(status='ready', before=b, after=a, amount=amount, portfolio_value=total,
                valuation_date=str(date)[:10], aligned_returns=len(aligned),
                aligned_start=str(aligned.index[0])[:10], aligned_end=str(date)[:10],
                candidate_correlation=correlation, largest_overlap=overlaps[0] if overlaps else None,
                overlaps=overlaps, facts=facts)
