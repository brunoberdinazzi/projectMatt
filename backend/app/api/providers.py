from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..models import (
    AuthUserResponse,
    OllamaLoadedModelResponse,
    OllamaModelsResponse,
    OllamaStatusResponse,
    ParserDetectionResponse,
    ParserProfileDefinition,
)
from ..runtime import ollama_report_content_builder, require_authenticated_user, store_upload
from ..services.bank_statement_parser import looks_like_bank_statement_pdf
from ..services.excel_parser import (
    get_parser_profile_definition,
    list_parser_profiles,
    resolve_parser_profile_for_workbook,
)


router = APIRouter()


@router.get("/parser/profiles", response_model=list[ParserProfileDefinition])
def parser_profiles(
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> list[ParserProfileDefinition]:
    return list_parser_profiles()


@router.post("/parser/detect", response_model=ParserDetectionResponse)
async def parser_detect(
    file: UploadFile = File(...),
    requested_profile: str = Form(default="auto"),
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> ParserDetectionResponse:
    temp_path = await store_upload(file)
    try:
        requested_definition = get_parser_profile_definition(requested_profile or "auto")
        try:
            if temp_path.suffix.lower() == ".pdf":
                if requested_definition.key not in {"auto", "financial_dre"}:
                    raise HTTPException(status_code=400, detail="PDFs sao suportados apenas no fluxo Financeiro / DRE.")
                if not looks_like_bank_statement_pdf(temp_path):
                    raise HTTPException(
                        status_code=400,
                        detail="O PDF enviado nao parece um extrato bancario compativel com a leitura financeira.",
                    )
                resolved_profile = "financial_dre"
            else:
                resolved_profile = resolve_parser_profile_for_workbook(temp_path, requested_profile)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Nao foi possivel inspecionar o arquivo enviado.",
            ) from exc

        resolved_definition = get_parser_profile_definition(resolved_profile)
        if requested_definition.key == "auto":
            message = (
                "A estrutura do arquivo indica esse perfil para a revisao completa."
                if temp_path.suffix.lower() != ".pdf"
                else "O PDF foi reconhecido como extrato bancario para consolidacao financeira."
            )
        else:
            message = "Perfil manual mantido para a revisao completa."

        return ParserDetectionResponse(
            requested_profile=requested_definition.key,
            resolved_profile=resolved_definition.key,
            resolved_label=resolved_definition.label,
            resolved_description=resolved_definition.description,
            message=message,
        )
    finally:
        temp_path.unlink(missing_ok=True)


@router.get("/providers/ollama/models", response_model=OllamaModelsResponse)
def ollama_models(
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> OllamaModelsResponse:
    try:
        models = ollama_report_content_builder.list_models()
        return OllamaModelsResponse(
            models=models,
            recommended_model=ollama_report_content_builder.recommended_model(),
        )
    except Exception:
        return OllamaModelsResponse(models=[], recommended_model=None)


@router.get("/providers/ollama/status", response_model=OllamaStatusResponse)
def ollama_status(
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> OllamaStatusResponse:
    try:
        diagnostics = ollama_report_content_builder.diagnostics()
        return OllamaStatusResponse(
            available=diagnostics["available"],
            latency_ms=diagnostics["latency_ms"],
            base_url=diagnostics["base_url"],
            recommended_model=diagnostics["recommended_model"],
            active_model=diagnostics["active_model"],
            installed_model_count=diagnostics["installed_model_count"],
            loaded_model_count=diagnostics["loaded_model_count"],
            loaded_models=[
                OllamaLoadedModelResponse(**item)
                for item in diagnostics["loaded_models"]
            ],
            message=diagnostics["message"],
        )
    except Exception as exc:
        return OllamaStatusResponse(
            available=False,
            base_url=ollama_report_content_builder.base_url,
            message=f"Nao foi possivel consultar o Ollama: {exc}",
        )
