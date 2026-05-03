from __future__ import annotations

import uuid

from app.core.config import settings
from app.shared.db import SQLiteRepository
from app.shared.time import utc_now


class FocusRepository(SQLiteRepository):
    def __init__(self, db_path: str):
        super().__init__(db_path)

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS focus_targets (
                    account TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    source_account TEXT,
                    source_job_id TEXT,
                    is_seed INTEGER NOT NULL DEFAULT 1,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS focus_events (
                    event_id TEXT PRIMARY KEY,
                    account TEXT NOT NULL,
                    action TEXT NOT NULL,
                    mode TEXT,
                    source_account TEXT,
                    source_job_id TEXT,
                    operator TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS focus_hidden_logs (
                    job_id TEXT NOT NULL,
                    hidden_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, hidden_by)
                );
                """
            )
            connection.commit()

    def upsert_target(
        self,
        *,
        account: str,
        mode: str,
        source_account: str | None,
        source_job_id: str | None,
        is_seed: bool,
        created_by: str,
    ) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO focus_targets (
                    account, mode, source_account, source_job_id, is_seed, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account) DO UPDATE SET
                    mode = excluded.mode,
                    source_account = excluded.source_account,
                    source_job_id = excluded.source_job_id,
                    is_seed = excluded.is_seed,
                    created_by = excluded.created_by,
                    updated_at = excluded.updated_at
                """,
                (
                    account,
                    mode,
                    source_account,
                    source_job_id,
                    int(is_seed),
                    created_by,
                    now,
                    now,
                ),
            )
            connection.commit()

    def delete_target(self, account: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM focus_targets WHERE account = ?",
                (account,),
            )
            connection.commit()
        return cursor.rowcount

    def list_targets(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT account, mode, source_account, source_job_id, is_seed, created_by, created_at, updated_at
                FROM focus_targets
                ORDER BY updated_at DESC, account ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_event(
        self,
        *,
        account: str,
        action: str,
        mode: str | None,
        source_account: str | None,
        source_job_id: str | None,
        operator: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO focus_events (
                    event_id, account, action, mode, source_account, source_job_id, operator, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    account,
                    action,
                    mode,
                    source_account,
                    source_job_id,
                    operator,
                    utc_now(),
                ),
            )
            connection.commit()

    def hide_log(self, *, job_id: str, hidden_by: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO focus_hidden_logs (job_id, hidden_by, created_at)
                VALUES (?, ?, ?)
                """,
                (job_id, hidden_by, utc_now()),
            )
            connection.commit()

    def list_hidden_logs(self, hidden_by: str) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT job_id FROM focus_hidden_logs WHERE hidden_by = ?",
                (hidden_by,),
            ).fetchall()
        return {row["job_id"] for row in rows}


repository = FocusRepository(settings.focus_db_path)
