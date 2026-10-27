import json
import numpy as np
import pandas as pd
import pytest
from flask import Flask
import stock_insights as calc
import insights_service as service
from stock_routes import stock_bp


def frame(n=300, seed=8, values=None):
    rng=np.random.default_rng(seed)
    prices=np.asarray(values) if values is not None else 100*np.cumprod(1+rng.normal(.0003,.01,n))
    return pd.DataFrame({'Close':prices,'RawClose':prices,'Volume':np.full(len(prices),1000.)},
                        index=pd.bdate_range('2024-01-01',periods=len(prices)))


def test_historical_independent_reference():
    f=frame(n=100)
    expected=np.array([f.Close.iloc[i+21]/f.Close.iloc[i]-1 for i in range(79)])
    d=calc.historical(f,10000,1)
    assert d['window_count']==79
    assert d['median_value']==pytest.approx(10000*(1+np.median(expected)))
    assert d['p10_return']==pytest.approx(np.quantile(expected,.1))
    assert d['losing_fraction']==pytest.approx(sum(expected<0)/len(expected))
    assert sum(b['count'] for b in d['distribution'])==79


def test_historical_gap_excludes_affected_windows():
    f=frame(n=100);f.loc[f.index[40],'Close']=np.nan
    assert calc.historical(f,10000,1)['window_count']==79-22
    assert pd.isna(calc.returns(f).iloc[40])
    assert pd.isna(calc.returns(f).iloc[41])


def test_short_history_and_constant_prices():
    assert calc.historical(frame(n=50),100,1)['status']=='insufficient_history'
    d=calc.historical(frame(values=np.ones(100)*100),100,1)
    assert d['median_value']==100 and d['losing_fraction']==0
    assert d['drawdown']['max_drawdown']==0


def test_drawdown_recovery_reference():
    d=calc.drawdown(frame(values=[100,120,90,60,90,120,110]).Close)
    assert d['max_drawdown']==-.5
    assert d['sessions_peak_to_recovery']==4
    assert d['recovery_date']=='2024-01-08'
    assert calc.drawdown(frame(values=[100,80,90]).Close)['recovery_date'] is None


def test_causal_movement_and_stock_specific_shock():
    rng=np.random.default_rng(12)
    market=rng.normal(0,.01,260)
    stock=1.2*market+rng.normal(0,.001,260)
    def prices(r): return frame(values=100*np.cumprod(np.r_[1,1+r]))
    b=prices(market);s=prices(stock)
    normal=calc.movement(s.iloc[:-1],b.iloc[:-1])
    # A later mutation must not alter an earlier assessment.
    s.iloc[-1,s.columns.get_loc('Close')]*=1.2
    assert calc.movement(s.iloc[:-1],b.iloc[:-1])==normal
    result=calc.movement(s,b)
    assert result['unusual'] is True and result['robust_score']>3.5
    assert result['volume_multiple']==1


def test_market_wide_shock_is_discounted():
    rng=np.random.default_rng(4)
    market=rng.normal(0,.01,260);market[-1]=-.12
    stock=1.1*market+rng.normal(0,.001,260)
    b=frame(values=100*np.cumprod(np.r_[1,1+market]))
    s=frame(values=100*np.cumprod(np.r_[1,1+stock]))
    d=calc.movement(s,b)
    assert d['unusual'] is False
    assert abs(d['raw_robust_score'])>3.5


def test_missing_benchmark_and_degenerate_reference():
    assert calc.movement(frame())['status']=='partial'
    d=calc.movement(frame(values=np.ones(300)*100),frame(values=np.ones(300)*100))
    assert d['robust_score'] is None and d['unusual'] is None
    f=frame();f.loc[f.index[-1],'Close']=np.nan
    assert calc.movement(f)['status']=='insufficient_history'


def test_portfolio_zero_purchase_is_unchanged():
    frames={'AAPL':frame(),'MSFT':frame(seed=9)}
    d=calc.portfolio(frames,{'AAPL':2,'MSFT':3},{'AAPL':'Technology','MSFT':'Technology'},'AAPL',0)
    assert d['before']==d['after']
    assert d['before']['sector_exposure']['Technology']==pytest.approx(1)


def test_portfolio_duplicate_exposure_and_current_valuation():
    f=frame();f['RawClose']=f.Close*2
    d=calc.portfolio({'AAPL':f},{'AAPL':2},{'AAPL':'Technology'},'AAPL',1000)
    assert d['portfolio_value']==pytest.approx(f.RawClose.iloc[-1]*2)
    assert d['candidate_correlation']==pytest.approx(1)
    assert d['before']['concentration_hhi']==1
    assert d['before']['annualized_volatility']==pytest.approx(d['after']['annualized_volatility'])


