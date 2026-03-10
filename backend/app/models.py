from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


FonteType = Literal["site_orgao", "portal_transparencia", "esic", "nao_informada"]
StatusType = Literal["Nao", "Parcialmente"]


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
    itens_processados: list[ChecklistItem] = Field(default_factory=list)
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


class ScrapePageResult(BaseModel):
    requested_url: str
    final_url: str
    page_title: Optional[str] = None
    summary: str
    links: list[ScrapedLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScrapedPageRecord(BaseModel):
    fonte: FonteType = "nao_informada"
    requested_url: str
    final_url: str
    page_title: Optional[str] = None
    summary: str
    links: list[ScrapedLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StoredAnalysisResponse(BaseModel):
    analysis_id: int
    parsed: ChecklistParseResult


class AnalysisContextResponse(BaseModel):
    analysis_id: int
    summary: str


class ReportSection(BaseModel):
    fonte: FonteType
    titulo: str
    texto: str


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
