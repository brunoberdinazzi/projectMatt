from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Optional

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.analysis_store import AnalysisStore
from backend.app.services.auth_store import AuthStore
from backend.app.services.financial_warehouse_store import FinancialWarehouseStore


APP_TABLES_IN_ORDER = [
    "auth_users",
    "auth_sessions",
    "analyses",
    "analysis_warnings",
    "analysis_items",
    "analysis_item_details",
    "scraped_pages",
    "scraped_page_warnings",
    "scraped_links",
    "analysis_generations",
    "analysis_parse_cache",
    "analysis_financial_dre_lines",
    "analysis_financial_months",
    "analysis_financial_clients",
    "analysis_financial_client_periods",
    "analysis_financial_contracts",
]

FINANCE_TABLES_IN_ORDER = [
    "finance_analysis_snapshots",
    "finance_canonical_clients",
    "finance_canonical_contracts",
    "finance_dre_lines",
    "finance_periods",
    "finance_clients",
    "finance_client_periods",
    "finance_contracts",
    "finance_entries",
]

TABLES_WITH_IDS = [
    *APP_TABLES_IN_ORDER,
    *FINANCE_TABLES_IN_ORDER,
]


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    backend_data = project_root / "backend" / "data"
    parser = argparse.ArgumentParser(
        description="Migra os bancos SQLite do Draux para PostgreSQL.",
    )
    parser.add_argument(
        "--source-app-db",
        default=str(backend_data / "matt.db"),
        help="Caminho do banco SQLite principal.",
    )
    parser.add_argument(
        "--source-finance-db",
        default=str(backend_data / "draux_finance.db"),
        help="Caminho do banco SQLite do warehouse financeiro.",
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="URL do PostgreSQL de destino para auth + analyses.",
    )
    parser.add_argument(
        "--finance-database-url",
        default=None,
        help="URL do PostgreSQL de destino para o warehouse financeiro. Usa --database-url se omitido.",
    )
    parser.add_argument(
        "--truncate-existing",
        action="store_true",
        help="Limpa as tabelas de destino antes de importar.",
    )
    return parser.parse_args()


def quote_ident(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def ensure_destination_schema(database_url: str, finance_database_url: str) -> None:
    AuthStore(database_url=database_url)
    AnalysisStore(database_url=database_url)
    FinancialWarehouseStore(database_url=finance_database_url)


def open_sqlite(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def open_postgres(database_url: str):
    return psycopg.connect(database_url, autocommit=False)


def sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def fetch_sqlite_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(row["name"]) for row in rows]


def destination_has_data(conn, tables: Iterable[str]) -> bool:
    with conn.cursor() as cursor:
        for table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {quote_ident(table_name)}")
            if int(cursor.fetchone()[0]) > 0:
                return True
    return False


def delete_destination_tables(conn, tables: Iterable[str]) -> None:
    with conn.cursor() as cursor:
        for table_name in reversed(list(tables)):
            cursor.execute(f"DELETE FROM {quote_ident(table_name)}")


def migrate_table(
    source_conn: sqlite3.Connection,
    destination_conn,
    table_name: str,
) -> int:
    if not sqlite_table_exists(source_conn, table_name):
        return 0

    columns = fetch_sqlite_columns(source_conn, table_name)
    if not columns:
        return 0

    quoted_columns = ", ".join(quote_ident(column) for column in columns)
    rows = source_conn.execute(f"SELECT {quoted_columns} FROM {quote_ident(table_name)}").fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {quote_ident(table_name)} ({quoted_columns}) VALUES ({placeholders})"
    values = [tuple(row[column] for column in columns) for row in rows]
    with destination_conn.cursor() as cursor:
        cursor.executemany(insert_sql, values)
    return len(values)


def reset_sequences(conn, tables: Iterable[str]) -> None:
    with conn.cursor() as cursor:
        for table_name in tables:
            cursor.execute("SELECT to_regclass(%s)", (table_name,))
            if cursor.fetchone()[0] is None:
                continue

            cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {quote_ident(table_name)}")
            max_id = int(cursor.fetchone()[0] or 0)

            cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table_name,))
            sequence_name = cursor.fetchone()[0]
            if not sequence_name:
                continue

            if max_id > 0:
                cursor.execute("SELECT setval(%s, %s, true)", (sequence_name, max_id))
            else:
                cursor.execute("SELECT setval(%s, %s, false)", (sequence_name, 1))


