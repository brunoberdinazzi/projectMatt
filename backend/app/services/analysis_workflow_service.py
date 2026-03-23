from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Optional

from fastapi import HTTPException

from ..models import (
    AnalysisContextResponse,
    AnalysisReviewResponse,
    AnalysisReviewStats,
    ChecklistParseResult,
    FinancialEntryTraceItem,
    GenerationTrace,
    StoredAnalysisResponse,
)
from .analysis_context_builder import AnalysisContextBuilder
from .analysis_scrape_service import AnalysisScrapeService
from .analysis_store import AnalysisStore
from .bank_statement_parser import BankStatementParser, looks_like_bank_statement_pdf
from .excel_parser import (
    ChecklistParser,
    build_parser_config,
    get_parser_profile_definition,
    resolve_parser_profile_for_workbook,
)
from .financial_warehouse_store import FinancialWarehouseStore
from .financial_workbook_parser import FinancialWorkbookParser
from .prompt_builder import PromptBuilder


LOGGER = logging.getLogger(__name__)

RECONCILIATION_ALIAS_STOP_WORDS = {
    "ltda",
    "sa",
    "me",
    "epp",
    "mei",
    "servicos",
    "servico",
    "construcoes",
    "construcao",
    "construtivo",
    "modulo",
    "versa",
    "unidade",
    "inicio",
    "contrato",
    "locacao",
    "locacoes",
}


@dataclass
class ParseWorkbookRequest:
    source_name: Optional[str]
    source_names: list[str] = field(default_factory=list)
    parser_profile: str = "auto"
    allowed_groups: Optional[str] = None
    allowed_status: Optional[str] = None
    checklist_sheet_name: Optional[str] = None
    metadata_row: Optional[int] = None


@dataclass
class AnalysisMetadataInput:
    orgao: Optional[str] = None
    tipo_orgao: Optional[str] = None
    layout_profile: Optional[str] = None
    periodo_analise: Optional[str] = None
    numero_relatorio: Optional[str] = None
    promotoria: Optional[str] = None
    requester_area: Optional[str] = None
    referencia: Optional[str] = None
    solicitacao: Optional[str] = None
    cidade_emissao: Optional[str] = None
    data_emissao: Optional[str] = None
    periodo_coleta: Optional[str] = None
    equipe_tecnica: Optional[str] = None
    relatorio_contabil_referencia: Optional[str] = None


