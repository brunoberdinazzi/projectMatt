from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


FonteType = Literal["site_orgao", "portal_transparencia", "esic", "nao_informada"]
StatusType = Literal["Sim", "Nao", "Parcialmente", "Nao se aplica"]
WorkbookLayerType = Literal[
    "checklist_scope",
    "reference_framework",
    "entity_reference",
    "registry_snapshot",
    "outcome_matrix",
    "financial_overview",
    "financial_cost_structure",
    "financial_results_bridge",
    "financial_client_rollup",
    "financial_contract_rollup",
]
ReferenceLinkKind = Literal["primary", "reference"]
FinancialEntryType = Literal[
    "receivable",
    "other_income",
    "permuta",
    "debt",
    "bank_fee",
    "internal_transfer",
    "tax",
    "personnel",
    "fixed_cost",
    "operating_cost",
    "inventory",
    "negotiation",
    "partnership",
    "summary",
]
FinancialStatementLineType = Literal["revenue", "deduction", "expense", "result", "balance", "note"]
FinancialSourceKind = Literal["workbook", "bank_statement"]
FinancialReconciliationStatus = Literal["matched", "probable", "unmatched", "excluded"]
FinancialAliasKind = Literal["client", "contract"]


class ParserOptions(BaseModel):
    profile: str = "default"
    allowed_groups: list[str] = Field(default_factory=lambda: ["1", "5"])
    allowed_status: list[StatusType] = Field(default_factory=lambda: ["Nao", "Parcialmente"])
    checklist_sheet_name: str = "auto"
    checklist_sheet_names: list[str] = Field(default_factory=list)
    metadata_row: int = Field(default=5, ge=1)


class ParserProfileDefinition(BaseModel):
    key: str
    label: str
    description: str
    allowed_groups: list[str] = Field(default_factory=list)
    allowed_status: list[StatusType] = Field(default_factory=list)


class ParserDetectionResponse(BaseModel):
    requested_profile: str
    resolved_profile: str
    resolved_label: str
    resolved_description: Optional[str] = None
    message: Optional[str] = None


class OllamaModelsResponse(BaseModel):
    models: list[str] = Field(default_factory=list)
    recommended_model: Optional[str] = None


class OllamaLoadedModelResponse(BaseModel):
    name: str
    size_vram: Optional[int] = None
    context_length: Optional[int] = None
    expires_at: Optional[str] = None


class OllamaStatusResponse(BaseModel):
    available: bool = False
    latency_ms: Optional[int] = None
    base_url: Optional[str] = None
    recommended_model: Optional[str] = None
    active_model: Optional[str] = None
    installed_model_count: int = 0
    loaded_model_count: int = 0
    loaded_models: list[OllamaLoadedModelResponse] = Field(default_factory=list)
    message: Optional[str] = None


class AuthRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthProfileUpdateRequest(BaseModel):
    full_name: str
    email: str


class AuthPasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str


class AuthPasswordForgotRequest(BaseModel):
    email: str


class AuthPasswordForgotResponse(BaseModel):
    ok: bool = True
    message: Optional[str] = None
    reset_token: Optional[str] = None
    expires_at: Optional[str] = None


class AuthPasswordResetRequest(BaseModel):
    token: str
    new_password: str


class AuthUserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: Optional[str] = None


