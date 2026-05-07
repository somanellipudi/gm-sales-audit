from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


LEAD_STATUSES = (
    "New",
    "Audited",
    "Contacted",
    "Replied",
    "Call Booked",
    "Won",
    "Lost",
)

DEFAULT_OWNER = "GrowingMonk Sales"
DB_ENV_VAR = "MONKAUDIT_DB_PATH"
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = APP_DIR / "data" / "monkaudit.sqlite3"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_path() -> Path:
    configured = os.getenv(DB_ENV_VAR, "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_sales_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_records (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                business_name TEXT NOT NULL,
                location TEXT,
                website TEXT,
                niche TEXT,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                confidence_label TEXT,
                recommended_offer TEXT,
                pitch_angle TEXT,
                next_step TEXT,
                notes TEXT,
                client_reviewed INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_records(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_records(created_at)")


def save_audit_record(record: dict[str, Any]) -> str:
    init_sales_store()
    now = utc_now_iso()
    record_id = record.get("id") or uuid4().hex
    payload = record.get("payload", {})
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_records (
                id, created_at, updated_at, mode, business_name, location, website,
                niche, status, owner, confidence_label, recommended_offer,
                pitch_angle, next_step, notes, client_reviewed, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                record.get("created_at") or now,
                now,
                record.get("mode") or "Unknown",
                record.get("business_name") or "Unknown business",
                record.get("location") or "",
                record.get("website") or "",
                record.get("niche") or "",
                record.get("status") or "Audited",
                record.get("owner") or DEFAULT_OWNER,
                record.get("confidence_label") or "",
                record.get("recommended_offer") or "",
                record.get("pitch_angle") or "",
                record.get("next_step") or "",
                record.get("notes") or "",
                1 if record.get("client_reviewed") else 0,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    return record_id


def list_audit_records(limit: int = 100) -> list[dict[str, Any]]:
    init_sales_store()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, updated_at, mode, business_name, location, website,
                   niche, status, owner, confidence_label, recommended_offer,
                   pitch_angle, next_step, notes, client_reviewed
            FROM audit_records
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_audit_record(record_id: str) -> dict[str, Any] | None:
    init_sales_store()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM audit_records WHERE id = ?",
            (record_id,),
        ).fetchone()
    if not row:
        return None
    record = dict(row)
    try:
        record["payload"] = json.loads(record.pop("payload_json") or "{}")
    except json.JSONDecodeError:
        record["payload"] = {}
    return record


def update_audit_record(record_id: str, **fields: Any) -> None:
    allowed_fields = {
        "status",
        "owner",
        "next_step",
        "notes",
        "client_reviewed",
        "confidence_label",
        "recommended_offer",
        "pitch_angle",
    }
    updates = {key: value for key, value in fields.items() if key in allowed_fields}
    if not updates:
        return

    if "status" in updates and updates["status"] not in LEAD_STATUSES:
        raise ValueError(f"Unsupported lead status: {updates['status']}")
    if "client_reviewed" in updates:
        updates["client_reviewed"] = 1 if updates["client_reviewed"] else 0

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    values.extend([utc_now_iso(), record_id])

    init_sales_store()
    with _connect() as connection:
        connection.execute(
            f"UPDATE audit_records SET {assignments}, updated_at = ? WHERE id = ?",
            values,
        )
