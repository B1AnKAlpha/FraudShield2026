from __future__ import annotations

from app.core.config import settings
from app.shared.db import SQLiteRepository
from app.shared.time import utc_now

from .security import hash_password

DEFAULT_TOTP_SECRETS = {
    "admin": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
    "analyst": "KRSXG5DSMFZWK3TPOJSS4Y3PNVQW4ZDT",
}


class AuthRepository(SQLiteRepository):
    def __init__(self, db_path: str):
        super().__init__(db_path, enable_foreign_keys=True)

    def _initialize(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    organization TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    totp_secret TEXT,
                    bootstrap_token TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_username TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS allowed_machines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    machine_code TEXT NOT NULL,
                    machine_label TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(username, machine_code)
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_allowed_machines_username ON allowed_machines (username)"
            )
            cursor.execute("UPDATE users SET bootstrap_token = NULL WHERE bootstrap_token IS NOT NULL")
            for username, secret in DEFAULT_TOTP_SECRETS.items():
                cursor.execute(
                    """
                    UPDATE users
                    SET totp_secret = COALESCE(NULLIF(TRIM(totp_secret), ''), ?),
                        updated_at = ?
                    WHERE username = ?
                    """,
                    (secret, utc_now(), username),
                )
            connection.commit()

        self._seed_defaults()

    def _seed_defaults(self) -> None:
        with self.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count:
                return

            now = utc_now()
            default_users = [
                (
                    "admin",
                    hash_password("admin"),
                    "系统管理员",
                    "admin",
                    "FraudShield Lab",
                    "13188888888",
                    "admin@fraudshield.com",
                    "A00",
                    1,
                    DEFAULT_TOTP_SECRETS["admin"],
                    None,
                    now,
                    now,
                ),
                (
                    "analyst",
                    hash_password("analyst"),
                    "风险分析员",
                    "analyst",
                    "FraudShield Lab",
                    "13188888887",
                    "a01@fraudshield.com",
                    "A01",
                    1,
                    DEFAULT_TOTP_SECRETS["analyst"],
                    None,
                    now,
                    now,
                ),
            ]
            connection.executemany(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, organization, phone,
                    email, job_id, is_active, totp_secret, bootstrap_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                default_users,
            )
            connection.commit()

    def _serialize_user(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        payload = dict(row)
        payload["is_active"] = bool(payload["is_active"])
        payload["totp_enabled"] = bool(payload["totp_secret"])
        return payload

    def get_user_by_username(self, username: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return self._serialize_user(row)

    def get_user_by_id(self, user_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._serialize_user(row)

    def list_users(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY role DESC, username ASC"
            ).fetchall()
        return [self._serialize_user(row) for row in rows]

    def create_user(self, payload: dict) -> dict:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role, organization, phone, email,
                    job_id, is_active, totp_secret, bootstrap_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["username"],
                    payload["password_hash"],
                    payload["display_name"],
                    payload["role"],
                    payload["organization"],
                    payload["phone"],
                    payload["email"],
                    payload["job_id"],
                    int(payload.get("is_active", True)),
                    payload.get("totp_secret"),
                    payload.get("bootstrap_token"),
                    now,
                    now,
                ),
            )
            connection.commit()
            user_id = cursor.lastrowid
        return self.get_user_by_id(user_id)

    def update_user(self, username: str, updates: dict) -> dict | None:
        if not updates:
            return self.get_user_by_username(username)

        assignments: list[str] = []
        values: list[object] = []
        for field, value in updates.items():
            assignments.append(f"{field} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(username)

        query = f"UPDATE users SET {', '.join(assignments)} WHERE username = ?"
        with self.connect() as connection:
            connection.execute(query, values)
            connection.commit()
        return self.get_user_by_username(username)

    def delete_user(self, username: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE username = ?)", (username,))
            connection.execute("DELETE FROM allowed_machines WHERE username = ?", (username,))
            connection.execute("DELETE FROM users WHERE username = ?", (username,))
            connection.commit()

    def count_admin_users(self) -> int:
        with self.connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()[0]

    def save_session(self, *, token: str, user_id: int, expires_at: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, now, expires_at),
            )
            connection.commit()

    def get_session_user(self, token: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.*
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.expires_at > ?
                """,
                (token, utc_now()),
            ).fetchone()
        return self._serialize_user(row)

    def delete_session(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
            connection.commit()

    def log_action(self, *, actor_username: str, action: str, target_username: str, detail: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (actor_username, action, target_username, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (actor_username, action, target_username, detail, utc_now()),
            )
            connection.commit()

    def list_active_machines(self, username: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT username, machine_code, machine_label, is_active, created_at, updated_at
                FROM allowed_machines
                WHERE username = ? AND is_active = 1
                ORDER BY created_at ASC
                """,
                (username,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_machine(self, username: str, machine_code: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT username, machine_code, machine_label, is_active, created_at, updated_at
                FROM allowed_machines
                WHERE username = ? AND machine_code = ? AND is_active = 1
                """,
                (username, machine_code),
            ).fetchone()
        return dict(row) if row else None

    def upsert_machine(self, *, username: str, machine_code: str, machine_label: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO allowed_machines (
                    username, machine_code, machine_label, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(username, machine_code) DO UPDATE SET
                    machine_label = excluded.machine_label,
                    is_active = 1,
                    updated_at = excluded.updated_at
                """,
                (username, machine_code, machine_label, now, now),
            )
            connection.commit()


repository = AuthRepository(settings.auth_db_path)
