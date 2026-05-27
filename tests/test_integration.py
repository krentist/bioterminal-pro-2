"""Integration tests — hit the live FastAPI app via TestClient."""
from fastapi.testclient import TestClient

from server import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Quote endpoint
# ---------------------------------------------------------------------------

def test_quote_mrna_status_200():
    r = client.get("/api/quote/MRNA")
    assert r.status_code == 200


def test_quote_mrna_response_shape():
    r = client.get("/api/quote/MRNA")
    data = r.json()
    assert "price" in data
    assert "changePercent" in data
    assert "currency" in data
    assert "currencySymbol" in data


def test_quote_mrna_price_is_positive():
    r = client.get("/api/quote/MRNA")
    data = r.json()
    assert data["price"] is not None
    assert data["price"] > 0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_invalid_ticker_special_chars_returns_400():
    r = client.get("/api/quote/DROP__TABLE")
    assert r.status_code == 400


def test_ticker_too_long_returns_400():
    r = client.get("/api/quote/TOOLONGTICKER1")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Dual-listing endpoint
# ---------------------------------------------------------------------------

def test_dual_listing_zai_lab():
    r = client.get("/api/dual-listing/9688.HK")
    assert r.status_code == 200
    data = r.json()
    assert data["dual_listed"] is True
    assert data["us_ticker"] == "ZLAB"
    assert data["hk_ticker"] == "9688.HK"
    assert data["premium_discount_pct"] is not None


def test_dual_listing_non_dual_listed():
    r = client.get("/api/dual-listing/MRNA")
    assert r.status_code == 200
    data = r.json()
    assert data["dual_listed"] is False


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def test_docs_are_public():
    r = client.get("/api/docs")
    assert r.status_code == 200


def test_spa_fallback_serves_index():
    r = client.get("/")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------

def test_request_id_header_present():
    r = client.get("/api/quote/MRNA")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) == 8
