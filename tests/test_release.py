"""Production release regressions, without network or model dependencies."""
import re
import pytest
from app import app, APP_COMMIT
from modules.modules import Chatterbot, FDCalculatorBot, SipChatterbot


def test_calculators():
    assert Chatterbot()._calculate_emi(12000, 0, 1) == (1000, 12000, 0)
    assert Chatterbot()._calculate_emi(1000000, 8.5, 10)[0] == pytest.approx(12398.57, abs=.01)
    assert FDCalculatorBot()._calculate_maturity(100000, 7, 365 * 5) == round(100000 * (1 + .07 / 4) ** 20, 2)
    assert SipChatterbot()._sip_calculator(1000, 1, 0) == (12000, 12000, 0)


def test_release_identity_and_health():
    client = app.test_client()
    assert client.get('/health').status_code == 200
    response = client.get('/api/version')
    assert response.json == {'commit': APP_COMMIT}
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('view', ['desktop', 'mobile'])
def test_templates_have_versioned_local_assets(view):
    response = app.test_client().get('/?view=' + view)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assets = re.findall(r'(?:src|href)="(/static/[^"?]+\.(?:js|css))([^" ]*)"', html)
    assert len(assets) >= 5
    assert all('v=' + APP_COMMIT in query for _, query in assets)


def test_debug_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    assert app.test_client().get('/api/portfolio/debug?username=someone').status_code == 404


def test_retired_artifacts_and_missing_models(monkeypatch, tmp_path):
    import engine.inference_service as research
    monkeypatch.setattr(research, 'ART', tmp_path)
    assert research.get_forecast_for_symbol('AAPL')['status'] == 'unavailable'
    assert research.simulate_forecast_whatif('AAPL', 0)['status'] == 'unavailable'
    assert research.get_benchmark_results()['status'] == 'unavailable'
    for artifact in ['paper', 'rebuttal', 'presentation']:
        assert app.test_client().get('/download/' + artifact).status_code == 410


def test_dashboard_serializes_provider_missing_numbers_as_null(monkeypatch):
    import json
    import numpy as np
    import stock_service
    monkeypatch.setattr(stock_service, 'get_full_dashboard', lambda symbol: {
        'symbol': symbol,
        'quote': {'current': 2535.0},
        'metrics': {'market_cap': float('nan'), 'beta': float('inf')},
        'profile': {'employees': np.int64(500)},
        'analyst': {'targets': [np.float32('nan'), float('-inf'), 100.25]},
    })
    response = app.test_client().get('/si/dashboard?symbol=TCS.NS')
    assert response.status_code == 200
    def reject_constant(value):
        raise AssertionError('Invalid JSON number: ' + value)
    data = json.loads(response.data, parse_constant=reject_constant)
    assert data['quote']['current'] == 2535.0
    assert data['metrics'] == {'market_cap': None, 'beta': None}
    assert data['profile']['employees'] == 500
    assert data['analyst']['targets'] == [None, None, 100.25]


@pytest.mark.parametrize('closes,expected', [
    ([100, float('nan'), 105, float('inf'), float('nan')], 105),
    ([float('nan'), 0, float('inf'), -1, float('nan')], None),
])
def test_quote_ignores_empty_provider_rows(monkeypatch, closes, expected):
    import pandas as pd
    import stock_service
    from types import SimpleNamespace
    history = pd.DataFrame({'Close': closes, 'Open': closes, 'High': closes,
                            'Low': closes, 'Volume': [float('nan')] * len(closes)},
                           index=pd.date_range('2026-10-20', periods=len(closes)))
    monkeypatch.setattr(stock_service, '_cache', {})
    monkeypatch.setattr(stock_service, '_twelve_data_quote', lambda symbol: None)
    monkeypatch.setattr(stock_service, '_get_ticker_data', lambda symbol: {'info': {}})
    monkeypatch.setattr(stock_service.yf, 'Ticker', lambda symbol: SimpleNamespace(history=lambda **kw: history))
    quote = stock_service.get_quote('TCS.NS')
    if expected is None:
        assert 'error' in quote
        response = app.test_client().get('/si/quote?symbol=TCS.NS')
        assert response.status_code == 502
        assert response.json['error']
    else:
        assert quote['current'] == expected
        assert quote['prev_close'] == 100
        assert quote['change_pct'] == 5
        assert quote['volume'] is None


def test_metrics_skip_nonfinite_primary_values(monkeypatch):
    import stock_service
    from types import SimpleNamespace
    monkeypatch.setattr(stock_service, '_cache', {})
    monkeypatch.setattr(stock_service, '_twelve_data_statistics', lambda symbol: {'pe_ratio': float('nan')})
    monkeypatch.setattr(stock_service, '_get_ticker_data', lambda symbol: {'info': {'trailingPE': 20.1234, 'returnOnEquity': .1}})
    monkeypatch.setattr(stock_service.yf, 'Ticker', lambda symbol: SimpleNamespace(fast_info=SimpleNamespace(market_cap=float('inf'), year_high=None, year_low=None)))
    metrics = stock_service.get_metrics('TCS.NS')
    assert metrics['pe_ratio'] == 20.1234
    assert metrics['market_cap'] is None
    assert stock_service._safe(float('inf')) is None
