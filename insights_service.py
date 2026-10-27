"""Bounded provider access, completed exchange sessions and shared insight metadata."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
import re
import threading
import time

import numpy as np
import pandas as pd
import pandas_market_calendars as calendars
import yfinance as yf
import stock_service as stocks
import stock_insights as calc

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='stock-insights')
_cache = {}
_lock = threading.Lock()
_pending = {}


def symbol(value):
    s = str(value or '').strip().upper().lstrip('$')
    s = {'BRK.B': 'BRK-B', 'BRK.A': 'BRK-A'}.get(s, s)
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&.-]{0,19}', s):
        raise ValueError('A valid resolved stock symbol is required.')
    if '.' in s and not s.endswith(('.NS', '.BO')):
        raise ValueError('Insights currently support Indian (.NS/.BO) and US stock symbols.')
    return s


def currency(s):
    return 'INR' if s.endswith(('.NS', '.BO')) or s=='^NSEI' else 'USD'


def amount(value):
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValueError('Enter a finite investment amount between 0 and 1 billion.')
    if not np.isfinite(n) or n < 0 or n > 1e9:
        raise ValueError('Enter a finite investment amount between 0 and 1 billion.')
    return n


@lru_cache(maxsize=64)
def schedule(market, start, end):
    return calendars.get_calendar(market).schedule(start, end)


def completed_sessions(s, now=None, start=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    if now.tzinfo is None:
        now = now.tz_localize('UTC')
    market = ('BSE' if s.endswith('.BO') else 'NSE') if currency(s)=='INR' else 'NYSE'
    start = start or str((now-pd.DateOffset(years=5)).date())
    sch = schedule(market, start, str(now.date()))
    # Give the provider 15 minutes after close to finalize a daily bar.
    return sch.index[sch.market_close + pd.Timedelta(minutes=15) <= now]


def clean_history(raw, sessions):
    if raw is None or raw.empty or 'Adj Close' not in raw or 'Close' not in raw:
        raise ValueError('Adjusted daily price history is unavailable.')
    frame = raw.copy()
    frame.index = pd.DatetimeIndex([pd.Timestamp(x).date() for x in frame.index])
    frame = frame.loc[frame.index.isin(sessions)]
    duplicates = int(frame.index.duplicated(keep='last').sum())
    frame = frame[~frame.index.duplicated(keep='last')].sort_index()
    invalid = ~np.isfinite(pd.to_numeric(frame['Adj Close'], errors='coerce')) | (pd.to_numeric(frame['Adj Close'], errors='coerce') <= 0)
    invalid_raw = ~np.isfinite(pd.to_numeric(frame['Close'], errors='coerce')) | (pd.to_numeric(frame['Close'], errors='coerce') <= 0)
    frame['RawClose'] = pd.to_numeric(frame['Close'], errors='coerce').mask(invalid_raw)
    frame['Close'] = pd.to_numeric(frame['Adj Close'], errors='coerce').mask(invalid)
    volume = pd.to_numeric(frame.get('Volume', pd.Series(np.nan, index=frame.index)), errors='coerce')
    frame['Volume'] = volume.where(np.isfinite(volume) & (volume >= 0))
    # Only padded AFTER listing starts. Missing scheduled bars remain NaN.
    valid = frame.Close.dropna()
    if valid.empty:
        raise ValueError('No valid adjusted prices.')
    sessions = sessions[sessions >= valid.index.min()]
    frame = frame.reindex(sessions)
    if frame.Close.dropna().empty:
        raise ValueError('No completed-session prices are available.')
    splits = frame.get('Stock Splits', pd.Series(0, index=frame.index)).fillna(0)
    warnings = []
    if duplicates:
        warnings.append(f'{duplicates} duplicate date(s) removed; last provider record retained.')
    if invalid.sum() or invalid_raw.sum():
        warnings.append('Invalid prices were marked missing; no interpolation or backward filling was used.')
    missing = int(frame.Close.isna().sum())
    if missing:
        warnings.append(f'{missing} scheduled session(s) have missing prices; affected return windows are excluded.')
    extreme = int((calc.returns(frame).abs()>.5).sum())
    if extreme:
        warnings.append(f'{extreme} adjusted daily move(s) exceed 50%; provider adjustment quality requires caution.')
    return frame, dict(duplicates_removed=duplicates, missing_sessions=missing, split_events=int((splits!=0).sum()), warnings=warnings)


def _download_uncached(s):
    fetched = datetime.now(timezone.utc)
    replay = os.environ.get('STOCK_INSIGHTS_AS_OF','').strip()
    now = pd.Timestamp(replay) if replay else pd.Timestamp(fetched)
    if now.tzinfo is None:
        now = now.tz_localize('UTC')
    if now > pd.Timestamp(fetched):
        raise ValueError('Historical demonstration date must not be in the future.')
    sessions = completed_sessions(s, now)
    if len(sessions)==0:
        raise ValueError('Exchange calendar has no completed sessions.')
    snapshot_dir = os.environ.get('STOCK_INSIGHTS_SNAPSHOT_DIR','').strip()
    snapshot_sha = None
    if snapshot_dir:
        if not replay:
            raise ValueError('Recorded snapshots require an explicit historical-demo cutoff.')
        from pathlib import Path
        import hashlib
        path = Path(snapshot_dir)/(s.replace('^','INDEX_')+'.csv')
        raw = pd.read_csv(path, index_col=0, parse_dates=True)
        raw['Adj Close'] = raw['Close']
        raw['Close'] = raw['RawClose']
        snapshot_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        raw = yf.Ticker(s).history(start=str(sessions[0].date()),
                                  end=str((pd.Timestamp(now)+pd.Timedelta(days=1)).date()),
                                  interval='1d', auto_adjust=False, actions=True, timeout=8)
    frame, quality = clean_history(raw, sessions)
    last = frame.Close.last_valid_index()
    valid = frame.Close.dropna()
    meta = dict(source='Recorded Yahoo Finance price snapshot' if snapshot_dir else 'Yahoo Finance via yfinance',
                snapshot_sha256=snapshot_sha, price_basis='adjusted daily close',
                fetched_at=fetched.isoformat(), analysis_mode='historical_demo' if replay else 'live',
                analysis_as_of=now.isoformat(), expected_session=str(sessions[-1].date()),
                observation_date=str(last.date()), stale=last < sessions[-1],
                coverage=dict(start=str(valid.index[0].date()), end=str(last.date()),
                              valid_prices=len(valid), **quality))
    with _lock:
        _cache[s] = (time.monotonic(), frame, meta)
    return frame, meta


def _download(s):
    import market_cache
    if not market_cache.enabled() or os.environ.get('STOCK_INSIGHTS_AS_OF') or os.environ.get('STOCK_INSIGHTS_SNAPSHOT_DIR'):
        return _download_uncached(s)
    def fetch():
        frame, meta = _download_uncached(s)
        # Completed-session eligibility determines refresh, including weekends/holidays.
        now = pd.Timestamp.now(tz='UTC')
        market = ('BSE' if s.endswith('.BO') else 'NSE') if currency(s)=='INR' else 'NYSE'
        upcoming = schedule(market, str(now.date()), str((now+pd.Timedelta(days=14)).date()))
        closes = upcoming.market_close + pd.Timedelta(minutes=15)
        future = closes[closes > now]
        ttl = 900 if meta['stale'] or future.empty else max(1, (future.iloc[0]-now).total_seconds())
        return {'frame': frame.to_json(orient='split', date_format='iso'), 'metadata': meta,
                '_source': meta['source'], '_observation_date': meta['observation_date'], '_ttl': ttl}
    data = market_cache.cache.get(s, 'history', fetch, 86400)
    if not data.get('frame'):
        raise ValueError('Daily price provider unavailable: '+str(data.get('error', 'missing history')))
    from io import StringIO
    frame = pd.read_json(StringIO(data['frame']), orient='split')
    meta = dict(data['metadata'])
    expected = completed_sessions(s)[-1]
    last = frame.Close.last_valid_index()
    meta.update(expected_session=str(expected.date()), observation_date=str(last.date()),
                stale=last < expected, data_quality=data['data_quality'])
    with _lock:
        _cache[s] = (time.monotonic(), frame, meta)
    return frame, meta


def _usable_history(frame, meta):
    if not os.environ.get('STOCK_INSIGHTS_AS_OF'):
        expected = pd.Timestamp(meta.get('expected_session') or frame.index[-1])
        observed = frame.Close.last_valid_index()
        if (expected-observed).days > 7:
            raise ValueError('Daily history is more than seven calendar days old.')
    return frame.copy(), dict(meta)


def history(s):
    replay = os.environ.get('STOCK_INSIGHTS_AS_OF', '').strip()
    eligible = completed_sessions(s, replay or None)
    expected = str(eligible[-1].date()) if len(eligible) else None
    with _lock:
        cached = _cache.get(s)
        ttl = 60 if cached and cached[2].get('stale') else 900
        # A session becoming complete invalidates even a recently fetched bar.
        if (cached and time.monotonic()-cached[0] < ttl
                and cached[2].get('expected_session') == expected):
            return _usable_history(cached[1], cached[2])
        future = _pending.get(s)
        if future is None or future.done():
            future = _pool.submit(_download, s)
            _pending[s] = future
    try:
        frame, meta = future.result(timeout=14)
        return _usable_history(frame, meta)
    except TimeoutError:
        raise ValueError('Price provider timed out. Retry shortly.')


def base(s, meta=None):
    return dict(symbol=s, currency=currency(s), calculation_version=calc.VERSION,
                parameters=calc.PARAMETERS, facts=[], **(meta or {}))


def safe(call, s):
    try:
        return call()
    except Exception as exc:
        log.warning('Stock insights unavailable for %s: %s', s, type(exc).__name__)
        return dict(base(s), status='unavailable', message='Price or calculation service unavailable. Please retry later.')


def historical(s, investment=10000, months=3):
    def run():
        frame, meta = history(s)
        # Stale data may still describe past experience; the date and warning are explicit.
        result = dict(base(s, meta), **calc.historical(frame, investment, months))
        if meta['stale']:
            result['facts'].append('History is stale; results end on the displayed observation date.')
        return result
    return safe(run, s)


def _news(s):
    if os.environ.get('STOCK_INSIGHTS_AS_OF'):
        return []  # Current headlines must never be attached to a historical replay.
    try:
        future = _pool.submit(stocks.get_news, s)
        articles = future.result(timeout=5).get('articles', [])
        cutoff = time.time()-7*86400
        return [a for a in articles if isinstance(a.get('datetime'), (int,float)) and cutoff <= a['datetime'] <= time.time()
                and str(a.get('url','')).startswith(('https://','http://'))][:3]
    except Exception:
        return []


def movement(s):
    def run():
        frame, meta = history(s)
        stock_date = frame.Close.last_valid_index()
        if stock_date is None:
            raise ValueError('No completed-session prices available.')
        frame = frame.loc[:stock_date]
        analysis_date = stock_date
        benchmark_symbol = '^NSEI' if currency(s)=='INR' else '^GSPC'
        try:
            benchmark, bm_meta = history(benchmark_symbol)
            # Calculate returns before alignment so missing sessions never become
            # multi-session moves. Use the latest session available in both feeds.
            common = pd.concat([calc.returns(frame), calc.returns(benchmark)], axis=1).dropna()
            if not common.empty:
                analysis_date = common.index[-1]
                frame = frame.loc[:analysis_date]
                benchmark = benchmark.loc[:analysis_date]
        except Exception:
            benchmark = None
        meta = _analysis_metadata(meta, frame, analysis_date)
        result = dict(base(s, meta), **calc.movement(frame, benchmark))
        result['stock_available_date'] = str(stock_date.date())
        result.update(benchmark_symbol=benchmark_symbol, benchmark_name='NIFTY 50' if currency(s)=='INR' else 'S&P 500', news=_news(s),
                      news_note='Recent provider-listed company headlines are context, not verified causes of movement.')
        result['facts'] = [result.get('message',''),
                           'Daily adjusted returns; regression uses preceding sessions only. Alert threshold: |robust score| > 3.5.',
                           'News association does not establish causation.']
        if result['stale']:
            result['facts'].append(f'Using latest available aligned prices as of {result["observation_date"]}; latest completed exchange session is {result.get("expected_session", "unavailable")}.')
            result['news_note'] = 'Recent company headlines may postdate the analysis session; they are context, not verified causes of that session’s movement.'
        return result
    return safe(run, s)


def _analysis_metadata(meta, frame, date):
    """Describe the actual calculation date, keeping the exchange target visible."""
    date_string = str(date.date())
    valid = frame.loc[:date, 'Close'].dropna()
    coverage = dict(meta.get('coverage', {}))
    if len(valid):
        coverage.update(start=str(valid.index[0].date()), end=date_string, valid_prices=len(valid))
    delayed = date_string < meta.get('expected_session', date_string)
    return {**meta, 'observation_date': date_string, 'coverage': coverage,
            'stale': delayed or bool(meta.get('stale')), 'latest_available_fallback': delayed or bool(meta.get('stale'))}


def portfolio_fit(s, holdings, investment):
    def run():
        quantities, excluded = {}, []
        for h in holdings:
            hs = symbol(h.get('symbol'))
            qty = float(h.get('qty', 0))
            if not np.isfinite(qty) or qty <= 0:
                raise ValueError('Holding quantities must be positive and finite.')
            if currency(hs) != currency(s):
                excluded.append(hs)
            else:
                quantities[hs] = quantities.get(hs,0)+qty
        result_base = dict(base(s), excluded_symbols=sorted(set(excluded)),
                           portfolio_scope=f'{currency(s)} subportfolio', holdings_count=len(quantities))
        if not quantities:
            return dict(result_base, status='empty_portfolio', message='Add holdings in this stock’s currency to assess portfolio fit.')
        symbols = sorted(set(quantities)|{s})
        deadline = time.monotonic()+20
        frames, metadata = {}, {}
        # Fail the fit rather than silently dropping an unavailable holding.
        for hs in symbols:
            if time.monotonic() >= deadline:
                raise TimeoutError('Portfolio history request exceeded its time budget.')
            frames[hs], metadata[hs] = history(hs)
        sectors = {}
        for hs in symbols:
            try:
                if time.monotonic() >= deadline:
                    sectors[hs] = 'Unknown'
                    continue
                profile = _pool.submit(stocks.get_profile, hs).result(timeout=5)
                sectors[hs] = profile.get('sector') if profile.get('sector') not in ('N/A','') else 'Unknown'
            except Exception:
                sectors[hs] = 'Unknown'
        computed = calc.portfolio(frames, quantities, sectors, s, investment)
        result = {**result_base, **metadata[s], **computed}
        if computed.get('valuation_date'):
            result.update(_analysis_metadata(metadata[s], frames[s], pd.Timestamp(computed['valuation_date'])))
        result['history_coverage'] = {hs:metadata[hs]['coverage'] for hs in symbols}
        result['facts'] = computed.get('facts', [])
        if result.get('latest_available_fallback'):
            result['facts'].append(f'Using latest common available prices as of {result["observation_date"]} for every holding and the candidate. Latest completed exchange session is {result.get("expected_session", "unavailable")}.')
        if excluded:
            result['facts'].append('Foreign-currency holdings are excluded: '+', '.join(sorted(set(excluded)))+'.')
        if 'Unknown' in sectors.values():
            result['facts'].append('Some sector classifications are unavailable and appear as Unknown.')
        result['facts'].append('Historical comparisons exclude taxes, transaction costs and future exchange-rate changes.')
        if result.get('analysis_mode') == 'historical_demo':
            result['facts'].append('Sector classifications use available company profiles, not a historical reconstruction.')
        return result
    return safe(run, s)


def explain(data, kind):
    """Grounded chatbot reply: only computed values; no model can add numbers."""
    from html import escape
    def p(n):
        return 'unavailable' if n is None else f'{n*100:.2f}%'
    title = {'movement':'Unusual Movement', 'historical':'Historical Experience', 'portfolio-fit':'Portfolio Fit'}[kind]
    lines = [f'{data["symbol"]} — {title}']
    if data.get('status') not in {'ready','partial'}:
        lines.append(data.get('message','Insight unavailable.'))
    elif kind=='portfolio-fit':
        lines += [f'Historical price swings (annualized volatility): {p(data["before"]["annualized_volatility"])} before, {p(data["after"]["annualized_volatility"])} after.',
                  f'Largest holding: {p(data["before"]["largest_stock_weight"])} before, {p(data["after"]["largest_stock_weight"])} after.',
                  'Price swings describe how much historical returns varied; they are not an expected gain or loss.',
                  'A lower volatility estimate does not guarantee a safer future investment.']
    elif kind=='movement':
        lines += [f'Stock move: {p(data["stock_return"])}. Market move: {p(data["benchmark_return"])}.',
                  f'Beyond the usual market relationship: {p(data["abnormal_return"])}.',
                  'This compares the stock with an estimate from its historical relationship with the market, rather than simply subtracting the two returns.',
                  'This measures unusual behavior relative to historical market relationships, not a future price direction.']
    else:
        lines += [f'For {data["currency"]} {data["amount"]:,.2f} held for {data["months"]} months, the middle historical outcome (median) was {data["currency"]} {data["median_value"]:,.2f}.',
                  f'The historical 10th–90th percentile range was {data["currency"]} {data["p10_value"]:,.2f} to {data["p90_value"]:,.2f}.',
                  f'{p(data["losing_fraction"])} of {data["window_count"]} overlapping windows ended in a loss.']
    if data.get('observation_date'):
        lines.append('Using prices from: '+data['observation_date'])
    if data.get('stale'):
        lines.append('Provider data is delayed; this explanation uses the available analysis session shown above.')
    lines.append('Calculation version: '+calc.VERSION)
    details = '<details class="sii-method"><summary>Supporting facts and assumptions</summary><ul>'+''.join('<li>'+escape(f)+'</li>' for f in data.get('facts', []))+'</ul></details>'
    return '<strong>FinAssist explanation</strong><br>'+'<br>'.join(escape(line) for line in lines)+details


def chat_request(form):
    import json
    s = symbol(form.get('insight_symbol'))
    investment = amount(form.get('insight_amount',10000))
    kind = form.get('insight_kind')
    if kind=='movement':
        data = movement(s)
    elif kind=='historical':
        months = int(form.get('insight_months',3))
        if months not in calc.HORIZONS:
            raise ValueError('Invalid holding period')
        data = historical(s, investment, months)
    elif kind=='portfolio-fit':
        holdings = json.loads(form.get('insight_holdings','[]'))
        if not isinstance(holdings,list) or len(holdings)>30:
            raise ValueError('Invalid holdings')
        for h in holdings:
            if not isinstance(h,dict):
                raise ValueError('Invalid holding')
            symbol(h.get('symbol'))
            q=float(h.get('qty',0))
            if not np.isfinite(q) or not 0<q<=1e12:
                raise ValueError('Invalid quantity')
        data = portfolio_fit(s, holdings, investment)
    else:
        raise ValueError('Invalid insight')
    return explain(data,kind)
