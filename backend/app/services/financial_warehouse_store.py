from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, selectinload, sessionmaker
from sqlalchemy.sql import func

from ..models import (
    ChecklistParseResult,
    FinancialAnalysisResult,
    FinancialAliasKind,
    FinancialClientPeriodRollup,
    FinancialClientRollup,
    FinancialContractRollup,
    FinancialPeriodSummary,
    FinancialStatementLine,
)

Base = declarative_base()


def _default_finance_database_url() -> str:
    configured = (os.getenv("FINANCE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if configured:
        return _normalize_sqlalchemy_database_url(configured)

    base_dir = Path(__file__).resolve().parents[3]
    data_dir = base_dir / "backend" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'draux_finance.db').resolve()}"


def _normalize_sqlalchemy_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgres://"):
        return "postgresql+psycopg://" + normalized.split("://", 1)[1]
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized.split("://", 1)[1]
    return normalized


class FinanceAnalysisSnapshot(Base):
    __tablename__ = "finance_analysis_snapshots"
    __table_args__ = (
        Index("idx_finance_analysis_snapshots_owner_period", "owner_user_id", "analysis_period_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(Integer, nullable=False, unique=True, index=True)
    owner_user_id = Column(Integer, nullable=True, index=True)
    entity_name = Column(String(255), nullable=True)
    entity_type = Column(String(120), nullable=True)
    analysis_period_label = Column(String(255), nullable=True)
    source_workbook_count = Column(Integer, nullable=False, default=1)
    source_workbook_names_json = Column(Text, nullable=False, default="[]")
    entry_count = Column(Integer, nullable=False, default=0)
    synced_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    dre_lines = relationship(
        "FinanceDreLine",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinanceDreLine.position",
    )
    periods = relationship(
        "FinancePeriod",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinancePeriod.position",
    )
    clients = relationship(
        "FinanceClient",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinanceClient.position",
    )
    client_periods = relationship(
        "FinanceClientPeriod",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinanceClientPeriod.position",
    )
    contracts = relationship(
        "FinanceContract",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinanceContract.position",
    )
    entries = relationship(
        "FinanceEntryRecord",
        cascade="all, delete-orphan",
        back_populates="snapshot",
        order_by="FinanceEntryRecord.position",
    )


class FinanceCanonicalClient(Base):
    __tablename__ = "finance_canonical_clients"
    __table_args__ = (
        UniqueConstraint("owner_scope_id", "normalized_key", name="uq_finance_canonical_clients_scope_key"),
        Index("idx_finance_canonical_clients_scope_name", "owner_scope_id", "canonical_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_scope_id = Column(Integer, nullable=False, default=0)
    normalized_key = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    aliases_json = Column(Text, nullable=False, default="[]")
    first_analysis_id = Column(Integer, nullable=True)
    last_analysis_id = Column(Integer, nullable=True)
    first_period_label = Column(String(255), nullable=True)
    last_period_label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FinanceCanonicalContract(Base):
    __tablename__ = "finance_canonical_contracts"
    __table_args__ = (
        UniqueConstraint("owner_scope_id", "normalized_key", name="uq_finance_canonical_contracts_scope_key"),
        Index("idx_finance_canonical_contracts_scope_name", "owner_scope_id", "canonical_name"),
        Index("idx_finance_canonical_contracts_scope_client", "owner_scope_id", "canonical_client_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_scope_id = Column(Integer, nullable=False, default=0)
    canonical_client_id = Column(Integer, ForeignKey("finance_canonical_clients.id", ondelete="SET NULL"), nullable=True)
    normalized_key = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    aliases_json = Column(Text, nullable=False, default="[]")
    unit = Column(String(120), nullable=True)
    contract_start_date = Column(String(64), nullable=True)
    contract_end_date = Column(String(64), nullable=True)
    first_analysis_id = Column(Integer, nullable=True)
    last_analysis_id = Column(Integer, nullable=True)
    first_period_label = Column(String(255), nullable=True)
    last_period_label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FinanceDreLine(Base):
    __tablename__ = "finance_dre_lines"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_dre_lines_snapshot_position"),
        Index("idx_finance_dre_lines_snapshot_line_key", "snapshot_id", "line_key"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    line_key = Column(String(120), nullable=True)
    label = Column(String(255), nullable=False)
    line_type = Column(String(64), nullable=True)
    amount = Column(Float, nullable=True)
    share_of_gross_revenue = Column(Float, nullable=True)
    share_of_operating_inflows = Column(Float, nullable=True)

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="dre_lines")


class FinancePeriod(Base):
    __tablename__ = "finance_periods"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_periods_snapshot_position"),
        Index("idx_finance_periods_snapshot_period", "snapshot_id", "period_label"),
        Index("idx_finance_periods_snapshot_net_result", "snapshot_id", "net_result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    sheet_name = Column(String(255), nullable=True)
    period_label = Column(String(255), nullable=False)
    fiscal_year = Column(Integer, nullable=True)
    gross_revenue_total = Column(Float, nullable=True)
    receivables_total = Column(Float, nullable=True)
    other_income_total = Column(Float, nullable=True)
    global_expenses_total = Column(Float, nullable=True)
    net_result = Column(Float, nullable=True)
    closing_total = Column(Float, nullable=True)
    pending_entry_count = Column(Integer, nullable=False, default=0)

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="periods")


class FinanceClient(Base):
    __tablename__ = "finance_clients"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_clients_snapshot_position"),
        Index("idx_finance_clients_snapshot_client", "snapshot_id", "client_name"),
        Index("idx_finance_clients_snapshot_revenue", "snapshot_id", "total_received_amount"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    canonical_client_id = Column(Integer, ForeignKey("finance_canonical_clients.id", ondelete="SET NULL"), nullable=True)
    canonical_client_name = Column(String(255), nullable=True)
    client_name = Column(String(255), nullable=False)
    total_received_amount = Column(Float, nullable=True)
    total_expected_amount = Column(Float, nullable=True)
    total_pending_amount = Column(Float, nullable=True)
    contract_count = Column(Integer, nullable=False, default=0)
    months_covered_json = Column(Text, nullable=False, default="[]")
    contract_labels_json = Column(Text, nullable=False, default="[]")

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="clients")


class FinanceClientPeriod(Base):
    __tablename__ = "finance_client_periods"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_client_periods_snapshot_position"),
        Index("idx_finance_client_periods_snapshot_client_period", "snapshot_id", "client_name", "period_label"),
        Index("idx_finance_client_periods_snapshot_revenue", "snapshot_id", "total_received_amount"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    canonical_client_id = Column(Integer, ForeignKey("finance_canonical_clients.id", ondelete="SET NULL"), nullable=True)
    canonical_client_name = Column(String(255), nullable=True)
    client_name = Column(String(255), nullable=False)
    period_label = Column(String(255), nullable=False)
    total_received_amount = Column(Float, nullable=True)
    total_expected_amount = Column(Float, nullable=True)
    total_pending_amount = Column(Float, nullable=True)
    contract_count = Column(Integer, nullable=False, default=0)
    contract_labels_json = Column(Text, nullable=False, default="[]")

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="client_periods")


class FinanceContract(Base):
    __tablename__ = "finance_contracts"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_contracts_snapshot_position"),
        Index("idx_finance_contracts_snapshot_client_contract", "snapshot_id", "client_name", "contract_label"),
        Index("idx_finance_contracts_snapshot_revenue", "snapshot_id", "total_received_amount"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    canonical_client_id = Column(Integer, ForeignKey("finance_canonical_clients.id", ondelete="SET NULL"), nullable=True)
    canonical_client_name = Column(String(255), nullable=True)
    canonical_contract_id = Column(
        Integer,
        ForeignKey("finance_canonical_contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    canonical_contract_name = Column(String(255), nullable=True)
    contract_label = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=True)
    unit = Column(String(120), nullable=True)
    contract_start_date = Column(String(64), nullable=True)
    contract_end_date = Column(String(64), nullable=True)
    latest_status = Column(String(120), nullable=True)
    total_received_amount = Column(Float, nullable=True)
    total_expected_amount = Column(Float, nullable=True)
    total_pending_amount = Column(Float, nullable=True)
    entry_count = Column(Integer, nullable=False, default=0)
    months_covered_json = Column(Text, nullable=False, default="[]")
    source_sheet_names_json = Column(Text, nullable=False, default="[]")

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="contracts")


class FinanceEntryRecord(Base):
    __tablename__ = "finance_entries"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_finance_entries_snapshot_position"),
        Index("idx_finance_entries_snapshot_period", "snapshot_id", "period_label"),
        Index("idx_finance_entries_snapshot_counterparty", "snapshot_id", "counterparty"),
        Index("idx_finance_entries_snapshot_contract", "snapshot_id", "contract_label"),
        Index("idx_finance_entries_snapshot_type", "snapshot_id", "entry_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("finance_analysis_snapshots.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    canonical_client_id = Column(Integer, ForeignKey("finance_canonical_clients.id", ondelete="SET NULL"), nullable=True)
    canonical_client_name = Column(String(255), nullable=True)
    canonical_contract_id = Column(
        Integer,
        ForeignKey("finance_canonical_contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    canonical_contract_name = Column(String(255), nullable=True)
    period_label = Column(String(255), nullable=False)
    sheet_name = Column(String(255), nullable=False)
    section_key = Column(String(120), nullable=False)
    section_title = Column(String(255), nullable=False)
    source_kind = Column(String(64), nullable=True)
    owner_label = Column(String(255), nullable=True)
    entry_type = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=True)
    status = Column(String(255), nullable=True)
    entry_date = Column(String(64), nullable=True)
    due_date = Column(String(64), nullable=True)
    counterparty = Column(String(255), nullable=True)
    unit = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    contract_label = Column(String(255), nullable=True)
    contract_start_date = Column(String(64), nullable=True)
    contract_end_date = Column(String(64), nullable=True)
    reconciliation_status = Column(String(64), nullable=True)
    reconciliation_score = Column(Float, nullable=True)
    reconciliation_partner_period_label = Column(String(255), nullable=True)
    reconciliation_partner_description = Column(Text, nullable=True)
    reconciliation_alias_label = Column(String(255), nullable=True)
    reconciliation_note = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=False, default="[]")

    snapshot = relationship("FinanceAnalysisSnapshot", back_populates="entries")


class FinancialWarehouseStore:
    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = _normalize_sqlalchemy_database_url(database_url or _default_finance_database_url())
        engine_kwargs = {"future": True, "pool_pre_ping": True}
        if self.database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(self.database_url, **engine_kwargs)
        self.session_factory = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False, future=True)
        self._initialize()

    def _initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_schema_extensions()
        self._create_views()

    def _ensure_schema_extensions(self) -> None:
        self._ensure_column("finance_clients", "canonical_client_id", "INTEGER")
        self._ensure_column("finance_clients", "canonical_client_name", "VARCHAR(255)")
        self._ensure_column("finance_client_periods", "canonical_client_id", "INTEGER")
        self._ensure_column("finance_client_periods", "canonical_client_name", "VARCHAR(255)")
        self._ensure_column("finance_contracts", "canonical_client_id", "INTEGER")
        self._ensure_column("finance_contracts", "canonical_client_name", "VARCHAR(255)")
        self._ensure_column("finance_contracts", "canonical_contract_id", "INTEGER")
        self._ensure_column("finance_contracts", "canonical_contract_name", "VARCHAR(255)")
        self._ensure_column("finance_entries", "canonical_client_id", "INTEGER")
        self._ensure_column("finance_entries", "canonical_client_name", "VARCHAR(255)")
        self._ensure_column("finance_entries", "canonical_contract_id", "INTEGER")
        self._ensure_column("finance_entries", "canonical_contract_name", "VARCHAR(255)")
        self._ensure_column("finance_entries", "source_kind", "VARCHAR(64)")
        self._ensure_column("finance_entries", "reconciliation_status", "VARCHAR(64)")
        self._ensure_column("finance_entries", "reconciliation_score", "FLOAT")
        self._ensure_column("finance_entries", "reconciliation_partner_period_label", "VARCHAR(255)")
        self._ensure_column("finance_entries", "reconciliation_partner_description", "TEXT")
        self._ensure_column("finance_entries", "reconciliation_alias_label", "VARCHAR(255)")
        self._ensure_column("finance_entries", "reconciliation_note", "TEXT")

        statements = [
            "CREATE INDEX IF NOT EXISTS idx_finance_clients_snapshot_canonical_client ON finance_clients (snapshot_id, canonical_client_id)",
            "CREATE INDEX IF NOT EXISTS idx_finance_client_periods_snapshot_canonical_client ON finance_client_periods (snapshot_id, canonical_client_id)",
            "CREATE INDEX IF NOT EXISTS idx_finance_contracts_snapshot_canonical_client ON finance_contracts (snapshot_id, canonical_client_id)",
            "CREATE INDEX IF NOT EXISTS idx_finance_contracts_snapshot_canonical_contract ON finance_contracts (snapshot_id, canonical_contract_id)",
            "CREATE INDEX IF NOT EXISTS idx_finance_entries_snapshot_canonical_client ON finance_entries (snapshot_id, canonical_client_id)",
            "CREATE INDEX IF NOT EXISTS idx_finance_entries_snapshot_canonical_contract ON finance_entries (snapshot_id, canonical_contract_id)",
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def _ensure_column(self, table_name: str, column_name: str, column_definition: str) -> None:
        inspector = inspect(self.engine)
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name in existing_columns:
            return
        with self.engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"))

    def _create_views(self) -> None:
        statements = [
            """
            DROP VIEW IF EXISTS finance_client_revenue_view
            """,
            """
            CREATE VIEW finance_client_revenue_view AS
            SELECT
                snapshots.analysis_id AS analysis_id,
                clients.snapshot_id AS snapshot_id,
                clients.position AS position,
                snapshots.entity_name AS entity_name,
                snapshots.entity_type AS entity_type,
                snapshots.analysis_period_label AS analysis_period_label,
                clients.canonical_client_id AS canonical_client_id,
                clients.canonical_client_name AS canonical_client_name,
                clients.client_name AS client_name,
                clients.total_received_amount AS total_received_amount,
                clients.total_expected_amount AS total_expected_amount,
                clients.total_pending_amount AS total_pending_amount,
                clients.contract_count AS contract_count,
                clients.months_covered_json AS months_covered_json,
                clients.contract_labels_json AS contract_labels_json
            FROM finance_clients AS clients
            JOIN finance_analysis_snapshots AS snapshots ON snapshots.id = clients.snapshot_id
            """,
            """
            DROP VIEW IF EXISTS finance_contract_revenue_view
            """,
            """
            CREATE VIEW finance_contract_revenue_view AS
            SELECT
                snapshots.analysis_id AS analysis_id,
                contracts.snapshot_id AS snapshot_id,
                contracts.position AS position,
                snapshots.entity_name AS entity_name,
                snapshots.entity_type AS entity_type,
                snapshots.analysis_period_label AS analysis_period_label,
                contracts.canonical_client_id AS canonical_client_id,
                contracts.canonical_client_name AS canonical_client_name,
                contracts.canonical_contract_id AS canonical_contract_id,
                contracts.canonical_contract_name AS canonical_contract_name,
                contracts.contract_label AS contract_label,
                contracts.client_name AS client_name,
                contracts.unit AS unit,
                contracts.contract_start_date AS contract_start_date,
                contracts.contract_end_date AS contract_end_date,
                contracts.latest_status AS latest_status,
                contracts.total_received_amount AS total_received_amount,
                contracts.total_expected_amount AS total_expected_amount,
                contracts.total_pending_amount AS total_pending_amount,
                contracts.entry_count AS entry_count,
                contracts.months_covered_json AS months_covered_json,
                contracts.source_sheet_names_json AS source_sheet_names_json
            FROM finance_contracts AS contracts
            JOIN finance_analysis_snapshots AS snapshots ON snapshots.id = contracts.snapshot_id
            """,
            """
            DROP VIEW IF EXISTS finance_period_result_view
            """,
            """
            CREATE VIEW finance_period_result_view AS
            SELECT
                snapshots.analysis_id AS analysis_id,
                periods.snapshot_id AS snapshot_id,
                periods.position AS position,
                snapshots.entity_name AS entity_name,
                snapshots.entity_type AS entity_type,
                snapshots.analysis_period_label AS analysis_period_label,
                periods.sheet_name AS sheet_name,
                periods.period_label AS period_label,
                periods.fiscal_year AS fiscal_year,
                periods.gross_revenue_total AS gross_revenue_total,
                periods.receivables_total AS receivables_total,
                periods.other_income_total AS other_income_total,
                periods.global_expenses_total AS global_expenses_total,
                periods.net_result AS net_result,
                periods.closing_total AS closing_total,
                periods.pending_entry_count AS pending_entry_count
            FROM finance_periods AS periods
            JOIN finance_analysis_snapshots AS snapshots ON snapshots.id = periods.snapshot_id
            """,
            """
            DROP VIEW IF EXISTS finance_entry_view
            """,
            """
            CREATE VIEW finance_entry_view AS
            SELECT
                snapshots.analysis_id AS analysis_id,
                entries.snapshot_id AS snapshot_id,
                entries.position AS position,
                snapshots.entity_name AS entity_name,
                snapshots.entity_type AS entity_type,
                snapshots.analysis_period_label AS analysis_period_label,
                entries.canonical_client_id AS canonical_client_id,
                entries.canonical_client_name AS canonical_client_name,
                entries.canonical_contract_id AS canonical_contract_id,
                entries.canonical_contract_name AS canonical_contract_name,
                entries.period_label AS period_label,
                entries.sheet_name AS sheet_name,
                entries.section_key AS section_key,
                entries.section_title AS section_title,
                entries.owner_label AS owner_label,
                entries.source_kind AS source_kind,
                entries.entry_type AS entry_type,
                entries.description AS description,
                entries.amount AS amount,
                entries.status AS status,
                entries.entry_date AS entry_date,
                entries.due_date AS due_date,
                entries.counterparty AS counterparty,
                entries.unit AS unit,
                entries.notes AS notes,
                entries.contract_label AS contract_label,
                entries.contract_start_date AS contract_start_date,
                entries.contract_end_date AS contract_end_date,
                entries.reconciliation_status AS reconciliation_status,
                entries.reconciliation_score AS reconciliation_score,
                entries.reconciliation_partner_period_label AS reconciliation_partner_period_label,
                entries.reconciliation_partner_description AS reconciliation_partner_description,
                entries.reconciliation_note AS reconciliation_note,
                entries.tags_json AS tags_json
            FROM finance_entries AS entries
            JOIN finance_analysis_snapshots AS snapshots ON snapshots.id = entries.snapshot_id
            """,
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def sync_analysis(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        owner_user_id: Optional[int] = None,
    ) -> None:
        with self.session_factory.begin() as session:
            existing = session.execute(
                select(FinanceAnalysisSnapshot).where(FinanceAnalysisSnapshot.analysis_id == analysis_id)
            ).scalar_one_or_none()
            if existing is not None:
                session.delete(existing)
                session.flush()

            analysis = parsed.financial_analysis
            if analysis is None:
                return

            owner_scope_id = self._resolve_owner_scope_id(owner_user_id)
            period_label = parsed.periodo_analise or self._build_analysis_period_label(analysis)
            canonical_clients_by_key = self._resolve_canonical_clients(
                session,
                analysis_id=analysis_id,
                owner_scope_id=owner_scope_id,
                period_label=period_label,
                analysis=analysis,
            )
            canonical_contracts_by_key = self._resolve_canonical_contracts(
                session,
                analysis_id=analysis_id,
                owner_scope_id=owner_scope_id,
                period_label=period_label,
                analysis=analysis,
                canonical_clients_by_key=canonical_clients_by_key,
            )
            self._absorb_reconciliation_aliases(
                analysis=analysis,
                canonical_clients_by_key=canonical_clients_by_key,
                canonical_contracts_by_key=canonical_contracts_by_key,
            )

            snapshot = FinanceAnalysisSnapshot(
                analysis_id=analysis_id,
                owner_user_id=owner_user_id,
                entity_name=parsed.orgao or analysis.entity_name,
                entity_type=parsed.tipo_orgao,
                analysis_period_label=period_label,
                source_workbook_count=analysis.source_workbook_count,
                source_workbook_names_json=self._dump_json_list(analysis.source_workbook_names),
                entry_count=analysis.entry_count,
            )
            session.add(snapshot)
            session.flush()

            snapshot.dre_lines = [
                FinanceDreLine(
                    position=position,
                    line_key=line.key,
                    label=line.label,
                    line_type=line.line_type,
                    amount=line.amount,
                    share_of_gross_revenue=line.share_of_gross_revenue,
                    share_of_operating_inflows=line.share_of_operating_inflows,
                )
                for position, line in enumerate(analysis.dre_lines, start=1)
            ]
            snapshot.periods = [
                FinancePeriod(
                    position=position,
                    sheet_name=month.sheet_name,
                    period_label=month.period_label,
                    fiscal_year=month.year,
                    gross_revenue_total=month.gross_revenue_total,
                    receivables_total=month.receivables_total,
                    other_income_total=month.other_income_total,
                    global_expenses_total=month.global_expenses_total,
                    net_result=month.net_result,
                    closing_total=month.closing_total,
                    pending_entry_count=month.pending_entry_count,
                )
                for position, month in enumerate(analysis.months, start=1)
            ]
            snapshot.clients = [
                FinanceClient(
                    position=position,
                    canonical_client_id=self._get_canonical_id(
                        canonical_clients_by_key.get(self._normalize_entity_key(client.client_name))
                    ),
                    canonical_client_name=self._get_canonical_name(
                        canonical_clients_by_key.get(self._normalize_entity_key(client.client_name))
                    ),
                    client_name=client.client_name,
                    total_received_amount=client.total_received_amount,
                    total_expected_amount=client.total_expected_amount,
                    total_pending_amount=client.total_pending_amount,
                    contract_count=client.contract_count,
                    months_covered_json=self._dump_json_list(client.months_covered),
                    contract_labels_json=self._dump_json_list(client.contract_labels),
                )
                for position, client in enumerate(analysis.client_rollups, start=1)
            ]
            snapshot.client_periods = [
                FinanceClientPeriod(
                    position=position,
                    canonical_client_id=self._get_canonical_id(
                        canonical_clients_by_key.get(self._normalize_entity_key(entry.client_name))
                    ),
                    canonical_client_name=self._get_canonical_name(
                        canonical_clients_by_key.get(self._normalize_entity_key(entry.client_name))
                    ),
                    client_name=entry.client_name,
                    period_label=entry.period_label,
                    total_received_amount=entry.total_received_amount,
                    total_expected_amount=entry.total_expected_amount,
                    total_pending_amount=entry.total_pending_amount,
                    contract_count=entry.contract_count,
                    contract_labels_json=self._dump_json_list(entry.contract_labels),
                )
                for position, entry in enumerate(analysis.client_period_rollups, start=1)
            ]
            snapshot.contracts = [
                FinanceContract(
                    position=position,
                    canonical_client_id=self._get_canonical_id(
                        canonical_clients_by_key.get(self._normalize_entity_key(contract.client_name))
                    ),
                    canonical_client_name=self._get_canonical_name(
                        canonical_clients_by_key.get(self._normalize_entity_key(contract.client_name))
                    ),
                    canonical_contract_id=self._get_canonical_id(
                        canonical_contracts_by_key.get(self._normalize_entity_key(contract.contract_label))
                    ),
                    canonical_contract_name=self._get_canonical_name(
                        canonical_contracts_by_key.get(self._normalize_entity_key(contract.contract_label))
                    ),
                    contract_label=contract.contract_label,
                    client_name=contract.client_name,
                    unit=contract.unit,
                    contract_start_date=contract.contract_start_date,
                    contract_end_date=contract.contract_end_date,
                    latest_status=contract.latest_status,
                    total_received_amount=contract.total_received_amount,
                    total_expected_amount=contract.total_expected_amount,
                    total_pending_amount=contract.total_pending_amount,
                    entry_count=contract.entry_count,
                    months_covered_json=self._dump_json_list(contract.months_covered),
                    source_sheet_names_json=self._dump_json_list(contract.source_sheet_names),
                )
                for position, contract in enumerate(analysis.contract_rollups, start=1)
            ]
            entry_position = 1
            snapshot.entries = []
            for month in analysis.months:
                for section in month.sections:
                    for entry in section.entries:
                        canonical_contract = canonical_contracts_by_key.get(
                            self._normalize_entity_key(entry.contract_label)
                        )
                        canonical_client = canonical_clients_by_key.get(
                            self._normalize_entity_key(entry.counterparty)
                        )
                        if canonical_client is None and canonical_contract is not None:
                            canonical_client = self._resolve_canonical_client_from_contract(
                                session,
                                canonical_contract,
                            )
                        snapshot.entries.append(
                            FinanceEntryRecord(
                                position=entry_position,
                                canonical_client_id=self._get_canonical_id(canonical_client),
                                canonical_client_name=self._get_canonical_name(canonical_client),
                                canonical_contract_id=self._get_canonical_id(canonical_contract),
                                canonical_contract_name=self._get_canonical_name(canonical_contract),
                                period_label=month.period_label,
                                sheet_name=entry.sheet_name,
                                section_key=section.section_key,
                                section_title=section.title,
                                source_kind=entry.source_kind,
                                owner_label=entry.owner_label or section.owner_label,
                                entry_type=entry.entry_type,
                                description=entry.description,
                                amount=entry.amount,
                                status=entry.status,
                                entry_date=entry.date,
                                due_date=entry.due_date,
                                counterparty=entry.counterparty,
                                unit=entry.unit,
                                notes=entry.notes,
                                contract_label=entry.contract_label,
                                contract_start_date=entry.contract_start_date,
                                contract_end_date=entry.contract_end_date,
                                reconciliation_status=entry.reconciliation_status,
                                reconciliation_score=entry.reconciliation_score,
                                reconciliation_partner_period_label=entry.reconciliation_partner_period_label,
                                reconciliation_partner_description=entry.reconciliation_partner_description,
                                reconciliation_alias_label=entry.reconciliation_alias_label,
                                reconciliation_note=entry.reconciliation_note,
                                tags_json=self._dump_json_list(entry.tags),
                            )
                        )
                        entry_position += 1

    def _resolve_owner_scope_id(self, owner_user_id: Optional[int]) -> int:
        return int(owner_user_id or 0)

    def _serialize_timestamp(self, value) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _serialize_aliases(self, canonical_name: Optional[str], aliases_json: Optional[str]) -> list[str]:
        canonical_key = self._normalize_entity_key(canonical_name)
        aliases: list[str] = []
        seen_keys: set[str] = set()
        for alias in self._load_json_list(aliases_json):
            alias_key = self._normalize_entity_key(alias)
            if not alias_key or alias_key == canonical_key or alias_key in seen_keys:
                continue
            aliases.append(alias)
            seen_keys.add(alias_key)
        return aliases

    def _serialize_canonical_alias_item(
        self,
        kind: FinancialAliasKind,
        entity,
        *,
        canonical_client_name: Optional[str] = None,
    ) -> dict[str, object]:
        return {
            "kind": kind,
            "entity_id": int(entity.id),
            "canonical_name": entity.canonical_name,
            "aliases": self._serialize_aliases(entity.canonical_name, entity.aliases_json),
            "canonical_client_id": getattr(entity, "canonical_client_id", None),
            "canonical_client_name": canonical_client_name,
            "unit": getattr(entity, "unit", None),
            "contract_start_date": getattr(entity, "contract_start_date", None),
            "contract_end_date": getattr(entity, "contract_end_date", None),
            "first_period_label": getattr(entity, "first_period_label", None),
            "last_period_label": getattr(entity, "last_period_label", None),
            "updated_at": self._serialize_timestamp(getattr(entity, "updated_at", None)),
        }

    def _load_canonical_entity(
        self,
        session: Session,
        *,
        kind: FinancialAliasKind,
        owner_scope_id: int,
        entity_id: int,
    ):
        model = FinanceCanonicalClient if kind == "client" else FinanceCanonicalContract
        entity = session.get(model, int(entity_id))
        if entity is None or entity.owner_scope_id != owner_scope_id:
            return None
        return entity

    def _find_alias_conflict(
        self,
        session: Session,
        *,
        kind: FinancialAliasKind,
        owner_scope_id: int,
        entity_id: int,
        alias_key: str,
    ):
        model = FinanceCanonicalClient if kind == "client" else FinanceCanonicalContract
        entities = session.execute(select(model).where(model.owner_scope_id == owner_scope_id)).scalars().all()
        for entity in entities:
            if int(entity.id) == int(entity_id):
                continue
            candidate_keys = {
                self._normalize_entity_key(entity.canonical_name),
                *{self._normalize_entity_key(alias) for alias in self._load_json_list(entity.aliases_json)},
            }
            if alias_key in candidate_keys:
                return entity
        return None

    def build_reconciliation_alias_registry(self, owner_user_id: Optional[int] = None) -> dict[str, dict[str, set[str]]]:
        owner_scope_id = self._resolve_owner_scope_id(owner_user_id)
        registry: dict[str, dict[str, set[str]]] = {"clients": {}, "contracts": {}}
        reverse_aliases: dict[str, dict[str, set[str]]] = {"clients": {}, "contracts": {}}
        with self.session_factory() as session:
            clients = session.execute(
                select(FinanceCanonicalClient).where(FinanceCanonicalClient.owner_scope_id == owner_scope_id)
            ).scalars().all()
            contracts = session.execute(
                select(FinanceCanonicalContract).where(FinanceCanonicalContract.owner_scope_id == owner_scope_id)
            ).scalars().all()

        for client in clients:
            aliases = {client.canonical_name, *self._load_json_list(client.aliases_json)}
            filtered_aliases = {alias for alias in aliases if self._normalize_entity_key(alias)}
            registry["clients"][client.normalized_key] = filtered_aliases
            for alias in filtered_aliases:
                reverse_aliases["clients"].setdefault(self._normalize_entity_key(alias), set()).add(client.normalized_key)
        for contract in contracts:
            aliases = {contract.canonical_name, *self._load_json_list(contract.aliases_json)}
            filtered_aliases = {alias for alias in aliases if self._normalize_entity_key(alias)}
            registry["contracts"][contract.normalized_key] = filtered_aliases
            for alias in filtered_aliases:
                reverse_aliases["contracts"].setdefault(self._normalize_entity_key(alias), set()).add(contract.normalized_key)

        for bucket_name in ("clients", "contracts"):
            for normalized_key, aliases in list(registry[bucket_name].items()):
                canonical_name = next(
                    (
                        alias
                        for alias in aliases
                        if self._normalize_entity_key(alias) == normalized_key
                    ),
                    None,
                )
                registry[bucket_name][normalized_key] = {
                    alias
                    for alias in aliases
                    if alias == canonical_name
                    or len(reverse_aliases[bucket_name].get(self._normalize_entity_key(alias), set())) == 1
                }
        return registry

    def list_canonical_aliases(
        self,
        owner_user_id: Optional[int] = None,
        *,
        kind: FinancialAliasKind,
        limit: int = 80,
    ) -> list[dict[str, object]]:
        owner_scope_id = self._resolve_owner_scope_id(owner_user_id)
        with self.session_factory() as session:
            if kind == "client":
                rows = session.execute(
                    select(FinanceCanonicalClient)
                    .where(FinanceCanonicalClient.owner_scope_id == owner_scope_id)
                    .order_by(FinanceCanonicalClient.canonical_name.asc())
                    .limit(int(limit))
                ).scalars().all()
                return [self._serialize_canonical_alias_item("client", entity) for entity in rows]

            rows = session.execute(
                select(FinanceCanonicalContract)
                .where(FinanceCanonicalContract.owner_scope_id == owner_scope_id)
                .order_by(FinanceCanonicalContract.canonical_name.asc())
                .limit(int(limit))
            ).scalars().all()
            client_ids = {row.canonical_client_id for row in rows if row.canonical_client_id is not None}
            client_map: dict[int, FinanceCanonicalClient] = {}
            if client_ids:
                client_map = {
                    row.id: row
                    for row in session.execute(
                        select(FinanceCanonicalClient).where(FinanceCanonicalClient.id.in_(client_ids))
                    ).scalars().all()
                }
            return [
                self._serialize_canonical_alias_item(
                    "contract",
                    entity,
                    canonical_client_name=client_map.get(entity.canonical_client_id).canonical_name
                    if entity.canonical_client_id in client_map
                    else None,
                )
                for entity in rows
            ]

    def add_canonical_alias(
        self,
        owner_user_id: Optional[int] = None,
        *,
        kind: FinancialAliasKind,
        entity_id: int,
        alias: str,
    ) -> dict[str, object]:
        owner_scope_id = self._resolve_owner_scope_id(owner_user_id)
        alias_value = alias.strip()
        alias_key = self._normalize_entity_key(alias_value)
        if not alias_key:
            raise ValueError("Informe um alias válido antes de salvar.")

        with self.session_factory() as session:
            entity = self._load_canonical_entity(
                session,
                kind=kind,
                owner_scope_id=owner_scope_id,
                entity_id=entity_id,
            )
            if entity is None:
                raise LookupError("A entidade canônica solicitada não foi encontrada.")

            if alias_key == self._normalize_entity_key(entity.canonical_name):
                return self._serialize_canonical_alias_item(
                    kind,
                    entity,
                    canonical_client_name=self._load_contract_client_name(session, entity) if kind == "contract" else None,
                )

            conflict = self._find_alias_conflict(
                session,
                kind=kind,
                owner_scope_id=owner_scope_id,
                entity_id=entity_id,
                alias_key=alias_key,
            )
            if conflict is not None:
                raise ValueError(
                    f"Esse alias já está associado a {conflict.canonical_name}. Use um identificador mais específico."
                )

            entity.aliases_json = self._merge_aliases(entity.aliases_json, alias_value)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return self._serialize_canonical_alias_item(
                kind,
                entity,
                canonical_client_name=self._load_contract_client_name(session, entity) if kind == "contract" else None,
            )

    def remove_canonical_alias(
        self,
        owner_user_id: Optional[int] = None,
        *,
        kind: FinancialAliasKind,
        entity_id: int,
        alias: str,
    ) -> dict[str, object]:
        owner_scope_id = self._resolve_owner_scope_id(owner_user_id)
        alias_key = self._normalize_entity_key(alias)
        if not alias_key:
            raise ValueError("Informe um alias válido para remover.")

        with self.session_factory() as session:
            entity = self._load_canonical_entity(
                session,
                kind=kind,
                owner_scope_id=owner_scope_id,
                entity_id=entity_id,
            )
            if entity is None:
                raise LookupError("A entidade canônica solicitada não foi encontrada.")

            if alias_key == self._normalize_entity_key(entity.canonical_name):
                raise ValueError("O nome canônico principal não pode ser removido.")

            remaining_aliases = [
                candidate
                for candidate in self._load_json_list(entity.aliases_json)
                if self._normalize_entity_key(candidate) != alias_key
            ]
            entity.aliases_json = self._dump_json_list(remaining_aliases)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return self._serialize_canonical_alias_item(
                kind,
                entity,
                canonical_client_name=self._load_contract_client_name(session, entity) if kind == "contract" else None,
            )

    def _load_contract_client_name(
        self,
        session: Session,
        contract: Optional[FinanceCanonicalContract],
    ) -> Optional[str]:
        if contract is None or contract.canonical_client_id is None:
            return None
        client = session.get(FinanceCanonicalClient, contract.canonical_client_id)
        return client.canonical_name if client is not None else None

    def _build_analysis_period_label(self, analysis: FinancialAnalysisResult) -> Optional[str]:
        if not analysis.months:
            return None
        first_period = analysis.months[0].period_label
        last_period = analysis.months[-1].period_label
        return first_period if first_period == last_period else f"{first_period} a {last_period}"

    def _normalize_entity_key(self, value: Optional[str]) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        cleaned = unicodedata.normalize("NFKD", cleaned)
        cleaned = "".join(character for character in cleaned if not unicodedata.combining(character))
        cleaned = cleaned.casefold()
        cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _resolve_canonical_clients(
        self,
        session: Session,
        *,
        analysis_id: int,
        owner_scope_id: int,
        period_label: Optional[str],
        analysis: FinancialAnalysisResult,
    ) -> dict[str, FinanceCanonicalClient]:
        resolved: dict[str, FinanceCanonicalClient] = {}
        for client in analysis.client_rollups:
            canonical = self._resolve_canonical_client(
                session,
                owner_scope_id=owner_scope_id,
                client_name=client.client_name,
                analysis_id=analysis_id,
                period_label=period_label,
            )
            if canonical is not None:
                resolved[self._normalize_entity_key(client.client_name)] = canonical
        return resolved

    def _resolve_canonical_contracts(
        self,
        session: Session,
        *,
        analysis_id: int,
        owner_scope_id: int,
        period_label: Optional[str],
        analysis: FinancialAnalysisResult,
        canonical_clients_by_key: dict[str, FinanceCanonicalClient],
    ) -> dict[str, FinanceCanonicalContract]:
        resolved: dict[str, FinanceCanonicalContract] = {}
        for contract in analysis.contract_rollups:
            canonical_client = canonical_clients_by_key.get(self._normalize_entity_key(contract.client_name))
            canonical_contract = self._resolve_canonical_contract(
                session,
                owner_scope_id=owner_scope_id,
                contract=contract,
                canonical_client=canonical_client,
                analysis_id=analysis_id,
                period_label=period_label,
            )
            if canonical_contract is not None:
                resolved[self._normalize_entity_key(contract.contract_label)] = canonical_contract
        return resolved

    def _resolve_canonical_client(
        self,
        session: Session,
        *,
        owner_scope_id: int,
        client_name: Optional[str],
        analysis_id: int,
        period_label: Optional[str],
    ) -> Optional[FinanceCanonicalClient]:
        normalized_key = self._normalize_entity_key(client_name)
        if not normalized_key:
            return None
        canonical = session.execute(
            select(FinanceCanonicalClient).where(
                FinanceCanonicalClient.owner_scope_id == owner_scope_id,
                FinanceCanonicalClient.normalized_key == normalized_key,
            )
        ).scalar_one_or_none()
        if canonical is None:
            canonical = FinanceCanonicalClient(
                owner_scope_id=owner_scope_id,
                normalized_key=normalized_key,
                canonical_name=(client_name or "").strip(),
                aliases_json=self._dump_json_list([client_name] if client_name else []),
                first_analysis_id=analysis_id,
                last_analysis_id=analysis_id,
                first_period_label=period_label,
                last_period_label=period_label,
            )
            session.add(canonical)
            session.flush()
            return canonical

        canonical.canonical_name = self._prefer_canonical_name(canonical.canonical_name, client_name)
        canonical.aliases_json = self._merge_aliases(canonical.aliases_json, client_name)
        canonical.last_analysis_id = analysis_id
        canonical.last_period_label = period_label or canonical.last_period_label
        if canonical.first_period_label is None:
            canonical.first_period_label = period_label
        return canonical

    def _resolve_canonical_contract(
        self,
        session: Session,
        *,
        owner_scope_id: int,
        contract: FinancialContractRollup,
        canonical_client: Optional[FinanceCanonicalClient],
        analysis_id: int,
        period_label: Optional[str],
    ) -> Optional[FinanceCanonicalContract]:
        normalized_key = self._normalize_entity_key(contract.contract_label)
        if not normalized_key:
            return None
        canonical = session.execute(
            select(FinanceCanonicalContract).where(
                FinanceCanonicalContract.owner_scope_id == owner_scope_id,
                FinanceCanonicalContract.normalized_key == normalized_key,
            )
        ).scalar_one_or_none()
        canonical_client_id = self._get_canonical_id(canonical_client)
        if canonical is None:
            canonical = FinanceCanonicalContract(
                owner_scope_id=owner_scope_id,
                canonical_client_id=canonical_client_id,
                normalized_key=normalized_key,
                canonical_name=contract.contract_label.strip(),
                aliases_json=self._dump_json_list([contract.contract_label]),
                unit=contract.unit,
                contract_start_date=contract.contract_start_date,
                contract_end_date=contract.contract_end_date,
                first_analysis_id=analysis_id,
                last_analysis_id=analysis_id,
                first_period_label=period_label,
                last_period_label=period_label,
            )
            session.add(canonical)
            session.flush()
            return canonical

        canonical.canonical_name = self._prefer_canonical_name(canonical.canonical_name, contract.contract_label)
        canonical.aliases_json = self._merge_aliases(canonical.aliases_json, contract.contract_label)
        if canonical.canonical_client_id is None and canonical_client_id is not None:
            canonical.canonical_client_id = canonical_client_id
        if canonical.unit is None:
            canonical.unit = contract.unit
        if canonical.contract_start_date is None:
            canonical.contract_start_date = contract.contract_start_date
        if canonical.contract_end_date is None:
            canonical.contract_end_date = contract.contract_end_date
        canonical.last_analysis_id = analysis_id
        canonical.last_period_label = period_label or canonical.last_period_label
        if canonical.first_period_label is None:
            canonical.first_period_label = period_label
        return canonical

    def _resolve_canonical_client_from_contract(
        self,
        session: Session,
        canonical_contract: Optional[FinanceCanonicalContract],
    ) -> Optional[FinanceCanonicalClient]:
        if canonical_contract is None or canonical_contract.canonical_client_id is None:
            return None
        return session.get(FinanceCanonicalClient, canonical_contract.canonical_client_id)

    def _prefer_canonical_name(self, current_name: Optional[str], incoming_name: Optional[str]) -> str:
        current = (current_name or "").strip()
        incoming = (incoming_name or "").strip()
        if not current:
            return incoming
        if not incoming:
            return current
        return incoming if len(incoming) > len(current) else current

    def _merge_aliases(self, aliases_json: Optional[str], candidate: Optional[str]) -> str:
        aliases = self._load_json_list(aliases_json)
        value = (candidate or "").strip()
        if not value:
            return self._dump_json_list(aliases)
        existing_keys = {self._normalize_entity_key(alias) for alias in aliases}
        if self._normalize_entity_key(value) not in existing_keys:
            aliases.append(value)
        return self._dump_json_list(aliases)

    def _get_canonical_id(self, entity) -> Optional[int]:
        return getattr(entity, "id", None) if entity is not None else None

    def _get_canonical_name(self, entity) -> Optional[str]:
        return getattr(entity, "canonical_name", None) if entity is not None else None

    def _absorb_reconciliation_aliases(
        self,
        *,
        analysis: FinancialAnalysisResult,
        canonical_clients_by_key: dict[str, FinanceCanonicalClient],
        canonical_contracts_by_key: dict[str, FinanceCanonicalContract],
    ) -> None:
        matched_bank_entries = self._index_bank_entries_by_reconciliation(analysis)
        for month in analysis.months:
            for section in month.sections:
                for entry in section.entries:
                    if entry.source_kind != "workbook" or entry.reconciliation_status not in {"matched", "probable"}:
                        continue
                    bank_entry = matched_bank_entries.get(self._build_reconciliation_signature(month.period_label, entry))
                    if bank_entry is None:
                        continue
                    client = canonical_clients_by_key.get(self._normalize_entity_key(entry.counterparty))
                    contract = canonical_contracts_by_key.get(self._normalize_entity_key(entry.contract_label))
                    for alias in self._extract_reconciliation_alias_candidates(bank_entry):
                        if client is not None:
                            client.aliases_json = self._merge_aliases(client.aliases_json, alias)
                        if contract is not None:
                            contract.aliases_json = self._merge_aliases(contract.aliases_json, alias)

    def _index_bank_entries_by_reconciliation(
        self,
        analysis: FinancialAnalysisResult,
    ) -> dict[tuple[str, str, float, str], object]:
        index: dict[tuple[str, str, float, str], object] = {}
        for month in analysis.months:
            for section in month.sections:
                for entry in section.entries:
                    if entry.source_kind != "bank_statement" or entry.reconciliation_status not in {"matched", "probable"}:
                        continue
                    signature = (
                        (entry.reconciliation_partner_period_label or "").strip(),
                        (entry.reconciliation_partner_description or "").strip(),
                        round(abs(float(entry.amount or 0.0)), 2),
                        entry.reconciliation_status or "",
                    )
                    if signature not in index:
                        index[signature] = entry
        return index

    def _build_reconciliation_signature(self, period_label: str, entry) -> tuple[str, str, float, str]:
        return (
            (entry.reconciliation_partner_period_label or period_label or "").strip(),
            (entry.description or "").strip(),
            round(abs(float(entry.amount or 0.0)), 2),
            entry.reconciliation_status or "",
        )

    def _extract_reconciliation_alias_candidates(self, entry) -> list[str]:
        candidates: list[str] = []
        for value in (getattr(entry, "counterparty", None),):
            normalized = self._normalize_entity_key(value)
            if not normalized:
                continue
            candidates.append(str(value).strip())
        return candidates

    def summarize_analysis(self, analysis_id: int) -> Optional[str]:
        snapshot = self._load_snapshot(analysis_id)

        if snapshot is None:
            return None

        lines = [
            "Warehouse financeiro canônico:",
            f"- Analise sincronizada: {snapshot.analysis_id}.",
            f"- Periodo consolidado: {snapshot.analysis_period_label or 'nao informado'}.",
            f"- Arquivos fonte: {snapshot.source_workbook_count}.",
            f"- Linhas de DRE: {len(snapshot.dre_lines)}.",
            f"- Periodos financeiros: {len(snapshot.periods)}.",
            f"- Clientes: {len(snapshot.clients)}.",
            f"- Clientes canonicos no snapshot: {len({client.canonical_client_id for client in snapshot.clients if client.canonical_client_id})}.",
            f"- Entradas cliente x periodo: {len(snapshot.client_periods)}.",
            f"- Contratos: {len(snapshot.contracts)}.",
            f"- Contratos canonicos no snapshot: {len({contract.canonical_contract_id for contract in snapshot.contracts if contract.canonical_contract_id})}.",
            f"- Lancamentos canonicos: {len(snapshot.entries) or snapshot.entry_count}.",
        ]
        top_clients = self.list_top_clients(analysis_id, limit=3)
        top_contracts = self.list_top_contracts(analysis_id, limit=3)
        top_periods = self.list_period_results(analysis_id, limit=3)
        if top_clients:
            top_client = top_clients[0]
            lines.append(
                f"- Cliente com maior rendimento: {top_client['client_name']} ({self._format_currency(top_client['total_received_amount'])})."
            )
            top_clients_label = "; ".join(
                f"{row['client_name']} ({self._format_currency(row['total_received_amount'])})"
                for row in top_clients
            )
            lines.append(f"- Top clientes no recorte: {top_clients_label}.")
        if top_contracts:
            top_contract = top_contracts[0]
            lines.append(
                f"- Contrato com maior rendimento: {top_contract['contract_label']} ({self._format_currency(top_contract['total_received_amount'])})."
            )
            top_contracts_label = "; ".join(
                f"{row['contract_label']} ({self._format_currency(row['total_received_amount'])})"
                for row in top_contracts
            )
            lines.append(f"- Top contratos no recorte: {top_contracts_label}.")
        if snapshot.periods:
            positive_months = [period for period in snapshot.periods if (period.net_result or 0) > 0]
            negative_months = [period for period in snapshot.periods if (period.net_result or 0) < 0]
            if positive_months:
                best_month = max(positive_months, key=lambda item: item.net_result or 0)
                lines.append(
                    f"- Melhor periodo: {best_month.period_label} ({self._format_currency(best_month.net_result)})."
                )
            if negative_months:
                worst_month = min(negative_months, key=lambda item: item.net_result or 0)
                lines.append(
                    f"- Periodo de maior pressao: {worst_month.period_label} ({self._format_currency(worst_month.net_result)})."
                )
        if top_periods:
            top_periods_label = "; ".join(
                f"{row['period_label']} ({self._format_currency(row['net_result'])})"
                for row in top_periods
            )
            lines.append(f"- Periodos de maior resultado: {top_periods_label}.")
        return "\n".join(lines)

    def load_financial_analysis(self, analysis_id: int) -> Optional[FinancialAnalysisResult]:
        snapshot = self._load_snapshot(analysis_id)
        if snapshot is None:
            return None

        return FinancialAnalysisResult(
            workbook_kind="financial_dre",
            entity_name=snapshot.entity_name,
            source_workbook_count=snapshot.source_workbook_count,
            source_workbook_names=self._load_json_list(snapshot.source_workbook_names_json),
            months=[
                FinancialPeriodSummary(
                    sheet_name=period.sheet_name or period.period_label,
                    period_label=period.period_label,
                    year=period.fiscal_year,
                    gross_revenue_total=period.gross_revenue_total,
                    receivables_total=period.receivables_total,
                    other_income_total=period.other_income_total,
                    global_expenses_total=period.global_expenses_total,
                    net_result=period.net_result,
                    closing_total=period.closing_total,
                    pending_entry_count=period.pending_entry_count,
                )
                for period in snapshot.periods
            ],
            dre_lines=[
                FinancialStatementLine(
                    key=line.line_key or f"line_{line.position}",
                    label=line.label,
                    amount=line.amount or 0.0,
                    line_type=line.line_type or "note",
                    share_of_gross_revenue=line.share_of_gross_revenue,
                    share_of_operating_inflows=line.share_of_operating_inflows,
                )
                for line in snapshot.dre_lines
            ],
            client_rollups=[
                FinancialClientRollup(
                    canonical_client_id=client.canonical_client_id,
                    canonical_client_name=client.canonical_client_name,
                    client_name=client.client_name,
                    total_received_amount=client.total_received_amount or 0.0,
                    total_expected_amount=client.total_expected_amount or 0.0,
                    total_pending_amount=client.total_pending_amount or 0.0,
                    contract_count=client.contract_count,
                    months_covered=self._load_json_list(client.months_covered_json),
                    contract_labels=self._load_json_list(client.contract_labels_json),
                )
                for client in snapshot.clients
            ],
            client_period_rollups=[
                FinancialClientPeriodRollup(
                    canonical_client_id=entry.canonical_client_id,
                    canonical_client_name=entry.canonical_client_name,
                    client_name=entry.client_name,
                    period_label=entry.period_label,
                    total_received_amount=entry.total_received_amount or 0.0,
                    total_expected_amount=entry.total_expected_amount or 0.0,
                    total_pending_amount=entry.total_pending_amount or 0.0,
                    contract_count=entry.contract_count,
                    contract_labels=self._load_json_list(entry.contract_labels_json),
                )
                for entry in snapshot.client_periods
            ],
            contract_rollups=[
                FinancialContractRollup(
                    canonical_client_id=contract.canonical_client_id,
                    canonical_client_name=contract.canonical_client_name,
                    canonical_contract_id=contract.canonical_contract_id,
                    canonical_contract_name=contract.canonical_contract_name,
                    contract_label=contract.contract_label,
                    client_name=contract.client_name,
                    unit=contract.unit,
                    contract_start_date=contract.contract_start_date,
                    contract_end_date=contract.contract_end_date,
                    latest_status=contract.latest_status,
                    total_received_amount=contract.total_received_amount or 0.0,
                    total_expected_amount=contract.total_expected_amount or 0.0,
                    total_pending_amount=contract.total_pending_amount or 0.0,
                    entry_count=contract.entry_count,
                    months_covered=self._load_json_list(contract.months_covered_json),
                    source_sheet_names=self._load_json_list(contract.source_sheet_names_json),
                )
                for contract in snapshot.contracts
            ],
            entry_count=snapshot.entry_count,
        )

    def list_top_clients(self, analysis_id: int, limit: int = 10) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM finance_client_revenue_view
                    WHERE analysis_id = :analysis_id
                    ORDER BY total_received_amount DESC NULLS LAST, client_name ASC
                    LIMIT :limit
                    """
                ),
                {"analysis_id": analysis_id, "limit": int(limit)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def list_top_contracts(self, analysis_id: int, limit: int = 10) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM finance_contract_revenue_view
                    WHERE analysis_id = :analysis_id
                    ORDER BY total_received_amount DESC NULLS LAST, contract_label ASC
                    LIMIT :limit
                    """
                ),
                {"analysis_id": analysis_id, "limit": int(limit)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def list_period_results(self, analysis_id: int, limit: int = 10) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM finance_period_result_view
                    WHERE analysis_id = :analysis_id
                    ORDER BY net_result DESC NULLS LAST, position ASC
                    LIMIT :limit
                    """
                ),
                {"analysis_id": analysis_id, "limit": int(limit)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def list_entries(
        self,
        analysis_id: int,
        limit: int = 100,
        client_name: Optional[str] = None,
        contract_label: Optional[str] = None,
        period_label: Optional[str] = None,
        entry_type: Optional[str] = None,
        source_kind: Optional[str] = None,
        reconciliation_status: Optional[str] = None,
        canonical_client_id: Optional[int] = None,
        canonical_contract_id: Optional[int] = None,
    ) -> list[dict[str, object]]:
        with self.session_factory() as session:
            statement = (
                select(FinanceEntryRecord)
                .join(FinanceAnalysisSnapshot, FinanceAnalysisSnapshot.id == FinanceEntryRecord.snapshot_id)
                .where(FinanceAnalysisSnapshot.analysis_id == analysis_id)
                .order_by(FinanceEntryRecord.position.asc())
                .limit(int(limit))
            )
            if client_name:
                statement = statement.where(FinanceEntryRecord.counterparty.ilike(f"%{client_name.strip()}%"))
            if contract_label:
                statement = statement.where(FinanceEntryRecord.contract_label.ilike(f"%{contract_label.strip()}%"))
            if period_label:
                statement = statement.where(FinanceEntryRecord.period_label == period_label.strip())
            if entry_type:
                statement = statement.where(FinanceEntryRecord.entry_type == entry_type.strip())
            if source_kind:
                statement = statement.where(FinanceEntryRecord.source_kind == source_kind.strip())
            if reconciliation_status:
                statement = statement.where(
                    FinanceEntryRecord.reconciliation_status == reconciliation_status.strip()
                )
            if canonical_client_id is not None:
                statement = statement.where(FinanceEntryRecord.canonical_client_id == int(canonical_client_id))
            if canonical_contract_id is not None:
                statement = statement.where(FinanceEntryRecord.canonical_contract_id == int(canonical_contract_id))

            rows = session.execute(statement).scalars().all()

        return [
            {
                "analysis_id": analysis_id,
                "position": row.position,
                "canonical_client_id": row.canonical_client_id,
                "canonical_client_name": row.canonical_client_name,
                "canonical_contract_id": row.canonical_contract_id,
                "canonical_contract_name": row.canonical_contract_name,
                "period_label": row.period_label,
                "sheet_name": row.sheet_name,
                "section_key": row.section_key,
                "section_title": row.section_title,
                "source_kind": row.source_kind,
                "owner_label": row.owner_label,
                "entry_type": row.entry_type,
                "description": row.description,
                "amount": row.amount,
                "status": row.status,
                "entry_date": row.entry_date,
                "due_date": row.due_date,
                "counterparty": row.counterparty,
                "unit": row.unit,
                "notes": row.notes,
                "contract_label": row.contract_label,
                "contract_start_date": row.contract_start_date,
                "contract_end_date": row.contract_end_date,
                "reconciliation_status": row.reconciliation_status,
                "reconciliation_score": row.reconciliation_score,
                "reconciliation_partner_period_label": row.reconciliation_partner_period_label,
                "reconciliation_partner_description": row.reconciliation_partner_description,
                "reconciliation_alias_label": row.reconciliation_alias_label,
                "reconciliation_note": row.reconciliation_note,
                "tags": self._load_json_list(row.tags_json),
            }
            for row in rows
        ]

    def merge_financial_analysis(
        self,
        existing_analysis: Optional[FinancialAnalysisResult],
        canonical_analysis: Optional[FinancialAnalysisResult],
    ) -> Optional[FinancialAnalysisResult]:
        if canonical_analysis is None:
            return existing_analysis
        if existing_analysis is None:
            return canonical_analysis

        existing_months_by_label = {month.period_label: month for month in existing_analysis.months}
        merged_months = []
        for canonical_month in canonical_analysis.months:
            existing_month = existing_months_by_label.pop(canonical_month.period_label, None)
            if existing_month is None:
                merged_months.append(canonical_month)
                continue
            merged_months.append(
                canonical_month.model_copy(
                    update={
                        "permuta_balance": existing_month.permuta_balance,
                        "debt_outstanding": existing_month.debt_outstanding,
                        "taxes_total": existing_month.taxes_total,
                        "personnel_total": existing_month.personnel_total,
                        "fixed_costs_total": existing_month.fixed_costs_total,
                        "operating_costs_total": existing_month.operating_costs_total,
                        "vbc_total": existing_month.vbc_total,
                        "modulo_total": existing_month.modulo_total,
                        "carried_balance": existing_month.carried_balance,
                        "sections": existing_month.sections,
                        "notes": existing_month.notes,
                    }
                )
            )

        for leftover_month in existing_months_by_label.values():
            merged_months.append(leftover_month)

        return canonical_analysis.model_copy(
            update={
                "workbook_kind": existing_analysis.workbook_kind or canonical_analysis.workbook_kind,
                "fiscal_year": canonical_analysis.fiscal_year or existing_analysis.fiscal_year,
                "entity_name": canonical_analysis.entity_name or existing_analysis.entity_name,
                "months": merged_months,
                "summary_notes": existing_analysis.summary_notes,
                "detected_entities": existing_analysis.detected_entities,
            }
        )

    def _load_snapshot(self, analysis_id: int) -> Optional[FinanceAnalysisSnapshot]:
        with self.session_factory() as session:
            return session.execute(
                select(FinanceAnalysisSnapshot)
                .options(
                    selectinload(FinanceAnalysisSnapshot.clients),
                    selectinload(FinanceAnalysisSnapshot.client_periods),
                    selectinload(FinanceAnalysisSnapshot.contracts),
                    selectinload(FinanceAnalysisSnapshot.periods),
                    selectinload(FinanceAnalysisSnapshot.dre_lines),
                    selectinload(FinanceAnalysisSnapshot.entries),
                )
                .where(FinanceAnalysisSnapshot.analysis_id == analysis_id)
            ).scalar_one_or_none()

    def _dump_json_list(self, values: list[str]) -> str:
        return json.dumps(values, ensure_ascii=False)

    def _load_json_list(self, raw_value: Optional[str]) -> list[str]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(value) for value in parsed if value not in {None, ""}]

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