def test_portfolio_alignment_short_and_constant():
    assert calc.portfolio({'AAPL':frame(n=120)},{'AAPL':1},{},'AAPL',100)['status']=='insufficient_history'
    f=frame(values=np.ones(200)*100)
    d=calc.portfolio({'AAPL':f},{'AAPL':1},{},'AAPL',100)
    assert d['before']['annualized_volatility']==0
    assert d['candidate_correlation'] is None
    assert d['largest_overlap']['correlation'] is None


def test_clean_split_adjustment_duplicates_and_missing_dates():
    idx=pd.bdate_range('2024-01-01',periods=5)
    raw=pd.DataFrame({'Adj Close':[50,50,50,50,50], 'Close':[100,100,50,50,50],
                      'Volume':[100]*5, 'Stock Splits':[0,0,2,0,0]},index=idx)
    raw=pd.concat([raw,raw.iloc[[2]]])
    clean,meta=service.clean_history(raw,idx)
    assert meta['duplicates_removed']==1 and meta['split_events']==1
    assert calc.returns(clean).dropna().eq(0).all()
    clean,meta=service.clean_history(raw.drop(idx[1]),idx)
    assert meta['missing_sessions']==1 and pd.isna(calc.returns(clean).iloc[2])


def test_completed_sessions_holiday_intraday_and_early_close():
    assert pd.Timestamp('2025-07-04') not in service.completed_sessions('AAPL','2025-07-05T12:00Z',start='2025-07-01')
    assert pd.Timestamp('2025-11-28') not in service.completed_sessions('AAPL','2025-11-28T17:00Z',start='2025-11-25')
    assert pd.Timestamp('2025-11-28') in service.completed_sessions('AAPL','2025-11-28T18:20Z',start='2025-11-25')
    assert pd.Timestamp('2025-10-13') not in service.completed_sessions('TCS.NS','2025-10-13T09:00Z',start='2025-10-10')


@pytest.fixture
def client(monkeypatch):
    meta=dict(observation_date='2025-02-21',expected_session='2025-02-21',stale=False,
              coverage=dict(start='2024-01-01',end='2025-02-21',valid_prices=300,warnings=[]))
    monkeypatch.setattr(service,'history',lambda s:(frame(seed=9 if s.startswith('^') else 8),meta.copy()))
    monkeypatch.setattr(service.stocks,'get_profile',lambda s:{'sector':'Technology'})
    monkeypatch.setattr(service,'_news',lambda s:[])
    app=Flask(__name__);app.register_blueprint(stock_bp)
    return app.test_client()


def test_api_all_tabs_both_currencies(client):
    for s,cur in [('AAPL','USD'),('TCS.NS','INR')]:
        for kind in ['movement','historical']:
            d=client.get(f'/si/insights/{kind}?symbol={s}').get_json()
            assert d['status']=='ready' and d['currency']==cur
            assert d['calculation_version']==calc.VERSION
        d=client.post('/si/insights/portfolio-fit',json={'symbol':s,'holdings':[{'symbol':s,'qty':2}], 'amount':1000}).get_json()
        assert d['status']=='ready'
        assert d['portfolio_scope']==f'{cur} subportfolio'


def test_api_repeated_holdings_mixed_currency_and_empty(client):
    d=client.post('/si/insights/portfolio-fit',json={'symbol':'AAPL','holdings':[{'symbol':'AAPL','qty':1},{'symbol':'AAPL','qty':2},{'symbol':'TCS.NS','qty':4}]}).get_json()
    assert d['holdings_count']==1 and d['excluded_symbols']==['TCS.NS']
    assert d['portfolio_value']==pytest.approx(frame().RawClose.iloc[-1]*3)
    assert client.post('/si/insights/portfolio-fit',json={'symbol':'AAPL','holdings':[]}).get_json()['status']=='empty_portfolio'


@pytest.mark.parametrize('query',['symbol=../etc','symbol=AAPL&amount=nan','symbol=AAPL&amount=-1','symbol=AAPL&months=2','symbol=AAPL&months=1.5','symbol=VOD.L'])
def test_api_invalid_inputs(client,query):
    assert client.get('/si/insights/historical?'+query).status_code==400


def test_api_provider_failure_stale_and_partial(client,monkeypatch):
    monkeypatch.setattr(service,'history',lambda s: (_ for _ in ()).throw(TimeoutError()))
    assert client.get('/si/insights/historical?symbol=AAPL').get_json()['status']=='unavailable'
    monkeypatch.setattr(service,'history',lambda s:(frame(seed=9 if s.startswith('^') else 8),{'stale':True,'observation_date':'2025-02-21','expected_session':'2025-02-24','coverage':{}}))
    assert client.get('/si/insights/movement?symbol=AAPL').get_json()['status']=='ready'
    assert client.post('/si/insights/portfolio-fit',json={'symbol':'AAPL','holdings':[{'symbol':'AAPL','qty':1}]}).get_json()['status']=='ready'
    monkeypatch.setattr(service,'history',lambda s: (_ for _ in ()).throw(ValueError()) if s.startswith('^') else (frame(),{'stale':False}))
    assert client.get('/si/insights/movement?symbol=AAPL').get_json()['status']=='partial'