class AuthSessionInfo(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse
    session: Optional[AuthSessionInfo] = None


class ChecklistDetail(BaseModel):
    descricao: str
    status: str


class ChecklistItem(BaseModel):
    grupo: str = Field(..., description="Grupo do checklist. Ex.: 1 ou 5.")
    item_codigo: str
    linha_referencia: int = Field(..., ge=1)
    ano_referencia: Optional[str] = None
    status: StatusType
    status_2024: Optional[str] = None
    status_2025: Optional[str] = None
    fonte: FonteType
    fonte_texto: Optional[str] = None
    descricao_item: str
    observacao: Optional[str] = None
    fundamentacao: Optional[str] = None
    detalhes: list[ChecklistDetail] = Field(default_factory=list)
    aba_origem: Optional[str] = None


class WorkbookContextLayer(BaseModel):
    layer_type: WorkbookLayerType
    sheet_name: str
    title: str
    summary: str
    details: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class WorkbookReferenceLink(BaseModel):
    url: str
    sheet_name: str
    cell_reference: Optional[str] = None
    label: Optional[str] = None
    context: Optional[str] = None
    source_hint: FonteType = "nao_informada"
    link_kind: ReferenceLinkKind = "reference"
    crawlable: bool = True
    selected_for_crawl: bool = False


class FinancialEntry(BaseModel):
    entry_type: FinancialEntryType
    sheet_name: str
    description: str
    source_kind: Optional[FinancialSourceKind] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    counterparty: Optional[str] = None
    unit: Optional[str] = None
    notes: Optional[str] = None
    owner_label: Optional[str] = None
    contract_label: Optional[str] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    reconciliation_status: Optional[FinancialReconciliationStatus] = None
    reconciliation_score: Optional[float] = None
    reconciliation_partner_period_label: Optional[str] = None
    reconciliation_partner_description: Optional[str] = None
    reconciliation_alias_label: Optional[str] = None
    reconciliation_note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class FinancialSectionSnapshot(BaseModel):
    section_key: str
    title: str
    owner_label: Optional[str] = None
    total_amount: Optional[float] = None
    entry_count: int = 0
    entries: list[FinancialEntry] = Field(default_factory=list)


class FinancialPeriodSummary(BaseModel):
    sheet_name: str
    period_label: str
    year: Optional[int] = None
    gross_revenue_total: Optional[float] = None
    receivables_total: Optional[float] = None
    other_income_total: Optional[float] = None
    permuta_balance: Optional[float] = None
    debt_outstanding: Optional[float] = None
    taxes_total: Optional[float] = None
    personnel_total: Optional[float] = None
    fixed_costs_total: Optional[float] = None
    operating_costs_total: Optional[float] = None
    vbc_total: Optional[float] = None
    modulo_total: Optional[float] = None
    global_expenses_total: Optional[float] = None
    net_result: Optional[float] = None
    carried_balance: Optional[float] = None
    closing_total: Optional[float] = None
    pending_entry_count: int = 0
    sections: list[FinancialSectionSnapshot] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FinancialStatementLine(BaseModel):
    key: str
    label: str
    amount: float = 0.0
    line_type: FinancialStatementLineType = "note"
    share_of_gross_revenue: Optional[float] = None
    share_of_operating_inflows: Optional[float] = None


class FinancialClientRollup(BaseModel):
    canonical_client_id: Optional[int] = None
    canonical_client_name: Optional[str] = None
    client_name: str
    total_received_amount: float = 0.0
    total_expected_amount: float = 0.0
    total_pending_amount: float = 0.0
    contract_count: int = 0
    months_covered: list[str] = Field(default_factory=list)
    contract_labels: list[str] = Field(default_factory=list)
    reconciliation_matched_count: int = 0
    reconciliation_probable_count: int = 0
    reconciliation_unmatched_count: int = 0
    reconciliation_excluded_count: int = 0
    reconciliation_matched_amount: float = 0.0
    reconciliation_probable_amount: float = 0.0
    reconciliation_unmatched_amount: float = 0.0
    reconciliation_excluded_amount: float = 0.0
    reconciliation_alias_supported_count: int = 0
    reconciliation_alias_supported_amount: float = 0.0
    reconciliation_coverage_ratio: Optional[float] = None


class FinancialClientPeriodRollup(BaseModel):
    canonical_client_id: Optional[int] = None
    canonical_client_name: Optional[str] = None
    client_name: str
    period_label: str
    total_received_amount: float = 0.0
    total_expected_amount: float = 0.0
    total_pending_amount: float = 0.0
    contract_count: int = 0
    contract_labels: list[str] = Field(default_factory=list)


class FinancialContractRollup(BaseModel):
    canonical_client_id: Optional[int] = None
    canonical_client_name: Optional[str] = None
    canonical_contract_id: Optional[int] = None
    canonical_contract_name: Optional[str] = None
    contract_label: str
    client_name: Optional[str] = None
    unit: Optional[str] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    latest_status: Optional[str] = None
    total_received_amount: float = 0.0
    total_expected_amount: float = 0.0
    total_pending_amount: float = 0.0
    entry_count: int = 0
    months_covered: list[str] = Field(default_factory=list)
    source_sheet_names: list[str] = Field(default_factory=list)
    reconciliation_matched_count: int = 0
    reconciliation_probable_count: int = 0
    reconciliation_unmatched_count: int = 0
    reconciliation_excluded_count: int = 0
    reconciliation_matched_amount: float = 0.0
    reconciliation_probable_amount: float = 0.0
    reconciliation_unmatched_amount: float = 0.0
    reconciliation_excluded_amount: float = 0.0
    reconciliation_alias_supported_count: int = 0
    reconciliation_alias_supported_amount: float = 0.0
    reconciliation_coverage_ratio: Optional[float] = None


class FinancialAnalysisResult(BaseModel):
    workbook_kind: str = "financial_dre"
    fiscal_year: Optional[int] = None
    entity_name: Optional[str] = None
    source_workbook_count: int = 1
    source_workbook_names: list[str] = Field(default_factory=list)
    months: list[FinancialPeriodSummary] = Field(default_factory=list)
    dre_lines: list[FinancialStatementLine] = Field(default_factory=list)
    client_rollups: list[FinancialClientRollup] = Field(default_factory=list)
    client_period_rollups: list[FinancialClientPeriodRollup] = Field(default_factory=list)
    contract_rollups: list[FinancialContractRollup] = Field(default_factory=list)
    summary_notes: list[str] = Field(default_factory=list)
    detected_entities: list[str] = Field(default_factory=list)
    entry_count: int = 0


class FinancialWarehouseTopClient(BaseModel):
    canonical_client_id: Optional[int] = None
    client_name: str
    total_received_amount: float = 0.0
    total_expected_amount: float = 0.0
    total_pending_amount: float = 0.0
    contract_count: int = 0


class FinancialWarehouseTopContract(BaseModel):
    canonical_contract_id: Optional[int] = None
    contract_label: str
    client_name: Optional[str] = None
    total_received_amount: float = 0.0
    total_expected_amount: float = 0.0
    total_pending_amount: float = 0.0
    entry_count: int = 0


class FinancialWarehouseTopPeriod(BaseModel):
    period_label: str
    net_result: float = 0.0
    gross_revenue_total: float = 0.0
    global_expenses_total: float = 0.0
    pending_entry_count: int = 0


class FinancialWarehouseOverview(BaseModel):
    analysis_id: int
    snapshot_available: bool = False
    entry_count: int = 0
    client_count: int = 0
    contract_count: int = 0
    period_count: int = 0
    top_clients: list[FinancialWarehouseTopClient] = Field(default_factory=list)
    top_contracts: list[FinancialWarehouseTopContract] = Field(default_factory=list)
    top_periods: list[FinancialWarehouseTopPeriod] = Field(default_factory=list)


class ChecklistParseResult(BaseModel):
    analysis_id: Optional[int] = None
    orgao: Optional[str] = None
    tipo_orgao: Optional[str] = None
    periodo_analise: Optional[str] = None
    sat_numero: Optional[str] = None
    site_url: Optional[str] = None
    portal_url: Optional[str] = None
    esic_url: Optional[str] = None
    numero_relatorio: Optional[str] = None
    promotoria: Optional[str] = None
    referencia: Optional[str] = None
    solicitacao: Optional[str] = None
    cidade_emissao: Optional[str] = None
    data_emissao: Optional[str] = None
    periodo_coleta: Optional[str] = None
    equipe_tecnica: Optional[str] = None
    relatorio_contabil_referencia: Optional[str] = None
    fontes_disponiveis: list[FonteType] = Field(default_factory=list)
    grupos_permitidos: list[str] = Field(default_factory=lambda: ["1", "5"])
    parser_options: ParserOptions = Field(default_factory=ParserOptions)
    itens_processados: list[ChecklistItem] = Field(default_factory=list)
    context_layers: list[WorkbookContextLayer] = Field(default_factory=list)
    reference_links: list[WorkbookReferenceLink] = Field(default_factory=list)
    financial_analysis: Optional[FinancialAnalysisResult] = None
    warehouse_overview: Optional[FinancialWarehouseOverview] = None
    parse_cache_hit: bool = False
    parse_duration_ms: Optional[int] = None
    parse_cache_saved_ms: Optional[int] = None
    scraped_pages: list["ScrapedPageRecord"] = Field(default_factory=list)
    database_summary: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PromptResponse(BaseModel):
    prompt: str


class PipelineRunResponse(BaseModel):
    parsed: ChecklistParseResult
    prompt: str


class ScrapedLink(BaseModel):
    label: str
    url: str
    category: str
    destination_type: str
    context: Optional[str] = None
    section: Optional[str] = None
    is_internal: bool = False
    score: int = 0
    matched_terms: list[str] = Field(default_factory=list)
    evidence_summary: Optional[str] = None


class ScrapePageResult(BaseModel):
    requested_url: str
    final_url: str
    page_title: Optional[str] = None
    summary: str
    links: list[ScrapedLink] = Field(default_factory=list)
    discovered_pages: list["ScrapedPageRecord"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None


class ScrapedPageRecord(BaseModel):
    fonte: FonteType = "nao_informada"
    requested_url: str
    final_url: str
    page_title: Optional[str] = None
    summary: str
    links: list[ScrapedLink] = Field(default_factory=list)
    discovery_depth: int = 0
    page_score: int = 0
    discovered_from_url: Optional[str] = None
    discovered_from_label: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class StoredAnalysisResponse(BaseModel):
    analysis_id: int
    parsed: ChecklistParseResult


class AnalysisListItem(BaseModel):
    analysis_id: int
    created_at: Optional[str] = None
    source_filename: Optional[str] = None
    orgao: Optional[str] = None
    tipo_orgao: Optional[str] = None
    periodo_analise: Optional[str] = None
    parser_profile: Optional[str] = None
    checklist_sheet_names: list[str] = Field(default_factory=list)
    extracted_item_count: int = 0
    scraped_page_count: int = 0
    generation_count: int = 0
    last_generation_at: Optional[str] = None


class AnalysisContextResponse(BaseModel):
    analysis_id: int
    summary: str


class FinancialWarehouseSyncResponse(BaseModel):
    analysis_id: int
    synced: bool = False
    snapshot_available: bool = False
    source: Literal["existing", "backfilled", "unavailable"] = "unavailable"
    database_summary: Optional[str] = None
    message: Optional[str] = None


class FinancialWarehouseBackfillResponse(BaseModel):
    processed_count: int = 0
    synced_count: int = 0
    skipped_count: int = 0
    analysis_ids: list[int] = Field(default_factory=list)


class FinancialAliasItem(BaseModel):
    kind: FinancialAliasKind
    entity_id: int
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    canonical_client_id: Optional[int] = None
    canonical_client_name: Optional[str] = None
    unit: Optional[str] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    first_period_label: Optional[str] = None
    last_period_label: Optional[str] = None
    updated_at: Optional[str] = None


class FinancialAliasCatalogResponse(BaseModel):
    clients: list[FinancialAliasItem] = Field(default_factory=list)
    contracts: list[FinancialAliasItem] = Field(default_factory=list)


class FinancialAliasUpsertRequest(BaseModel):
    kind: FinancialAliasKind
    entity_id: int = Field(..., ge=1)
    alias: str


class FinancialAliasDeleteRequest(BaseModel):
    kind: FinancialAliasKind
    entity_id: int = Field(..., ge=1)
    alias: str


class FinancialEntryTraceItem(BaseModel):
    analysis_id: int
    position: int
    canonical_client_id: Optional[int] = None
    canonical_client_name: Optional[str] = None
    canonical_contract_id: Optional[int] = None
    canonical_contract_name: Optional[str] = None
    period_label: str
    sheet_name: str
    section_key: str
    section_title: str
    owner_label: Optional[str] = None
    entry_type: str
    description: str
    amount: Optional[float] = None
    status: Optional[str] = None
    entry_date: Optional[str] = None
    due_date: Optional[str] = None
    counterparty: Optional[str] = None
    unit: Optional[str] = None
    notes: Optional[str] = None
    contract_label: Optional[str] = None
    contract_start_date: Optional[str] = None
    contract_end_date: Optional[str] = None
    source_kind: Optional[FinancialSourceKind] = None
    reconciliation_status: Optional[FinancialReconciliationStatus] = None
    reconciliation_score: Optional[float] = None
    reconciliation_partner_period_label: Optional[str] = None
    reconciliation_partner_description: Optional[str] = None
    reconciliation_alias_label: Optional[str] = None
    reconciliation_note: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class AnalysisReviewStats(BaseModel):
    extracted_item_count: int = 0
    warning_count: int = 0
    scraped_page_count: int = 0
    scraped_link_count: int = 0
    parse_duration_ms: Optional[int] = None
    scrape_duration_ms: Optional[int] = None
    parse_cache_hit: bool = False
    parse_cache_saved_ms: Optional[int] = None


class AnalysisReviewResponse(BaseModel):
    analysis_id: int
    parsed: ChecklistParseResult
    summary: str
    prompt_preview: str
    stats: AnalysisReviewStats


class ReportSection(BaseModel):
    fonte: FonteType
    titulo: str
    texto: str
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)


class GenerationTrace(BaseModel):
    id: Optional[int] = None
    session_public_id: Optional[str] = None
    requested_mode: str
    used_mode: str
    provider: str
    model_name: Optional[str] = None
    output_format: str
    prompt_snapshot: Optional[str] = None
    raw_response: Optional[str] = None
    fallback_reason: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: Optional[str] = None


class GeneratedReportPayload(BaseModel):
    report: "ReportBuildRequest"
    trace: GenerationTrace


class ReportBuildRequest(BaseModel):
    titulo_relatorio: str = "Relatorio Tecnico de Analise"
    orgao: Optional[str] = None
    tipo_orgao: Optional[str] = None
    periodo_analise: Optional[str] = None
    sat_numero: Optional[str] = None
    numero_relatorio: Optional[str] = None
    promotoria: Optional[str] = None
    referencia: Optional[str] = None
    solicitacao: Optional[str] = None
    cidade_emissao: Optional[str] = None
    data_emissao: Optional[str] = None
    periodo_coleta: Optional[str] = None
    equipe_tecnica: Optional[str] = None
    relatorio_contabil_referencia: Optional[str] = None
    site_url: Optional[str] = None
    portal_url: Optional[str] = None
    esic_url: Optional[str] = None
    secoes: list[ReportSection] = Field(default_factory=list)


ChecklistParseResult.model_rebuild()
StoredAnalysisResponse.model_rebuild()
AnalysisReviewResponse.model_rebuild()
GeneratedReportPayload.model_rebuild()