class AnalysisWorkflowService:
    def __init__(
        self,
        analysis_store: AnalysisStore,
        analysis_context_builder: AnalysisContextBuilder,
        analysis_scrape_service: AnalysisScrapeService,
        prompt_builder: PromptBuilder,
        financial_warehouse_store: Optional[FinancialWarehouseStore] = None,
    ) -> None:
        self.analysis_store = analysis_store
        self.analysis_context_builder = analysis_context_builder
        self.analysis_scrape_service = analysis_scrape_service
        self.prompt_builder = prompt_builder
        self.financial_warehouse_store = financial_warehouse_store

    def parse_workbook(
        self,
        workbook_path: Path,
        request: ParseWorkbookRequest,
        owner_user_id: Optional[int] = None,
    ) -> ChecklistParseResult:
        return self.parse_workbooks([workbook_path], request, owner_user_id=owner_user_id)

    def parse_workbooks(
        self,
        workbook_paths: list[Path],
        request: ParseWorkbookRequest,
        owner_user_id: Optional[int] = None,
    ) -> ChecklistParseResult:
        if not workbook_paths:
            raise HTTPException(status_code=400, detail="Nenhum workbook foi informado para leitura.")

        parse_started_at = perf_counter()
        requested_profile = (request.parser_profile or "auto").strip().lower() or "auto"
        source_names = self._resolve_source_names(workbook_paths, request)
        resolved_profile = self._resolve_parser_profile_for_workbooks(workbook_paths, requested_profile)
        parser_config = build_parser_config(
            profile=resolved_profile,
            allowed_groups_text=request.allowed_groups,
            allowed_status_text=request.allowed_status,
            checklist_sheet_name=request.checklist_sheet_name,
            metadata_row=request.metadata_row,
        )
        if len(workbook_paths) > 1 and parser_config.profile != "financial_dre":
            raise HTTPException(
                status_code=400,
                detail="O envio de varios arquivos esta disponivel apenas para o fluxo Financeiro / DRE.",
            )
        if parser_config.profile == "financial_dre":
            workbook_hash = self._hash_workbooks(workbook_paths)
            parser_fingerprint = self._build_parse_fingerprint(request, source_names=source_names)
            cached = self.analysis_store.get_cached_parse_result(
                workbook_hash=workbook_hash,
                parser_fingerprint=parser_fingerprint,
                owner_user_id=owner_user_id,
            )
            if cached is not None:
                current_duration_ms = int(round((perf_counter() - parse_started_at) * 1000))
                saved_duration_ms = None
                if cached.parse_duration_ms is not None:
                    saved_duration_ms = max(cached.parse_duration_ms - current_duration_ms, 0)
                return cached.model_copy(
                    update={
                        "parse_cache_hit": True,
                        "parse_duration_ms": current_duration_ms,
                        "parse_cache_saved_ms": saved_duration_ms,
                    },
                    deep=True,
                )

        if parser_config.profile == "financial_dre":
            parsed = self._parse_financial_workbook_batch(
                workbook_paths,
                source_names,
                parser_config,
                owner_user_id=owner_user_id,
            )
        else:
            parser = ChecklistParser(parser_config)
            parsed = parser.parse(workbook_paths[0], source_name=source_names[0])
        parsed.parse_duration_ms = int(round((perf_counter() - parse_started_at) * 1000))
        parsed.parse_cache_hit = False
        parsed.parse_cache_saved_ms = None
        if requested_profile == "auto":
            profile_label = get_parser_profile_definition(parser_config.profile).label
            parsed.warnings.insert(0, f"Perfil detectado automaticamente: {profile_label}.")
        if parser_config.profile == "financial_dre":
            parsed = self._annotate_financial_sources(parsed, source_names)
            self.analysis_store.set_cached_parse_result(
                workbook_hash=workbook_hash,
                parser_fingerprint=parser_fingerprint,
                source_filename=self._build_source_batch_label(source_names),
                parsed=parsed,
                owner_user_id=owner_user_id,
            )
        return parsed

    def parse_and_apply_metadata(
        self,
        workbook_path: Path,
        parse_request: ParseWorkbookRequest,
        metadata: AnalysisMetadataInput,
        owner_user_id: Optional[int] = None,
        workbook_paths: Optional[list[Path]] = None,
    ) -> ChecklistParseResult:
        parsed = self.parse_workbooks(
            workbook_paths or [workbook_path],
            parse_request,
            owner_user_id=owner_user_id,
        )
        self.apply_metadata(parsed, metadata)
        return parsed

    def apply_metadata(self, parsed: ChecklistParseResult, metadata: AnalysisMetadataInput) -> ChecklistParseResult:
        if metadata.orgao:
            parsed.orgao = metadata.orgao

        tipo_orgao = self._resolve_layout_profile(metadata.tipo_orgao, metadata.layout_profile)
        if tipo_orgao:
            parsed.tipo_orgao = tipo_orgao

        if metadata.periodo_analise:
            parsed.periodo_analise = metadata.periodo_analise
        if metadata.numero_relatorio:
            parsed.numero_relatorio = metadata.numero_relatorio

        promotoria = metadata.promotoria or metadata.requester_area
        if promotoria:
            parsed.promotoria = promotoria
        if metadata.referencia:
            parsed.referencia = metadata.referencia
        if metadata.solicitacao:
            parsed.solicitacao = metadata.solicitacao
        if metadata.cidade_emissao:
            parsed.cidade_emissao = metadata.cidade_emissao
        if metadata.data_emissao:
            parsed.data_emissao = metadata.data_emissao
        if metadata.periodo_coleta:
            parsed.periodo_coleta = metadata.periodo_coleta
        if metadata.equipe_tecnica:
            parsed.equipe_tecnica = metadata.equipe_tecnica
        if metadata.relatorio_contabil_referencia:
            parsed.relatorio_contabil_referencia = metadata.relatorio_contabil_referencia

        return parsed

    def get_analysis_or_404(
        self,
        analysis_id: int,
        owner_user_id: Optional[int] = None,
    ) -> ChecklistParseResult:
        parsed = self.analysis_store.get_analysis(analysis_id, owner_user_id=owner_user_id)
        if parsed is None:
            raise HTTPException(status_code=404, detail="Analise nao encontrada.")
        if parsed.financial_analysis is not None:
            parsed = self._rehydrate_financial_analysis_from_warehouse(analysis_id, parsed)
            parsed.database_summary = self._build_database_backed_summary(analysis_id, parsed)
        return parsed

    def create_intake(
        self,
        parsed: ChecklistParseResult,
        source_filename: Optional[str],
        owner_user_id: Optional[int] = None,
        session_public_id: Optional[str] = None,
    ) -> StoredAnalysisResponse:
        analysis_id = self.analysis_store.create_analysis(
            parsed,
            source_filename=source_filename,
            owner_user_id=owner_user_id,
            session_public_id=session_public_id,
        )
        parsed.analysis_id = analysis_id
        self._sync_financial_warehouse(analysis_id, parsed, owner_user_id=owner_user_id)
        parsed.database_summary = self._build_database_backed_summary(analysis_id, parsed)
        self.analysis_store.set_database_summary(analysis_id, parsed.database_summary)
        return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)

    def create_review(
        self,
        parsed: ChecklistParseResult,
        source_filename: Optional[str],
        owner_user_id: Optional[int] = None,
        session_public_id: Optional[str] = None,
    ) -> AnalysisReviewResponse:
        scrape_started_at = perf_counter()
        parsed.scraped_pages = self.analysis_scrape_service.scrape_pages_for_analysis(parsed)
        scrape_duration_ms = int(round((perf_counter() - scrape_started_at) * 1000))
        analysis_id = self.analysis_store.create_analysis(
            parsed,
            source_filename=source_filename,
            owner_user_id=owner_user_id,
            session_public_id=session_public_id,
        )
        parsed.analysis_id = analysis_id
        self.analysis_store.update_analysis(analysis_id, parsed, session_public_id=session_public_id)
        self._sync_financial_warehouse(analysis_id, parsed, owner_user_id=owner_user_id)
        parsed.database_summary = self._build_database_backed_summary(analysis_id, parsed)
        self.analysis_store.set_database_summary(analysis_id, parsed.database_summary)
        return self.build_review_response(analysis_id, parsed, scrape_duration_ms=scrape_duration_ms)

    def prepare_analysis_for_generation(
        self,
        parsed: ChecklistParseResult,
        source_filename: Optional[str],
        generation_mode: str,
        output_format: str,
        owner_user_id: Optional[int] = None,
        session_public_id: Optional[str] = None,
    ) -> int:
        analysis_id = self.analysis_store.create_analysis(
            parsed,
            source_filename=source_filename,
            generation_mode=generation_mode,
            output_format=output_format,
            owner_user_id=owner_user_id,
            session_public_id=session_public_id,
        )
        parsed.analysis_id = analysis_id
        parsed.scraped_pages = self.analysis_scrape_service.scrape_pages_for_analysis(parsed)
        self.analysis_store.update_analysis(
            analysis_id,
            parsed,
            generation_mode=generation_mode,
            output_format=output_format,
            session_public_id=session_public_id,
        )
        self._sync_financial_warehouse(analysis_id, parsed, owner_user_id=owner_user_id)
        parsed.database_summary = self._build_database_backed_summary(analysis_id, parsed)
        self.analysis_store.set_database_summary(analysis_id, parsed.database_summary)
        return analysis_id

    def refresh_scrape(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        session_public_id: Optional[str] = None,
    ) -> StoredAnalysisResponse:
        parsed.scraped_pages = self.analysis_scrape_service.scrape_pages_for_analysis(parsed)
        self.analysis_store.update_analysis(analysis_id, parsed, session_public_id=session_public_id)
        self._sync_financial_warehouse(analysis_id, parsed)
        parsed.database_summary = self._build_database_backed_summary(analysis_id, parsed)
        self.analysis_store.set_database_summary(analysis_id, parsed.database_summary)
        return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)

    def build_review_response(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        scrape_duration_ms: Optional[int] = None,
    ) -> AnalysisReviewResponse:
        summary = parsed.database_summary or self.analysis_context_builder.build_summary(parsed)
        parsed.database_summary = summary
        prompt_preview = self.prompt_builder.build(parsed)
        return AnalysisReviewResponse(
            analysis_id=analysis_id,
            parsed=parsed,
            summary=summary,
            prompt_preview=prompt_preview,
            stats=AnalysisReviewStats(
                extracted_item_count=(
                    parsed.financial_analysis.entry_count
                    if parsed.financial_analysis is not None
                    else len(parsed.itens_processados)
                ),
                warning_count=len(parsed.warnings),
                scraped_page_count=len(parsed.scraped_pages),
                scraped_link_count=sum(len(page.links) for page in parsed.scraped_pages),
                parse_duration_ms=parsed.parse_duration_ms,
                scrape_duration_ms=scrape_duration_ms,
                parse_cache_hit=parsed.parse_cache_hit,
                parse_cache_saved_ms=parsed.parse_cache_saved_ms,
            ),
        )

    def build_context_response(self, analysis_id: int, parsed: ChecklistParseResult) -> AnalysisContextResponse:
        summary = parsed.database_summary or self.analysis_context_builder.build_summary(parsed)
        if summary != parsed.database_summary:
            self.analysis_store.set_database_summary(analysis_id, summary)
        return AnalysisContextResponse(analysis_id=analysis_id, summary=summary)

    def list_generations(self, analysis_id: int, owner_user_id: Optional[int] = None) -> list[GenerationTrace]:
        self.get_analysis_or_404(analysis_id, owner_user_id=owner_user_id)
        return self.analysis_store.list_generations(analysis_id)

    def list_financial_entries(
        self,
        analysis_id: int,
        owner_user_id: Optional[int] = None,
        limit: int = 100,
        client_name: Optional[str] = None,
        contract_label: Optional[str] = None,
        period_label: Optional[str] = None,
        entry_type: Optional[str] = None,
        source_kind: Optional[str] = None,
        reconciliation_status: Optional[str] = None,
    ) -> list[FinancialEntryTraceItem]:
        parsed = self.get_analysis_or_404(analysis_id, owner_user_id=owner_user_id)
        if parsed.financial_analysis is None or self.financial_warehouse_store is None:
            return []
        try:
            rows = self.financial_warehouse_store.list_entries(
                analysis_id,
                limit=limit,
                client_name=client_name,
                contract_label=contract_label,
                period_label=period_label,
                entry_type=entry_type,
                source_kind=source_kind,
                reconciliation_status=reconciliation_status,
            )
        except Exception:
            LOGGER.exception("Falha ao consultar lancamentos financeiros da analise %s.", analysis_id)
            return []
        return [FinancialEntryTraceItem.model_validate(row) for row in rows]

    def _hash_workbook(self, workbook_path: Path) -> str:
        digest = hashlib.sha256()
        with workbook_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _build_database_backed_summary(self, analysis_id: int, parsed: ChecklistParseResult) -> str:
        summary = self.analysis_context_builder.build_summary(parsed)
        if parsed.financial_analysis is None:
            return summary
        summary_blocks = [summary]
        financial_database_summary = self.analysis_store.get_financial_database_summary(analysis_id)
        if financial_database_summary:
            summary_blocks.append(financial_database_summary)
        warehouse_summary = self._build_financial_warehouse_summary(analysis_id)
        if warehouse_summary and warehouse_summary not in summary_blocks:
            summary_blocks.append(warehouse_summary)
        if len(summary_blocks) == 1:
            return summary
        return "\n\n".join(summary_blocks)

    def _sync_financial_warehouse(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        owner_user_id: Optional[int] = None,
    ) -> None:
        if parsed.financial_analysis is None or self.financial_warehouse_store is None:
            return
        effective_owner_user_id = owner_user_id
        if effective_owner_user_id is None:
            effective_owner_user_id = self.analysis_store.get_analysis_owner_user_id(analysis_id)
        try:
            self.financial_warehouse_store.sync_analysis(
                analysis_id=analysis_id,
                parsed=parsed,
                owner_user_id=effective_owner_user_id,
            )
        except Exception:
            LOGGER.exception("Falha ao sincronizar a analise %s com o warehouse financeiro.", analysis_id)

    def _build_financial_warehouse_summary(self, analysis_id: int) -> Optional[str]:
        if self.financial_warehouse_store is None:
            return None
        try:
            return self.financial_warehouse_store.summarize_analysis(analysis_id)
        except Exception:
            LOGGER.exception("Falha ao resumir a analise %s a partir do warehouse financeiro.", analysis_id)
            return None

    def _load_reconciliation_alias_registry(self, owner_user_id: Optional[int]) -> dict[str, dict[str, set[str]]]:
        if self.financial_warehouse_store is None:
            return {"clients": {}, "contracts": {}}
        try:
            return self.financial_warehouse_store.build_reconciliation_alias_registry(owner_user_id=owner_user_id)
        except Exception:
            LOGGER.exception("Falha ao carregar aliases canonicos para conciliacao financeira.")
            return {"clients": {}, "contracts": {}}

    def _rehydrate_financial_analysis_from_warehouse(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
    ) -> ChecklistParseResult:
        if parsed.financial_analysis is None or self.financial_warehouse_store is None:
            return parsed
        try:
            canonical_analysis = self.financial_warehouse_store.load_financial_analysis(analysis_id)
        except Exception:
            LOGGER.exception("Falha ao reidratar a analise %s a partir do warehouse financeiro.", analysis_id)
            return parsed

        merged_analysis = self.financial_warehouse_store.merge_financial_analysis(
            parsed.financial_analysis,
            canonical_analysis,
        )
        if merged_analysis is None:
            return parsed
        enriched = parsed.model_copy(update={"financial_analysis": merged_analysis})
        self._enrich_financial_rollups_with_reconciliation(enriched)
        return enriched

    def _hash_workbooks(self, workbook_paths: list[Path]) -> str:
        if len(workbook_paths) == 1:
            return self._hash_workbook(workbook_paths[0])

        digest = hashlib.sha256()
        for workbook_hash in sorted(self._hash_workbook(path) for path in workbook_paths):
            digest.update(workbook_hash.encode("utf-8"))
        return digest.hexdigest()

    def _build_parse_fingerprint(
        self,
        request: ParseWorkbookRequest,
        source_names: Optional[list[str]] = None,
    ) -> str:
        payload = {
            "source_name": (request.source_name or "").strip().lower(),
            "source_names": sorted(
                (source_name or "").strip().lower()
                for source_name in (source_names or request.source_names or [])
                if (source_name or "").strip()
            ),
            "parser_profile": (request.parser_profile or "").strip().lower(),
            "allowed_groups": (request.allowed_groups or "").strip(),
            "allowed_status": (request.allowed_status or "").strip(),
            "checklist_sheet_name": (request.checklist_sheet_name or "").strip(),
            "metadata_row": int(request.metadata_row or 5),
        }
        raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    def _resolve_source_names(self, workbook_paths: list[Path], request: ParseWorkbookRequest) -> list[str]:
        requested_names = [name.strip() for name in request.source_names if name and name.strip()]
        if len(requested_names) == len(workbook_paths):
            return requested_names
        if len(workbook_paths) == 1:
            return [request.source_name or workbook_paths[0].name]
        return [path.name for path in workbook_paths]

    def _resolve_parser_profile_for_workbooks(self, workbook_paths: list[Path], requested_profile: str) -> str:
        resolved_profiles = {
            self._resolve_parser_profile_for_path(workbook_path, requested_profile)
            for workbook_path in workbook_paths
        }
        if len(workbook_paths) > 1 and requested_profile == "auto" and len(resolved_profiles) > 1:
            labels = ", ".join(
                get_parser_profile_definition(profile).label
                for profile in sorted(resolved_profiles)
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Os arquivos selecionados foram detectados com perfis diferentes "
                    f"({labels}). Para consolidar varios arquivos, envie apenas planilhas financeiras."
                ),
            )
        return next(iter(resolved_profiles))

    def _parse_financial_workbook_batch(
        self,
        workbook_paths: list[Path],
        source_names: list[str],
        parser_config,
        owner_user_id: Optional[int] = None,
    ) -> ChecklistParseResult:
        parsed_results: list[ChecklistParseResult] = []
        apply_prefix = len(workbook_paths) > 1
        for workbook_path, source_name in zip(workbook_paths, source_names):
            parser = (
                BankStatementParser(parser_config)
                if workbook_path.suffix.lower() == ".pdf"
                else FinancialWorkbookParser(parser_config)
            )
            parsed = parser.parse(workbook_path, source_name=source_name)
            parsed = self._tag_financial_entry_sources(parsed, source_name)
            parsed_results.append(self._namespace_financial_parse_result(parsed, source_name, apply_prefix=apply_prefix))

        if len(parsed_results) == 1:
            return parsed_results[0]
        return self._merge_financial_parse_results(
            parsed_results,
            source_names,
            parser_config,
            owner_user_id=owner_user_id,
        )

    def _namespace_financial_parse_result(
        self,
        parsed: ChecklistParseResult,
        source_name: str,
        apply_prefix: bool,
    ) -> ChecklistParseResult:
        if not apply_prefix:
            return parsed

        label = self._normalize_source_label(source_name)
        namespaced = parsed.model_copy(deep=True)
        if namespaced.parser_options.checklist_sheet_names:
            namespaced.parser_options.checklist_sheet_names = [
                self._prefix_source_label(label, sheet_name)
                for sheet_name in namespaced.parser_options.checklist_sheet_names
            ]
        namespaced.context_layers = [
            layer.model_copy(update={"sheet_name": self._prefix_source_label(label, layer.sheet_name)}, deep=True)
            for layer in namespaced.context_layers
        ]
        namespaced.reference_links = [
            reference_link.model_copy(
                update={"sheet_name": self._prefix_source_label(label, reference_link.sheet_name)},
                deep=True,
            )
            for reference_link in namespaced.reference_links
        ]
        namespaced.warnings = [f"{label}: {warning}" for warning in namespaced.warnings]
        if namespaced.financial_analysis is None:
            return namespaced

        namespaced.financial_analysis.source_workbook_count = 1
        namespaced.financial_analysis.source_workbook_names = [source_name]
        for month in namespaced.financial_analysis.months:
            month.sheet_name = self._prefix_source_label(label, month.sheet_name)
            for section in month.sections:
                for entry in section.entries:
                    entry.sheet_name = month.sheet_name
        return namespaced

    def _merge_financial_parse_results(
        self,
        parsed_results: list[ChecklistParseResult],
        source_names: list[str],
        parser_config,
        owner_user_id: Optional[int] = None,
    ) -> ChecklistParseResult:
        merged = parsed_results[0].model_copy(deep=True)
        merged.financial_analysis = None
        merged.itens_processados = []
        merged.scraped_pages = []
        merged.database_summary = None
        merged.warnings = []

        unique_sheet_names = self._unique_in_order(
            sheet_name
            for parsed in parsed_results
            for sheet_name in parsed.parser_options.checklist_sheet_names
        )
        merged.parser_options.checklist_sheet_names = unique_sheet_names

        merged.fontes_disponiveis = self._unique_in_order(
            fonte
            for parsed in parsed_results
            for fonte in parsed.fontes_disponiveis
        )
        merged.grupos_permitidos = self._unique_in_order(
            grupo
            for parsed in parsed_results
            for grupo in parsed.grupos_permitidos
        )
        merged.reference_links = self._merge_reference_links(parsed_results)
        merged.site_url = self._first_nonempty(parsed.site_url for parsed in parsed_results)
        merged.portal_url = self._first_nonempty(parsed.portal_url for parsed in parsed_results)
        merged.esic_url = self._first_nonempty(parsed.esic_url for parsed in parsed_results)

        merged_orgao = self._first_nonempty(parsed.orgao for parsed in parsed_results)
        orgao_candidates = self._unique_in_order(parsed.orgao for parsed in parsed_results if parsed.orgao)
        merged.orgao = merged_orgao
        if len(orgao_candidates) > 1:
            merged.warnings.append(
                "Os arquivos apontaram entidades diferentes ("
                + ", ".join(orgao_candidates[:4])
                + f"). O consolidado assumiu '{merged_orgao}'."
            )

        months = [
            month.model_copy(deep=True)
            for parsed in parsed_results
            if parsed.financial_analysis is not None
            for month in parsed.financial_analysis.months
        ]
        self._disambiguate_duplicate_period_labels(months)

        summary_notes = self._unique_in_order(
            note
            for parsed in parsed_results
            if parsed.financial_analysis is not None
            for note in parsed.financial_analysis.summary_notes
        )
        detected_entities = {
            entity
            for parsed in parsed_results
            if parsed.financial_analysis is not None
            for entity in parsed.financial_analysis.detected_entities
        }

        parser = FinancialWorkbookParser(parser_config)
        merged.financial_analysis = parser._build_financial_analysis(
            entity_name=merged.orgao,
            months=months,
            summary_notes=[
                f"Arquivos consolidados: {', '.join(source_names)}.",
                *summary_notes,
            ],
            detected_entities=detected_entities,
        )
        alias_registry = self._load_reconciliation_alias_registry(owner_user_id)
        self._apply_financial_reconciliation(merged, alias_registry=alias_registry)
        self._enrich_financial_rollups_with_reconciliation(merged)
        merged.financial_analysis.source_workbook_count = len(source_names)
        merged.financial_analysis.source_workbook_names = list(source_names)
        merged.context_layers = parser._build_context_layers(merged.financial_analysis)
        merged.periodo_analise = self._resolve_combined_period_label(merged.financial_analysis.months, parsed_results)
        merged.warnings.extend(parser._build_financial_warnings(merged.financial_analysis))
        merged.warnings.extend(
            warning
            for parsed in parsed_results
            for warning in parsed.warnings
        )
        if self._has_duplicate_periods(months):
            merged.warnings.insert(
                0,
                "Foram identificados periodos coincidentes entre arquivos. Revise se os workbooks representam bases complementares ou sobrepostas.",
            )
        return merged

    def _tag_financial_entry_sources(
        self,
        parsed: ChecklistParseResult,
        source_name: str,
    ) -> ChecklistParseResult:
        if parsed.financial_analysis is None:
            return parsed
        source_kind = "bank_statement" if Path(source_name).suffix.lower() == ".pdf" else "workbook"
        for month in parsed.financial_analysis.months:
            for section in month.sections:
                for entry in section.entries:
                    entry.source_kind = source_kind
                    tag = f"source_kind:{source_kind}"
                    if tag not in entry.tags:
                        entry.tags.append(tag)
        return parsed

    def _apply_financial_reconciliation(
        self,
        parsed: ChecklistParseResult,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> None:
        analysis = parsed.financial_analysis
        if analysis is None:
            return

        entry_records = []
        for month in analysis.months:
            base_period_label = self._normalize_reconciliation_period(month.period_label)
            for section in month.sections:
                for entry in section.entries:
                    source_kind = self._resolve_entry_source_kind(entry)
                    entry.reconciliation_status = None
                    entry.reconciliation_score = None
                    entry.reconciliation_partner_period_label = None
                    entry.reconciliation_partner_description = None
                    entry.reconciliation_alias_label = None
                    entry.reconciliation_note = None
                    entry_records.append(
                        {
                            "month": month,
                            "section": section,
                            "entry": entry,
                            "base_period_label": base_period_label,
                            "source_kind": source_kind,
                        }
                    )

        source_kinds = {record["source_kind"] for record in entry_records if record["source_kind"]}
        if "workbook" not in source_kinds or "bank_statement" not in source_kinds:
            return

        workbook_records = []
        bank_records = []
        excluded_records = 0
        for record in entry_records:
            entry = record["entry"]
            source_kind = record["source_kind"]
            if source_kind == "workbook":
                if self._is_reconciliation_eligible(entry, source_kind):
                    workbook_records.append(record)
                else:
                    self._mark_reconciliation_excluded(entry, "Lançamento fora do escopo de conciliação com extrato.")
                    excluded_records += 1
            elif source_kind == "bank_statement":
                if self._is_reconciliation_eligible(entry, source_kind):
                    bank_records.append(record)
                else:
                    self._mark_reconciliation_excluded(entry, "Movimento bancário neutro ou fora da DRE.")
                    excluded_records += 1

        if not workbook_records or not bank_records:
            return

        candidates: list[tuple[float, int, int, str, Optional[str]]] = []
        bank_indexes_by_period: dict[str, list[int]] = {}
        for bank_index, bank_record in enumerate(bank_records):
            bank_indexes_by_period.setdefault(bank_record["base_period_label"], []).append(bank_index)

        for workbook_index, workbook_record in enumerate(workbook_records):
            bank_candidates = bank_indexes_by_period.get(workbook_record["base_period_label"], [])
            for bank_index in bank_candidates:
                bank_record = bank_records[bank_index]
                score, note, alias_label = self._score_reconciliation_pair(
                    workbook_record["entry"],
                    bank_record["entry"],
                    alias_registry=alias_registry,
                )
                if score >= 0.65:
                    candidates.append((score, workbook_index, bank_index, note, alias_label))

        candidates.sort(key=lambda item: item[0], reverse=True)
        assigned_workbook: set[int] = set()
        assigned_bank: set[int] = set()
        matched_count = 0
        probable_count = 0

        for score, workbook_index, bank_index, note, alias_label in candidates:
            if workbook_index in assigned_workbook or bank_index in assigned_bank:
                continue
            workbook_record = workbook_records[workbook_index]
            bank_record = bank_records[bank_index]
            status = "matched" if score >= 0.85 else "probable"
            self._assign_reconciliation_pair(
                workbook_record["entry"],
                bank_record["entry"],
                score=score,
                status=status,
                note=note,
                alias_label=alias_label,
                bank_period_label=bank_record["month"].period_label,
            )
            assigned_workbook.add(workbook_index)
            assigned_bank.add(bank_index)
            if status == "matched":
                matched_count += 1
            else:
                probable_count += 1

        unmatched_workbook = 0
        for index, workbook_record in enumerate(workbook_records):
            if index in assigned_workbook:
                continue
            unmatched_workbook += 1
            workbook_record["entry"].reconciliation_status = "unmatched"
            workbook_record["entry"].reconciliation_note = "Sem correspondência suficiente no extrato bancário."

        unmatched_bank = 0
        for index, bank_record in enumerate(bank_records):
            if index in assigned_bank:
                continue
            unmatched_bank += 1
            bank_record["entry"].reconciliation_status = "unmatched"
            bank_record["entry"].reconciliation_note = "Movimento do extrato sem correspondência suficiente na planilha."

        eligible_workbook = len(workbook_records)
        eligible_bank = len(bank_records)
        analysis.summary_notes.append(
            "Conciliacao planilha x extrato: "
            f"{matched_count} correspondencia(s) confirmada(s), "
            f"{probable_count} provavel(is), "
            f"{unmatched_workbook} lancamento(s) da planilha sem pareamento, "
            f"{unmatched_bank} movimento(s) do extrato sem pareamento "
            f"e {excluded_records} item(ns) fora do escopo. "
            f"Base elegivel: {eligible_workbook} lancamento(s) da planilha e {eligible_bank} do extrato."
        )
        if eligible_workbook and (matched_count + probable_count) / eligible_workbook < 0.45:
            parsed.warnings.insert(
                0,
                "A conciliacao entre planilha e extrato ficou baixa neste recorte. Revise nomes de clientes, datas e se o extrato cobre o mesmo periodo.",
            )

    def _enrich_financial_rollups_with_reconciliation(self, parsed: ChecklistParseResult) -> None:
        analysis = parsed.financial_analysis
        if analysis is None:
            return

        client_lookup = {
            self._normalize_rollup_key(client.canonical_client_name or client.client_name): client
            for client in analysis.client_rollups
        }
        contract_lookup = {
            self._normalize_rollup_key(contract.canonical_contract_name or contract.contract_label): contract
            for contract in analysis.contract_rollups
        }

        for client in analysis.client_rollups:
            self._reset_rollup_reconciliation_metrics(client)
        for contract in analysis.contract_rollups:
            self._reset_rollup_reconciliation_metrics(contract)

        for month in analysis.months:
            for section in month.sections:
                for entry in section.entries:
                    if self._resolve_entry_source_kind(entry) != "workbook" or entry.entry_type != "receivable":
                        continue

                    status = entry.reconciliation_status or "excluded"
                    amount = abs(float(entry.amount or 0.0))
                    alias_supported = bool(getattr(entry, "reconciliation_alias_label", None))

                    client = client_lookup.get(self._normalize_rollup_key(entry.counterparty))
                    if client is not None:
                        self._accumulate_rollup_reconciliation(client, status, amount, alias_supported=alias_supported)

                    contract = contract_lookup.get(self._normalize_rollup_key(entry.contract_label))
                    if contract is not None:
                        self._accumulate_rollup_reconciliation(contract, status, amount, alias_supported=alias_supported)

        for client in analysis.client_rollups:
            self._finalize_rollup_reconciliation(client)
        for contract in analysis.contract_rollups:
            self._finalize_rollup_reconciliation(contract)

    def _resolve_entry_source_kind(self, entry) -> Optional[str]:
        if getattr(entry, "source_kind", None):
            return entry.source_kind
        for tag in getattr(entry, "tags", []) or []:
            if tag.startswith("source_kind:"):
                return tag.split(":", 1)[1]
        return None

    def _is_reconciliation_eligible(self, entry, source_kind: Optional[str]) -> bool:
        if source_kind == "workbook":
            return entry.entry_type in {"receivable", "other_income", "fixed_cost", "personnel", "operating_cost", "bank_fee"}
        if source_kind == "bank_statement":
            return entry.entry_type in {"receivable", "other_income", "fixed_cost", "personnel", "operating_cost", "bank_fee"}
        return False

    def _mark_reconciliation_excluded(self, entry, note: str) -> None:
        entry.reconciliation_status = "excluded"
        entry.reconciliation_note = note

    def _assign_reconciliation_pair(
        self,
        workbook_entry,
        bank_entry,
        *,
        score: float,
        status: str,
        note: str,
        alias_label: Optional[str],
        bank_period_label: str,
    ) -> None:
        workbook_entry.reconciliation_status = status
        workbook_entry.reconciliation_score = round(score, 4)
        workbook_entry.reconciliation_partner_period_label = bank_period_label
        workbook_entry.reconciliation_partner_description = bank_entry.description
        workbook_entry.reconciliation_alias_label = alias_label
        workbook_entry.reconciliation_note = note

        bank_entry.reconciliation_status = status
        bank_entry.reconciliation_score = round(score, 4)
        bank_entry.reconciliation_partner_period_label = bank_period_label
        bank_entry.reconciliation_partner_description = workbook_entry.description
        bank_entry.reconciliation_alias_label = alias_label
        bank_entry.reconciliation_note = note

    def _reset_rollup_reconciliation_metrics(self, rollup) -> None:
        rollup.reconciliation_matched_count = 0
        rollup.reconciliation_probable_count = 0
        rollup.reconciliation_unmatched_count = 0
        rollup.reconciliation_excluded_count = 0
        rollup.reconciliation_matched_amount = 0.0
        rollup.reconciliation_probable_amount = 0.0
        rollup.reconciliation_unmatched_amount = 0.0
        rollup.reconciliation_excluded_amount = 0.0
        rollup.reconciliation_alias_supported_count = 0
        rollup.reconciliation_alias_supported_amount = 0.0
        rollup.reconciliation_coverage_ratio = None

    def _accumulate_rollup_reconciliation(self, rollup, status: str, amount: float, alias_supported: bool = False) -> None:
        if alias_supported:
            rollup.reconciliation_alias_supported_count += 1
            rollup.reconciliation_alias_supported_amount += amount
        if status == "matched":
            rollup.reconciliation_matched_count += 1
            rollup.reconciliation_matched_amount += amount
            return
        if status == "probable":
            rollup.reconciliation_probable_count += 1
            rollup.reconciliation_probable_amount += amount
            return
        if status == "unmatched":
            rollup.reconciliation_unmatched_count += 1
            rollup.reconciliation_unmatched_amount += amount
            return
        rollup.reconciliation_excluded_count += 1
        rollup.reconciliation_excluded_amount += amount

    def _finalize_rollup_reconciliation(self, rollup) -> None:
        eligible_count = (
            rollup.reconciliation_matched_count
            + rollup.reconciliation_probable_count
            + rollup.reconciliation_unmatched_count
        )
        if eligible_count <= 0:
            rollup.reconciliation_coverage_ratio = None
            return
        covered_count = rollup.reconciliation_matched_count + rollup.reconciliation_probable_count
        rollup.reconciliation_coverage_ratio = covered_count / eligible_count

    def _score_reconciliation_pair(
        self,
        workbook_entry,
        bank_entry,
        *,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> tuple[float, str, Optional[str]]:
        workbook_amount = self._normalized_entry_amount(workbook_entry.amount)
        bank_amount = self._normalized_entry_amount(bank_entry.amount)
        if workbook_amount is None or bank_amount is None:
            return (0.0, "", None)

        amount_delta = abs(workbook_amount - bank_amount)
        amount_tolerance = max(1.0, workbook_amount * 0.03, bank_amount * 0.03)
        if amount_delta > amount_tolerance:
            return (0.0, "", None)

        score = 0.0
        if amount_delta <= 0.01:
            score += 0.56
        elif amount_delta <= max(0.5, workbook_amount * 0.01):
            score += 0.48
        else:
            score += 0.38

        if workbook_entry.entry_type == bank_entry.entry_type:
            score += 0.18
        else:
            score += 0.1

        score += 0.04

        workbook_party = self._normalize_reconciliation_text(
            workbook_entry.counterparty or workbook_entry.contract_label or workbook_entry.description
        )
        bank_party = self._normalize_reconciliation_text(
            bank_entry.counterparty or bank_entry.contract_label or bank_entry.description
        )
        party_note = ""
        if workbook_party and bank_party:
            if workbook_party == bank_party:
                score += 0.18
                party_note = "contraparte equivalente"
            elif workbook_party in bank_party or bank_party in workbook_party:
                score += 0.12
                party_note = "contraparte parcialmente equivalente"

        alias_overlap = self._match_reconciliation_aliases(
            workbook_entry,
            bank_entry,
            alias_registry=alias_registry,
        )
        registry_alias = self._match_persisted_reconciliation_alias(
            workbook_entry,
            bank_entry,
            alias_registry=alias_registry,
        )
        if registry_alias:
            score += 0.14
            party_note = f"alias canônico '{registry_alias}' reaproveitado entre planilha e extrato"
        elif alias_overlap:
            score += 0.14
            party_note = f"alias textual '{alias_overlap}' identificado entre planilha e extrato"
        elif self._is_generic_bank_inflow_entry(bank_entry) and amount_delta <= 0.01:
            score += 0.1
            party_note = "movimento bancario generico de recebimento tratado como neutro"

        workbook_date = self._parse_reconciliation_date(workbook_entry.date or workbook_entry.due_date)
        bank_date = self._parse_reconciliation_date(bank_entry.date or bank_entry.due_date)
        if workbook_date and bank_date:
            day_delta = abs((workbook_date - bank_date).days)
            if day_delta == 0:
                score += 0.14
            elif day_delta <= 3:
                score += 0.1
            elif day_delta <= 10:
                score += 0.06

        score = min(score, 0.99)
        note = (
            f"Pareamento por valor {self._format_reconciliation_amount(workbook_amount)} e "
            f"proximidade operacional com '{bank_entry.description}'."
        )
        if party_note:
            note += f" Sinal adicional: {party_note}."
        return (score, note, registry_alias)

    def _normalize_rollup_key(self, value: Optional[str]) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        cleaned = unicodedata.normalize("NFKD", cleaned)
        cleaned = "".join(character for character in cleaned if not unicodedata.combining(character))
        cleaned = cleaned.casefold()
        cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _match_reconciliation_aliases(
        self,
        workbook_entry,
        bank_entry,
        *,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> Optional[str]:
        workbook_aliases = self._build_reconciliation_aliases(workbook_entry, alias_registry=alias_registry)
        bank_aliases = self._build_reconciliation_aliases(bank_entry)
        if not workbook_aliases or not bank_aliases:
            return None
        overlaps = sorted(workbook_aliases & bank_aliases, key=len, reverse=True)
        if overlaps:
            return overlaps[0]
        return None

    def _match_persisted_reconciliation_alias(
        self,
        workbook_entry,
        bank_entry,
        *,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> Optional[str]:
        if not alias_registry:
            return None
        registry_aliases = self._build_persisted_reconciliation_aliases(workbook_entry, alias_registry=alias_registry)
        if not registry_aliases:
            return None
        bank_aliases = self._build_reconciliation_aliases(bank_entry)
        overlaps = sorted(registry_aliases & bank_aliases, key=len, reverse=True)
        if overlaps:
            return overlaps[0]
        return None

    def _build_reconciliation_aliases(
        self,
        entry,
        *,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> set[str]:
        aliases: set[str] = set()
        for raw_value in (
            getattr(entry, "counterparty", None),
            getattr(entry, "contract_label", None),
            getattr(entry, "description", None),
        ):
            if not raw_value:
                continue
            for alias in self._expand_reconciliation_aliases(raw_value):
                if alias:
                    aliases.add(alias)
        if alias_registry:
            for raw_value, bucket in (
                (getattr(entry, "counterparty", None), "clients"),
                (getattr(entry, "contract_label", None), "contracts"),
            ):
                normalized_key = self._normalize_rollup_key(raw_value)
                if not normalized_key:
                    continue
                for alias in alias_registry.get(bucket, {}).get(normalized_key, set()):
                    for expanded in self._expand_reconciliation_aliases(alias):
                        if expanded:
                            aliases.add(expanded)
        return aliases

    def _build_persisted_reconciliation_aliases(
        self,
        entry,
        *,
        alias_registry: Optional[dict[str, dict[str, set[str]]]] = None,
    ) -> set[str]:
        if not alias_registry:
            return set()
        aliases: set[str] = set()
        for raw_value, bucket in (
            (getattr(entry, "counterparty", None), "clients"),
            (getattr(entry, "contract_label", None), "contracts"),
        ):
            normalized_key = self._normalize_rollup_key(raw_value)
            if not normalized_key:
                continue
            for alias in alias_registry.get(bucket, {}).get(normalized_key, set()):
                for expanded in self._expand_reconciliation_aliases(alias):
                    if expanded:
                        aliases.add(expanded)
        return aliases

    def _expand_reconciliation_aliases(self, raw_value: str) -> set[str]:
        aliases: set[str] = set()
        normalized = self._normalize_reconciliation_text(raw_value)
        if not normalized:
            return aliases
        aliases.add(normalized)

        primary_segment = normalized.split(" unidade ", 1)[0].split(" inicio ", 1)[0].strip()
        if primary_segment:
            aliases.add(primary_segment)

        tokens = [
            token
            for token in primary_segment.split()
            if token and token not in RECONCILIATION_ALIAS_STOP_WORDS
        ]
        if tokens:
            aliases.add(" ".join(tokens))
            for token in tokens:
                if len(token) >= 3 or any(character.isdigit() for character in token):
                    aliases.add(token)
            if len(tokens) >= 2:
                acronym = "".join(token[0] for token in tokens if token)
                if len(acronym) >= 2:
                    aliases.add(acronym)
        return aliases

    def _is_generic_bank_inflow_entry(self, entry) -> bool:
        if self._resolve_entry_source_kind(entry) != "bank_statement":
            return False
        normalized_description = self._normalize_reconciliation_text(getattr(entry, "description", None))
        normalized_counterparty = self._normalize_reconciliation_text(getattr(entry, "counterparty", None))
        if "pix recebido" in normalized_description or "recebimento" in normalized_description:
            if not normalized_counterparty or normalized_counterparty.replace(" ", "").isdigit():
                return True
        return normalized_description.startswith("cr cob") or "cob bloq" in normalized_description

    def _normalized_entry_amount(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return abs(float(value))

    def _normalize_reconciliation_period(self, period_label: Optional[str]) -> str:
        if not period_label:
            return ""
        return period_label.split(" [", 1)[0].strip().casefold()

    def _normalize_reconciliation_text(self, value: Optional[str]) -> str:
        cleaned = "".join(character.lower() if character.isalnum() else " " for character in (value or ""))
        return " ".join(cleaned.split())

    def _parse_reconciliation_date(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        cleaned = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    def _format_reconciliation_amount(self, value: float) -> str:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _annotate_financial_sources(
        self,
        parsed: ChecklistParseResult,
        source_names: list[str],
    ) -> ChecklistParseResult:
        if parsed.financial_analysis is None:
            return parsed
        annotated = parsed.model_copy(deep=True)
        annotated.financial_analysis.source_workbook_count = len(source_names)
        annotated.financial_analysis.source_workbook_names = list(source_names)
        return annotated

    def _resolve_combined_period_label(
        self,
        months,
        parsed_results: list[ChecklistParseResult],
    ) -> Optional[str]:
        if months:
            parser = FinancialWorkbookParser(build_parser_config(profile="financial_dre"))
            sorted_months = sorted(months, key=parser._period_sort_key)
            first_label = sorted_months[0].period_label
            last_label = sorted_months[-1].period_label
            if first_label == last_label:
                return first_label
            return f"{first_label} a {last_label}"
        return self._first_nonempty(parsed.periodo_analise for parsed in parsed_results)

    def _merge_reference_links(self, parsed_results: list[ChecklistParseResult]):
        merged_links = []
        seen_keys: set[tuple[str, str, str]] = set()
        for parsed in parsed_results:
            for reference_link in parsed.reference_links:
                key = (
                    reference_link.url.strip().lower(),
                    reference_link.sheet_name.strip().lower(),
                    (reference_link.cell_reference or "").strip().lower(),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                merged_links.append(reference_link.model_copy(deep=True))
        return merged_links

    def _disambiguate_duplicate_period_labels(self, months) -> None:
        counts = Counter(month.period_label for month in months if month.period_label)
        for month in months:
            if not month.period_label or counts[month.period_label] < 2:
                continue
            source_label = month.sheet_name.split("::", 1)[0].strip() if "::" in month.sheet_name else month.sheet_name
            month.period_label = f"{month.period_label} [{source_label}]"

    def _has_duplicate_periods(self, months) -> bool:
        counts = Counter(month.period_label.split(" [", 1)[0] for month in months if month.period_label)
        return any(count > 1 for count in counts.values())

    def _build_source_batch_label(self, source_names: list[str]) -> Optional[str]:
        cleaned_names = [name.strip() for name in source_names if name and name.strip()]
        if not cleaned_names:
            return None
        if len(cleaned_names) == 1:
            return cleaned_names[0]
        return f"{Path(cleaned_names[0]).name} + {len(cleaned_names) - 1} arquivo(s)"

    def _normalize_source_label(self, source_name: Optional[str]) -> str:
        raw_label = Path(source_name or "Workbook").stem.replace("_", " ").replace("-", " ")
        return " ".join(raw_label.split())[:80] or "Workbook"

    def _prefix_source_label(self, source_label: str, value: Optional[str]) -> str:
        cleaned_value = (value or "Sem identificacao").strip()
        return f"{source_label} :: {cleaned_value}"

    def _first_nonempty(self, values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    def _unique_in_order(self, values):
        unique_values = []
        seen = set()
        for value in values:
            if value is None:
                continue
            if isinstance(value, str):
                normalized = value.strip()
                if not normalized:
                    continue
                marker = normalized.lower()
                resolved_value = normalized
            else:
                marker = value
                resolved_value = value
            if marker in seen:
                continue
            seen.add(marker)
            unique_values.append(resolved_value)
        return unique_values

    def _resolve_parser_profile_for_path(self, input_path: Path, requested_profile: str) -> str:
        if input_path.suffix.lower() == ".pdf":
            normalized_profile = (requested_profile or "auto").strip().lower() or "auto"
            if normalized_profile not in {"", "auto", "automatico", "automatic", "detectar", "financial_dre"}:
                raise HTTPException(
                    status_code=400,
                    detail="PDFs sao suportados apenas no fluxo Financeiro / DRE.",
                )
            if not looks_like_bank_statement_pdf(input_path):
                raise HTTPException(
                    status_code=400,
                    detail="O PDF enviado nao parece um extrato bancario compativel com a leitura financeira.",
                )
            return "financial_dre"
        return resolve_parser_profile_for_workbook(input_path, requested_profile)

    @staticmethod
    def _resolve_layout_profile(
        tipo_orgao: Optional[str],
        layout_profile: Optional[str],
    ) -> Optional[str]:
        if tipo_orgao:
            return tipo_orgao
        mapping = {
            "profile_a": "prefeitura",
            "profile_b": "camara",
        }
        return mapping.get((layout_profile or "").strip().lower())
