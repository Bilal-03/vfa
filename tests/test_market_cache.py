from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import time
import json
import numpy as np
import pandas as pd
import pytest
import requests
from market_cache import MarketCache, note_error, reason
from market_metrics import calculate


class Store:
    def __init__(self): self.rows = {}
    def load(self, s, c): return deepcopy(self.rows.get((s,c)))
    def save(self, s, c, row): self.rows[s,c] = deepcopy(row)
    def touch(self, s, c): pass


def test_partial_and_failed_refresh_preserve_field_value_and_original_timestamp():
    now = [1000.]
    cache = MarketCache(clock=lambda:now[0])
    first = cache._refresh('TCS.NS','metrics',lambda:{'pe_ratio':20,'roe':.1},100)
    now[0] = 1200
    result = cache._refresh('TCS.NS','metrics',lambda:{'pe_ratio':None,'roe':.2},100)
    assert result['pe_ratio']==20 and result['roe']==.2
    assert result['data_quality']['fields']['pe_ratio']['fetched_at']==first['data_quality']['fields']['pe_ratio']['fetched_at']
    assert result['data_quality']['fields']['pe_ratio']['freshness']=='stale'
    def denied():
        note_error('permission_denied');return {'pe_ratio':float('nan')}
    result=cache._refresh('TCS.NS','metrics',denied,100)
    assert result['pe_ratio']==20
    assert cache.rows['TCS.NS','metrics']['next_refresh']==now[0]+86400
    assert result['data_quality']['last_error']=='permission_denied'


@pytest.mark.parametrize('code,expected',[(401,'permission_denied'),(403,'permission_denied'),(429,'rate_limited'),(500,'provider_unavailable')])
def test_http_failure_classification(code,expected):
    response=requests.Response();response.status_code=code
    assert reason(requests.HTTPError(response=response))==expected


def test_timeout_and_missing_coverage():
    assert reason(requests.Timeout())=='timeout'
    assert reason(ValueError('No price data available'))=='missing_coverage'


def test_persistent_cache_survives_a_new_application_and_does_not_retry_denial():
    store=Store();now=[1000.]
    cache=MarketCache(store,clock=lambda:now[0])
    cache._refresh('AAPL','profile',lambda:{'name':'Apple','sector':'Technology'},100)
    now[0]+=200
    cache._refresh('AAPL','profile',lambda:{'error':'403 Forbidden'},100)
    restarted=MarketCache(store,clock=lambda:now[0])
    result=restarted.get('AAPL','profile',lambda:pytest.fail('Permission denial must be backed off'))
    assert result['name']=='Apple' and result['sector']=='Technology'
    assert result['data_quality']['fields']['name']['freshness']=='stale'


def test_stale_returns_immediately_and_single_refresh_serves_concurrent_readers():
    now=[1000.];cache=MarketCache(clock=lambda:now[0]);gate=threading.Event();started=threading.Event();calls=[]
    cache._refresh('AAPL','quote',lambda:{'current':100},10)
    now[0]+=20
    def loader():
        calls.append(1);started.set();gate.wait(2);return {'current':101}
    try:
        assert cache.get('AAPL','quote',loader)['current']==100
        assert started.wait(1)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:cache.get('AAPL','quote',loader),range(8)))
        assert all(r['current']==100 for r in results) and len(calls)==1
    finally:gate.set()
    cache.pending['AAPL','quote'].result(2)
    assert cache.get('AAPL','quote',loader)['current']==101


def test_nested_cold_categories_do_not_exhaust_refresh_pool():
    cache=MarketCache(executor=ThreadPoolExecutor(max_workers=1))
    result=cache.get('AAPL','profile',lambda:{'name':cache.get('AAPL','yahoo_info',lambda:{'name':'Apple'})['name']})
    assert result['name']=='Apple'


def test_empty_payload_invalid_numbers_and_reference_catalog():
    cache=MarketCache(clock=lambda:1000.)
    result=cache._refresh('TCS.NS','metrics',lambda:{'pe_ratio':float('inf')},100)
    assert result['pe_ratio'] is None and result['data_quality']['fields']['pe_ratio']['freshness']=='unavailable'
    from market_metrics import enrich
    result=enrich('TCS.NS','profile',{'name':'TCS.NS','currency':'INR','exchange':'NSE'})
    assert result['name']=='Tata Consultancy Services'
    assert result['_field_sources']['name']['source']=='FinAssist reference catalog'


def test_bounds_and_benchmark_retention():
    now=[1000.];cache=MarketCache(clock=lambda:now[0])
    cache._refresh('^NSEI','history',lambda:{'frame':'recorded'},100)
    for i in range(105):
        now[0]+=1;cache._refresh('S'+str(i),'quote',lambda:{'current':1},100)
    assert len({s for s,c in cache.rows if s!='^NSEI'})==100
    assert ('^NSEI','history') in cache.rows and ('S0','quote') not in cache.rows
    now[0]+=31*86400;cache._prune()
    assert set(cache.rows)=={('^NSEI','history')}


