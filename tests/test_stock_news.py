from datetime import datetime, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from xml.sax.saxutils import escape
import pytest
import stock_service as service


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(service, '_cache', {})


def test_empty_yahoo_uses_real_fallback_and_deduplicates(monkeypatch):
    monkeypatch.setattr(service.yf, 'Ticker', lambda s: SimpleNamespace(get_news=lambda **kw: []))
    article = dict(headline='Company earnings', url='https://example.com/article',
                   source='Publisher', datetime=service.time.time(), summary='')
    calls = []
    monkeypatch.setattr(service, '_google_stock_news', lambda s: calls.append(s) or [article, dict(article)])
    result = service.get_news('TCS.NS')
    assert result['status'] == 'ready' and result['count'] == 1
    assert result['provider'] == 'Google News RSS'
    assert service.get_news('TCS.NS') == result and calls == ['TCS.NS']


def test_yahoo_new_format_and_no_unnecessary_fallback(monkeypatch):
    entry = {'content': {'title': 'Financial report', 'canonicalUrl': {'url': 'https://example.com/report'},
                         'pubDate': datetime.now(timezone.utc).isoformat(), 'provider': {'displayName': 'Publisher'}}}
    monkeypatch.setattr(service.yf, 'Ticker', lambda s: SimpleNamespace(get_news=lambda **kw: [entry]))
    monkeypatch.setattr(service, '_google_stock_news', lambda s: pytest.fail('Fallback should not be called'))
    result = service.get_news('AAPL')
    assert result['provider'] == 'Yahoo Finance' and result['count'] == 1


def test_failed_providers_do_not_claim_no_news(monkeypatch):
    def fail(*a, **kw): raise TimeoutError()
    monkeypatch.setattr(service.yf, 'Ticker', fail)
    monkeypatch.setattr(service, '_google_stock_news', fail)
    result = service.get_news('AAPL')
    assert result['status'] == 'unavailable' and result['articles'] == []
    assert service._cache['news:AAPL']['ttl'] == 60


@pytest.mark.parametrize('symbol,name,region', [('TCS.NS', 'Tata Consultancy Services', 'IN'), ('AAPL','Apple','US')])
def test_rss_company_query_dates_and_safe_links(monkeypatch, symbol, name, region):
    now = service.time.time()
    def item(title, stamp, url='https://news.google.com/rss/articles/example'):
        date = format_datetime(datetime.fromtimestamp(stamp, timezone.utc))
        return f'<item><title>{escape(title)} - Publisher</title><link>{escape(url)}</link><pubDate>{date}</pubDate><source>Publisher</source></item>'
    xml = '<rss><channel>' + item(name+' report', now-3600) + item('Old report', now-8*86400) + item('Future report', now+86400) + item('Unsafe link', now-3600, 'javascript:alert(1)') + '</channel></rss>'
    def get(url, **kw):
        assert name in kw['params']['q'] and kw['params']['gl'] == region
        assert kw['timeout'] == 6
        return SimpleNamespace(content=xml.encode(), raise_for_status=lambda: None)
    monkeypatch.setattr(service.requests, 'get', get)
    articles = service._google_stock_news(symbol)
    assert len(articles) == 1 and articles[0]['headline'] == name+' report'
    assert articles[0]['source'] == 'Publisher'


def test_rss_excludes_unrelated_company_and_normalizes_syndicated_titles(monkeypatch):
    now=service.time.time()
    def item(title):
        return '<item><title>'+escape(title)+'</title><link>https://example.com/news</link><pubDate>'+format_datetime(datetime.fromtimestamp(now-100,timezone.utc))+'</pubDate><source>Publisher</source></item>'
    xml='<rss><channel>'+item('EverestIMS share price')+item('TCS earnings rise')+item('TCS earnings rise —')+'</channel></rss>'
    monkeypatch.setattr(service.requests,'get',lambda *a,**kw:SimpleNamespace(content=xml.encode(),raise_for_status=lambda:None))
    articles=service._google_stock_news('TCS.NS')
    assert len(articles)==2 and all('TCS' in a['headline'] for a in articles)
    monkeypatch.setattr(service.yf,'Ticker',lambda s:SimpleNamespace(get_news=lambda **kw:[]))
    result=service.get_news('TCS.NS')
    assert result['count']==1
