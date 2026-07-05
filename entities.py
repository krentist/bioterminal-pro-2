"""
entities.py — Private company entity model (Phase K / §1 of INSTITUTIONAL_PROMPT.md).

A private / pre-IPO biotech has no ticker, no price, no yfinance. This module models it as
a first-class entity keyed by name, valued by its *actual* ClinicalTrials.gov pipeline (rNPV
only — never a price-based DCF/backtest/scenario), with funding-round and licensing-deal comps
and attachable diligence notes.

Lifecycle: a company carries a `listing_status` (private | pre_ipo | public) and an optional
`linked_ticker`, so when it IPOs its history (notes, funding, prior rNPV) carries forward and
new notes about it route through the MNPI wall (compliance.py) because it now has a security.

Storage is local SQLite (`ENTITIES_DB` env override for tests, else `entities.db`).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from data_fetcher import fetch_clinicaltrials_multi, _ct_name_variants
from pipeline_analyzer import enrich_trials
from rnpv_calculator import pipeline_rnpv, AssetAssumptions, DEFAULT_PEAK_SALES_USD

_LOCK = threading.Lock()

_VALID_STATUS = ("private", "pre_ipo", "public")

# Typical share of a licensee's rNPV that a licensor captures as total deal value
# (upfront + milestones + royalty NPV). Industry heuristic, exposed as a labelled comp.
_LICENSING_LOW, _LICENSING_MID, _LICENSING_HIGH = 0.25, 0.30, 0.35

_SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    aliases        TEXT,
    listing_status TEXT NOT NULL DEFAULT 'private',
    ct_sponsor_name TEXT,
    linked_ticker  TEXT,
    description    TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS funding_rounds (
    id             TEXT PRIMARY KEY,
    company_id     TEXT NOT NULL,
    date           TEXT,
    round_type     TEXT,
    amount_usd     REAL,
    post_money_usd REAL,
    lead_investor  TEXT,
    source         TEXT,
    source_url     TEXT,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS company_notes (
    id         TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source     TEXT,
    text       TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db_path() -> str:
    return os.getenv("ENTITIES_DB") or str(Path(__file__).parent / "entities.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Company CRUD
# ---------------------------------------------------------------------------

def _company_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "aliases": json.loads(row["aliases"]) if row["aliases"] else [],
        "listingStatus": row["listing_status"],
        "ctSponsorName": row["ct_sponsor_name"],
        "linkedTicker": row["linked_ticker"],
        "description": row["description"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_company(
    name: str,
    *,
    listing_status: str = "private",
    ct_sponsor_name: Optional[str] = None,
    linked_ticker: Optional[str] = None,
    description: str = "",
    aliases: Optional[list[str]] = None,
) -> dict[str, Any]:
    if not (name or "").strip():
        raise ValueError("name is required")
    if listing_status not in _VALID_STATUS:
        raise ValueError(f"listing_status must be one of {_VALID_STATUS}")
    cid = uuid.uuid4().hex[:12]
    ts = _now()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO companies (id, name, aliases, listing_status, ct_sponsor_name, "
                "linked_ticker, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, name.strip(), json.dumps(aliases or []), listing_status,
                 (ct_sponsor_name or "").strip() or None,
                 (linked_ticker or "").strip().upper() or None,
                 description.strip(), ts, ts),
            )
            conn.commit()
        finally:
            conn.close()
    return get_company(cid)


def get_company(company_id: str) -> Optional[dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        return _company_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_companies(query: Optional[str] = None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        if query:
            like = f"%{query.strip().lower()}%"
            rows = conn.execute(
                "SELECT * FROM companies WHERE lower(name) LIKE ? OR lower(aliases) LIKE ? "
                "ORDER BY created_at DESC",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM companies ORDER BY created_at DESC").fetchall()
        return [_company_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_company(
    company_id: str,
    *,
    listing_status: Optional[str] = None,
    linked_ticker: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if listing_status is not None and listing_status not in _VALID_STATUS:
        raise ValueError(f"listing_status must be one of {_VALID_STATUS}")
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT id FROM companies WHERE id = ?", (company_id,)).fetchone()
            if not row:
                return None
            sets, vals = [], []
            if listing_status is not None:
                sets.append("listing_status = ?"); vals.append(listing_status)
            if linked_ticker is not None:
                sets.append("linked_ticker = ?"); vals.append(linked_ticker.strip().upper() or None)
            if description is not None:
                sets.append("description = ?"); vals.append(description.strip())
            sets.append("updated_at = ?"); vals.append(_now())
            vals.append(company_id)
            conn.execute(f"UPDATE companies SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()
    return get_company(company_id)


# ---------------------------------------------------------------------------
# Funding rounds  (a private-market comp source)
# ---------------------------------------------------------------------------

def add_funding_round(
    company_id: str,
    *,
    date: Optional[str] = None,
    round_type: Optional[str] = None,
    amount_usd: Optional[float] = None,
    post_money_usd: Optional[float] = None,
    lead_investor: Optional[str] = None,
    source: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if get_company(company_id) is None:
        return None
    rid = uuid.uuid4().hex[:12]
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO funding_rounds (id, company_id, date, round_type, amount_usd, "
                "post_money_usd, lead_investor, source, source_url, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, company_id, date, round_type,
                 float(amount_usd) if amount_usd is not None else None,
                 float(post_money_usd) if post_money_usd is not None else None,
                 lead_investor, source, source_url, _now()),
            )
            conn.commit()
        finally:
            conn.close()
    return {"id": rid, "companyId": company_id}


def list_funding_rounds(company_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM funding_rounds WHERE company_id = ? ORDER BY date DESC, created_at DESC",
            (company_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "roundType": r["round_type"],
                "amountUsd": r["amount_usd"],
                "postMoneyUsd": r["post_money_usd"],
                "leadInvestor": r["lead_investor"],
                "source": r["source"],
                "sourceUrl": r["source_url"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Diligence notes  (data-room attachment)
# For a public entity with a linked ticker the MNPI wall (compliance.py) applies;
# for a private/pre-IPO entity there is no tradable security to abuse, so notes are
# stored directly and legitimately feed the entity's own diligence view.
# ---------------------------------------------------------------------------

def attach_note(
    company_id: str,
    text: str,
    *,
    source: str = "",
    is_material_nonpublic: bool = False,
) -> Optional[dict[str, Any]]:
    company = get_company(company_id)
    if company is None:
        return None
    if company["listingStatus"] == "public" and company["linkedTicker"]:
        # Now a public security → route through the compliance wall for MNPI triage.
        from compliance import add_note as _add_note
        note = _add_note(
            company["name"], text, source=source,
            subject_ticker=company["linkedTicker"],
            is_public_subject=True, is_material_nonpublic=is_material_nonpublic,
        )
        return {**note, "companyId": company_id, "routedToComplianceWall": True}

    nid = uuid.uuid4().hex[:12]
    ts = _now()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO company_notes (id, company_id, created_at, source, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (nid, company_id, ts, source, text),
            )
            conn.commit()
        finally:
            conn.close()
    return {"id": nid, "companyId": company_id, "createdAt": ts, "source": source,
            "routedToComplianceWall": False}


def list_company_notes(company_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, created_at, source, text FROM company_notes "
            "WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,),
        ).fetchall()
        return [
            {"id": r["id"], "createdAt": r["created_at"], "source": r["source"], "text": r["text"]}
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pipeline + valuation  (rNPV only — no price, no DCF, no backtest)
# ---------------------------------------------------------------------------

def _select_programs(enriched: pd.DataFrame, name: str) -> tuple[pd.DataFrame, bool]:
    """Keep trials this company leads (sponsor name matches) and de-duplicate to one program
    per (phase, indication) so the same drug is not counted as several $500M assets."""
    if enriched.empty:
        return enriched, False
    terms = [v.lower() for v in _ct_name_variants(name) if len(v) >= 4]
    sponsor_l = enriched.get("sponsor", pd.Series("", index=enriched.index)).fillna("").str.lower()
    mask = sponsor_l.apply(lambda s: any(t in s for t in terms)) if terms else pd.Series(False, index=enriched.index)
    matched = bool(mask.any())
    df = enriched[mask].copy() if matched else enriched.copy()
    cond = df.get("condition", pd.Series("", index=df.index)).fillna("")
    df["_ind"] = cond.str.split(",").str[0].str.strip().str.lower()
    df["_key"] = df["phase_clean"].astype(str) + "|" + df["_ind"]
    sort_cols = [c for c in ("is_active", "enrollment") if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False, na_position="last")
    df = df.drop_duplicates("_key").drop(columns=["_ind", "_key"])
    return df, matched


def _fetch_pipeline_raw(company: dict[str, Any]) -> pd.DataFrame:
    """Fetch this company's trials from ClinicalTrials.gov by sponsor name."""
    sponsor = company.get("ctSponsorName") or company.get("name")
    terms = _ct_name_variants(sponsor)
    return fetch_clinicaltrials_multi(terms)


