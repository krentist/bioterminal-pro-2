"""
Phase K / §1 acceptance tests — the private company entity model.

Proves: a private company can be created by name, valued by rNPV from an (injected) pipeline
with visible assumptions, shown funding + licensing-deal comps, and annotated — with no
price / DCF / backtest / scenario fields anywhere in the view. Also proves the lifecycle tie
to the compliance wall: notes on a company that has gone public route through MNPI triage.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import compliance as _compliance
import entities as _entities
from server import app

client = TestClient(app, raise_server_exceptions=False)


def _fixture_pipeline() -> pd.DataFrame:
    """A small trials frame (full CT.gov column shape) standing in for a live pull."""
    return pd.DataFrame([
        {"nct_id": "NCT00000001", "title": "Lead Asset in Solid Tumors", "phase": "Phase 3",
         "status": "Recruiting", "condition": "Solid Tumor", "start_date": "2024-01-01",
         "primary_completion_date": "2027-01-01", "enrollment": 300, "sponsor": "PrivateBio"},
        {"nct_id": "NCT00000002", "title": "Second Program in Lymphoma", "phase": "Phase 1",
         "status": "Recruiting", "condition": "Lymphoma", "start_date": "2025-01-01",
         "primary_completion_date": "2028-01-01", "enrollment": 40, "sponsor": "PrivateBio"},
    ])


@pytest.fixture(autouse=True)
def _isolated_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTITIES_DB", str(tmp_path / "entities_test.db"))
    monkeypatch.setenv("COMPLIANCE_DB", str(tmp_path / "compliance_test.db"))
    # Keep the live ClinicalTrials.gov fetch out of tests — deterministic pipeline.
    monkeypatch.setattr(_entities, "_fetch_pipeline_raw", lambda company: _fixture_pipeline())
    _entities.clear_all()
    _compliance.clear_all()
    yield
    _entities.clear_all()
    _compliance.clear_all()


def _make_company(**kw):
    body = {"name": "PrivateBio Inc", "ctSponsorName": "PrivateBio", **kw}
    return client.post("/api/company", json=body).json()


# --- creation & listing -----------------------------------------------------

def test_create_and_get_company():
    c = _make_company()
    assert c["id"] and c["listingStatus"] == "private"
    got = client.get(f"/api/company/{c['id']}")
    assert got.status_code == 200


def test_create_requires_name():
    assert client.post("/api/company", json={"ctSponsorName": "X"}).status_code == 400


def test_list_and_search_companies():
    _make_company(name="Alpha Bio")
    _make_company(name="Beta Therapeutics")
    all_c = client.get("/api/company").json()["companies"]
    assert len(all_c) == 2
    found = client.get("/api/company", params={"q": "beta"}).json()["companies"]
    assert len(found) == 1 and "Beta" in found[0]["name"]


# --- valuation (rNPV only, assumptions visible) -----------------------------

def test_company_view_values_pipeline_by_rnpv():
    c = _make_company()
    view = _entities.company_view(c["id"], programs=_fixture_pipeline())
    val = view["valuation"]
    assert val["valuationMethod"] == "rNPV"
    assert val["rnpvTotal"] > 0
    assert len(val["programs"]) == 2
    # assumptions must be visible, not buried
    assert val["assumptions"]["defaultPeakSalesUsd"] > 0
    assert "note" in val["assumptions"]
    # licensing-deal comps present with the 25–35% band ordered low < mid < high
    lc = val["licensingComps"]
    assert lc["low"] < lc["mid"] < lc["high"]


def test_view_has_no_price_or_dcf_fields():
    c = _make_company()
    view = _entities.company_view(c["id"], programs=_fixture_pipeline())
    text = str(view)
    for banned in ("price", "dcf", "backtest", "scenario", "monteCarlo", "impliedSharePrice"):
        assert banned.lower() not in text.lower(), banned


# --- funding comps ----------------------------------------------------------

def test_funding_round_produces_comp():
    c = _make_company()
    r = client.post(f"/api/company/{c['id']}/funding", json={
        "date": "2025-06-01", "roundType": "Series B", "postMoneyUsd": 400_000_000,
        "leadInvestor": "Some VC", "source": "press release",
    })
    assert r.status_code == 200
    view = _entities.company_view(c["id"], programs=_fixture_pipeline())
    fc = view["fundingComps"]
    assert len(fc["rounds"]) == 1
    assert fc["impliedByRnpv"]["lastPostMoneyUsd"] == 400_000_000
    assert fc["impliedByRnpv"]["rnpvVsPostMoney"] is not None


def test_funding_on_missing_company_404():
    assert client.post("/api/company/nope/funding", json={"postMoneyUsd": 1}).status_code == 404


# --- notes / data-room ------------------------------------------------------

def test_private_note_stored_directly_not_restricted():
    c = _make_company()
    r = client.post(f"/api/company/{c['id']}/notes", json={
        "text": "Founder shared preclinical tox data at dinner", "source": "founder dinner",
        "isMaterialNonpublic": True,
    })
    assert r.status_code == 200
    assert r.json()["routedToComplianceWall"] is False
    view = _entities.company_view(c["id"], programs=_fixture_pipeline())
    assert len(view["notes"]) == 1


def test_public_company_note_routes_through_compliance_wall():
    # A company that has IPO'd has a tradable security → MNPI triage must apply.
    c = _make_company(name="NowPublic Bio", listingStatus="public", linkedTicker="NPUB")
    r = client.post(f"/api/company/{c['id']}/notes", json={
        "text": "CEO hinted at a trial miss", "isMaterialNonpublic": True,
    })
    assert r.status_code == 200
    assert r.json()["routedToComplianceWall"] is True
    assert _compliance.is_restricted("NPUB")
    # and the signal for that now-restricted ticker is suppressed
    assert client.get("/api/confidence/NPUB").json().get("restricted") is True


def test_note_requires_text():
    c = _make_company()
    assert client.post(f"/api/company/{c['id']}/notes", json={"source": "x"}).status_code == 400


# --- middleware: company ids are not rejected as bad tickers -----------------

def test_company_id_not_rejected_by_ticker_validator():
    c = _make_company()
    # a 12-char lowercase hex id would fail the ticker regex if the middleware applied it
    assert client.get(f"/api/company/{c['id']}").status_code in (200, 502)
    assert client.get("/api/company/doesnotexist99").status_code == 404
