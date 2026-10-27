"""Bounded, server-only last-successful market cache with stale-while-refresh."""
from concurrent.futures import ThreadPoolExecutor, Future
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import logging
import os
import re
import threading
import time

import requests
from json_provider import finite_values

log = logging.getLogger(__name__)
_errors = ContextVar('market_provider_errors', default=None)
BENCHMARKS = {'^NSEI', '^GSPC'}
TTLS = {'profile': 7*86400, 'quote': 900, 'metrics': 86400,
        'analyst': 86400, 'news': 900, 'yahoo_info': 86400,
        'twelve_statistics': 86400, 'history': 900}


def enabled():
    return os.environ.get('MARKET_CACHE_ENABLED', 'true').lower() not in {'false', '0', 'no'}


def reason(error):
    status = getattr(getattr(error, 'response', None), 'status_code', None)
    text = str(error).lower()
    if status in (401, 403) or any(s in text for s in ('401', '403', 'unauthorized', 'forbidden', 'upgrade', 'invalid crumb')):
        return 'permission_denied'
    if status == 429 or any(s in text for s in ('429', 'too many requests', 'rate limit')):
        return 'rate_limited'
    if isinstance(error, (TimeoutError, requests.Timeout)) or 'timed out' in text:
        return 'timeout'
    if any(s in text for s in ('no data', 'not found', 'delisted', 'no price', 'not covered')):
        return 'missing_coverage'
    return 'provider_unavailable'


def note_error(error):
    errors = _errors.get()
    if errors is not None:
        errors.append(error if error in {'permission_denied', 'rate_limited', 'timeout', 'missing_coverage', 'provider_unavailable'} else reason(error))


def usable(value):
    if value is None or isinstance(value, str) and value.strip().lower() in {'', 'n/a', 'unknown', 'none'}:
        return False
    return not isinstance(value, (dict, list)) or bool(value)


def leaves(data, prefix=''):
    for key, value in data.items():
        if key.startswith('_') or key in {'error', 'data_quality', 'fetched_at', 'message', 'status'}:
            continue
        path = f'{prefix}.{key}' if prefix else key
        if isinstance(value, dict):
            yield from leaves(value, path)
        else:
            yield path, value


