"""
Phase N / §4 acceptance tests — provenance & credibility hardening.

Two guarantees:
  1. Provenance — every data surface carries a `source` (and an as-of / retrieved-at stamp
     where a timestamp is meaningful).
  2. No fabrication — missing numbers render as null / honest "not available", never a
     fabricated 0 or default presented as fact.
"""
import math

import pandas as pd
import data_fetcher as dfm
import dual_listing as dl
import server as _srv
from server import app, _epoch_to_iso, _safe, _to_json_safe
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


# ── Provenance on core market-data routes (deterministic via patched upstream) ──

def test_quote_carries_source_and_asof(monkeypatch):
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {
        "regularMarketPrice": 10.0, "regularMarketPreviousClose": 9.0,
        "currency": "USD", "regularMarketTime": 1_700_000_000,
    })
    d = client.get("/api/quote/TEST").json()
    assert d["source"] == "Yahoo Finance"
    assert isinstance(d["asOf"], str) and d["asOf"].endswith("Z")


def test_fundamentals_carries_source(monkeypatch):
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {
        "currency": "USD", "longName": "Test", "regularMarketTime": 1_700_000_000,
    })
    d = client.get("/api/fundamentals/TEST").json()
    assert d["source"] == "Yahoo Finance"
    assert d["asOf"].endswith("Z")


def test_trials_carries_source(monkeypatch):
    fixture = pd.DataFrame([{
        "nct_id": "NCT1", "title": "T", "phase": "Phase 2", "status": "RECRUITING",
        "condition": "X", "start_date": "2024-01-01", "primary_completion_date": "2027-01-01",
        "enrollment": 100, "sponsor": "Test",
    }])
    monkeypatch.setattr(_srv, "fetch_clinicaltrials", lambda t: fixture)
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "Test"})
    d = client.get("/api/trials/TEST").json()
    assert d["source"] == "ClinicalTrials.gov"
    assert d["retrievedAt"].endswith("Z")


def test_ownership_carries_source(monkeypatch):
    class _Fake:
        institutional_holders = None
        def __init__(self, *_a, **_k): pass
    monkeypatch.setattr(dfm, "_cached_yf_info", lambda t: {"heldPercentInstitutions": 0.5})
    monkeypatch.setattr(dfm.yf, "Ticker", _Fake)
    dfm._OWNERSHIP_CACHE.clear()
    r = dfm.get_ownership("TESTPROV")
    assert r["source"] == "Yahoo Finance"
    assert r["retrievedAt"].endswith("Z")


def test_cross_border_and_competition_and_nmpa_carry_source(monkeypatch):
    monkeypatch.setattr(dl, "_fetch_price", lambda tk: {"6160.HK": 150.0, "ONC": 200.0, "688235.SS": 260.0}.get(tk.upper()))
    monkeypatch.setattr(dl, "_usdhkd_rate", lambda: 7.8)
    monkeypatch.setattr(dl, "_usdcny_rate", lambda: 7.2)
    assert dl.get_cross_border_info("6160.HK")["source"] == "Yahoo Finance"

    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "X"})
    n = client.get("/api/nmpa/688180.SS").json()
    assert n["source"] and n["status"] == "not_available"


# ── No fabrication: missing values stay null, never a default ──────────────────

def test_safe_returns_none_not_zero():
    assert _safe(None) is None
    assert _safe(float("nan")) is None
    assert _safe(float("inf")) is None
    assert _safe(0) == 0            # a real zero is preserved
    assert _safe(3.14) == 3.14


def test_to_json_safe_nulls_nan_inf():
    out = _to_json_safe({"a": float("nan"), "b": [float("inf"), 1.0], "c": 2})
    assert out["a"] is None
    assert out["b"] == [None, 1.0]
    assert out["c"] == 2


def test_epoch_to_iso_honest():
    assert _epoch_to_iso(1_700_000_000).endswith("Z")
    assert _epoch_to_iso(0) is None
    assert _epoch_to_iso(None) is None
    assert _epoch_to_iso(-5) is None


def test_missing_short_interest_not_fabricated(monkeypatch):
    class _Fake:
        institutional_holders = None
        def __init__(self, *_a, **_k): pass
    monkeypatch.setattr(dfm, "_cached_yf_info", lambda t: {"heldPercentInstitutions": 0.3})
    monkeypatch.setattr(dfm.yf, "Ticker", _Fake)
    dfm._OWNERSHIP_CACHE.clear()
    r = dfm.get_ownership("TESTPROV2")
    # absent short interest must be null, not 0
    assert r["sharesShort"] is None
    assert r["shortPctOfFloat"] is None
    assert r["shortInterestChangePct"] is None


def test_cross_border_none_not_fabricated_for_unknown():
    assert dl.get_cross_border_info("MRNA") is None


def test_math_no_nan_leaks_in_safe():
    # a NaN must never survive as a numeric in a response
    assert _safe(math.nan) is None
