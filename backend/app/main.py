from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    AnalysisContextResponse,
    ChecklistParseResult,
    PipelineRunResponse,
    PromptResponse,
    ReportBuildRequest,
    ScrapePageResult,
    ScrapedPageRecord,
    StoredAnalysisResponse,
)
from .services.analysis_context_builder import AnalysisContextBuilder
from .services.analysis_store import AnalysisStore
from .services.excel_parser import ChecklistParser, ParserConfig
from .services.link_scraper import LinkScraper
from .services.ollama_report_content_builder import OllamaReportContentBuilder
from .services.openai_report_content_builder import OpenAIReportContentBuilder
from .services.prompt_builder import PromptBuilder
from .services.report_content_builder import ReportContentBuilder
from .services.report_builder import ReportBuilder
from .services.technical_report_composer import TechnicalReportComposer

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Matt Backend MVP",
    version="0.1.0",
    description="Backend inicial para leitura de checklist, montagem de prompt e geracao de relatorio.",
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

parser = ChecklistParser(ParserConfig())
prompt_builder = PromptBuilder()
report_content_builder = ReportContentBuilder()
openai_report_content_builder = OpenAIReportContentBuilder()
ollama_report_content_builder = OllamaReportContentBuilder()
report_builder = ReportBuilder()
technical_report_composer = TechnicalReportComposer()
link_scraper = LinkScraper()
analysis_store = AnalysisStore()
analysis_context_builder = AnalysisContextBuilder()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/providers/ollama/models")
def ollama_models() -> dict[str, list[str]]:
    try:
        return {"models": ollama_report_content_builder.list_models()}
    except Exception:
        return {"models": []}


@app.get("/scrape/links", response_model=ScrapePageResult)
def scrape_links(url: str, max_links: int = 40) -> ScrapePageResult:
    if max_links < 1 or max_links > 200:
        raise HTTPException(status_code=400, detail="Use max_links entre 1 e 200.")

    try:
        return link_scraper.scrape(url=url, max_links=max_links)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao acessar a URL informada: {exc}",
        ) from exc


@app.post("/analysis/intake", response_model=StoredAnalysisResponse)
async def analysis_intake(
    file: UploadFile = File(...),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    layout_profile: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
    numero_relatorio: Optional[str] = Form(default=None),
    promotoria: Optional[str] = Form(default=None),
    requester_area: Optional[str] = Form(default=None),
    referencia: Optional[str] = Form(default=None),
    solicitacao: Optional[str] = Form(default=None),
    cidade_emissao: Optional[str] = Form(default=None),
    data_emissao: Optional[str] = Form(default=None),
    periodo_coleta: Optional[str] = Form(default=None),
    equipe_tecnica: Optional[str] = Form(default=None),
    relatorio_contabil_referencia: Optional[str] = Form(default=None),
) -> StoredAnalysisResponse:
    temp_path = await _store_upload(file)
    try:
        parsed = parser.parse(temp_path, source_name=file.filename)
        if orgao:
            parsed.orgao = orgao
        tipo_orgao = _resolve_layout_profile(tipo_orgao, layout_profile)
        if tipo_orgao:
            parsed.tipo_orgao = tipo_orgao
        if periodo_analise:
            parsed.periodo_analise = periodo_analise
        _apply_report_metadata(
            parsed,
            numero_relatorio=numero_relatorio,
            promotoria=promotoria or requester_area,
            referencia=referencia,
            solicitacao=solicitacao,
            cidade_emissao=cidade_emissao,
            data_emissao=data_emissao,
            periodo_coleta=periodo_coleta,
            equipe_tecnica=equipe_tecnica,
            relatorio_contabil_referencia=relatorio_contabil_referencia,
        )
        parsed.database_summary = analysis_context_builder.build_summary(parsed)
        analysis_id = analysis_store.create_analysis(parsed, source_filename=file.filename)
        parsed.analysis_id = analysis_id
        analysis_store.set_database_summary(analysis_id, parsed.database_summary)
        return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)
    finally:
        temp_path.unlink(missing_ok=True)


