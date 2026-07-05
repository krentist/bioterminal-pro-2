"""
Phase M / §3 acceptance tests — China (NMPA) + cross-border.

Covers CN exchange-adapter routing/normalisation, the A/H/US cross-border valuation
(prices patched for determinism), and the honest NMPA not-available deep-link endpoint.
"""
import dual_listing as dl
import server as _srv
from exchanges import get_exchange_adapter, CNExchangeAdapter
from server import app
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


# --- CN adapter: routing + normalisation ------------------------------------

def test_factory_routes_china_tickers():
    assert get_exchange_adapter("688235.SS").get_region() == "CN"
    assert get_exchange_adapter("300760.SZ").get_region() == "CN"
    assert get_exchange_adapter("600276").get_region() == "CN"    # bare 6-digit A-share
    # existing routing is unchanged
    assert get_exchange_adapter("6160.HK").get_region() == "HK"
    assert get_exchange_adapter("700").get_region() == "HK"       # bare ≤5-digit HK
    assert get_exchange_adapter("MRNA").get_region() == "US"


def test_cn_normalize_ticker():
    a = CNExchangeAdapter()
    assert a._normalize_ticker("600276.SS") == "600276.SS"
    assert a._normalize_ticker("688180.ss") == "688180.SS"
    assert a._normalize_ticker("600276") == "600276.SS"   # SSE prefix
    assert a._normalize_ticker("300760") == "300760.SZ"   # ChiNext / SZSE prefix
    assert a._normalize_ticker("000001") == "000001.SZ"


# --- Cross-border A/H/US ------------------------------------------------------

def _patch_prices(monkeypatch):
    prices = {"6160.HK": 156.0, "ONC": 200.0, "688235.SS": 259.2}
    monkeypatch.setattr(dl, "_fetch_price", lambda tk: prices.get(tk.upper()))
    monkeypatch.setattr(dl, "_usdhkd_rate", lambda: 7.8)
    monkeypatch.setattr(dl, "_usdcny_rate", lambda: 7.2)


def test_cross_border_three_legs_priced_and_referenced(monkeypatch):
    _patch_prices(monkeypatch)
    d = dl.get_cross_border_info("6160.HK")
    assert d["cross_border"] is True
    assert d["listedExchanges"] == ["CN", "HK", "US"]
    legs = {l["exchange"]: l for l in d["legs"]}
    # HK is the reference leg → 0% premium; per-share USD = 156/7.8 = 20.0
    assert d["referenceExchange"] == "HK"
    assert legs["HK"]["pricePerShareUsd"] == 20.0
    assert legs["HK"]["premiumVsRefPct"] == 0.0
    # US ADS = 13 ordinary shares → 200/13 = 15.3846 USD/share
    assert legs["US"]["adsRatio"] == 13.0
    assert abs(legs["US"]["pricePerShareUsd"] - 15.3846) < 1e-3
    # CN = 259.2/7.2 = 36.0 USD/share → +80% vs HK
    assert legs["CN"]["pricePerShareUsd"] == 36.0
    assert legs["CN"]["premiumVsRefPct"] == 80.0


def test_cross_border_two_legs_no_us(monkeypatch):
    monkeypatch.setattr(dl, "_fetch_price", lambda tk: {"1877.HK": 39.0, "688180.SS": 43.2}.get(tk.upper()))
    monkeypatch.setattr(dl, "_usdhkd_rate", lambda: 7.8)
    monkeypatch.setattr(dl, "_usdcny_rate", lambda: 7.2)
    d = dl.get_cross_border_info("688180.SS")   # look up from the A-share leg
    assert d["name"] == "Shanghai Junshi Biosciences"
    assert d["listedExchanges"] == ["CN", "HK"]
    assert all(l["exchange"] != "US" for l in d["legs"])


def test_cross_border_none_for_unknown():
    assert dl.get_cross_border_info("MRNA") is None


def test_cross_border_route(monkeypatch):
    _patch_prices(monkeypatch)
    r = client.get("/api/cross-border/6160.HK")
    assert r.status_code == 200 and r.json()["cross_border"] is True
    r2 = client.get("/api/cross-border/MRNA")
    assert r2.json()["cross_border"] is False


# --- NMPA honest deep-link ---------------------------------------------------

def test_nmpa_route_is_honest_not_available(monkeypatch):
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "Junshi Biosciences"})
    d = client.get("/api/nmpa/688180.SS").json()
    assert d["status"] == "not_available"
    assert d["ai_generated"] is False
    assert d["nmpaQueryUrl"].startswith("https://www.nmpa.gov.cn")
    assert "chinadrugtrials" in d["cdeTrialsUrl"]
    assert d["company"] == "Junshi Biosciences"


def test_sources_includes_nmpa_for_cn(monkeypatch):
    monkeypatch.setattr(_srv.df_mod, "_cached_yf_info", lambda t: {"longName": "Hengrui"})
    s = client.get("/api/sources/600276.SS").json()["sources"]
    assert "nmpa_query_url" in s
    assert "cde_trials_url" in s
