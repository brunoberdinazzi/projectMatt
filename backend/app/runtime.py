from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request, UploadFile

from .models import AuthUserResponse
from .services.analysis_context_builder import AnalysisContextBuilder
from .services.analysis_report_service import AnalysisReportService
from .services.analysis_scrape_service import AnalysisScrapeService
from .services.analysis_store import AnalysisStore
from .services.analysis_workflow_service import AnalysisWorkflowService
from .services.auth_service import AuthService, AuthenticatedSession
from .services.auth_store import AuthStore
from .services.app_database import (
    is_local_postgres_database_url,
    is_postgres_database_url,
    postgres_url_uses_secure_transport,
)
from .services.financial_report_content_builder import FinancialReportContentBuilder
from .services.financial_warehouse_store import FinancialWarehouseStore
from .services.link_scraper import LinkScraper
from .services.ollama_report_content_builder import OllamaReportContentBuilder
from .services.openai_report_content_builder import OpenAIReportContentBuilder
from .services.prompt_builder import PromptBuilder
from .services.rate_limit_service import RateLimitService
from .services.report_builder import ReportBuilder
from .services.report_content_builder import ReportContentBuilder
from .services.technical_report_composer import TechnicalReportComposer


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_STATIC_DIR = FRONTEND_DIST_DIR / "static"
LOGGER = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_WORKBOOK_UPLOAD_BYTES = int(os.getenv("DRAUX_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_TEMPLATE_UPLOAD_BYTES = int(os.getenv("DRAUX_MAX_TEMPLATE_BYTES", str(10 * 1024 * 1024)))

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
rate_limit_service = RateLimitService()
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


@dataclass(frozen=True)
class SecurityPreflightIssue:
    level: str
    message: str


def require_authenticated_user(request: Request) -> AuthUserResponse:
    return auth_service.get_authenticated_user(request)


def require_authenticated_session(request: Request) -> AuthenticatedSession:
    return auth_service.get_authenticated_session(request)


def require_trusted_origin(request: Request) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return

    candidate_origin = _extract_request_origin(request)
    if not candidate_origin:
        raise HTTPException(status_code=403, detail="Origem da requisicao nao permitida.")

    if candidate_origin not in _trusted_origins_for_request(request):
        raise HTTPException(status_code=403, detail="Origem da requisicao nao permitida.")


async def store_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xlsm", ".pdf"}:
        raise HTTPException(status_code=400, detail="Envie um arquivo suportado: .xlsx, .xlsm ou .pdf.")

    try:
        path = await _store_limited_upload(
            file=file,
            suffix=suffix,
            max_bytes=MAX_WORKBOOK_UPLOAD_BYTES,
        )
        _validate_saved_upload(path, suffix)
        return path
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
        path = await _store_limited_upload(
            file=file,
            suffix=suffix,
            max_bytes=MAX_TEMPLATE_UPLOAD_BYTES,
        )
        _validate_saved_upload(path, suffix)
        return path
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Falha ao salvar o template temporario.") from exc


def safe_temp_prefix(filename: Optional[str]) -> str:
    stem = Path(filename or "upload").stem
    cleaned = "".join(char if char.isalnum() else "_" for char in stem).strip("_")
    cleaned = cleaned[:40] or "upload"
    return f"{cleaned}_"


async def _store_limited_upload(file: UploadFile, suffix: str, max_bytes: int) -> Path:
    total_bytes = 0
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            prefix=safe_temp_prefix(file.filename),
            suffix=suffix,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"O arquivo excede o limite permitido de {max_bytes // (1024 * 1024)} MB.",
                    )
                temp_file.write(chunk)
        return temp_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _validate_saved_upload(path: Path, suffix: str) -> None:
    if suffix == ".pdf":
        _validate_pdf_file(path)
        return
    if suffix in {".xlsx", ".xlsm"}:
        _validate_zip_payload(
            path,
            required_members={"[Content_Types].xml", "xl/workbook.xml"},
            detail="A planilha enviada nao parece um workbook Excel valido.",
        )
        return
    if suffix == ".docx":
        _validate_zip_payload(
            path,
            required_members={"[Content_Types].xml", "word/document.xml"},
            detail="O template enviado nao parece um arquivo DOCX valido.",
        )


def _validate_pdf_file(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(5)
    if header != b"%PDF-":
        raise HTTPException(status_code=400, detail="O arquivo enviado nao parece um PDF valido.")


def _validate_zip_payload(path: Path, required_members: set[str], detail: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            members = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=detail) from exc

    if not required_members.issubset(members):
        raise HTTPException(status_code=400, detail=detail)


def _extract_request_origin(request: Request) -> Optional[str]:
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        return origin.rstrip("/")

    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return None

    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}".rstrip("/")


def _trusted_origins_for_request(request: Request) -> set[str]:
    scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",", 1)[0].strip().lower()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc or "").split(",", 1)[0].strip().lower()
    trusted = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
    if host:
        trusted.add(f"{scheme}://{host}")

    configured = os.getenv("DRAUX_TRUSTED_ORIGINS", "")
    for origin in configured.split(","):
        normalized = origin.strip().rstrip("/")
        if normalized:
            trusted.add(normalized)
    return trusted