def test_grounded_explanation_uses_same_values_and_escapes(client):
    d=client.get('/si/insights/historical?symbol=AAPL&amount=1000').get_json()
    text=service.explain(d,'historical')
    assert f'{d["median_value"]:,.2f}' in text
    assert f'{d["window_count"]}' in text
    d['facts']=['<script>alert(1)</script>']
    assert '<script>' not in service.explain(d,'historical')


def test_portfolio_drawdown_never_bridges_a_price_gap():
    a=frame();b=frame(seed=9)
    b.loc[b.index[-80],'Close']=np.nan
    d=calc.portfolio({'AAPL':a,'MSFT':b},{'AAPL':1,'MSFT':1},{},'AAPL',1000)
    assert d['status']=='insufficient_history' and d['aligned_returns']==78


def test_fractional_dividend_yield_and_small_values(monkeypatch):
    import stock_service as stocks
    monkeypatch.setattr(stocks,'_get',lambda key:None)
    monkeypatch.setattr(stocks,'_twelve_data_statistics',lambda symbol:{})
    monkeypatch.setattr(stocks,'_get_ticker_data',lambda symbol:{'info':{'dividendRate':1.08,'currentPrice':340.275,'dividendYield':.32,'returnOnEquity':.1}})
    from types import SimpleNamespace
    monkeypatch.setattr(stocks.yf,'Ticker',lambda symbol:SimpleNamespace(fast_info=SimpleNamespace(market_cap=None,year_high=None,year_low=None)))
    d=stocks.get_metrics('AAPL')
    assert d['dividend_yield']==pytest.approx(1.08/340.275)


def test_local_portfolio_persistence_and_atomic_validation(tmp_path):
    from local_portfolio import configure
    app=Flask(__name__);app.config.update(PORTFOLIO_STORAGE='sqlite',PORTFOLIO_SQLITE_PATH=str(tmp_path/'holdings.db'))
    configure(app)
    for action in ['identify','load','save','delete','sync']:
        app.add_url_rule('/api/portfolio/'+action,action,lambda:('cloud should not be called',500),methods=['GET','POST'])
    c=app.test_client()
    assert c.post('/api/portfolio/identify',json={'username':'Test_User'}).get_json()['storage']=='sqlite'
    h={'username':'Test_User','symbol':'AAPL','qty':2,'avg':100}
    assert c.post('/api/portfolio/save',json=h).get_json()['ok']
    # A second application/client reads the durable file, with case-insensitive identity.
    app2=Flask('reopened');app2.config.update(app.config);configure(app2)
    app2.add_url_rule('/api/portfolio/load','load',lambda:('',500))
    stored=app2.test_client().get('/api/portfolio/load?username=test_user').get_json()['holdings']
    assert len(stored)==1 and stored[0]['qty']==2
    assert c.post('/api/portfolio/sync',json={'username':'Test_User','holdings':[{'symbol':'MSFT','qty':-1,'avg':200}]}).status_code==400
    assert len(c.get('/api/portfolio/load?username=Test_User').get_json()['holdings'])==1
    assert c.post('/api/portfolio/delete',json={'username':'Test_User','symbol':'AAPL'}).get_json()['ok']
    assert c.get('/api/portfolio/load?username=Test_User').get_json()['holdings']==[]


def test_nifty_benchmark_uses_indian_completed_sessions():
    when='2025-10-13T11:00Z'
    assert pd.Timestamp('2025-10-13') in service.completed_sessions('^NSEI',when,start='2025-10-10')
    assert pd.Timestamp('2025-10-13') not in service.completed_sessions('^GSPC',when,start='2025-10-10')


def test_historical_snapshot_is_explicit_and_ignores_future_bad_prices(tmp_path,monkeypatch):
    p=tmp_path/'AAPL.csv'
    raw=pd.DataFrame({'Close':[100.,np.nan],'RawClose':[100.,np.nan],'Volume':[100,100]},index=pd.to_datetime(['2024-01-02','2024-01-03']))
    raw.to_csv(p)
    monkeypatch.setenv('STOCK_INSIGHTS_SNAPSHOT_DIR',str(tmp_path))
    monkeypatch.setenv('STOCK_INSIGHTS_AS_OF','2024-01-02T23:59Z')
    f,m=service._download('AAPL')
    assert m['analysis_mode']=='historical_demo' and not m['stale']
    assert m['observation_date']=='2024-01-02' and m['coverage']['warnings']==[]
    assert m['snapshot_sha256'] and len(f)==1
    monkeypatch.delenv('STOCK_INSIGHTS_AS_OF')
    with pytest.raises(ValueError):service._download('AAPL')


