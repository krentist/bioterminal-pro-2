"""
compliance.py — the MNPI compliance wall (Phase J / §0 of INSTITUTIONAL_PROMPT.md).

Captures user-supplied private research notes with provenance, triages whether a note
may constitute material non-public information (MNPI) about a *public* security, and if
so restricts that ticker: the restriction is what the trade-oriented API routes consult
to suppress any computed signal for that name.

Hard invariant: note free-text is *never* fed into a computed public signal and never
transmitted to any external service. This module stores and classifies notes; it exposes
only a boolean restriction check and provenance-safe listings to the rest of the app.

Storage is a local SQLite database (single-user). Path is `COMPLIANCE_DB` if set, else
`compliance.db` next to this file — the env override exists so tests run against a temp DB.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id                    TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    subject               TEXT NOT NULL,
    subject_ticker        TEXT,
    source                TEXT,
    free_text             TEXT NOT NULL,
    is_public_subject     INTEGER NOT NULL DEFAULT 0,
    is_material_nonpublic INTEGER NOT NULL DEFAULT 0,
    restricted            INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS restricted (
    ticker     TEXT PRIMARY KEY,
    reason     TEXT,
    note_id    TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id     TEXT PRIMARY KEY,
    ts     TEXT NOT NULL,
    action TEXT NOT NULL,
    ticker TEXT,
    detail TEXT
);
"""

_DEFAULT_REASON = "You logged potential material non-public information on this name."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db_path() -> str:
    return os.getenv("COMPLIANCE_DB") or str(Path(__file__).parent / "compliance.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def normalize_ticker(ticker: Optional[str]) -> str:
    """Canonical upper-case ticker used as the restriction key.

    Reuses the data layer's normaliser (so bare HK codes like '700' map to '0700.HK'
    consistently with the rest of the app) and falls back to a plain upper/strip.
    """
    t = (ticker or "").strip()
    if not t:
        return ""
    try:
        from data_fetcher import normalize_ticker as _norm
        return (_norm(t) or t).upper()
    except Exception:
        return t.upper()


def _audit(conn: sqlite3.Connection, action: str, ticker: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (id, ts, action, ticker, detail) VALUES (?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, _now(), action, ticker, detail),
    )


def add_note(
    subject: str,
    free_text: str,
    *,
    source: str = "",
    subject_ticker: Optional[str] = None,
    is_public_subject: bool = False,
    is_material_nonpublic: bool = False,
) -> dict[str, Any]:
    """Persist a private note and run MNPI triage.

    If the note concerns a *public* security AND the user flags it material and
    non-public, the ticker is added to the restricted list and an audit entry is written.
    Returns the stored note plus whether a restriction was triggered.
    """
    note_id = uuid.uuid4().hex
    created = _now()
    ticker = normalize_ticker(subject_ticker)
    triggered = bool(is_public_subject and is_material_nonpublic and ticker)

    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO notes (id, created_at, subject, subject_ticker, source, "
                "free_text, is_public_subject, is_material_nonpublic, restricted) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    note_id, created, subject, ticker or None, source, free_text,
                    int(is_public_subject), int(is_material_nonpublic), int(triggered),
                ),
            )
            if triggered:
                conn.execute(
                    "INSERT INTO restricted (ticker, reason, note_id, created_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(ticker) DO UPDATE SET reason=excluded.reason, "
                    "note_id=excluded.note_id, created_at=excluded.created_at",
                    (ticker, _DEFAULT_REASON, note_id, created),
                )
                _audit(conn, "restrict", ticker, f"note={note_id}")
            conn.commit()
        finally:
            conn.close()

    return {
        "id": note_id,
        "createdAt": created,
        "subject": subject,
        "subjectTicker": ticker or None,
        "source": source,
        "isPublicSubject": bool(is_public_subject),
        "isMaterialNonpublic": bool(is_material_nonpublic),
        "restrictedTriggered": triggered,
    }


def _note_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Provenance-safe projection. free_text is intentionally omitted so no caller can
    route it into a signal; the full text is returned only by get_note_text()."""
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "subject": row["subject"],
        "subjectTicker": row["subject_ticker"],
        "source": row["source"],
        "isPublicSubject": bool(row["is_public_subject"]),
        "isMaterialNonpublic": bool(row["is_material_nonpublic"]),
        "restricted": bool(row["restricted"]),
    }


def list_notes(subject_ticker: Optional[str] = None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        if subject_ticker:
            rows = conn.execute(
                "SELECT * FROM notes WHERE subject_ticker = ? ORDER BY created_at DESC",
                (normalize_ticker(subject_ticker),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
        return [_note_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_note_text(note_id: str) -> Optional[str]:
    """Return a note's full text to its author. Deliberately separate from list_notes so
    that text access is an explicit call, never an incidental field on a signal payload."""
    conn = _connect()
    try:
        row = conn.execute("SELECT free_text FROM notes WHERE id = ?", (note_id,)).fetchone()
        return row["free_text"] if row else None
    finally:
        conn.close()


def is_restricted(ticker: str) -> bool:
    t = normalize_ticker(ticker)
    if not t:
        return False
    conn = _connect()
    try:
        return conn.execute(
            "SELECT 1 FROM restricted WHERE ticker = ?", (t,)
        ).fetchone() is not None
    finally:
        conn.close()


def restricted_reason(ticker: str) -> Optional[str]:
    t = normalize_ticker(ticker)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT reason FROM restricted WHERE ticker = ?", (t,)
        ).fetchone()
        return row["reason"] if row else None
    finally:
        conn.close()


def list_restricted() -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT ticker, reason, created_at FROM restricted ORDER BY created_at DESC"
        ).fetchall()
        return [
            {"ticker": r["ticker"], "reason": r["reason"], "createdAt": r["created_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def restricted_tickers() -> set[str]:
    return {r["ticker"] for r in list_restricted()}


def lift_restriction(ticker: str, note: str = "") -> bool:
    """Remove a ticker from the restricted list (e.g. after the information became public
    or was cleared by compliance). Audit-logged; never silent."""
    t = normalize_ticker(ticker)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM restricted WHERE ticker = ?", (t,))
            lifted = cur.rowcount > 0
            if lifted:
                _audit(conn, "lift", t, note)
            conn.commit()
            return lifted
        finally:
            conn.close()


def list_audit() -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT ts, action, ticker, detail FROM audit_log ORDER BY ts DESC"
        ).fetchall()
        return [
            {"ts": r["ts"], "action": r["action"], "ticker": r["ticker"], "detail": r["detail"]}
            for r in rows
        ]
    finally:
        conn.close()


def clear_all() -> None:
    """Wipe all compliance state. Intended for tests only."""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM notes")
            conn.execute("DELETE FROM restricted")
            conn.execute("DELETE FROM audit_log")
            conn.commit()
        finally:
            conn.close()