def frames(n=330):
    rng=np.random.default_rng(4);r=rng.normal(.0002,.01,n-1)
    index=pd.bdate_range(end='2026-10-26',periods=n)
    market=np.r_[100,100*np.cumprod(1+r)]
    stock=np.r_[100,100*np.cumprod(1+1.5*r)]
    def make(close):return pd.DataFrame({'Close':close,'RawClose':close,'High':close+1,'Low':close-1,'Volume':np.arange(n)+100.,'Stock Splits':0.},index=index)
    return make(stock),make(market)


def test_computed_metrics_against_independent_references():
    stock,market=frames();result,q=calculate(stock,market,'2026-10-27')
    assert result['avg_volume']==pytest.approx(stock.Volume.tail(20).sum()/20)
    year=stock.loc[stock.index>stock.index[-1]-pd.Timedelta(weeks=52)]
    assert result['week52_high']==year.High.max() and result['week52_low']==year.Low.min()
    assert result['beta']==pytest.approx(1.5)
    assert q['beta']['return_count']==252


def test_gaps_short_history_and_constant_market_are_not_filled():
    stock,market=frames(100)
    result,q=calculate(stock,market,'2026-10-27')
    assert 'beta' not in result and 'week52_high' not in result
    assert q['week52_high']['reason']=='incomplete_52_week_coverage'
    stock,market=frames();market.Close=100
    stock.loc[stock.index[-5],'Volume']=np.nan
    result,q=calculate(stock,market,'2026-10-27')
    assert 'avg_volume' not in result and 'beta' not in result
    stock.loc[stock.index[-10],'High']=np.nan
    assert 'week52_high' not in calculate(stock,market,'2026-10-27')[0]
    assert calculate(stock,market,'2026-11-10')[0]=={}


def test_split_rebasing_and_history_json_roundtrip():
    stock,_=frames();stock.loc[stock.index[-1],'Stock Splits']=2
    values,_=calculate(stock,now='2026-10-27')
    start=stock.index[-1]-pd.Timedelta(weeks=52)
    prices=stock.loc[stock.index>start,'High'].copy();prices.iloc[:-1]/=2
    assert values['week52_high']==prices.max()
    from io import StringIO
    decoded=pd.read_json(StringIO(stock.to_json(orient='split',date_format='iso')),orient='split')
    assert decoded.index.equals(stock.index)


def test_old_history_refused_by_insights(monkeypatch):
    import insights_service
    stock,_=frames()
    monkeypatch.delenv('STOCK_INSIGHTS_AS_OF',raising=False)
    with pytest.raises(ValueError,match='seven calendar days'):
        insights_service._usable_history(stock,{'expected_session':'2026-11-10'})


def test_render_permission_failure_does_not_prevent_success_on_local_network():
    store=Store();now=[1000.]
    cloud=MarketCache(store,clock=lambda:now[0],origin='render')
    cloud._refresh('TCS.NS','yahoo_info',lambda:{'error':'403 Forbidden'},86400)
    laptop=MarketCache(store,clock=lambda:now[0],origin='local')
    result=laptop.get('TCS.NS','yahoo_info',lambda:{'info':{'longName':'Tata Consultancy Services','trailingPE':20.5}})
    assert result['info']['trailingPE']==20.5


def test_memory_revalidates_success_from_other_instances():
    store=Store();now=[1000.]
    first=MarketCache(store,clock=lambda:now[0]);first._refresh('AAPL','profile',lambda:{'name':'Apple'},86400)
    other=MarketCache(store,clock=lambda:now[0]);other._refresh('AAPL','profile',lambda:{'name':'Apple','sector':'Technology'},86400)
    now[0]+=301
    result=first.get('AAPL','profile',lambda:pytest.fail('Fresh shared entry should not need a provider'))
    assert result['sector']=='Technology'


def test_storage_failure_leaves_memory_usable(monkeypatch):
    from market_cache import SupabaseStore
    monkeypatch.setenv('SUPABASE_URL','https://example.com');monkeypatch.setenv('SUPABASE_KEY','test')
    monkeypatch.setattr(requests,'request',lambda *a,**kw:(_ for _ in ()).throw(requests.Timeout()))
    cache=MarketCache(SupabaseStore())
    assert cache.get('AAPL','quote',lambda:{'current':100})['current']==100
    assert cache.get('AAPL','quote',lambda:pytest.fail('Memory should survive storage outage'))['current']==100


def test_daily_chart_reuses_completed_history_and_adjusts_ohlc(monkeypatch):
    import insights_service,market_metrics
    stock,_=frames()
    stock['Open']=stock.RawClose
    monkeypatch.setattr(insights_service,'history',lambda s:(stock,{'source':'Recorded test prices','observation_date':'2026-10-26'}))
    result=market_metrics.daily_candles('AAPL','1Y',now='2026-10-27')
    assert result['candles'] and result['candles'][-1]['close']==round(stock.Close.iloc[-1],2)
    assert result['_observation_date']=='2026-10-26'


def test_expired_computed_metric_is_not_used_as_current_analytics():
    from datetime import datetime,timezone
    now=datetime(2026,10,28,tzinfo=timezone.utc).timestamp()
    cache=MarketCache(clock=lambda:now)
    result=cache._refresh('AAPL','metrics',lambda:{'beta':1.5,'_field_sources':{'beta':{'source':'Calculated','observation_date':'2026-10-01','calculation':'120 returns'}}},86400)
    assert result['beta'] is None and result['data_quality']['fields']['beta']['reason']=='history_too_old'
