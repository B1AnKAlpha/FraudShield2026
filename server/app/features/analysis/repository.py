from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.core.config import settings


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class AnalysisRepository:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parser_summary_json TEXT,
                    result_json TEXT,
                    normalized_json TEXT,
                    report_path TEXT,
                    report_title TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_assets (
                    asset_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id) ON DELETE CASCADE
                );
                """
            )
            connection.commit()

    def create_job(self, *, job_id: str, created_by: str, status: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_jobs (
                    job_id, created_by, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, created_by, status, now, now),
            )
            connection.commit()

    def add_asset(
        self,
        *,
        asset_id: str,
        job_id: str,
        asset_type: str,
        original_name: str,
        mime_type: str,
        local_path: str,
        size_bytes: int,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_assets (
                    asset_id, job_id, asset_type, original_name, mime_type, local_path, size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset_id, job_id, asset_type, original_name, mime_type, local_path, size_bytes, utc_now()),
            )
            connection.commit()

    def list_assets(self, job_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT asset_id, job_id, asset_type, original_name, mime_type, local_path, size_bytes, created_at
                FROM analysis_assets
                WHERE job_id = ?
                ORDER BY created_at ASC
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_job(self, job_id: str, updates: dict) -> None:
        if not updates:
            return

        assignments: list[str] = []
        values: list[object] = []
        for field, value in updates.items():
            assignments.append(f"{field} = ?")
            if field.endswith("_json") and value is not None:
                values.append(json.dumps(value, ensure_ascii=False))
            else:
                values.append(value)

        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(job_id)

        query = f"UPDATE analysis_jobs SET {', '.join(assignments)} WHERE job_id = ?"
        with self.connect() as connection:
            connection.execute(query, values)
            connection.commit()

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM analysis_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._deserialize_job(row)

    def list_jobs(self, *, created_by: str | None = None) -> list[dict]:
        query = "SELECT * FROM analysis_jobs"
        params: tuple[object, ...] = ()
        if created_by is not None:
            query += " WHERE created_by = ?"
            params = (created_by,)
        query += " ORDER BY created_at DESC"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._deserialize_job(row) for row in rows]

    def _deserialize_job(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None

        payload = dict(row)
        for field in ("parser_summary_json", "result_json", "normalized_json"):
            raw_value = payload.get(field)
            payload[field] = json.loads(raw_value) if raw_value else None
        return payload


repository = AnalysisRepository(settings.analysis_db_path)
