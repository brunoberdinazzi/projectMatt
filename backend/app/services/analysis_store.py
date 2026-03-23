from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import (
    AnalysisListItem,
    ChecklistDetail,
    ChecklistItem,
    ChecklistParseResult,
    FinancialAnalysisResult,
    GenerationTrace,
    ParserOptions,
    ScrapedLink,
    ScrapedPageRecord,
    WorkbookContextLayer,
    WorkbookReferenceLink,
)
from .app_database import DatabaseConnection, connect_database, resolve_database_url
from .data_protection_service import DataProtectionService


class AnalysisStore:
    def __init__(
        self,
        database_path: Optional[Path] = None,
        database_url: Optional[str] = None,
        data_protection_service: Optional[DataProtectionService] = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[3]
        data_dir = base_dir / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path or (data_dir / "matt.db")
        self.database_url = resolve_database_url(default_sqlite_path=self.database_path, database_url=database_url)
        self.data_protection_service = data_protection_service or DataProtectionService()
        self._initialize()

    def create_analysis(
        self,
        parsed: ChecklistParseResult,
        source_filename: Optional[str] = None,
        generation_mode: Optional[str] = None,
        output_format: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        session_public_id: Optional[str] = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses (
                    created_by_user_id,
                    created_in_session_id,
                    last_session_id,
                    source_filename,
                    orgao,
                    tipo_orgao,
                    periodo_analise,
                    sat_numero,
                    site_url,
                    portal_url,
                    esic_url,
                    numero_relatorio,
                    promotoria,
                    referencia,
                    solicitacao,
                    cidade_emissao,
                    data_emissao,
                    periodo_coleta,
                    equipe_tecnica,
                    relatorio_contabil_referencia,
                    fontes_disponiveis_json,
                    grupos_permitidos_json,
                    parser_options_json,
                    financial_analysis_json,
                    context_layers_json,
                    reference_links_json,
                    generation_mode,
                    output_format,
                    parse_cache_hit,
                    parse_duration_ms,
                    parse_cache_saved_ms,
                    database_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_user_id,
                    self._encrypt_text(owner_user_id, session_public_id, "analysis.created_in_session_id"),
                    self._encrypt_text(owner_user_id, session_public_id, "analysis.last_session_id"),
                    self._encrypt_text(owner_user_id, source_filename, "analysis.source_filename"),
                    self._encrypt_text(owner_user_id, parsed.orgao, "analysis.orgao"),
                    self._encrypt_text(owner_user_id, parsed.tipo_orgao, "analysis.tipo_orgao"),
                    self._encrypt_text(owner_user_id, parsed.periodo_analise, "analysis.periodo_analise"),
                    self._encrypt_text(owner_user_id, parsed.sat_numero, "analysis.sat_numero"),
                    self._encrypt_text(owner_user_id, parsed.site_url, "analysis.site_url"),
                    self._encrypt_text(owner_user_id, parsed.portal_url, "analysis.portal_url"),
                    self._encrypt_text(owner_user_id, parsed.esic_url, "analysis.esic_url"),
                    self._encrypt_text(owner_user_id, parsed.numero_relatorio, "analysis.numero_relatorio"),
                    self._encrypt_text(owner_user_id, parsed.promotoria, "analysis.promotoria"),
                    self._encrypt_text(owner_user_id, parsed.referencia, "analysis.referencia"),
                    self._encrypt_text(owner_user_id, parsed.solicitacao, "analysis.solicitacao"),
                    self._encrypt_text(owner_user_id, parsed.cidade_emissao, "analysis.cidade_emissao"),
                    self._encrypt_text(owner_user_id, parsed.data_emissao, "analysis.data_emissao"),
                    self._encrypt_text(owner_user_id, parsed.periodo_coleta, "analysis.periodo_coleta"),
                    self._encrypt_text(owner_user_id, parsed.equipe_tecnica, "analysis.equipe_tecnica"),
                    self._encrypt_text(
                        owner_user_id,
                        parsed.relatorio_contabil_referencia,
                        "analysis.relatorio_contabil_referencia",
                    ),
                    self._encrypt_json(owner_user_id, parsed.fontes_disponiveis, "analysis.fontes_disponiveis_json"),
                    self._encrypt_json(owner_user_id, parsed.grupos_permitidos, "analysis.grupos_permitidos_json"),
                    self._encrypt_text(
                        owner_user_id,
                        parsed.parser_options.model_dump_json(),
                        "analysis.parser_options_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_financial_analysis(parsed.financial_analysis),
                        "analysis.financial_analysis_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_context_layers(parsed.context_layers),
                        "analysis.context_layers_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_reference_links(parsed.reference_links),
                        "analysis.reference_links_json",
                    ),
                    self._encrypt_text(owner_user_id, generation_mode, "analysis.generation_mode"),
                    self._encrypt_text(owner_user_id, output_format, "analysis.output_format"),
                    int(bool(parsed.parse_cache_hit)),
                    parsed.parse_duration_ms,
                    parsed.parse_cache_saved_ms,
                    self._encrypt_text(owner_user_id, parsed.database_summary, "analysis.database_summary"),
                ),
            )
            analysis_id = int(cursor.lastrowid)
            self._replace_warnings(conn, analysis_id, parsed.warnings, owner_user_id)
            self._replace_items(conn, analysis_id, parsed.itens_processados, owner_user_id)
            self._replace_financial_structures(conn, analysis_id, parsed.financial_analysis, owner_user_id)
            if parsed.scraped_pages:
                self._replace_scraped_pages(conn, analysis_id, parsed.scraped_pages, owner_user_id)
            conn.commit()
            return analysis_id

    def update_analysis(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        generation_mode: Optional[str] = None,
        output_format: Optional[str] = None,
        session_public_id: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
            conn.execute(
                """
                UPDATE analyses
                SET
                    orgao = ?,
                    tipo_orgao = ?,
                    periodo_analise = ?,
                    sat_numero = ?,
                    site_url = ?,
                    portal_url = ?,
                    esic_url = ?,
                    numero_relatorio = ?,
                    promotoria = ?,
                    referencia = ?,
                    solicitacao = ?,
                    cidade_emissao = ?,
                    data_emissao = ?,
                    periodo_coleta = ?,
                    equipe_tecnica = ?,
                    relatorio_contabil_referencia = ?,
                    fontes_disponiveis_json = ?,
                    grupos_permitidos_json = ?,
                    parser_options_json = ?,
                    financial_analysis_json = ?,
                    context_layers_json = ?,
                    reference_links_json = ?,
                    last_session_id = COALESCE(?, last_session_id),
                    generation_mode = COALESCE(?, generation_mode),
                    output_format = COALESCE(?, output_format),
                    parse_cache_hit = ?,
                    parse_duration_ms = ?,
                    parse_cache_saved_ms = ?,
                    database_summary = ?
                WHERE id = ?
                """,
                (
                    self._encrypt_text(owner_user_id, parsed.orgao, "analysis.orgao"),
                    self._encrypt_text(owner_user_id, parsed.tipo_orgao, "analysis.tipo_orgao"),
                    self._encrypt_text(owner_user_id, parsed.periodo_analise, "analysis.periodo_analise"),
                    self._encrypt_text(owner_user_id, parsed.sat_numero, "analysis.sat_numero"),
                    self._encrypt_text(owner_user_id, parsed.site_url, "analysis.site_url"),
                    self._encrypt_text(owner_user_id, parsed.portal_url, "analysis.portal_url"),
                    self._encrypt_text(owner_user_id, parsed.esic_url, "analysis.esic_url"),
                    self._encrypt_text(owner_user_id, parsed.numero_relatorio, "analysis.numero_relatorio"),
                    self._encrypt_text(owner_user_id, parsed.promotoria, "analysis.promotoria"),
                    self._encrypt_text(owner_user_id, parsed.referencia, "analysis.referencia"),
                    self._encrypt_text(owner_user_id, parsed.solicitacao, "analysis.solicitacao"),
                    self._encrypt_text(owner_user_id, parsed.cidade_emissao, "analysis.cidade_emissao"),
                    self._encrypt_text(owner_user_id, parsed.data_emissao, "analysis.data_emissao"),
                    self._encrypt_text(owner_user_id, parsed.periodo_coleta, "analysis.periodo_coleta"),
                    self._encrypt_text(owner_user_id, parsed.equipe_tecnica, "analysis.equipe_tecnica"),
                    self._encrypt_text(
                        owner_user_id,
                        parsed.relatorio_contabil_referencia,
                        "analysis.relatorio_contabil_referencia",
                    ),
                    self._encrypt_json(owner_user_id, parsed.fontes_disponiveis, "analysis.fontes_disponiveis_json"),
                    self._encrypt_json(owner_user_id, parsed.grupos_permitidos, "analysis.grupos_permitidos_json"),
                    self._encrypt_text(
                        owner_user_id,
                        parsed.parser_options.model_dump_json(),
                        "analysis.parser_options_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_financial_analysis(parsed.financial_analysis),
                        "analysis.financial_analysis_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_context_layers(parsed.context_layers),
                        "analysis.context_layers_json",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        self._dump_reference_links(parsed.reference_links),
                        "analysis.reference_links_json",
                    ),
                    self._encrypt_text(owner_user_id, session_public_id, "analysis.last_session_id"),
                    self._encrypt_text(owner_user_id, generation_mode, "analysis.generation_mode"),
                    self._encrypt_text(owner_user_id, output_format, "analysis.output_format"),
                    int(bool(parsed.parse_cache_hit)),
                    parsed.parse_duration_ms,
                    parsed.parse_cache_saved_ms,
                    self._encrypt_text(owner_user_id, parsed.database_summary, "analysis.database_summary"),
                    analysis_id,
                ),
            )
            self._replace_warnings(conn, analysis_id, parsed.warnings, owner_user_id)
            self._replace_items(conn, analysis_id, parsed.itens_processados, owner_user_id)
            self._replace_financial_structures(conn, analysis_id, parsed.financial_analysis, owner_user_id)
            self._replace_scraped_pages(conn, analysis_id, parsed.scraped_pages, owner_user_id)
            conn.commit()

    def set_database_summary(self, analysis_id: int, summary: str) -> None:
        with self._connect() as conn:
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
            conn.execute(
                "UPDATE analyses SET database_summary = ? WHERE id = ?",
                (self._encrypt_text(owner_user_id, summary, "analysis.database_summary"), analysis_id),
            )
            conn.commit()

    def get_financial_database_summary(self, analysis_id: int) -> Optional[str]:
        with self._connect() as conn:
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
            dre_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_financial_dre_lines WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()[0]
            month_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_financial_months WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()[0]
            client_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_financial_clients WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()[0]
            client_period_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_financial_client_periods WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()[0]
            contract_count = conn.execute(
                "SELECT COUNT(*) FROM analysis_financial_contracts WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()[0]

            if not any((dre_count, month_count, client_count, client_period_count, contract_count)):
                return None

            top_client_rows = conn.execute(
                """
                SELECT client_name, total_received_amount
                FROM analysis_financial_clients
                WHERE analysis_id = ?
                ORDER BY position
                LIMIT 3
                """,
                (analysis_id,),
            ).fetchall()
            top_contract_rows = conn.execute(
                """
                SELECT contract_label, total_received_amount
                FROM analysis_financial_contracts
                WHERE analysis_id = ?
                ORDER BY position
                LIMIT 3
                """,
                (analysis_id,),
            ).fetchall()

        lines = [
            "Base financeira persistida no banco:",
            f"- Linhas de DRE gravadas: {dre_count}.",
            f"- Periodos gravados: {month_count}.",
            f"- Clientes gravados: {client_count}.",
            f"- Entradas cliente x periodo gravadas: {client_period_count}.",
            f"- Contratos gravados: {contract_count}.",
        ]
        if top_client_rows:
            top_clients = "; ".join(
                f"{self._decrypt_text(owner_user_id, row['client_name'], 'financial_client.client_name')}: {self._format_currency_from_storage(owner_user_id, row['total_received_amount'], 'financial_client.total_received_amount')}"
                for row in top_client_rows
            )
            lines.append(f"- Maiores clientes: {top_clients}.")
        if top_contract_rows:
            top_contracts = "; ".join(
                f"{self._decrypt_text(owner_user_id, row['contract_label'], 'financial_contract.contract_label')}: {self._format_currency_from_storage(owner_user_id, row['total_received_amount'], 'financial_contract.total_received_amount')}"
                for row in top_contract_rows
            )
            lines.append(f"- Contratos de maior rendimento: {top_contracts}.")
        return "\n".join(lines)

    def get_analysis_owner_user_id(self, analysis_id: int) -> Optional[int]:
        with self._connect() as conn:
            return self._get_owner_user_id(conn, analysis_id)

    def replace_scraped_pages(self, analysis_id: int, pages: list[ScrapedPageRecord]) -> None:
        with self._connect() as conn:
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
            self._replace_scraped_pages(conn, analysis_id, pages, owner_user_id)
            conn.commit()

    def record_generation(
        self,
        analysis_id: int,
        trace: GenerationTrace,
        session_public_id: Optional[str] = None,
    ) -> int:
        with self._connect() as conn:
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
            cursor = conn.execute(
                """
                INSERT INTO analysis_generations (
                    analysis_id,
                    requested_mode,
                    used_mode,
                    provider,
                    model_name,
                    output_format,
                    prompt_snapshot,
                    raw_response,
                    fallback_reason,
                    session_public_id,
                    duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    self._encrypt_text(owner_user_id, trace.requested_mode, "generation.requested_mode"),
                    self._encrypt_text(owner_user_id, trace.used_mode, "generation.used_mode"),
                    self._encrypt_text(owner_user_id, trace.provider, "generation.provider"),
                    self._encrypt_text(owner_user_id, trace.model_name, "generation.model_name"),
                    self._encrypt_text(owner_user_id, trace.output_format, "generation.output_format"),
                    self._encrypt_text(owner_user_id, trace.prompt_snapshot, "generation.prompt_snapshot"),
                    self._encrypt_text(owner_user_id, trace.raw_response, "generation.raw_response"),
                    self._encrypt_text(owner_user_id, trace.fallback_reason, "generation.fallback_reason"),
                    self._encrypt_text(owner_user_id, session_public_id, "generation.session_public_id"),
                    trace.duration_ms,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_generations(self, analysis_id: int) -> list[GenerationTrace]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    requested_mode,
                    used_mode,
                    provider,
                    model_name,
                    output_format,
                    prompt_snapshot,
                    raw_response,
                    fallback_reason,
                    session_public_id,
                    duration_ms,
                    created_at
                FROM analysis_generations
                WHERE analysis_id = ?
                ORDER BY id DESC
                """,
                (analysis_id,),
            ).fetchall()
            owner_user_id = self._get_owner_user_id(conn, analysis_id)
        return [
            GenerationTrace(
                id=row["id"],
                requested_mode=self._decrypt_text(owner_user_id, row["requested_mode"], "generation.requested_mode"),
                used_mode=self._decrypt_text(owner_user_id, row["used_mode"], "generation.used_mode"),
                provider=self._decrypt_text(owner_user_id, row["provider"], "generation.provider"),
                model_name=self._decrypt_text(owner_user_id, row["model_name"], "generation.model_name"),
                output_format=self._decrypt_text(owner_user_id, row["output_format"], "generation.output_format"),
                prompt_snapshot=self._decrypt_text(owner_user_id, row["prompt_snapshot"], "generation.prompt_snapshot"),
                raw_response=self._decrypt_text(owner_user_id, row["raw_response"], "generation.raw_response"),
                session_public_id=self._decrypt_text(
                    owner_user_id,
                    row["session_public_id"],
                    "generation.session_public_id",
                ),
                fallback_reason=self._decrypt_text(
                    owner_user_id,
                    row["fallback_reason"],
                    "generation.fallback_reason",
                ),
                duration_ms=row["duration_ms"],
                created_at=row["created_at"],
            )
            for row in rows
            ]

    def get_cached_parse_result(
        self,
        workbook_hash: str,
        parser_fingerprint: str,
        owner_user_id: Optional[int],
    ) -> Optional[ChecklistParseResult]:
        if owner_user_id is None:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT parsed_payload_json
                FROM analysis_parse_cache
                WHERE owner_user_id = ? AND workbook_hash = ? AND parser_fingerprint = ?
                """,
                (owner_user_id, workbook_hash, parser_fingerprint),
            ).fetchone()
            if row is None:
                return None
            payload = self._decrypt_text(
                owner_user_id,
                row["parsed_payload_json"],
                "parse_cache.parsed_payload_json",
            )
        if not payload:
            return None
        try:
            return ChecklistParseResult.model_validate_json(payload)
        except ValueError:
            return None

    def set_cached_parse_result(
        self,
        workbook_hash: str,
        parser_fingerprint: str,
        source_filename: Optional[str],
        parsed: ChecklistParseResult,
        owner_user_id: Optional[int],
    ) -> None:
        if owner_user_id is None:
            return
        cache_payload = parsed.model_copy(
            update={
                "analysis_id": None,
                "scraped_pages": [],
                "database_summary": None,
            },
            deep=True,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_parse_cache (
                    owner_user_id,
                    workbook_hash,
                    parser_fingerprint,
                    source_filename,
                    parser_profile,
                    parsed_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_user_id, workbook_hash, parser_fingerprint)
                DO UPDATE SET
                    source_filename = excluded.source_filename,
                    parser_profile = excluded.parser_profile,
                    parsed_payload_json = excluded.parsed_payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    owner_user_id,
                    workbook_hash,
                    parser_fingerprint,
                    self._encrypt_text(owner_user_id, source_filename, "parse_cache.source_filename"),
                    self._encrypt_text(
                        owner_user_id,
                        parsed.parser_options.profile,
                        "parse_cache.parser_profile",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        cache_payload.model_dump_json(),
                        "parse_cache.parsed_payload_json",
                    ),
                ),
            )
            conn.commit()

    def list_recent_analyses(self, limit: int = 8, owner_user_id: Optional[int] = None) -> list[AnalysisListItem]:
        with self._connect() as conn:
            query = """
                SELECT
                    analyses.id,
                    analyses.created_by_user_id,
                    analyses.created_at,
                    analyses.source_filename,
                    analyses.orgao,
                    analyses.tipo_orgao,
                    analyses.periodo_analise,
                    analyses.parser_options_json,
                    analyses.financial_analysis_json,
                    (
                        SELECT COUNT(*)
                        FROM analysis_items
                        WHERE analysis_items.analysis_id = analyses.id
                    ) AS extracted_item_count,
                    (
                        SELECT COUNT(*)
                        FROM scraped_pages
                        WHERE scraped_pages.analysis_id = analyses.id
                    ) AS scraped_page_count,
                    (
                        SELECT COUNT(*)
                        FROM analysis_generations
                        WHERE analysis_generations.analysis_id = analyses.id
                    ) AS generation_count,
                    (
                        SELECT created_at
                        FROM analysis_generations
                        WHERE analysis_generations.analysis_id = analyses.id
                        ORDER BY analysis_generations.id DESC
                        LIMIT 1
                    ) AS last_generation_at
                FROM analyses
            """
            parameters: tuple[object, ...]
            if owner_user_id is not None:
                query += " WHERE analyses.created_by_user_id = ?"
                parameters = (owner_user_id, limit)
            else:
                parameters = (limit,)

            query += """
                ORDER BY analyses.id DESC
                LIMIT ?
            """
            rows = conn.execute(query, parameters).fetchall()

        analyses: list[AnalysisListItem] = []
        for row in rows:
            row_owner_user_id = int(row["created_by_user_id"]) if row["created_by_user_id"] is not None else None
            parser_options = self._load_parser_options(
                self._decrypt_text(row_owner_user_id, row["parser_options_json"], "analysis.parser_options_json")
            )
            extracted_item_count = int(row["extracted_item_count"] or 0)
            if extracted_item_count == 0 and parser_options.profile == "financial_dre":
                financial_analysis = self._load_financial_analysis(
                    self._decrypt_text(
                        row_owner_user_id,
                        row["financial_analysis_json"],
                        "analysis.financial_analysis_json",
                    )
                )
                if financial_analysis is not None:
                    extracted_item_count = financial_analysis.entry_count
            analyses.append(
                AnalysisListItem(
                    analysis_id=int(row["id"]),
                    created_at=row["created_at"],
                    source_filename=self._decrypt_text(
                        row_owner_user_id,
                        row["source_filename"],
                        "analysis.source_filename",
                    ),
                    orgao=self._decrypt_text(row_owner_user_id, row["orgao"], "analysis.orgao"),
                    tipo_orgao=self._decrypt_text(row_owner_user_id, row["tipo_orgao"], "analysis.tipo_orgao"),
                    periodo_analise=self._decrypt_text(
                        row_owner_user_id,
                        row["periodo_analise"],
                        "analysis.periodo_analise",
                    ),
                    parser_profile=parser_options.profile,
                    checklist_sheet_names=parser_options.checklist_sheet_names,
                    extracted_item_count=extracted_item_count,
                    scraped_page_count=int(row["scraped_page_count"] or 0),
                    generation_count=int(row["generation_count"] or 0),
                    last_generation_at=row["last_generation_at"],
                )
            )

        return analyses

    def get_analysis(self, analysis_id: int, owner_user_id: Optional[int] = None) -> Optional[ChecklistParseResult]:
        with self._connect() as conn:
            if owner_user_id is None:
                analysis_row = conn.execute(
                    "SELECT * FROM analyses WHERE id = ?",
                    (analysis_id,),
                ).fetchone()
            else:
                analysis_row = conn.execute(
                    "SELECT * FROM analyses WHERE id = ? AND created_by_user_id = ?",
                    (analysis_id, owner_user_id),
                ).fetchone()
            if analysis_row is None:
                return None
            owner_user_id = (
                int(analysis_row["created_by_user_id"])
                if analysis_row["created_by_user_id"] is not None
                else None
            )

            parsed = ChecklistParseResult(
                analysis_id=int(analysis_row["id"]),
                orgao=self._decrypt_text(owner_user_id, analysis_row["orgao"], "analysis.orgao"),
                tipo_orgao=self._decrypt_text(owner_user_id, analysis_row["tipo_orgao"], "analysis.tipo_orgao"),
                periodo_analise=self._decrypt_text(
                    owner_user_id,
                    analysis_row["periodo_analise"],
                    "analysis.periodo_analise",
                ),
                sat_numero=self._decrypt_text(owner_user_id, analysis_row["sat_numero"], "analysis.sat_numero"),
                site_url=self._decrypt_text(owner_user_id, analysis_row["site_url"], "analysis.site_url"),
                portal_url=self._decrypt_text(owner_user_id, analysis_row["portal_url"], "analysis.portal_url"),
                esic_url=self._decrypt_text(owner_user_id, analysis_row["esic_url"], "analysis.esic_url"),
                numero_relatorio=self._decrypt_text(
                    owner_user_id,
                    analysis_row["numero_relatorio"],
                    "analysis.numero_relatorio",
                ),
                promotoria=self._decrypt_text(owner_user_id, analysis_row["promotoria"], "analysis.promotoria"),
                referencia=self._decrypt_text(owner_user_id, analysis_row["referencia"], "analysis.referencia"),
                solicitacao=self._decrypt_text(owner_user_id, analysis_row["solicitacao"], "analysis.solicitacao"),
                cidade_emissao=self._decrypt_text(
                    owner_user_id,
                    analysis_row["cidade_emissao"],
                    "analysis.cidade_emissao",
                ),
                data_emissao=self._decrypt_text(owner_user_id, analysis_row["data_emissao"], "analysis.data_emissao"),
                periodo_coleta=self._decrypt_text(
                    owner_user_id,
                    analysis_row["periodo_coleta"],
                    "analysis.periodo_coleta",
                ),
                equipe_tecnica=self._decrypt_text(
                    owner_user_id,
                    analysis_row["equipe_tecnica"],
                    "analysis.equipe_tecnica",
                ),
                relatorio_contabil_referencia=self._decrypt_text(
                    owner_user_id,
                    analysis_row["relatorio_contabil_referencia"],
                    "analysis.relatorio_contabil_referencia",
                ),
                fontes_disponiveis=self._load_json_list(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["fontes_disponiveis_json"],
                        "analysis.fontes_disponiveis_json",
                    )
                ),
                grupos_permitidos=self._load_json_list(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["grupos_permitidos_json"],
                        "analysis.grupos_permitidos_json",
                    )
                )
                or ["1", "5"],
                parser_options=self._load_parser_options(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["parser_options_json"],
                        "analysis.parser_options_json",
                    )
                ),
                financial_analysis=self._load_financial_analysis(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["financial_analysis_json"],
                        "analysis.financial_analysis_json",
                    )
                ),
                parse_cache_hit=bool(analysis_row["parse_cache_hit"]),
                parse_duration_ms=analysis_row["parse_duration_ms"],
                parse_cache_saved_ms=analysis_row["parse_cache_saved_ms"],
                context_layers=self._load_context_layers(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["context_layers_json"],
                        "analysis.context_layers_json",
                    )
                ),
                reference_links=self._load_reference_links(
                    self._decrypt_text(
                        owner_user_id,
                        analysis_row["reference_links_json"],
                        "analysis.reference_links_json",
                    )
                ),
                database_summary=self._decrypt_text(
                    owner_user_id,
                    analysis_row["database_summary"],
                    "analysis.database_summary",
                ),
                warnings=[
                    self._decrypt_text(owner_user_id, row["warning"], "warning.warning")
                    for row in conn.execute(
                        "SELECT warning FROM analysis_warnings WHERE analysis_id = ? ORDER BY id",
                        (analysis_id,),
                    ).fetchall()
                ],
                itens_processados=self._load_items(conn, analysis_id, owner_user_id),
                scraped_pages=self._load_scraped_pages(conn, analysis_id, owner_user_id),
            )
            return parsed

    def _connect(self) -> DatabaseConnection:
        connection = connect_database(database_url=self.database_url)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_by_user_id INTEGER,
                    created_in_session_id TEXT,
                    last_session_id TEXT,
                    source_filename TEXT,
                    orgao TEXT,
                    tipo_orgao TEXT,
                    periodo_analise TEXT,
                    sat_numero TEXT,
                    site_url TEXT,
                    portal_url TEXT,
                    esic_url TEXT,
                    numero_relatorio TEXT,
                    promotoria TEXT,
                    referencia TEXT,
                    solicitacao TEXT,
                    cidade_emissao TEXT,
                    data_emissao TEXT,
                    periodo_coleta TEXT,
                    equipe_tecnica TEXT,
                    relatorio_contabil_referencia TEXT,
                    fontes_disponiveis_json TEXT,
                    grupos_permitidos_json TEXT,
                    parser_options_json TEXT,
                    financial_analysis_json TEXT,
                    context_layers_json TEXT,
                    reference_links_json TEXT,
                    generation_mode TEXT,
                    output_format TEXT,
                    parse_cache_hit INTEGER NOT NULL DEFAULT 0,
                    parse_duration_ms INTEGER,
                    parse_cache_saved_ms INTEGER,
                    database_summary TEXT
                );

                CREATE TABLE IF NOT EXISTS analysis_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    warning TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    grupo TEXT NOT NULL,
                    item_codigo TEXT NOT NULL,
                    linha_referencia INTEGER NOT NULL,
                    ano_referencia TEXT,
                    status TEXT NOT NULL,
                    status_2024 TEXT,
                    status_2025 TEXT,
                    fonte TEXT NOT NULL,
                    fonte_texto TEXT,
                    descricao_item TEXT NOT NULL,
                    observacao TEXT,
                    fundamentacao TEXT,
                    aba_origem TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_item_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_item_id INTEGER NOT NULL,
                    descricao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (analysis_item_id) REFERENCES analysis_items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    fonte TEXT NOT NULL,
                    requested_url TEXT NOT NULL,
                    final_url TEXT NOT NULL,
                    page_title TEXT,
                    summary TEXT NOT NULL,
                    discovery_depth INTEGER NOT NULL DEFAULT 0,
                    page_score INTEGER NOT NULL DEFAULT 0,
                    discovered_from_url TEXT,
                    discovered_from_label TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_page_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    warning TEXT NOT NULL,
                    FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    url TEXT NOT NULL,
                    category TEXT NOT NULL,
                    destination_type TEXT NOT NULL,
                    context TEXT,
                    section TEXT,
                    is_internal INTEGER NOT NULL DEFAULT 0,
                    score INTEGER NOT NULL DEFAULT 0,
                    matched_terms_json TEXT,
                    evidence_summary TEXT,
                    FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    requested_mode TEXT NOT NULL,
                    used_mode TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT,
                    output_format TEXT NOT NULL,
                    prompt_snapshot TEXT,
                    raw_response TEXT,
                    fallback_reason TEXT,
                    session_public_id TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_parse_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    workbook_hash TEXT NOT NULL,
                    parser_fingerprint TEXT NOT NULL,
                    source_filename TEXT,
                    parser_profile TEXT,
                    parsed_payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(owner_user_id, workbook_hash, parser_fingerprint)
                );

                CREATE TABLE IF NOT EXISTS analysis_financial_dre_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    line_key TEXT,
                    label TEXT,
                    line_type TEXT,
                    amount TEXT,
                    share_of_gross_revenue TEXT,
                    share_of_operating_inflows TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_financial_months (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    sheet_name TEXT,
                    period_label TEXT,
                    fiscal_year INTEGER,
                    gross_revenue_total TEXT,
                    receivables_total TEXT,
                    other_income_total TEXT,
                    global_expenses_total TEXT,
                    net_result TEXT,
                    closing_total TEXT,
                    pending_entry_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_financial_clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    client_name TEXT,
                    total_received_amount TEXT,
                    total_expected_amount TEXT,
                    total_pending_amount TEXT,
                    contract_count INTEGER NOT NULL DEFAULT 0,
                    months_covered_json TEXT,
                    contract_labels_json TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_financial_client_periods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    client_name TEXT,
                    period_label TEXT,
                    total_received_amount TEXT,
                    total_expected_amount TEXT,
                    total_pending_amount TEXT,
                    contract_count INTEGER NOT NULL DEFAULT 0,
                    contract_labels_json TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_financial_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    contract_label TEXT,
                    client_name TEXT,
                    unit TEXT,
                    contract_start_date TEXT,
                    contract_end_date TEXT,
                    latest_status TEXT,
                    total_received_amount TEXT,
                    total_expected_amount TEXT,
                    total_pending_amount TEXT,
                    entry_count INTEGER NOT NULL DEFAULT 0,
                    months_covered_json TEXT,
                    source_sheet_names_json TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );
                """
            )
            self._ensure_column(conn, "analyses", "parser_options_json", "TEXT")
            self._ensure_column(conn, "analyses", "financial_analysis_json", "TEXT")
            self._ensure_column(conn, "analyses", "context_layers_json", "TEXT")
            self._ensure_column(conn, "analyses", "reference_links_json", "TEXT")
            self._ensure_column(conn, "analyses", "created_by_user_id", "INTEGER")
            self._ensure_column(conn, "analyses", "created_in_session_id", "TEXT")
            self._ensure_column(conn, "analyses", "last_session_id", "TEXT")
            self._ensure_column(conn, "analyses", "parse_cache_hit", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "analyses", "parse_duration_ms", "INTEGER")
            self._ensure_column(conn, "analyses", "parse_cache_saved_ms", "INTEGER")
            self._ensure_column(conn, "scraped_pages", "discovery_depth", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_pages", "page_score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_pages", "discovered_from_url", "TEXT")
            self._ensure_column(conn, "scraped_pages", "discovered_from_label", "TEXT")
            self._ensure_column(conn, "scraped_links", "score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_links", "matched_terms_json", "TEXT")
            self._ensure_column(conn, "scraped_links", "evidence_summary", "TEXT")
            self._ensure_column(conn, "analysis_generations", "session_public_id", "TEXT")
            self._ensure_column(conn, "analysis_generations", "duration_ms", "INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analyses_created_by_user_id ON analyses(created_by_user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_parse_cache_lookup ON analysis_parse_cache(owner_user_id, workbook_hash, parser_fingerprint)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_financial_months_analysis_id ON analysis_financial_months(analysis_id, position)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_financial_clients_analysis_id ON analysis_financial_clients(analysis_id, position)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_financial_client_periods_analysis_id ON analysis_financial_client_periods(analysis_id, position)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_financial_contracts_analysis_id ON analysis_financial_contracts(analysis_id, position)"
            )
            conn.commit()

    def _replace_warnings(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        warnings: list[str],
        owner_user_id: Optional[int],
    ) -> None:
        conn.execute("DELETE FROM analysis_warnings WHERE analysis_id = ?", (analysis_id,))
        conn.executemany(
            "INSERT INTO analysis_warnings (analysis_id, warning) VALUES (?, ?)",
            [
                (
                    analysis_id,
                    self._encrypt_text(owner_user_id, warning, "warning.warning"),
                )
                for warning in warnings
            ],
        )

    def _replace_items(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        items: list[ChecklistItem],
        owner_user_id: Optional[int],
    ) -> None:
        item_rows = conn.execute(
            "SELECT id FROM analysis_items WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchall()
        item_ids = [row["id"] for row in item_rows]
        if item_ids:
            conn.executemany(
                "DELETE FROM analysis_item_details WHERE analysis_item_id = ?",
                [(item_id,) for item_id in item_ids],
            )
        conn.execute("DELETE FROM analysis_items WHERE analysis_id = ?", (analysis_id,))

        for item in items:
            cursor = conn.execute(
                """
                INSERT INTO analysis_items (
                    analysis_id,
                    grupo,
                    item_codigo,
                    linha_referencia,
                    ano_referencia,
                    status,
                    status_2024,
                    status_2025,
                    fonte,
                    fonte_texto,
                    descricao_item,
                    observacao,
                    fundamentacao,
                    aba_origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    self._encrypt_text(owner_user_id, item.grupo, "item.grupo"),
                    self._encrypt_text(owner_user_id, item.item_codigo, "item.item_codigo"),
                    item.linha_referencia,
                    self._encrypt_text(owner_user_id, item.ano_referencia, "item.ano_referencia"),
                    self._encrypt_text(owner_user_id, item.status, "item.status"),
                    self._encrypt_text(owner_user_id, item.status_2024, "item.status_2024"),
                    self._encrypt_text(owner_user_id, item.status_2025, "item.status_2025"),
                    self._encrypt_text(owner_user_id, item.fonte, "item.fonte"),
                    self._encrypt_text(owner_user_id, item.fonte_texto, "item.fonte_texto"),
                    self._encrypt_text(owner_user_id, item.descricao_item, "item.descricao_item"),
                    self._encrypt_text(owner_user_id, item.observacao, "item.observacao"),
                    self._encrypt_text(owner_user_id, item.fundamentacao, "item.fundamentacao"),
                    self._encrypt_text(owner_user_id, item.aba_origem, "item.aba_origem"),
                ),
            )
            analysis_item_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT INTO analysis_item_details (analysis_item_id, descricao, status)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        analysis_item_id,
                        self._encrypt_text(owner_user_id, detail.descricao, "item_detail.descricao"),
                        self._encrypt_text(owner_user_id, detail.status, "item_detail.status"),
                    )
                    for detail in item.detalhes
                ],
            )

    def _replace_scraped_pages(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        pages: list[ScrapedPageRecord],
        owner_user_id: Optional[int],
    ) -> None:
        page_rows = conn.execute(
            "SELECT id FROM scraped_pages WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchall()
        page_ids = [row["id"] for row in page_rows]
        if page_ids:
            conn.executemany(
                "DELETE FROM scraped_page_warnings WHERE page_id = ?",
                [(page_id,) for page_id in page_ids],
            )
            conn.executemany(
                "DELETE FROM scraped_links WHERE page_id = ?",
                [(page_id,) for page_id in page_ids],
            )
        conn.execute("DELETE FROM scraped_pages WHERE analysis_id = ?", (analysis_id,))

        for page in pages:
            cursor = conn.execute(
                """
                INSERT INTO scraped_pages (
                    analysis_id,
                    fonte,
                    requested_url,
                    final_url,
                    page_title,
                    summary,
                    discovery_depth,
                    page_score,
                    discovered_from_url,
                    discovered_from_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    self._encrypt_text(owner_user_id, page.fonte, "page.fonte"),
                    self._encrypt_text(owner_user_id, page.requested_url, "page.requested_url"),
                    self._encrypt_text(owner_user_id, page.final_url, "page.final_url"),
                    self._encrypt_text(owner_user_id, page.page_title, "page.page_title"),
                    self._encrypt_text(owner_user_id, page.summary, "page.summary"),
                    page.discovery_depth,
                    page.page_score,
                    self._encrypt_text(owner_user_id, page.discovered_from_url, "page.discovered_from_url"),
                    self._encrypt_text(owner_user_id, page.discovered_from_label, "page.discovered_from_label"),
                ),
            )
            page_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO scraped_page_warnings (page_id, warning) VALUES (?, ?)",
                [
                    (page_id, self._encrypt_text(owner_user_id, warning, "page_warning.warning"))
                    for warning in page.warnings
                ],
            )
            conn.executemany(
                """
                INSERT INTO scraped_links (
                    page_id,
                    label,
                    url,
                    category,
                    destination_type,
                    context,
                    section,
                    is_internal,
                    score,
                    matched_terms_json,
                    evidence_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        page_id,
                        self._encrypt_text(owner_user_id, link.label, "link.label"),
                        self._encrypt_text(owner_user_id, link.url, "link.url"),
                        self._encrypt_text(owner_user_id, link.category, "link.category"),
                        self._encrypt_text(owner_user_id, link.destination_type, "link.destination_type"),
                        self._encrypt_text(owner_user_id, link.context, "link.context"),
                        self._encrypt_text(owner_user_id, link.section, "link.section"),
                        1 if link.is_internal else 0,
                        link.score,
                        self._encrypt_json(owner_user_id, link.matched_terms, "link.matched_terms_json"),
                        self._encrypt_text(owner_user_id, link.evidence_summary, "link.evidence_summary"),
                    )
                    for link in page.links
                ],
            )

    def _replace_financial_structures(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        analysis: Optional[FinancialAnalysisResult],
        owner_user_id: Optional[int],
    ) -> None:
        for table_name in (
            "analysis_financial_dre_lines",
            "analysis_financial_months",
            "analysis_financial_clients",
            "analysis_financial_client_periods",
            "analysis_financial_contracts",
        ):
            conn.execute(f"DELETE FROM {table_name} WHERE analysis_id = ?", (analysis_id,))

        if analysis is None:
            return

        conn.executemany(
            """
            INSERT INTO analysis_financial_dre_lines (
                analysis_id,
                position,
                line_key,
                label,
                line_type,
                amount,
                share_of_gross_revenue,
                share_of_operating_inflows
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    analysis_id,
                    position,
                    self._encrypt_text(owner_user_id, line.key, "financial_dre.line_key"),
                    self._encrypt_text(owner_user_id, line.label, "financial_dre.label"),
                    self._encrypt_text(owner_user_id, line.line_type, "financial_dre.line_type"),
                    self._encrypt_float(owner_user_id, line.amount, "financial_dre.amount"),
                    self._encrypt_float(
                        owner_user_id,
                        line.share_of_gross_revenue,
                        "financial_dre.share_of_gross_revenue",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        line.share_of_operating_inflows,
                        "financial_dre.share_of_operating_inflows",
                    ),
                )
                for position, line in enumerate(analysis.dre_lines, start=1)
            ],
        )

        conn.executemany(
            """
            INSERT INTO analysis_financial_months (
                analysis_id,
                position,
                sheet_name,
                period_label,
                fiscal_year,
                gross_revenue_total,
                receivables_total,
                other_income_total,
                global_expenses_total,
                net_result,
                closing_total,
                pending_entry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    analysis_id,
                    position,
                    self._encrypt_text(owner_user_id, month.sheet_name, "financial_month.sheet_name"),
                    self._encrypt_text(owner_user_id, month.period_label, "financial_month.period_label"),
                    month.year,
                    self._encrypt_float(owner_user_id, month.gross_revenue_total, "financial_month.gross_revenue_total"),
                    self._encrypt_float(owner_user_id, month.receivables_total, "financial_month.receivables_total"),
                    self._encrypt_float(owner_user_id, month.other_income_total, "financial_month.other_income_total"),
                    self._encrypt_float(
                        owner_user_id,
                        month.global_expenses_total,
                        "financial_month.global_expenses_total",
                    ),
                    self._encrypt_float(owner_user_id, month.net_result, "financial_month.net_result"),
                    self._encrypt_float(owner_user_id, month.closing_total, "financial_month.closing_total"),
                    month.pending_entry_count,
                )
                for position, month in enumerate(analysis.months, start=1)
            ],
        )

        conn.executemany(
            """
            INSERT INTO analysis_financial_clients (
                analysis_id,
                position,
                client_name,
                total_received_amount,
                total_expected_amount,
                total_pending_amount,
                contract_count,
                months_covered_json,
                contract_labels_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    analysis_id,
                    position,
                    self._encrypt_text(owner_user_id, client.client_name, "financial_client.client_name"),
                    self._encrypt_float(
                        owner_user_id,
                        client.total_received_amount,
                        "financial_client.total_received_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        client.total_expected_amount,
                        "financial_client.total_expected_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        client.total_pending_amount,
                        "financial_client.total_pending_amount",
                    ),
                    client.contract_count,
                    self._encrypt_json(owner_user_id, client.months_covered, "financial_client.months_covered_json"),
                    self._encrypt_json(owner_user_id, client.contract_labels, "financial_client.contract_labels_json"),
                )
                for position, client in enumerate(analysis.client_rollups, start=1)
            ],
        )

        conn.executemany(
            """
            INSERT INTO analysis_financial_client_periods (
                analysis_id,
                position,
                client_name,
                period_label,
                total_received_amount,
                total_expected_amount,
                total_pending_amount,
                contract_count,
                contract_labels_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    analysis_id,
                    position,
                    self._encrypt_text(
                        owner_user_id,
                        entry.client_name,
                        "financial_client_period.client_name",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        entry.period_label,
                        "financial_client_period.period_label",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        entry.total_received_amount,
                        "financial_client_period.total_received_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        entry.total_expected_amount,
                        "financial_client_period.total_expected_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        entry.total_pending_amount,
                        "financial_client_period.total_pending_amount",
                    ),
                    entry.contract_count,
                    self._encrypt_json(
                        owner_user_id,
                        entry.contract_labels,
                        "financial_client_period.contract_labels_json",
                    ),
                )
                for position, entry in enumerate(analysis.client_period_rollups, start=1)
            ],
        )

        conn.executemany(
            """
            INSERT INTO analysis_financial_contracts (
                analysis_id,
                position,
                contract_label,
                client_name,
                unit,
                contract_start_date,
                contract_end_date,
                latest_status,
                total_received_amount,
                total_expected_amount,
                total_pending_amount,
                entry_count,
                months_covered_json,
                source_sheet_names_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    analysis_id,
                    position,
                    self._encrypt_text(owner_user_id, contract.contract_label, "financial_contract.contract_label"),
                    self._encrypt_text(owner_user_id, contract.client_name, "financial_contract.client_name"),
                    self._encrypt_text(owner_user_id, contract.unit, "financial_contract.unit"),
                    self._encrypt_text(
                        owner_user_id,
                        contract.contract_start_date,
                        "financial_contract.contract_start_date",
                    ),
                    self._encrypt_text(
                        owner_user_id,
                        contract.contract_end_date,
                        "financial_contract.contract_end_date",
                    ),
                    self._encrypt_text(owner_user_id, contract.latest_status, "financial_contract.latest_status"),
                    self._encrypt_float(
                        owner_user_id,
                        contract.total_received_amount,
                        "financial_contract.total_received_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        contract.total_expected_amount,
                        "financial_contract.total_expected_amount",
                    ),
                    self._encrypt_float(
                        owner_user_id,
                        contract.total_pending_amount,
                        "financial_contract.total_pending_amount",
                    ),
                    contract.entry_count,
                    self._encrypt_json(
                        owner_user_id,
                        contract.months_covered,
                        "financial_contract.months_covered_json",
                    ),
                    self._encrypt_json(
                        owner_user_id,
                        contract.source_sheet_names,
                        "financial_contract.source_sheet_names_json",
                    ),
                )
                for position, contract in enumerate(analysis.contract_rollups, start=1)
            ],
        )

    def _load_items(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        owner_user_id: Optional[int],
    ) -> list[ChecklistItem]:
        item_rows = conn.execute(
            "SELECT * FROM analysis_items WHERE analysis_id = ? ORDER BY id",
            (analysis_id,),
        ).fetchall()
        items: list[ChecklistItem] = []
        for item_row in item_rows:
            detail_rows = conn.execute(
                "SELECT descricao, status FROM analysis_item_details WHERE analysis_item_id = ? ORDER BY id",
                (item_row["id"],),
            ).fetchall()
            items.append(
                ChecklistItem(
                    grupo=self._decrypt_text(owner_user_id, item_row["grupo"], "item.grupo"),
                    item_codigo=self._decrypt_text(owner_user_id, item_row["item_codigo"], "item.item_codigo"),
                    linha_referencia=item_row["linha_referencia"],
                    ano_referencia=self._decrypt_text(
                        owner_user_id,
                        item_row["ano_referencia"],
                        "item.ano_referencia",
                    ),
                    status=self._decrypt_text(owner_user_id, item_row["status"], "item.status"),
                    status_2024=self._decrypt_text(owner_user_id, item_row["status_2024"], "item.status_2024"),
                    status_2025=self._decrypt_text(owner_user_id, item_row["status_2025"], "item.status_2025"),
                    fonte=self._decrypt_text(owner_user_id, item_row["fonte"], "item.fonte"),
                    fonte_texto=self._decrypt_text(owner_user_id, item_row["fonte_texto"], "item.fonte_texto"),
                    descricao_item=self._decrypt_text(
                        owner_user_id,
                        item_row["descricao_item"],
                        "item.descricao_item",
                    ),
                    observacao=self._decrypt_text(owner_user_id, item_row["observacao"], "item.observacao"),
                    fundamentacao=self._decrypt_text(
                        owner_user_id,
                        item_row["fundamentacao"],
                        "item.fundamentacao",
                    ),
                    detalhes=[
                        ChecklistDetail(
                            descricao=self._decrypt_text(
                                owner_user_id,
                                detail["descricao"],
                                "item_detail.descricao",
                            ),
                            status=self._decrypt_text(owner_user_id, detail["status"], "item_detail.status"),
                        )
                        for detail in detail_rows
                    ],
                    aba_origem=self._decrypt_text(owner_user_id, item_row["aba_origem"], "item.aba_origem"),
                )
            )
        return items

    def _load_scraped_pages(
        self,
        conn: DatabaseConnection,
        analysis_id: int,
        owner_user_id: Optional[int],
    ) -> list[ScrapedPageRecord]:
        page_rows = conn.execute(
            "SELECT * FROM scraped_pages WHERE analysis_id = ? ORDER BY id",
            (analysis_id,),
        ).fetchall()
        pages: list[ScrapedPageRecord] = []
        for page_row in page_rows:
            link_rows = conn.execute(
                "SELECT * FROM scraped_links WHERE page_id = ? ORDER BY id",
                (page_row["id"],),
            ).fetchall()
            warning_rows = conn.execute(
                "SELECT warning FROM scraped_page_warnings WHERE page_id = ? ORDER BY id",
                (page_row["id"],),
            ).fetchall()
            pages.append(
                ScrapedPageRecord(
                    fonte=self._decrypt_text(owner_user_id, page_row["fonte"], "page.fonte"),
                    requested_url=self._decrypt_text(owner_user_id, page_row["requested_url"], "page.requested_url"),
                    final_url=self._decrypt_text(owner_user_id, page_row["final_url"], "page.final_url"),
                    page_title=self._decrypt_text(owner_user_id, page_row["page_title"], "page.page_title"),
                    summary=self._decrypt_text(owner_user_id, page_row["summary"], "page.summary"),
                    discovery_depth=int(page_row["discovery_depth"] or 0),
                    page_score=int(page_row["page_score"] or 0),
                    discovered_from_url=self._decrypt_text(
                        owner_user_id,
                        page_row["discovered_from_url"],
                        "page.discovered_from_url",
                    ),
                    discovered_from_label=self._decrypt_text(
                        owner_user_id,
                        page_row["discovered_from_label"],
                        "page.discovered_from_label",
                    ),
                    links=[
                        ScrapedLink(
                            label=self._decrypt_text(owner_user_id, link_row["label"], "link.label"),
                            url=self._decrypt_text(owner_user_id, link_row["url"], "link.url"),
                            category=self._decrypt_text(owner_user_id, link_row["category"], "link.category"),
                            destination_type=self._decrypt_text(
                                owner_user_id,
                                link_row["destination_type"],
                                "link.destination_type",
                            ),
                            context=self._decrypt_text(owner_user_id, link_row["context"], "link.context"),
                            section=self._decrypt_text(owner_user_id, link_row["section"], "link.section"),
                            is_internal=bool(link_row["is_internal"]),
                            score=int(link_row["score"] or 0),
                            matched_terms=self._load_json_list(
                                self._decrypt_text(
                                    owner_user_id,
                                    link_row["matched_terms_json"],
                                    "link.matched_terms_json",
                                )
                            ),
                            evidence_summary=self._decrypt_text(
                                owner_user_id,
                                link_row["evidence_summary"],
                                "link.evidence_summary",
                            ),
                        )
                        for link_row in link_rows
                    ],
                    warnings=[
                        self._decrypt_text(owner_user_id, warning_row["warning"], "page_warning.warning")
                        for warning_row in warning_rows
                    ],
                )
            )
        return pages

    def _load_json_list(self, value: Optional[str]) -> list[str]:
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
        return []

    def _load_parser_options(self, value: Optional[str]) -> ParserOptions:
        if not value:
            return ParserOptions()
        try:
            return ParserOptions.model_validate_json(value)
        except ValueError:
            return ParserOptions()

    def _dump_financial_analysis(self, value: Optional[FinancialAnalysisResult]) -> Optional[str]:
        if value is None:
            return None
        return value.model_dump_json()

    def _load_financial_analysis(self, value: Optional[str]) -> Optional[FinancialAnalysisResult]:
        if not value:
            return None
        try:
            return FinancialAnalysisResult.model_validate_json(value)
        except ValueError:
            return None

    def _dump_context_layers(self, layers: list[WorkbookContextLayer]) -> str:
        return json.dumps(
            [layer.model_dump(mode="json") for layer in layers],
            ensure_ascii=False,
        )

    def _load_context_layers(self, value: Optional[str]) -> list[WorkbookContextLayer]:
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []

        layers: list[WorkbookContextLayer] = []
        for item in loaded:
            try:
                layers.append(WorkbookContextLayer.model_validate(item))
            except ValueError:
                continue
        return layers

    def _dump_reference_links(self, links: list[WorkbookReferenceLink]) -> str:
        return json.dumps(
            [link.model_dump(mode="json") for link in links],
            ensure_ascii=False,
        )

    def _load_reference_links(self, value: Optional[str]) -> list[WorkbookReferenceLink]:
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []

        links: list[WorkbookReferenceLink] = []
        for item in loaded:
            try:
                links.append(WorkbookReferenceLink.model_validate(item))
            except ValueError:
                continue
        return links

    def _get_owner_user_id(self, conn: DatabaseConnection, analysis_id: int) -> Optional[int]:
        row = conn.execute(
            "SELECT created_by_user_id FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
        if row is None or row["created_by_user_id"] is None:
            return None
        return int(row["created_by_user_id"])

    def _encrypt_text(
        self,
        owner_user_id: Optional[int],
        value: Optional[str],
        field_name: str,
    ) -> Optional[str]:
        if value is None or owner_user_id is None:
            return value
        return self.data_protection_service.encrypt_for_user(owner_user_id, value, field_name)

    def _encrypt_json(
        self,
        owner_user_id: Optional[int],
        value,
        field_name: str,
    ) -> str:
        dumped = json.dumps(value, ensure_ascii=False)
        return self._encrypt_text(owner_user_id, dumped, field_name) or dumped

    def _encrypt_float(
        self,
        owner_user_id: Optional[int],
        value: Optional[float],
        field_name: str,
    ) -> Optional[str]:
        if value is None:
            return None
        serialized = f"{float(value):.10f}"
        return self._encrypt_text(owner_user_id, serialized, field_name) or serialized

    def _decrypt_text(
        self,
        owner_user_id: Optional[int],
        value: Optional[str],
        field_name: str,
    ) -> Optional[str]:
        if value is None or owner_user_id is None:
            return value
        return self.data_protection_service.decrypt_for_user(owner_user_id, value, field_name)

    def _decrypt_float(
        self,
        owner_user_id: Optional[int],
        value: Optional[str],
        field_name: str,
    ) -> Optional[float]:
        decrypted = self._decrypt_text(owner_user_id, value, field_name)
        if decrypted in {None, ""}:
            return None
        try:
            return float(decrypted)
        except (TypeError, ValueError):
            return None

    def _format_currency_from_storage(
        self,
        owner_user_id: Optional[int],
        value: Optional[str],
        field_name: str,
    ) -> str:
        amount = self._decrypt_float(owner_user_id, value, field_name)
        if amount is None:
            return "-"
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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