@app.get("/analysis/{analysis_id}", response_model=StoredAnalysisResponse)
def get_analysis(analysis_id: int) -> StoredAnalysisResponse:
    parsed = analysis_store.get_analysis(analysis_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")
    return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)


@app.post("/analysis/{analysis_id}/scrape", response_model=StoredAnalysisResponse)
def scrape_analysis(analysis_id: int) -> StoredAnalysisResponse:
    parsed = analysis_store.get_analysis(analysis_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")

    parsed.scraped_pages = _scrape_pages_for_analysis(parsed)
    parsed.database_summary = analysis_context_builder.build_summary(parsed)
    analysis_store.update_analysis(analysis_id, parsed)
    return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)


@app.get("/analysis/{analysis_id}/context", response_model=AnalysisContextResponse)
def get_analysis_context(analysis_id: int) -> AnalysisContextResponse:
    parsed = analysis_store.get_analysis(analysis_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="Analise nao encontrada.")

    summary = parsed.database_summary or analysis_context_builder.build_summary(parsed)
    if summary != parsed.database_summary:
        analysis_store.set_database_summary(analysis_id, summary)
    return AnalysisContextResponse(analysis_id=analysis_id, summary=summary)


@app.post("/checklist/upload", response_model=ChecklistParseResult)
async def upload_checklist(
    file: UploadFile = File(...),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
) -> ChecklistParseResult:
    temp_path = await _store_upload(file)
    try:
        result = parser.parse(temp_path, source_name=file.filename)
        if orgao:
            result.orgao = orgao
        if tipo_orgao:
            result.tipo_orgao = tipo_orgao
        if periodo_analise:
            result.periodo_analise = periodo_analise
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/prompt/build", response_model=PromptResponse)
def build_prompt(payload: ChecklistParseResult) -> PromptResponse:
    prompt = prompt_builder.build(payload)
    return PromptResponse(prompt=prompt)


@app.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(
    file: UploadFile = File(...),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
) -> PipelineRunResponse:
    temp_path = await _store_upload(file)
    try:
        parsed = parser.parse(temp_path, source_name=file.filename)
        if orgao:
            parsed.orgao = orgao
        if tipo_orgao:
            parsed.tipo_orgao = tipo_orgao
        if periodo_analise:
            parsed.periodo_analise = periodo_analise

        prompt = prompt_builder.build(parsed)
        return PipelineRunResponse(parsed=parsed, prompt=prompt)
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/report/build")
def build_report(payload: ReportBuildRequest, background_tasks: BackgroundTasks) -> FileResponse:
    report_path = report_builder.build(payload)
    background_tasks.add_task(report_path.unlink, True)
    filename = report_path.name
    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@app.post("/report/generate")
