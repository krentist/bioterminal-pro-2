"""
Phase J / §0 acceptance tests — the MNPI compliance wall.

Proves the hard invariant: when a user logs potential material non-public information on a
public ticker, that ticker is restricted, every trade-oriented signal for it is suppressed,
an audit entry is written, and the note's free text never appears in any signal response.
"""
import time

import pytest
from fastapi.testclient import TestClient

import compliance as _compliance
import server as _srv
from server import app

client = TestClient(app, raise_server_exceptions=False)

SECRET = "CFO_SAID_PHASE3_WILL_MISS_PRIMARY_ENDPOINT_XYZZY"
TICKER = "FAKECO"


@pytest.fixture(autouse=True)
def _isolated_compliance_db(tmp_path, monkeypatch):
    """Point the compliance store at a throwaway DB and clear caches around each test."""
    monkeypatch.setenv("COMPLIANCE_DB", str(tmp_path / "compliance_test.db"))
    _compliance.clear_all()
    _srv._SCREEN_CACHE.clear()
    _srv._CONFIDENCE_CACHE.clear()
    _srv._BACKTEST_CACHE.clear()
    yield
    _compliance.clear_all()


def _log_mnpi_note():
    return client.post("/api/notes", json={
        "subject": "FakeCo Ltd",
        "subjectTicker": TICKER,
        "source": "CFO at investor dinner",
        "text": SECRET,
        "isPublicSubject": True,
        "isMaterialNonpublic": True,
    })


# --- triage & restriction ---------------------------------------------------

def test_mnpi_note_restricts_ticker():
    r = _log_mnpi_note()
    assert r.status_code == 200
    assert r.json()["restrictedTriggered"] is True
    assert _compliance.is_restricted(TICKER)
    listed = client.get("/api/restricted").json()["restricted"]
    assert any(x["ticker"] == TICKER for x in listed)


def test_audit_entry_written_on_restrict():
    _log_mnpi_note()
    audit = client.get("/api/compliance/audit").json()["audit"]
    assert any(a["action"] == "restrict" and a["ticker"] == TICKER for a in audit)


# --- signal suppression -----------------------------------------------------

def test_signals_suppressed_for_restricted_ticker():
    _log_mnpi_note()
    for path in (
        f"/api/confidence/{TICKER}",
        f"/api/dcf/{TICKER}",
        f"/api/rnpv/{TICKER}",
        f"/api/scenarios/{TICKER}",
        f"/api/backtest/{TICKER}",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert resp.json().get("restricted") is True, path

    conf = client.get(f"/api/confidence/{TICKER}").json()
    assert conf["signal"] == "RESTRICTED"
    assert conf["score"] is None


def test_dcf_post_also_suppressed():
    _log_mnpi_note()
    resp = client.post(f"/api/dcf/{TICKER}", json={"growthRate": 0.2})
    assert resp.status_code == 200
    assert resp.json().get("restricted") is True


def test_note_text_never_appears_in_signal_responses():
    _log_mnpi_note()
    for path in (
        f"/api/confidence/{TICKER}",
        f"/api/dcf/{TICKER}",
        f"/api/rnpv/{TICKER}",
        f"/api/scenarios/{TICKER}",
        f"/api/backtest/{TICKER}",
    ):
        assert SECRET not in client.get(path).text, path
    # Provenance-safe notes listing must not carry the free text either.
    assert SECRET not in client.get("/api/notes").text


def test_screener_excludes_restricted_ticker():
    _log_mnpi_note()
    _srv._SCREEN_CACHE["US"] = ({
        "region": "US",
        "results": [
            {"rank": 1, "ticker": TICKER, "totalScore": 9},
            {"rank": 2, "ticker": "SAFECO", "totalScore": 8},
        ],
        "cachedAt": None,
    }, time.monotonic())
    tickers = [r["ticker"] for r in client.get("/api/screen?region=US").json()["results"]]
    assert TICKER not in tickers
    assert "SAFECO" in tickers


# --- negative cases: no over-restriction ------------------------------------

def test_public_but_not_material_does_not_restrict():
    r = client.post("/api/notes", json={
        "subject": "FakeCo", "subjectTicker": TICKER, "text": "already public info",
        "isPublicSubject": True, "isMaterialNonpublic": False,
    })
    assert r.json()["restrictedTriggered"] is False
    assert not _compliance.is_restricted(TICKER)


def test_private_company_note_does_not_restrict():
    # A private company has no tradable security to abuse — material info is legitimate.
    r = client.post("/api/notes", json={
        "subject": "PrivateBio (Series B)", "text": SECRET,
        "isPublicSubject": False, "isMaterialNonpublic": True,
    })
    assert r.json()["restrictedTriggered"] is False


# --- lifting ----------------------------------------------------------------

def test_lift_restriction_clears_and_audits():
    _log_mnpi_note()
    assert _compliance.is_restricted(TICKER)
    r = client.post(f"/api/restricted/{TICKER}/lift")
    assert r.status_code == 200
    assert not _compliance.is_restricted(TICKER)
    audit = client.get("/api/compliance/audit").json()["audit"]
    assert any(a["action"] == "lift" and a["ticker"] == TICKER for a in audit)


def test_lift_unrestricted_ticker_404():
    assert client.post(f"/api/restricted/{TICKER}/lift").status_code == 404


# --- validation & provenance-safe listing -----------------------------------

def test_note_requires_subject_and_text():
    assert client.post("/api/notes", json={"subject": "X"}).status_code == 400
    assert client.post("/api/notes", json={"text": "Y"}).status_code == 400


def test_notes_listing_omits_free_text_field():
    _log_mnpi_note()
    notes = client.get("/api/notes").json()["notes"]
    assert len(notes) >= 1
    assert "freeText" not in notes[0] and "text" not in notes[0]
    assert notes[0]["subjectTicker"] == TICKER
