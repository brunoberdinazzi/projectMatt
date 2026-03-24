from __future__ import annotations

import os
import re
import sqlite3
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg


_AUTOINCREMENT_PATTERN = re.compile(r"\bINTEGER PRIMARY KEY AUTOINCREMENT\b", re.IGNORECASE)
_CURRENT_TIMESTAMP_PATTERN = re.compile(r"\bCURRENT_TIMESTAMP\b", re.IGNORECASE)
_PRAGMA_TABLE_INFO_PATTERN = re.compile(r"^\s*PRAGMA\s+table_info\((?P<table>[^)]+)\)\s*$", re.IGNORECASE)
_SECURE_POSTGRES_SSLMODES = {"require", "verify-ca", "verify-full"}


class DatabaseRow:
    def __init__(self, columns: Sequence[str], values: Sequence[Any]) -> None:
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._mapping = {column: self._values[index] for index, column in enumerate(self._columns)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self) -> Sequence[str]:
        return self._columns

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)


class DatabaseCursor:
    def __init__(
        self,
        cursor,
        *,
        lastrowid: Optional[int] = None,
        prefetched_rows: Optional[list[DatabaseRow]] = None,
    ) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid
        self._prefetched_rows = prefetched_rows
        self.rowcount = getattr(cursor, "rowcount", -1) if cursor is not None else -1

    def fetchone(self) -> Optional[DatabaseRow]:
        if self._prefetched_rows is not None:
            if not self._prefetched_rows:
                return None
            return self._prefetched_rows.pop(0)

        if self._cursor is None:
            return None
        row = self._cursor.fetchone()
        return self._wrap_row(row)

    def fetchall(self) -> list[DatabaseRow]:
        if self._prefetched_rows is not None:
            rows = list(self._prefetched_rows)
            self._prefetched_rows = []
            return rows

        if self._cursor is None:
            return []
        return [self._wrap_row(row) for row in self._cursor.fetchall()]

    def _wrap_row(self, row) -> Optional[DatabaseRow]:
        if row is None:
            return None
        if isinstance(row, DatabaseRow):
            return row
        columns = [column[0] for column in (self._cursor.description or [])]
        return DatabaseRow(columns, row)


class DatabaseConnection:
    def __init__(self, kind: str, raw_connection) -> None:
        self.kind = kind
        self._raw_connection = raw_connection

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.close()

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> DatabaseCursor:
        normalized_params = tuple(params or ())
        if self.kind == "postgres":
            return self._execute_postgres(sql, normalized_params)

        cursor = self._raw_connection.cursor()
        cursor.execute(sql, normalized_params)
        lastrowid = getattr(cursor, "lastrowid", None)
        return DatabaseCursor(cursor, lastrowid=lastrowid)

    def executemany(self, sql: str, params_seq: Iterable[Sequence[Any]]) -> DatabaseCursor:
        normalized_params = [tuple(params) for params in params_seq]
        if self.kind == "postgres":
            if self._is_pragma_foreign_keys(sql):
                return DatabaseCursor(None, prefetched_rows=[])
            cursor = self._raw_connection.cursor()
            cursor.executemany(self._transform_postgres_sql(sql), normalized_params)
            return DatabaseCursor(cursor)

        cursor = self._raw_connection.cursor()
        cursor.executemany(sql, normalized_params)
        return DatabaseCursor(cursor, lastrowid=getattr(cursor, "lastrowid", None))

    def executescript(self, script: str) -> None:
        if self.kind == "postgres":
            for statement in self._split_sql_script(script):
                self.execute(statement)
            return
        self._raw_connection.executescript(script)

    def commit(self) -> None:
        self._raw_connection.commit()

    def rollback(self) -> None:
        self._raw_connection.rollback()

    def close(self) -> None:
        self._raw_connection.close()

    def _execute_postgres(self, sql: str, params: Sequence[Any]) -> DatabaseCursor:
        if self._is_pragma_foreign_keys(sql):
            return DatabaseCursor(None, prefetched_rows=[])

        pragma_table = self._parse_pragma_table_info(sql)
        if pragma_table is not None:
            cursor = self._raw_connection.cursor()
            cursor.execute(
                """
                SELECT column_name AS name
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = %s
                ORDER BY ordinal_position
                """,
                (pragma_table,),
            )
            return DatabaseCursor(cursor)

        transformed_sql = self._transform_postgres_sql(sql)
        append_returning_id = self._should_append_returning_id(transformed_sql)
        if append_returning_id:
            transformed_sql = f"{transformed_sql.rstrip().rstrip(';')} RETURNING id"

        cursor = self._raw_connection.cursor()
        cursor.execute(transformed_sql, params)

        lastrowid = None
        prefetched_rows: Optional[list[DatabaseRow]] = None
        if append_returning_id:
            returned_row = cursor.fetchone()
            if returned_row is not None:
                wrapped_row = DatabaseRow([column[0] for column in (cursor.description or [])], returned_row)
                lastrowid = int(wrapped_row[0])
                prefetched_rows = [wrapped_row]
        return DatabaseCursor(cursor, lastrowid=lastrowid, prefetched_rows=prefetched_rows)

    def _transform_postgres_sql(self, sql: str) -> str:
        transformed = _AUTOINCREMENT_PATTERN.sub("BIGSERIAL PRIMARY KEY", sql)
        transformed = _CURRENT_TIMESTAMP_PATTERN.sub("CAST(CURRENT_TIMESTAMP AS TEXT)", transformed)
        return transformed.replace("?", "%s")

    def _is_pragma_foreign_keys(self, sql: str) -> bool:
        return sql.strip().upper().startswith("PRAGMA FOREIGN_KEYS")

    def _parse_pragma_table_info(self, sql: str) -> Optional[str]:
        match = _PRAGMA_TABLE_INFO_PATTERN.match(sql.strip())
        if match is None:
            return None
        table_name = match.group("table").strip().strip("'\"")
        return table_name or None

    def _should_append_returning_id(self, sql: str) -> bool:
        upper_sql = sql.lstrip().upper()
        return upper_sql.startswith("INSERT INTO ") and " RETURNING " not in upper_sql

    def _split_sql_script(self, script: str) -> list[str]:
        statements: list[str] = []
        for candidate in script.split(";"):
            statement = candidate.strip()
            if statement:
                statements.append(statement)
        return statements


