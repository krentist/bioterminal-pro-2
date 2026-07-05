"""
Phase L / §2 acceptance tests — public-side institutional depth.

Covers trial-level depth surfaced in /api/trials (endpoints, comparator, enrollment type),
the competitive-landscape route, and insider transactions added to ownership. All
deterministic: ClinicalTrials.gov and yfinance are patched with small fixtures.
"""
import pandas as pd

import data_fetcher as dfm
import server as _srv
from server import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


def _own_trials() -> pd.DataFrame:
    return pd.DataFrame([
        {"nct_id": "NCT1", "title": "Lead in NSCLC", "phase": "Phase 3", "status": "RECRUITING",
         "condition": "Non-Small Cell Lung Cancer", "start_date": "2024-01-01",
         "primary_completion_date": "2027-06-01", "enrollment": 500, "enrollment_type": "ESTIMATED",
         "sponsor": "Moderna, Inc.", "primary_endpoint": "Overall Survival",
         "interventions": "mRNA-4157, pembrolizumab", "comparator": "Placebo",
         "primary_purpose": "TREATMENT"},
    ])


def _rivals() -> pd.DataFrame:
    common = {"condition": "Non-Small Cell Lung Cancer", "start_date": "2025-01-01",
              "primary_completion_date": "2028-01-01", "enrollment_type": "ESTIMATED",
              "primary_endpoint": "PFS", "interventions": "x", "comparator": None,
              "primary_purpose": "TREATMENT"}
    return pd.DataFrame([
        {"nct_id": "NCT2", "title": "Rival A Ph3", "phase": "Phase 3", "status": "RECRUITING",
         "enrollment": 400, "sponsor": "BioNTech SE", **common},
        {"nct_id": "NCT3", "title": "Rival B Ph1", "phase": "Phase 1", "status": "RECRUITING",
         "enrollment": 30, "sponsor": "Pfizer Inc.", **common},
        {"nct_id": "NCT4", "title": "Own dup", "phase": "Phase 2", "status": "RECRUITING",
         "enrollment": 100, "sponsor": "Moderna, Inc.", **common},
        {"nct_id": "NCT5", "title": "BioNTech earlier", "phase": "Phase 1", "status": "RECRUITING",
         "enrollment": 20, "sponsor": "BioNTech SE", **common},
        # Academic + investigator studies that must be filtered out of a competitive set:
        {"nct_id": "NCT6", "title": "Academic Ph3", "phase": "Phase 3", "status": "RECRUITING",
         "enrollment": 200, "sponsor": "Harvard University", **common},
        {"nct_id": "NCT7", "title": "PI-led", "phase": "Phase 3", "status": "RECRUITING",
         "enrollment": 50, "sponsor": "john smith", **common},
    ])


# --- L1: trial-level depth --------------------------------------------------

def test_trials_route_surfaces_depth(monkeypatch):
    monkeypatch.setattr(_srv, "fetch_clinicaltrials", lambda t: _own_trials())
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "Moderna, Inc."})
    t = client.get("/api/trials/MRNA").json()["trials"][0]
    assert t["primaryEndpoint"] == "Overall Survival"
    assert t["enrollmentType"] == "ESTIMATED"
    assert t["comparator"] == "Placebo"
    assert t["hasComparator"] is True
    assert "pembrolizumab" in t["interventions"]
    assert t["primaryPurpose"] == "TREATMENT"


# --- L2: competitive landscape ----------------------------------------------

def test_competition_lists_rivals_deduped_and_ranked(monkeypatch):
    _srv._COMPETITION_CACHE.clear()
    monkeypatch.setattr(_srv, "fetch_clinicaltrials", lambda t: _own_trials())
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "Moderna, Inc."})
    monkeypatch.setattr(_srv.df_mod, "fetch_clinicaltrials_by_condition",
                        lambda cond, page_size=60: _rivals())
    d = client.get("/api/competition/MRNA").json()

    assert d["indication"] == "Non-Small Cell Lung Cancer"
    assert d["leadPhase"] == "Phase 3"
    sponsors = [c["sponsor"] for c in d["competitors"]]
    # our own sponsor is excluded from the competitive set
    assert all("moderna" not in s.lower() for s in sponsors)
    # one (most-advanced) row per rival sponsor
    assert sponsors.count("BioNTech SE") == 1
    biontech = next(c for c in d["competitors"] if c["sponsor"] == "BioNTech SE")
    assert biontech["phase"] == "Phase 3"
    # ranked by phase, most advanced first
    assert sponsors.index("BioNTech SE") < sponsors.index("Pfizer Inc.")
    # academic + investigator sponsors are excluded from the commercial competitive set
    assert not any("univers" in s.lower() or s == s.lower() for s in sponsors)
    assert d["competitorCount"] == 2
    assert d["source"] == "ClinicalTrials.gov"


def test_competition_empty_pipeline(monkeypatch):
    _srv._COMPETITION_CACHE.clear()
    monkeypatch.setattr(_srv, "fetch_clinicaltrials", lambda t: dfm._empty_trials_df())
    d = client.get("/api/competition/ZZZZ").json()
    assert d["competitors"] == []


# --- L3: insider transactions in ownership ----------------------------------

class _FakeTickerInsider:
    institutional_holders = None
    insider_transactions = pd.DataFrame([
        {"Start Date": pd.Timestamp("2026-05-01"), "Insider": "Jane Doe", "Position": "CEO",
         "Transaction": "Sale", "Shares": 10000, "Value": 500000},
        {"Start Date": pd.Timestamp("2026-04-15"), "Insider": "John Roe", "Position": "Director",
         "Transaction": "Buy", "Shares": 2000, "Value": 90000},
    ])

    def __init__(self, *_a, **_k):
        pass


def test_ownership_includes_insider_transactions(monkeypatch):
    monkeypatch.setattr(dfm, "_cached_yf_info", lambda t: {"heldPercentInstitutions": 0.7})
    monkeypatch.setattr(dfm.yf, "Ticker", _FakeTickerInsider)
    dfm._OWNERSHIP_CACHE.clear()
    r = dfm.get_ownership("TESTINS")
    txns = r["insiderTransactions"]
    assert isinstance(txns, list) and len(txns) == 2
    assert txns[0]["insider"] == "Jane Doe"
    assert txns[0]["transaction"] == "Sale"
    assert txns[0]["shares"] == 10000
    assert txns[0]["date"] == "2026-05-01"


def test_ownership_insider_absent_is_empty_list(monkeypatch):
    # yfinance with no insider table (attribute missing) → empty list, not an error.
    class _Bare:
        institutional_holders = None
        def __init__(self, *_a, **_k): pass
    monkeypatch.setattr(dfm, "_cached_yf_info", lambda t: {"heldPercentInstitutions": 0.3})
    monkeypatch.setattr(dfm.yf, "Ticker", _Bare)
    dfm._OWNERSHIP_CACHE.clear()
    r = dfm.get_ownership("TESTINS2")
    assert r["insiderTransactions"] == []