def test_cloud_storage_does_not_silently_fall_back(tmp_path):
    from local_portfolio import configure
    app=Flask('cloud-default');app.config['PORTFOLIO_SQLITE_PATH']=str(tmp_path/'should-not-exist.db');configure(app)
    app.add_url_rule('/api/portfolio/load','load',lambda:('cloud route selected',503))
    r=app.test_client().get('/api/portfolio/load?username=someone')
    assert r.status_code==503 and not (tmp_path/'should-not-exist.db').exists()


def test_missing_unadjusted_valuation_is_withheld():
    f=frame();f.loc[f.index[-1],'RawClose']=np.nan
    assert calc.portfolio({'AAPL':f},{'AAPL':1},{},'AAPL',1000)['status']=='unavailable'


@pytest.mark.parametrize('age,stale,expected,refresh', [
    (30, True, '2024-02-02', False),
    (61, True, '2024-02-02', True),
    (30, False, '2024-02-01', True),
    (899, False, '2024-02-02', False),
])
def test_history_refreshes_delayed_data_and_new_sessions(monkeypatch, age, stale, expected, refresh):
    from concurrent.futures import Future
    f = frame()
    metadata = dict(stale=stale, expected_session=expected)
    monkeypatch.setattr(service, '_cache', {'AAPL': (1000-age, f, metadata)})
    monkeypatch.setattr(service, '_pending', {})
    monkeypatch.setattr(service.time, 'monotonic', lambda: 1000)
    monkeypatch.setattr(service, 'completed_sessions', lambda *a: pd.DatetimeIndex(['2024-02-02']))
    calls = []
    class Pool:
        def submit(self, fn, s):
            calls.append(s)
            future = Future()
            future.set_result((f, dict(metadata, expected_session='2024-02-02', refreshed=True)))
            return future
    monkeypatch.setattr(service, '_pool', Pool())
    _, result = service.history('AAPL')
    assert bool(calls) == refresh
    assert bool(result.get('refreshed')) == refresh


def test_movement_delayed_feeds_use_latest_common_return_session(client, monkeypatch):
    stock, benchmark = frame(), frame(seed=9)
    stock.loc[stock.index[-1], 'Close'] = np.nan
    benchmark.loc[benchmark.index[-2]:, 'Close'] = np.nan
    expected = str(stock.index[-1].date())
    def history(s):
        f = benchmark if s.startswith('^') else stock
        return f, dict(stale=True, expected_session=expected, analysis_mode='live',
                       observation_date=str(f.Close.last_valid_index().date()), coverage={})
    monkeypatch.setattr(service, 'history', history)
    result = client.get('/si/insights/movement?symbol=AAPL').get_json()
    date = benchmark.index[-3]
    reference = calc.movement(stock.loc[:date], benchmark.loc[:date])
    assert result['status'] == 'ready' and result['latest_available_fallback']
    assert result['observation_date'] == str(date.date())
    assert result['coverage']['end'] == result['observation_date']
    assert result['stock_return'] == pytest.approx(reference['stock_return'])
    assert result['benchmark_return'] == pytest.approx(reference['benchmark_return'])
    assert result['robust_score'] == pytest.approx(reference['robust_score'])
    assert 'postdate' in result['news_note']
    assert result['observation_date'] in service.explain(result, 'movement')


def test_portfolio_delayed_holding_uses_common_valuation_not_candidate_date(client, monkeypatch):
    candidate, holding = frame(), frame(seed=12)
    holding.loc[holding.index[-1], ['Close','RawClose']] = np.nan
    expected = str(candidate.index[-1].date())
    def history(s):
        f = candidate if s == 'AAPL' else holding
        return f, dict(stale=s != 'AAPL', expected_session=expected, analysis_mode='live',
                       observation_date=str(f.Close.last_valid_index().date()), coverage={})
    monkeypatch.setattr(service, 'history', history)
    result = client.post('/si/insights/portfolio-fit', json={
        'symbol':'AAPL', 'holdings':[{'symbol':'MSFT','qty':2}], 'amount':1000}).get_json()
    assert result['status'] == 'ready' and result['stale']
    assert result['latest_available_fallback']
    assert result['observation_date'] == result['valuation_date'] == str(holding.index[-2].date())
    assert result['portfolio_value'] == pytest.approx(2*holding.RawClose.iloc[-2])