def resolve_database_url(
    default_sqlite_path: Optional[Path] = None,
    database_url: Optional[str] = None,
) -> str:
    configured = (database_url or os.getenv("DATABASE_URL") or "").strip()
    if configured:
        return normalize_database_url(configured)

    if default_sqlite_path is None:
        raise ValueError("A database URL or default SQLite path must be provided.")
    return f"sqlite:///{default_sqlite_path.resolve()}"


def connect_database(
    default_sqlite_path: Optional[Path] = None,
    database_url: Optional[str] = None,
) -> DatabaseConnection:
    resolved_url = resolve_database_url(default_sqlite_path=default_sqlite_path, database_url=database_url)
    if resolved_url.startswith("sqlite:///"):
        sqlite_path = resolved_url.replace("sqlite:///", "", 1)
        raw_connection = sqlite3.connect(sqlite_path)
        return DatabaseConnection("sqlite", raw_connection)
    if resolved_url.startswith("postgres://") or resolved_url.startswith("postgresql://"):
        raw_connection = psycopg.connect(resolved_url, autocommit=False)
        return DatabaseConnection("postgres", raw_connection)
    raise ValueError(f"Unsupported database URL: {resolved_url}")


def normalize_database_url(database_url: str, *, sqlalchemy: bool = False) -> str:
    normalized = database_url.strip()
    if sqlalchemy:
        if normalized.startswith("postgres://"):
            normalized = "postgresql+psycopg://" + normalized.split("://", 1)[1]
        elif normalized.startswith("postgresql://"):
            normalized = "postgresql+psycopg://" + normalized.split("://", 1)[1]
    else:
        if normalized.startswith("postgresql+"):
            normalized = "postgresql://" + normalized.split("://", 1)[1]
        elif normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized.split("://", 1)[1]
    return ensure_postgres_sslmode(normalized)


def ensure_postgres_sslmode(database_url: str) -> str:
    normalized = database_url.strip()
    if not is_postgres_database_url(normalized):
        return normalized

    parsed = urlsplit(normalized)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in query_items:
        if key.lower() == "sslmode" and value.strip():
            return normalized

    configured_sslmode = (os.getenv("DRAUX_DB_SSLMODE") or "").strip()
    if configured_sslmode:
        sslmode = configured_sslmode
    elif is_local_postgres_database_url(normalized):
        return normalized
    else:
        sslmode = "require"

    query_items.append(("sslmode", sslmode))
    return urlunsplit(parsed._replace(query=urlencode(query_items)))


def is_postgres_database_url(database_url: str) -> bool:
    normalized = database_url.strip().lower()
    return normalized.startswith(("postgres://", "postgresql://", "postgresql+"))


def get_postgres_sslmode(database_url: str) -> Optional[str]:
    if not is_postgres_database_url(database_url):
        return None
    parsed = urlsplit(database_url)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "sslmode":
            return value.strip().lower() or None
    return None


def is_local_postgres_database_url(database_url: str) -> bool:
    host = _postgres_transport_host(database_url)
    if not host:
        return True
    if host.startswith("/"):
        return True

    normalized_host = host.strip().strip("[]").lower()
    if normalized_host in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        address = ip_address(normalized_host)
    except ValueError:
        return False
    return address.is_loopback


def postgres_url_uses_secure_transport(database_url: str) -> bool:
    if not is_postgres_database_url(database_url):
        return True
    if is_local_postgres_database_url(database_url):
        return True
    return (get_postgres_sslmode(database_url) or "") in _SECURE_POSTGRES_SSLMODES


def _postgres_transport_host(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if parsed.hostname:
        return parsed.hostname
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "host" and value.strip():
            return value.strip()
    return ""
