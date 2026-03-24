from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .app_database import DatabaseConnection, DatabaseRow, connect_database, resolve_database_url


class AuthStore:
    def __init__(self, database_path: Optional[Path] = None, database_url: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parents[3]
        data_dir = base_dir / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path or (data_dir / "matt.db")
        self.database_url = resolve_database_url(default_sqlite_path=self.database_path, database_url=database_url)
        self._initialize()

    def create_user(self, full_name: str, email: str, password_hash: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO auth_users (full_name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (full_name, email, password_hash),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_user_by_email(self, email: str) -> Optional[DatabaseRow]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, full_name, email, password_hash, created_at
                FROM auth_users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[DatabaseRow]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, full_name, email, created_at
                FROM auth_users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

    def get_user_auth_by_id(self, user_id: int) -> Optional[DatabaseRow]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, full_name, email, password_hash, created_at
                FROM auth_users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

    def update_user_profile(self, user_id: int, full_name: str, email: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_users
                SET full_name = ?, email = ?
                WHERE id = ?
                """,
                (full_name, email, user_id),
            )
            conn.commit()

    def update_user_password(self, user_id: int, password_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_users
                SET password_hash = ?
                WHERE id = ?
                """,
                (password_hash, user_id),
            )
            conn.commit()

    def create_session(
        self,
        user_id: int,
        session_public_id: str,
        token_hash: str,
        expires_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO auth_sessions (user_id, session_public_id, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, session_public_id, token_hash, expires_at),
            )
            conn.commit()

    def get_session_by_token_hash(self, token_hash: str) -> Optional[DatabaseRow]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    auth_sessions.id,
                    auth_sessions.created_at AS session_created_at,
                    auth_sessions.user_id,
                    auth_sessions.session_public_id,
                    auth_sessions.expires_at,
                    auth_sessions.revoked_at,
                    auth_users.full_name,
                    auth_users.email,
                    auth_users.created_at AS user_created_at
                FROM auth_sessions
                JOIN auth_users ON auth_users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()

    def revoke_session_by_token_hash(self, token_hash: str, revoked_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE token_hash = ?
                """,
                (revoked_at, token_hash),
            )
            conn.commit()

    def revoke_expired_sessions(self, now_iso: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE expires_at <= ? AND revoked_at IS NULL
                """,
                (now_iso, now_iso),
            )
            conn.commit()

    def revoke_sessions_for_user(self, user_id: int, revoked_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (revoked_at, user_id),
            )
            conn.commit()

    def _connect(self) -> DatabaseConnection:
        connection = connect_database(database_url=self.database_url)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL,
                    session_public_id TEXT,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash ON auth_sessions(token_hash);
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
                """
            )
            self._ensure_column(conn, "auth_sessions", "session_public_id", "TEXT")
            self._ensure_column(conn, "auth_sessions", "revoked_at", "TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_sessions_public_id ON auth_sessions(session_public_id)"
            )
            self._backfill_session_public_ids(conn)
            conn.commit()

    def _backfill_session_public_ids(self, conn: DatabaseConnection) -> None:
        rows = conn.execute(
            "SELECT id, created_at FROM auth_sessions WHERE session_public_id IS NULL OR session_public_id = ''"
        ).fetchall()
        for row in rows:
            created_at = row["created_at"] or datetime.now(timezone.utc).isoformat()
            created_stamp = created_at.replace("-", "").replace(":", "").replace(" ", "").replace(".", "")
            session_public_id = f"sess_legacy_{row['id']}_{created_stamp[:14]}"
            conn.execute(
                "UPDATE auth_sessions SET session_public_id = ? WHERE id = ?",
                (session_public_id, row["id"]),
            )

    def _ensure_column(
        self,
        conn: DatabaseConnection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if any(column["name"] == column_name for column in columns):
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
