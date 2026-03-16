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
]


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


class AnalysisContextResponse(BaseModel):
    analysis_id: int
    summary: str


class AnalysisReviewStats(BaseModel):
    extracted_item_count: int = 0
    warning_count: int = 0
    scraped_page_count: int = 0
    scraped_link_count: int = 0
    scrape_duration_ms: Optional[int] = None


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


class GenerationTrace(BaseModel):
    id: Optional[int] = None
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
    titulo_relatorio: str = "Relatorio de Transparencia"
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
