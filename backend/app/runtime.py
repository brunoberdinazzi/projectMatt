from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, UploadFile

from .models import AuthUserResponse
from .services.analysis_context_builder import AnalysisContextBuilder
from .services.analysis_report_service import AnalysisReportService
from .services.analysis_scrape_service import AnalysisScrapeService
from .services.analysis_store import AnalysisStore
from .services.analysis_workflow_service import AnalysisWorkflowService
from .services.auth_service import AuthService, AuthenticatedSession
from .services.auth_store import AuthStore
from .services.financial_report_content_builder import FinancialReportContentBuilder
from .services.financial_warehouse_store import FinancialWarehouseStore
from .services.link_scraper import LinkScraper
from .services.ollama_report_content_builder import OllamaReportContentBuilder
from .services.openai_report_content_builder import OpenAIReportContentBuilder
from .services.prompt_builder import PromptBuilder
from .services.report_builder import ReportBuilder
from .services.report_content_builder import ReportContentBuilder
from .services.technical_report_composer import TechnicalReportComposer


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_STATIC_DIR = FRONTEND_DIST_DIR / "static"
LOGGER = logging.getLogger(__name__)

prompt_builder = PromptBuilder()
report_content_builder = ReportContentBuilder()
openai_report_content_builder = OpenAIReportContentBuilder()
ollama_report_content_builder = OllamaReportContentBuilder()
report_builder = ReportBuilder()
technical_report_composer = TechnicalReportComposer()
link_scraper = LinkScraper()
analysis_scrape_service = AnalysisScrapeService(link_scraper)
analysis_store = AnalysisStore()
auth_store = AuthStore()
auth_service = AuthService(auth_store=auth_store)
analysis_context_builder = AnalysisContextBuilder()
try:
    financial_warehouse_store: Optional[FinancialWarehouseStore] = FinancialWarehouseStore()
except Exception:
    LOGGER.exception("Falha ao inicializar o warehouse financeiro canônico.")
    financial_warehouse_store = None
financial_report_content_builder = FinancialReportContentBuilder(
    financial_warehouse_store=financial_warehouse_store
)
analysis_workflow_service = AnalysisWorkflowService(
    analysis_store=analysis_store,
    analysis_context_builder=analysis_context_builder,
    analysis_scrape_service=analysis_scrape_service,
    prompt_builder=prompt_builder,
    financial_warehouse_store=financial_warehouse_store,
)
analysis_report_service = AnalysisReportService(
    analysis_store=analysis_store,
    report_content_builder=report_content_builder,
    financial_report_content_builder=financial_report_content_builder,
    financial_warehouse_store=financial_warehouse_store,
    openai_report_content_builder=openai_report_content_builder,
    ollama_report_content_builder=ollama_report_content_builder,
    technical_report_composer=technical_report_composer,
    report_builder=report_builder,
)


def require_authenticated_user(request: Request) -> AuthUserResponse:
    return auth_service.get_authenticated_user(request)


def require_authenticated_session(request: Request) -> AuthenticatedSession:
    return auth_service.get_authenticated_session(request)


async def store_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".pdf"}:
        raise HTTPException(status_code=400, detail="Envie um arquivo suportado: .xlsx, .xlsm ou .pdf.")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=safe_temp_prefix(file.filename),
            suffix=suffix,
        ) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            return Path(temp_file.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Falha ao salvar o upload temporario.") from exc


def resolve_workbook_uploads(
    file: Optional[UploadFile] = None,
    files: Optional[list[UploadFile]] = None,
) -> list[UploadFile]:
    uploads: list[UploadFile] = []
    for candidate in [file, *(files or [])]:
        if candidate is None:
            continue
        if not (candidate.filename or "").strip():
            continue
        uploads.append(candidate)

    if not uploads:
        raise HTTPException(status_code=400, detail="Envie pelo menos um arquivo suportado: .xlsx, .xlsm ou .pdf.")
    return uploads


async def store_uploads(files: list[UploadFile]) -> list[Path]:
    stored_paths: list[Path] = []
    try:
        for file in files:
            stored_paths.append(await store_upload(file))
        return stored_paths
    except Exception:
        for path in stored_paths:
            path.unlink(missing_ok=True)
        raise


async def store_template_upload(file: Optional[UploadFile]) -> Optional[Path]:
    if file is None or not file.filename:
        return None

    suffix = Path(file.filename).suffix.lower()
    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="O template precisa ser um arquivo .docx.")

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=safe_temp_prefix(file.filename),
            suffix=suffix,
        ) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            return Path(temp_file.name)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Falha ao salvar o template temporario.") from exc


def safe_temp_prefix(filename: Optional[str]) -> str:
    stem = Path(filename or "upload").stem
    cleaned = "".join(char if char.isalnum() else "_" for char in stem).strip("_")
    cleaned = cleaned[:40] or "upload"
    return f"{cleaned}_"
