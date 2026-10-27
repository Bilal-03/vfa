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