def migrate_sqlite_to_postgres(
    source_app_db: Path,
    source_finance_db: Path,
    database_url: str,
    finance_database_url: str,
    truncate_existing: bool,
) -> None:
    ensure_destination_schema(database_url, finance_database_url)

    with open_sqlite(source_app_db) as app_source, open_sqlite(source_finance_db) as finance_source:
        with open_postgres(database_url) as app_destination, open_postgres(finance_database_url) as finance_destination:
            if finance_database_url == database_url:
                same_destination = app_destination
            else:
                same_destination = None

            if same_destination is not None:
                tables_to_check = [*APP_TABLES_IN_ORDER, *FINANCE_TABLES_IN_ORDER]
                if destination_has_data(app_destination, tables_to_check):
                    if not truncate_existing:
                        raise RuntimeError(
                            "O banco PostgreSQL de destino ja possui dados. Rode com --truncate-existing para sobrescrever."
                        )
                    delete_destination_tables(app_destination, tables_to_check)
            else:
                if destination_has_data(app_destination, APP_TABLES_IN_ORDER):
                    if not truncate_existing:
                        raise RuntimeError(
                            "O banco PostgreSQL de destino ja possui dados. Rode com --truncate-existing para sobrescrever."
                        )
                    delete_destination_tables(app_destination, APP_TABLES_IN_ORDER)
                if destination_has_data(finance_destination, FINANCE_TABLES_IN_ORDER):
                    if not truncate_existing:
                        raise RuntimeError(
                            "O warehouse financeiro de destino ja possui dados. Rode com --truncate-existing para sobrescrever."
                        )
                    delete_destination_tables(finance_destination, FINANCE_TABLES_IN_ORDER)

            copied_app_counts: dict[str, int] = {}
            copied_finance_counts: dict[str, int] = {}

            for table_name in APP_TABLES_IN_ORDER:
                copied_app_counts[table_name] = migrate_table(app_source, app_destination, table_name)

            finance_target = same_destination or finance_destination
            for table_name in FINANCE_TABLES_IN_ORDER:
                copied_finance_counts[table_name] = migrate_table(finance_source, finance_target, table_name)

            reset_sequences(app_destination, APP_TABLES_IN_ORDER)
            if same_destination is None:
                reset_sequences(finance_destination, FINANCE_TABLES_IN_ORDER)
            else:
                reset_sequences(app_destination, FINANCE_TABLES_IN_ORDER)

            app_destination.commit()
            if same_destination is None:
                finance_destination.commit()

    print("Migracao concluida.")
    print("App tables:")
    for table_name in APP_TABLES_IN_ORDER:
        print(f" - {table_name}: {copied_app_counts.get(table_name, 0)}")
    print("Warehouse financeiro:")
    for table_name in FINANCE_TABLES_IN_ORDER:
        print(f" - {table_name}: {copied_finance_counts.get(table_name, 0)}")


def main() -> None:
    args = parse_args()
    source_app_db = Path(args.source_app_db).expanduser().resolve()
    source_finance_db = Path(args.source_finance_db).expanduser().resolve()
    database_url = args.database_url.strip()
    finance_database_url = (args.finance_database_url or database_url).strip()

    if not source_app_db.exists():
        raise SystemExit(f"Banco principal nao encontrado: {source_app_db}")
    if not source_finance_db.exists():
        raise SystemExit(f"Banco financeiro nao encontrado: {source_finance_db}")

    migrate_sqlite_to_postgres(
        source_app_db=source_app_db,
        source_finance_db=source_finance_db,
        database_url=database_url,
        finance_database_url=finance_database_url,
        truncate_existing=args.truncate_existing,
    )


if __name__ == "__main__":
    main()
