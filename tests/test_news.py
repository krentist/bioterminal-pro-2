"""
Tests for fetch_yfinance_news — news coverage via get_news(tab="all").

The bare yfinance .news property returns [] for some tickers (e.g. HK biotechs like 6628.HK)
even when Yahoo has news, because their news is press releases surfaced only under tab="all".
These tests lock in the tab="all" primary path plus fallbacks, deterministically (no network).
"""
import data_fetcher as dfm


class _FakeTicker:
    def __init__(self, get_items=None, news_items=None, raise_get=False):
        self._g = get_items or []
        self._n = news_items or []
        self._raise = raise_get

    def get_news(self, count=10, tab="all"):
        if self._raise:
            raise AttributeError("older yfinance has no get_news")
        return self._g

    @property
    def news(self):
        return self._n


def _nested(title, url="https://example/x"):
    return {"content": {
        "title": title, "pubDate": "2026-04-23T11:00:00Z",
        "provider": {"displayName": "GlobeNewswire"},
        "canonicalUrl": {"url": url}, "summary": "summary",
    }}


def test_uses_get_news_tab_all(monkeypatch):
    ft = _FakeTicker(get_items=[_nested("Transcenta presents Phase I/II data")])
    monkeypatch.setattr(dfm.yf, "Ticker", lambda t: ft)
    df = dfm.fetch_yfinance_news("6628.HK", limit=10)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["title"] == "Transcenta presents Phase I/II data"
    assert row["source"] == "GlobeNewswire"
    assert row["url"] == "https://example/x"


def test_falls_back_to_dot_news_when_get_news_empty(monkeypatch):
    ft = _FakeTicker(get_items=[], news_items=[_nested("Legacy item")])
    monkeypatch.setattr(dfm.yf, "Ticker", lambda t: ft)
    df = dfm.fetch_yfinance_news("X", limit=10)
    assert len(df) == 1 and df.iloc[0]["title"] == "Legacy item"


def test_falls_back_when_get_news_missing(monkeypatch):
    ft = _FakeTicker(raise_get=True, news_items=[_nested("Old-yfinance item")])
    monkeypatch.setattr(dfm.yf, "Ticker", lambda t: ft)
    df = dfm.fetch_yfinance_news("X", limit=10)
    assert len(df) == 1 and df.iloc[0]["title"] == "Old-yfinance item"


def test_empty_everywhere_yields_empty_df(monkeypatch):
    ft = _FakeTicker(get_items=[], news_items=[])
    monkeypatch.setattr(dfm.yf, "Ticker", lambda t: ft)
    df = dfm.fetch_yfinance_news("X", limit=10)
    assert df.empty
    assert list(df.columns) == ["date", "title", "source", "url", "summary"]