async def generate_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    template_file: Optional[UploadFile] = File(default=None),
    output_format: str = Form(default="docx"),
    generation_mode: str = Form(default="auto"),
    local_model: Optional[str] = Form(default=None),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    layout_profile: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
    numero_relatorio: Optional[str] = Form(default=None),
    promotoria: Optional[str] = Form(default=None),
    requester_area: Optional[str] = Form(default=None),
    referencia: Optional[str] = Form(default=None),
    solicitacao: Optional[str] = Form(default=None),
    cidade_emissao: Optional[str] = Form(default=None),
    data_emissao: Optional[str] = Form(default=None),
    periodo_coleta: Optional[str] = Form(default=None),
    equipe_tecnica: Optional[str] = Form(default=None),
    relatorio_contabil_referencia: Optional[str] = Form(default=None),
) -> FileResponse:
    if output_format not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="Formato de saida invalido. Use docx ou pdf.")
    if generation_mode not in {"auto", "ai", "local", "rules"}:
        raise HTTPException(status_code=400, detail="Modo de geracao invalido. Use auto, ai, local ou rules.")

    temp_path = await _store_upload(file)
    template_path = await _store_template_upload(template_file)
    try:
        parsed = parser.parse(temp_path, source_name=file.filename)
        if orgao:
            parsed.orgao = orgao
        tipo_orgao = _resolve_layout_profile(tipo_orgao, layout_profile)
        if tipo_orgao:
            parsed.tipo_orgao = tipo_orgao
        if periodo_analise:
            parsed.periodo_analise = periodo_analise
        _apply_report_metadata(
            parsed,
            numero_relatorio=numero_relatorio,
            promotoria=promotoria or requester_area,
            referencia=referencia,
            solicitacao=solicitacao,
            cidade_emissao=cidade_emissao,
            data_emissao=data_emissao,
            periodo_coleta=periodo_coleta,
            equipe_tecnica=equipe_tecnica,
            relatorio_contabil_referencia=relatorio_contabil_referencia,
        )

        analysis_id = analysis_store.create_analysis(
            parsed,
            source_filename=file.filename,
            generation_mode=generation_mode,
            output_format=output_format,
        )
        parsed.analysis_id = analysis_id
        parsed.scraped_pages = _scrape_pages_for_analysis(parsed)
        parsed.database_summary = analysis_context_builder.build_summary(parsed)
        analysis_store.update_analysis(
            analysis_id,
            parsed,
            generation_mode=generation_mode,
            output_format=output_format,
        )

        dynamic_payload = _build_report_payload(parsed, generation_mode, local_model=local_model)
        report_payload = technical_report_composer.compose(parsed, dynamic_payload)
        report_path = report_builder.build(
            report_payload,
            output_format=output_format,
            template_path=template_path,
        )
        background_tasks.add_task(report_path.unlink, True)

        filename = _build_output_filename(parsed.orgao, output_format)
        media_type = (
            "application/pdf"
            if output_format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return FileResponse(
            report_path,
            media_type=media_type,
            filename=filename,
            headers={"X-Analysis-ID": str(analysis_id)},
        )
    finally:
        temp_path.unlink(missing_ok=True)
        if template_path:
            template_path.unlink(missing_ok=True)


async def _store_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Envie um arquivo Excel .xlsx ou .xlsm.")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=_safe_temp_prefix(file.filename),
            suffix=suffix,
        ) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            return Path(temp_file.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Falha ao salvar o upload temporario.") from exc


async def _store_template_upload(file: Optional[UploadFile]) -> Optional[Path]:
    if file is None or not file.filename:
        return None

    suffix = Path(file.filename).suffix.lower()
    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="O template precisa ser um arquivo .docx.")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=_safe_temp_prefix(file.filename),
            suffix=suffix,
        ) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            return Path(temp_file.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Falha ao salvar o template temporario.") from exc


def _build_output_filename(orgao: Optional[str], output_format: str) -> str:
    base_name = orgao or "relatorio-tecnico"
    slug = "".join(char.lower() if char.isalnum() else "-" for char in base_name).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug or "relatorio-tecnico"
    return f"{slug}.{output_format}"


def _safe_temp_prefix(filename: Optional[str]) -> str:
    stem = Path(filename or "upload").stem
    cleaned = "".join(char if char.isalnum() else "_" for char in stem).strip("_")
    cleaned = cleaned[:40] or "upload"
    return f"{cleaned}_"


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


def _scrape_pages_for_analysis(parsed: ChecklistParseResult) -> list[ScrapedPageRecord]:
    queue = [
        ("site_orgao", parsed.site_url),
        ("portal_transparencia", parsed.portal_url),
        ("esic", parsed.esic_url),
    ]
    pages: list[ScrapedPageRecord] = []
    seen_urls: set[str] = set()
    discovered_sources: set[str] = set()

    while queue:
        source_key, url = queue.pop(0)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            result = link_scraper.scrape(url=url, max_links=25)
        except Exception as exc:
            parsed.warnings.append(
                f"Falha ao raspar {source_key} ({url}): {exc}"
            )
            continue

        pages.append(
            ScrapedPageRecord(
                fonte=source_key,
                requested_url=result.requested_url,
                final_url=result.final_url,
                page_title=result.page_title,
                summary=result.summary,
                links=result.links,
                warnings=result.warnings,
            )
        )

        for link in result.links:
            if (
                link.category == "portal_transparencia"
                and not parsed.portal_url
                and "portal_transparencia" not in discovered_sources
                and _is_discovery_candidate(link, source_key, "portal_transparencia", url)
            ):
                parsed.portal_url = link.url
                if "portal_transparencia" not in parsed.fontes_disponiveis:
                    parsed.fontes_disponiveis.append("portal_transparencia")
                queue.append(("portal_transparencia", link.url))
                discovered_sources.add("portal_transparencia")
            if (
                link.category == "esic"
                and not parsed.esic_url
                and "esic" not in discovered_sources
                and _is_discovery_candidate(link, source_key, "esic", url)
            ):
                parsed.esic_url = link.url
                if "esic" not in parsed.fontes_disponiveis:
                    parsed.fontes_disponiveis.append("esic")
                queue.append(("esic", link.url))
                discovered_sources.add("esic")

    return pages


def _is_discovery_candidate(
    link,
    current_source_key: str,
    target_source_key: str,
    current_url: str,
) -> bool:
    haystack = " ".join(
        part for part in [link.label, link.context or "", link.section or "", link.url] if part
    ).lower()
    current_host = urlparse(current_url).netloc.lower()
    target_host = urlparse(link.url).netloc.lower()

    if target_source_key == "portal_transparencia":
        return (
            "portal da transparencia" in haystack
            or "acesso a informacao" in haystack
            or "transparencia" in target_host
            or (target_host and target_host != current_host and "transpar" in haystack)
        )

    if target_source_key == "esic":
        return (
            "e-sic" in haystack
            or "esic" in haystack
            or "servico de informacao ao cidadao" in haystack
            or "pedido de informacao" in haystack
            or "informacao ao cidadao" in haystack
        )

    return False


def _build_report_payload(
    parsed: ChecklistParseResult,
    generation_mode: str,
    local_model: Optional[str] = None,
) -> ReportBuildRequest:
    if not parsed.itens_processados:
        return report_content_builder.build(parsed)

    if generation_mode == "rules":
        return report_content_builder.build(parsed)

    if generation_mode == "local":
        if not ollama_report_content_builder.is_configured(local_model):
            raise HTTPException(
                status_code=400,
                detail="Modo local solicitado, mas o Ollama nao esta disponivel com o modelo configurado.",
            )
        try:
            return ollama_report_content_builder.build(parsed, model_override=local_model)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via Ollama: {exc}") from exc

    if generation_mode == "ai":
        if not openai_report_content_builder.is_configured():
            raise HTTPException(
                status_code=400,
                detail="Modo IA solicitado, mas OPENAI_API_KEY nao esta configurada no servidor.",
            )
        try:
            return openai_report_content_builder.build(parsed)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via IA: {exc}") from exc

    if ollama_report_content_builder.is_configured(local_model):
        try:
            return ollama_report_content_builder.build(parsed, model_override=local_model)
        except Exception:
            pass

    if openai_report_content_builder.is_configured():
        try:
            return openai_report_content_builder.build(parsed)
        except Exception:
            return report_content_builder.build(parsed)

    return report_content_builder.build(parsed)


def _apply_report_metadata(
    parsed: ChecklistParseResult,
    numero_relatorio: Optional[str],
    promotoria: Optional[str],
    referencia: Optional[str],
    solicitacao: Optional[str],
    cidade_emissao: Optional[str],
    data_emissao: Optional[str],
    periodo_coleta: Optional[str],
    equipe_tecnica: Optional[str],
    relatorio_contabil_referencia: Optional[str],
) -> None:
    if numero_relatorio:
        parsed.numero_relatorio = numero_relatorio
    if promotoria:
        parsed.promotoria = promotoria
    if referencia:
        parsed.referencia = referencia
    if solicitacao:
        parsed.solicitacao = solicitacao
    if cidade_emissao:
        parsed.cidade_emissao = cidade_emissao
    if data_emissao:
        parsed.data_emissao = data_emissao
    if periodo_coleta:
        parsed.periodo_coleta = periodo_coleta
    if equipe_tecnica:
        parsed.equipe_tecnica = equipe_tecnica
    if relatorio_contabil_referencia:
        parsed.relatorio_contabil_referencia = relatorio_contabil_referencia
