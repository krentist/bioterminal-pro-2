"""Offline tests for peer selection and comps assembly."""
import data_fetcher as dfm


def test_get_peers_excludes_self():
    peers = dfm.get_peers("MRNA")
    assert "MRNA" not in [p.upper() for p in peers]
    assert len(peers) > 0


def test_get_peers_region_fallback_hk():
    # A HK biotech not in the explicit override map falls back to the HK set.
    peers = dfm.get_peers("1801.HK")
    assert all(p.endswith(".HK") for p in peers)
    assert "1801.HK" not in peers


def test_get_peers_normalizes_bare_hk_code():
    # Bare code 6160 -> 6160.HK -> HK peer set, self excluded.
    peers = dfm.get_peers("6160")
    assert "6160.HK" not in [p.upper() for p in peers]
    assert all(p.endswith(".HK") for p in peers)


def test_peer_comps_subject_first(monkeypatch):
    # Deterministic info per ticker; subject must be row 0, peers by mkt cap desc.
    caps = {"AAA": 500, "BBB": 900, "CCC": 100}
    monkeypatch.setattr(dfm, "get_peers", lambda t, n=5: ["BBB", "CCC"])
    monkeypatch.setattr(
        dfm, "_cached_yf_info",
        lambda t: {"marketCap": caps.get(t.upper()), "regularMarketPrice": 10, "currency": "USD"},
    )
    dfm._PEERS_CACHE.clear()
    rows = dfm.get_peer_comps("AAA")
    assert rows[0]["ticker"] == "AAA" and rows[0]["isSubject"] is True
    assert [r["ticker"] for r in rows[1:]] == ["BBB", "CCC"]  # 900 > 100