def company_pipeline(company: dict[str, Any]) -> tuple[pd.DataFrame, bool, int]:
    raw = _fetch_pipeline_raw(company)
    if raw.empty:
        return raw, False, 0
    enriched = enrich_trials(raw)
    programs, matched = _select_programs(enriched, company.get("ctSponsorName") or company["name"])
    return programs, matched, int(len(enriched))


def _programs_list(programs: pd.DataFrame) -> list[dict[str, Any]]:
    if programs.empty:
        return []
    out = []
    for _, r in programs.iterrows():
        out.append({
            "title": str(r.get("title", ""))[:120],
            "phase": r.get("phase_clean") or r.get("phase"),
            "status": r.get("status"),
            "condition": r.get("condition"),
            "enrollment": (int(r["enrollment"]) if pd.notna(r.get("enrollment")) else None)
                          if "enrollment" in programs.columns else None,
        })
    return out


def compute_valuation(programs: pd.DataFrame) -> dict[str, Any]:
    """rNPV from the company's actual pipeline, with assumptions made explicit."""
    total, detail = pipeline_rnpv(programs)
    a = AssetAssumptions()
    programs_detail = []
    for _, row in detail.iterrows():
        programs_detail.append({
            "name": str(row.get("name", ""))[:80],
            "phase": row.get("phase"),
            "probApproval": round(float(row.get("prob_approval", 0)), 4),
            "peakSales": row.get("peak_sales"),
            "rnpv": row.get("rnpv"),
            "netRnpv": row.get("net_rnpv"),
        })
    licensing = None
    if total and total > 0:
        licensing = {
            "basis": "Licensor typically captures 25–35% of the licensee's rNPV "
                     "(upfront + milestones + royalty NPV).",
            "low": round(total * _LICENSING_LOW),
            "mid": round(total * _LICENSING_MID),
            "high": round(total * _LICENSING_HIGH),
        }
    return {
        "valuationMethod": "rNPV",
        "rnpvTotal": round(float(total), 0) if total else 0.0,
        "programs": programs_detail,
        "assumptions": {
            "defaultPeakSalesUsd": DEFAULT_PEAK_SALES_USD,
            "discountRate": getattr(a, "discount_rate", None),
            "note": "Peak sales default applied per program where unknown; probability of "
                    "approval is phase-derived (BIO/Informa). No per-share figure: a private "
                    "company has no share count — this is total pipeline rNPV.",
        },
        "licensingComps": licensing,
    }


