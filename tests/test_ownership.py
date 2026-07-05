"""Offline tests for data_fetcher.get_ownership (short-interest derivation)."""
import data_fetcher as dfm


class _FakeTicker:
    institutional_holders = None

    def __init__(self, *_a, **_k):
        pass


def _patch(monkeypatch, info):
    monkeypatch.setattr(dfm, "_cached_yf_info", lambda t: info)
    monkeypatch.setattr(dfm.yf, "Ticker", _FakeTicker)
    dfm._OWNERSHIP_CACHE.clear()


def test_short_interest_change_and_date(monkeypatch):
    _patch(monkeypatch, {
        "sharesShort": 110, "sharesShortPriorMonth": 100,
        "shortPercentOfFloat": 0.20, "shortRatio": 5.0,
        "dateShortInterest": 1750000000, "heldPercentInstitutions": 0.8,
    })
    r = dfm.get_ownership("TESTOWNA")
    assert abs(r["shortInterestChangePct"] - 0.10) < 1e-9
    assert r["daysToCover"] == 5.0
    assert isinstance(r["dateShortInterest"], str) and len(r["dateShortInterest"]) == 10
    assert r["topInstitutions"] == []


def test_missing_short_interest_is_none(monkeypatch):
    # HK-style: ownership present, short interest absent.
    _patch(monkeypatch, {
        "heldPercentInstitutions": 0.28, "heldPercentInsiders": 0.14,
        "sharesShort": None, "sharesShortPriorMonth": None,
    })
    r = dfm.get_ownership("TESTOWNB")
    assert r["shortInterestChangePct"] is None
    assert r["shortPctOfFloat"] is None
    assert r["heldPctInstitutions"] == 0.28


def test_zero_prior_month_does_not_divide_by_zero(monkeypatch):
    _patch(monkeypatch, {"sharesShort": 100, "sharesShortPriorMonth": 0})
    r = dfm.get_ownership("TESTOWNC")
    assert r["shortInterestChangePct"] is None