def run_security_preflight() -> None:
    issues = _collect_security_preflight_issues()
    for issue in issues:
        if issue.level == "error":
            LOGGER.error("Preflight de seguranca: %s", issue.message)
        else:
            LOGGER.warning("Preflight de seguranca: %s", issue.message)

    if _env_flag("DRAUX_STRICT_SECURITY_PREFLIGHT") and any(issue.level == "error" for issue in issues):
        raise RuntimeError("O preflight de seguranca encontrou configuracoes que exigem ajuste antes do startup.")


def _collect_security_preflight_issues() -> list[SecurityPreflightIssue]:
    issues: list[SecurityPreflightIssue] = []
    database_targets = [
        ("DATABASE_URL", analysis_store.database_url),
        ("AUTH_DATABASE_URL", auth_store.database_url),
        ("FINANCE_DATABASE_URL", financial_warehouse_store.database_url if financial_warehouse_store is not None else ""),
    ]
    seen_urls: set[str] = set()
    deployment_like = False

    for label, database_url in database_targets:
        normalized_url = (database_url or "").strip()
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        if not is_postgres_database_url(normalized_url):
            continue

        is_local_db = is_local_postgres_database_url(normalized_url)
        if not is_local_db:
            deployment_like = True
        if not postgres_url_uses_secure_transport(normalized_url):
            issues.append(
                SecurityPreflightIssue(
                    level="error",
                    message=(
                        f"{label} aponta para PostgreSQL sem TLS forte. "
                        "Use '?sslmode=require' (ou 'verify-full') no DATABASE_URL/FINANCE_DATABASE_URL."
                    ),
                )
            )

    configured_origins = _configured_trusted_origins()
    for origin in configured_origins:
        if _is_local_origin(origin):
            continue
        deployment_like = True
        if not origin.startswith("https://"):
            issues.append(
                SecurityPreflightIssue(
                    level="warning",
                    message=(
                        f"DRAUX_TRUSTED_ORIGINS inclui uma origem nao-HTTPS ({origin}). "
                        "Prefira HTTPS para evitar cookie/session leakage fora de localhost."
                    ),
                )
            )

    auth_cookie_secure = os.getenv("AUTH_COOKIE_SECURE", "").strip().lower()
    if deployment_like and auth_cookie_secure in {"0", "false", "no"}:
        issues.append(
            SecurityPreflightIssue(
                level="error",
                message="AUTH_COOKIE_SECURE esta desabilitado fora de localhost. Reative Secure cookies no deploy.",
            )
        )

    if deployment_like and not os.getenv("DRAUX_DATA_KEY", "").strip():
        issues.append(
            SecurityPreflightIssue(
                level="warning",
                message=(
                    "DRAUX_DATA_KEY nao esta definido. O app vai depender da chave local em backend/data/.draux_master_key; "
                    "para deploy e backup, prefira uma chave externa estavel."
                ),
            )
        )

    return issues


def _configured_trusted_origins() -> list[str]:
    configured = os.getenv("DRAUX_TRUSTED_ORIGINS", "")
    origins: list[str] = []
    for origin in configured.split(","):
        normalized = origin.strip().rstrip("/")
        if normalized:
            origins.append(normalized)
    return origins


def _is_local_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
