"""SQLite storage. Every read/write is scoped by organization_id so one tenant
can never see another tenant's rows (RULES.md, Engineering Rule 1: Tenancy
Isolation). There is no query in this file that fetches a record by record_id
alone -- org_id is always part of the WHERE clause.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.schemas import EvidenceRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    record_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL,  -- full EvidenceRecord as JSON
    PRIMARY KEY (record_id, organization_id)
);
CREATE INDEX IF NOT EXISTS idx_records_org ON records(organization_id);

CREATE TABLE IF NOT EXISTS images (
    image_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    path TEXT NOT NULL,
    PRIMARY KEY (image_id, organization_id)
);
CREATE INDEX IF NOT EXISTS idx_images_org ON images(organization_id);
"""


class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_record(self, record: EvidenceRecord) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO records (record_id, organization_id, unit_id, "
            "created_at, data) VALUES (?, ?, ?, ?, ?)",
            (
                record.record_id,
                record.organization_id,
                record.subject.unit_id,
                record.captured_at,
                record.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get_record(self, record_id: str, organization_id: str) -> EvidenceRecord | None:
        """Scoped to organization_id: a record from another org is invisible,
        not just access-denied -- guessing an id returns nothing either way."""
        row = self.conn.execute(
            "SELECT data FROM records WHERE record_id = ? AND organization_id = ?",
            (record_id, organization_id),
        ).fetchone()
        if row is None:
            return None
        return EvidenceRecord.model_validate(json.loads(row[0]))

    def list_records(self, organization_id: str, limit: int = 100) -> list[EvidenceRecord]:
        rows = self.conn.execute(
            "SELECT data FROM records WHERE organization_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (organization_id, limit),
        ).fetchall()
        return [EvidenceRecord.model_validate(json.loads(r[0])) for r in rows]

    def register_image(self, image_id: str, organization_id: str, record_id: str, path: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO images (image_id, organization_id, record_id, path) "
            "VALUES (?, ?, ?, ?)",
            (image_id, organization_id, record_id, path),
        )
        self.conn.commit()

    def get_image_path(self, image_id: str, organization_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT path FROM images WHERE image_id = ? AND organization_id = ?",
            (image_id, organization_id),
        ).fetchone()
        return row[0] if row else None