def funding_comps(company_id: str, rnpv_total: float) -> dict[str, Any]:
    rounds = list_funding_rounds(company_id)
    latest_post = next((r for r in rounds if r.get("postMoneyUsd")), None)
    implied = None
    if latest_post and rnpv_total:
        pm = latest_post["postMoneyUsd"]
        implied = {
            "lastPostMoneyUsd": pm,
            "asOf": latest_post.get("date"),
            "rnpvTotal": rnpv_total,
            "rnpvVsPostMoney": round(rnpv_total / pm - 1, 4) if pm else None,
            "source": latest_post.get("source"),
            "sourceUrl": latest_post.get("sourceUrl"),
        }
    return {"rounds": rounds, "impliedByRnpv": implied}


def company_view(company_id: str, programs: Optional[pd.DataFrame] = None) -> Optional[dict[str, Any]]:
    """Full private-company view. Deliberately excludes price / DCF / backtest / scenarios —
    those are meaningless for a company with no traded security."""
    company = get_company(company_id)
    if company is None:
        return None
    if programs is None:
        programs, matched, found = company_pipeline(company)
    else:
        matched, found = True, int(len(programs))
    valuation = compute_valuation(programs)
    return {
        "company": company,
        "listingStatus": company["listingStatus"],
        "pipeline": {
            "programs": _programs_list(programs),
            "sponsorMatched": matched,
            "trialsFound": found,
            "source": "ClinicalTrials.gov",
        },
        "valuation": valuation,
        "fundingComps": funding_comps(company_id, valuation["rnpvTotal"]),
        "notes": list_company_notes(company_id),
        "sources": [
            {"field": "pipeline", "source": "ClinicalTrials.gov", "url": "https://clinicaltrials.gov"},
            {"field": "valuation", "source": "rNPV (BIO/Informa phase probabilities)", "url": None},
            {"field": "fundingComps", "source": "user-entered funding rounds", "url": None},
        ],
    }


def clear_all() -> None:
    """Wipe all entity state. Intended for tests only."""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM companies")
            conn.execute("DELETE FROM funding_rounds")
            conn.execute("DELETE FROM company_notes")
            conn.commit()
        finally:
            conn.close()
