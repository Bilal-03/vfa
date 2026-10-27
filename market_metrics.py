"""Observable daily-price fallbacks. No inferred fundamentals or analyst opinions."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd

CATALOG = {
    'TCS.NS': ('Tata Consultancy Services', 'NSE', 'INR'),
    'INFY.NS': ('Infosys', 'NSE', 'INR'),
    'SBIN.NS': ('State Bank of India', 'NSE', 'INR'),
    'AAPL': ('Apple', 'NASDAQ', 'USD'),
    'MSFT': ('Microsoft', 'NASDAQ', 'USD'),
    'NVDA': ('Nvidia', 'NASDAQ', 'USD'),
}


def calculate(frame, benchmark=None, now=None):
    """Use completed-session frames; never bridge missing daily returns."""
    now = pd.Timestamp(now or datetime.now(timezone.utc)).tz_localize(None).normalize()
    valid = frame.RawClose.dropna()
    if valid.empty:
        return {}, {}
    end = valid.index[-1]
    if (now-end).days > 7:
        return {}, {}
    result, quality = {}, {}
    def add(field, value, detail):
        if value is not None and np.isfinite(value):
            result[field] = float(value)
            quality[field] = {'source': 'Calculated from completed daily prices',
                'observation_date': str(end.date()), 'calculation': detail}
    volumes = frame.loc[:end, 'Volume'].tail(20)
    quality['avg_volume'] = {'source': 'Completed daily prices', 'observation_date': str(end.date()), 'reason': 'incomplete_volume_history'}
    if len(volumes) == 20 and volumes.notna().all() and np.isfinite(volumes).all():
        add('avg_volume', volumes.mean(), 'Mean volume across 20 consecutive completed exchange sessions')
    start = end-pd.Timedelta(weeks=52)
    year = frame.loc[frame.index > start].loc[:end]
    # Rebase OHLC for subsequent splits, retaining the current share-price basis.
    splits = frame.get('Stock Splits', pd.Series(0., index=frame.index)).fillna(0).replace(0, 1)
    factors = splits.iloc[::-1].cumprod().iloc[::-1] / splits
    complete = frame.index[0] <= start and not year.empty
    for column, field in [('High', 'week52_high'), ('Low', 'week52_low')]:
        if column not in year:
            continue
        series = pd.to_numeric(year[column], errors='coerce') / factors.reindex(year.index)
        if complete and series.notna().all() and np.isfinite(series).all() and (series > 0).all():
            add(field, series.max() if column == 'High' else series.min(), '52 calendar weeks of daily '+column.lower()+' prices, rebased for splits')
        else:
            quality[field] = {'source': 'Daily price history', 'observation_date': str(end.date()),
                              'reason': 'incomplete_52_week_coverage'}
    quality['beta'] = {'source': 'Completed daily prices', 'observation_date': str(end.date()), 'reason': 'benchmark_unavailable'}
    if benchmark is not None:
        sr = frame.Close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        br = benchmark.Close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        aligned = pd.concat([sr.rename('stock'), br.rename('market')], axis=1).loc[:end].dropna().tail(252)
        quality['beta']['reason'] = 'insufficient_aligned_history'
        if len(aligned) >= 120 and aligned.index[-1] == end:
            variance = aligned.market.var(ddof=1)
            quality['beta']['reason'] = 'zero_benchmark_variance'
            if np.isfinite(variance) and variance > 1e-12:
                beta = aligned.stock.cov(aligned.market) / variance
                add('beta', beta, f'Covariance / benchmark variance; {len(aligned)} aligned adjusted daily returns')
                quality['beta'].update(start_date=str(aligned.index[0].date()), return_count=len(aligned))
    return result, quality


def enrich(symbol, category, data):
    data = dict(data)
    sources = dict(data.get('_field_sources', {}))
    if category == 'profile' and symbol in CATALOG:
        for field, value in zip(('name', 'exchange', 'currency'), CATALOG[symbol]):
            if not data.get(field) or data[field] in {'N/A', symbol}:
                data[field] = value
                sources[field] = {'source': 'FinAssist reference catalog', 'observation_date': None}
    if category in {'quote', 'metrics'} and not data.get('error'):
        try:
            import insights_service as insights
            frame, meta = insights.history(symbol)
            reference = None
            benchmark = '^NSEI' if symbol.endswith(('.NS', '.BO')) else '^GSPC'
            if category == 'metrics' and data.get('beta') is None:
                try:
                    reference, _ = insights.history(benchmark)
                except ValueError:
                    pass
            computed, details = calculate(frame, reference)
            if 'beta' in details:
                details['beta']['benchmark'] = benchmark
            fields = ['avg_volume'] if category == 'quote' else ['week52_high', 'week52_low', 'beta']
            for field in fields:
                if field in computed and (category == 'quote' or data.get(field) is None):
                    data[field] = computed[field]
                    sources[field] = {**details[field], 'fetched_at': meta['fetched_at']}
                elif field in details and data.get(field) is None:
                    sources[field] = {**details[field], 'fetched_at': meta['fetched_at']}
        except (ValueError, KeyError, TypeError):
            pass
    data['_field_sources'] = sources
    return data


def daily_candles(symbol, timeframe, now=None):
    import insights_service
    frame, meta = insights_service.history(symbol)
    days = {'3M':92, '6M':183, '1Y':366}[timeframe]
    start = pd.Timestamp(now or datetime.now(timezone.utc)).tz_localize(None).normalize()-pd.Timedelta(days=days)
    candles=[]
    for ts,row in frame.loc[frame.index>=start].iterrows():
        raw,close=row.get('RawClose'),row.get('Close')
        if not raw or not np.isfinite(raw) or not np.isfinite(close):
            continue
        factor=close/raw
        prices=[row.get(k,np.nan)*factor for k in ('Open','High','Low')]+[close]
        if not all(np.isfinite(v) and v>0 for v in prices):
            continue
        volume=row.get('Volume')
        candles.append(dict(time=int(ts.tz_localize('UTC').timestamp()),open=round(prices[0],2),high=round(prices[1],2),low=round(prices[2],2),close=round(prices[3],2),volume=int(volume) if np.isfinite(volume) else 0))
    if not candles:
        raise ValueError('No completed daily candles')
    return dict(symbol=symbol,timeframe=timeframe,candles=candles,count=len(candles),
                _source=meta['source'],_observation_date=meta['observation_date'],
                _field_sources={'candles': {key:meta[key] for key in ('source','observation_date','fetched_at') if key in meta}})