def assign(data, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


def stamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


class SupabaseStore:
    """Bounded REST operations; cache failures never take down the application."""
    def __init__(self):
        self.retry_at = 0

    def request(self, method, params=None, body=None, resource="market_data_cache"):
        url, key = os.getenv('SUPABASE_URL', ''), os.getenv('SUPABASE_KEY', '')
        if not url or not key or time.time() < self.retry_at:
            return None
        try:
            r = requests.request(method, url.rstrip('/')+'/rest/v1/'+resource,
                params=params, json=body, timeout=(2, 3), headers={
                    'apikey': key, 'Authorization': 'Bearer '+key,
                    'Prefer': 'resolution=merge-duplicates,return=minimal'})
            r.raise_for_status()
            return r.json() if r.content else []
        except Exception:
            self.retry_at = time.time()+60
            log.warning('Market cache storage unavailable; using memory')
            return None

    def load(self, symbol, category):
        rows = self.request('GET', {'symbol': 'eq.'+symbol, 'category': 'eq.'+category, 'select': 'entry'})
        return rows[0]['entry'] if rows else None

    def save(self, symbol, category, entry):
        return self.request('POST', body={'p_symbol': symbol, 'p_category': category,
            'p_entry': finite_values(entry)}, resource='rpc/save_market_data_cache')

    def touch(self, symbol, category):
        self.request('PATCH', {'symbol': 'eq.'+symbol, 'category': 'eq.'+category},
                     {'last_accessed_at': stamp(time.time())})


class MarketCache:
    def __init__(self, store=None, clock=time.time, executor=None, origin=None):
        self.store = store
        self.clock = clock
        self.rows = {}
        self.pending = {}
        self.lock = threading.RLock()
        self.pool = executor or ThreadPoolExecutor(max_workers=4, thread_name_prefix='market-refresh')
        self.touched = {}
        self.loaded_at = {}
        self.origin = origin or ('render' if os.getenv('RENDER') == 'true' else 'local')

    def _prune(self):
        now = self.clock()
        access = {}
        for (symbol, _), row in self.rows.items():
            access[symbol] = max(access.get(symbol, 0), row.get('accessed_at', 0))
        keep = set(sorted((s for s in access if s not in BENCHMARKS and now-access[s] <= 30*86400), key=access.get, reverse=True)[:100]) | BENCHMARKS
        for key in list(self.rows):
            if key[0] not in keep:
                self.rows.pop(key, None)
                self.touched.pop(key, None)
                self.loaded_at.pop(key, None)
        self.pending = {key: future for key, future in self.pending.items() if not future.done()}

    def _refresh(self, symbol, category, loader, ttl):
        key = symbol, category
        token = _errors.set([])
        try:
            try:
                incoming = finite_values(loader() or {})
                if category == 'analyst' and incoming.get('consensus') not in {'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'} and not incoming.get('total') and not incoming.get('analyst_count') and not incoming.get('target_mean'):
                    incoming = {'symbol': symbol, 'error': 'No data for analyst ratings'}
                if incoming.get('error'):
                    note_error(incoming['error'])
            except Exception as exc:
                incoming = {}
                note_error(reason(exc))
            failures = list(_errors.get())
            now = self.clock()
            with self.lock:
                row = deepcopy(self.rows.get(key) or {'payload': {}, 'quality': {}, 'failures': 0})
                source = incoming.get('_source') or incoming.get('provider') or 'Yahoo Finance'
                source = {'twelvedata': 'Twelve Data', 'yfinance_info': 'Yahoo Finance', 'yfinance_history': 'Yahoo Finance daily prices'}.get(source, source)
                sources = incoming.pop('_field_sources', {})
                observed = incoming.get('_observation_date')
                previous_observed = row.get('observation_date')
                regressed = category in {'history', 'quote'} and previous_observed and observed and observed < previous_observed
                if category == 'news' and row['payload'].get('articles') and not incoming.get('articles'):
                    for field in ('count', 'status', 'provider'):
                        incoming.pop(field, None)
                incoming_paths = list(leaves(incoming)) if not regressed else []
                updated = False
                row.setdefault('missing', {})
                for path, value in incoming_paths:
                    if usable(value):
                        assign(row['payload'], path, value)
                        details = sources.get(path, {})
                        if isinstance(details, str):
                            details = {'source': details}
                        row['quality'][path] = {**dict(source=source, observation_date=observed,
                            fetched_at=stamp(now), expires_at=now+ttl), **details}
                        original_time = details.get('fetched_at')
                        if original_time:
                            row['quality'][path]['expires_at'] = datetime.fromisoformat(original_time).timestamp()+ttl
                        row['missing'].pop(path, None)
                        updated |= path not in {'symbol', 'currency', 'exchange', 'count', 'total', 'analyst_count'}
                    elif path not in row['quality']:
                        details = sources.get(path, {})
                        row['missing'][path] = dict(details) if isinstance(details, dict) else {'source': details}
                        assign(row['payload'], path, None)
                # Lists such as articles are atomic: an empty result cannot erase a successful result.
                for key_name in ('status', 'provider', 'message', '_source'):
                    if key_name in incoming and (updated or not row['payload']):
                        row['payload'][key_name] = incoming[key_name]
                failure = next((f for f in failures if f == 'permission_denied'), None) or (failures[0] if failures else None)
                if not updated and not failure:
                    failure = 'missing_coverage'
                row['failures'] = row.get('failures', 0)+1 if failure else 0
                wait = 86400 if failure == 'permission_denied' else min(3600, 300 * 2**min(row['failures']-1, 4)) if failure else incoming.get('_ttl', ttl)
                if category == 'quote':
                    wait = min(wait, ttl)
                row['attempted_at'] = now
                row.update(next_refresh=now+max(1, wait), accessed_at=now, last_error=failure, failure_origin=self.origin if failure else None)
                if not regressed and observed:
                    row['observation_date'] = observed
                self.rows[key] = row
                self.loaded_at[key] = now
                self._prune()
            if self.store:
                saved = self.store.save(symbol, category, row)
                if isinstance(saved, dict) and 'payload' in saved:
                    row = saved
                    with self.lock:
                        self.rows[key] = row
            return self._output(row, category)
        finally:
            _errors.reset(token)

    def _output(self, row, category):
        now = self.clock()
        data = deepcopy(row['payload'])
        quality = {}
        for path, meta in row['quality'].items():
            meta = dict(meta)
            expires = meta.pop('expires_at', 0)
            meta['freshness'] = 'stale' if expires <= now else 'fresh'
            if row.get('last_error') and expires <= now and meta.get('source') != 'FinAssist reference catalog':
                meta['reason'] = row['last_error']
            if meta.get('calculation') and meta.get('observation_date'):
                age = (datetime.fromtimestamp(now, timezone.utc).date() - datetime.fromisoformat(meta['observation_date']).date()).days
                if age > 7:
                    assign(data, path, None)
                    meta.update(freshness='unavailable', reason='history_too_old')
            quality[path] = meta
        for path, meta in row.get('missing', {}).items():
            quality[path] = dict(source='Provider', **meta) if 'source' not in meta else dict(meta)
            quality[path].update(freshness='unavailable', reason=meta.get('reason') or row.get('last_error') or 'missing_coverage')
        if category == 'news' and data.get('articles'):
            data['articles'] = [a for a in data['articles'] if now-7*86400 <= a.get('datetime', 0) <= now]
            data['count'] = len(data['articles'])
            if not data['articles']:
                data['status'] = 'empty'
        data['data_quality'] = {'fields': quality, 'last_error': row.get('last_error'),
            'next_refresh_at': stamp(row['next_refresh']), 'category': category}
        # Internal callers still receive a failure signal when no actual data exists.
        if not any(path not in {'symbol', 'currency', 'count', 'total', 'analyst_count'} for path in row['quality']):
            data['error'] = row.get('last_error') or 'missing_coverage'
        return data

    def get(self, symbol, category, loader, ttl=None):
        ttl = ttl or TTLS[category]
        key = symbol, category
        if not re.fullmatch(r'[A-Z0-9^][A-Z0-9&.^-]{0,24}', symbol):
            return {'error': 'Invalid symbol'}
        now = self.clock()
        inline = _errors.get() is not None or category in {'history', 'yahoo_info', 'twelve_statistics', 'twelve_quote'}
        with self.lock:
            row = self.rows.get(key)
            if self.store and (row is None or now-self.loaded_at.get(key, 0) >= 300):
                row = self.store.load(symbol, category) or row
                self.loaded_at[key] = now
                if row:
                    self.rows[key] = row
            if row:
                row['accessed_at'] = now
                if self.store and now-self.touched.get(key, 0) > 3600:
                    self.store.touch(symbol, category)
                    self.touched[key] = now
                same_origin = not row.get('last_error') or row.get('failure_origin', self.origin) == self.origin
                if now < row['next_refresh'] and same_origin:
                    output = self._output(row, category)
                    if row.get('last_error'):
                        note_error(row['last_error'])
                    return output
                if not inline:
                    future = self.pending.get(key)
                    if (future is None or future.done()) and sum(not f.done() for f in self.pending.values()) < 16:
                        self.pending[key] = self.pool.submit(self._refresh, symbol, category, loader, ttl)
                    return self._output(row, category)
            future = self.pending.get(key)
            owner = future is None or future.done()
            if owner:
                if _errors.get() is None and sum(not f.done() for f in self.pending.values()) >= 16:
                    return {'error': 'Refresh capacity reached', 'data_quality': {'fields': {}, 'last_error': 'busy'}}
                future = Future()
                self.pending[key] = future
        if owner:
            def run():
                try:
                    future.set_result(self._refresh(symbol, category, loader, ttl))
                except Exception as exc:
                    future.set_exception(exc)
            if inline:
                run()
            else:
                self.pool.submit(run)
        try:
            result = future.result(timeout=25)
            if result['data_quality'].get('last_error'):
                note_error(result['data_quality']['last_error'])
            return deepcopy(result)
        except TimeoutError:
            return {'error': 'timeout', 'data_quality': {'fields': {}, 'last_error': 'timeout'}}


cache = MarketCache(SupabaseStore())


def cached(category, ttl=None):
    def decorate(function):
        @wraps(function)
        def wrapped(symbol):
            if not enabled():
                return function(symbol)
            def load():
                value = function(symbol)
                if category in {'profile', 'quote', 'metrics'}:
                    from market_metrics import enrich
                    value = enrich(symbol, category, value)
                return value
            return cache.get(symbol, category, load, ttl)
        return wrapped
    return decorate
