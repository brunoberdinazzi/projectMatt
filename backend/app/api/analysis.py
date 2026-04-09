from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..models import (
    AnalysisContextResponse,
    AnalysisListItem,
    AnalysisReviewResponse,
    AuthUserResponse,
    ChecklistParseResult,
    FinancialAliasCatalogResponse,
    FinancialAliasDeleteRequest,
    FinancialAliasItem,
    FinancialAliasUpsertRequest,
    FinancialEntryTraceItem,
    FinancialWarehouseBackfillResponse,
    FinancialWarehouseSyncResponse,
    GenerationTrace,
    PipelineRunResponse,
    PromptResponse,
    StoredAnalysisResponse,
)
from ..runtime import (
    analysis_store,
    analysis_workflow_service,
    financial_warehouse_store,
    prompt_builder,
    require_authenticated_session,
    require_trusted_origin,
    require_authenticated_user,
    resolve_workbook_uploads,
    store_uploads,
)
from ..services.analysis_workflow_service import AnalysisMetadataInput, ParseWorkbookRequest
from ..services.auth_service import AuthenticatedSession


router = APIRouter()


def _require_financial_warehouse():
    if financial_warehouse_store is None:
        raise HTTPException(status_code=503, detail="O warehouse financeiro não está disponível neste ambiente.")
    return financial_warehouse_store


def _build_parse_request(
    source_name: Optional[str],
    source_names: Optional[list[str]],
    parser_profile: str,
    allowed_groups: Optional[str],
    allowed_status: Optional[str],
    checklist_sheet_name: Optional[str],
    metadata_row: Optional[int],
) -> ParseWorkbookRequest:
    return ParseWorkbookRequest(
        source_name=source_name,
        source_names=source_names or [],
        parser_profile=parser_profile,
        allowed_groups=allowed_groups,
        allowed_status=allowed_status,
        checklist_sheet_name=checklist_sheet_name,
        metadata_row=metadata_row,
    )


def _build_metadata_input(
    orgao: Optional[str] = None,
    tipo_orgao: Optional[str] = None,
    layout_profile: Optional[str] = None,
    periodo_analise: Optional[str] = None,
    numero_relatorio: Optional[str] = None,
    promotoria: Optional[str] = None,
    requester_area: Optional[str] = None,
    referencia: Optional[str] = None,
    solicitacao: Optional[str] = None,
    cidade_emissao: Optional[str] = None,
    data_emissao: Optional[str] = None,
    periodo_coleta: Optional[str] = None,
    equipe_tecnica: Optional[str] = None,
    relatorio_contabil_referencia: Optional[str] = None,
) -> AnalysisMetadataInput:
    return AnalysisMetadataInput(
        orgao=orgao,
        tipo_orgao=tipo_orgao,
        layout_profile=layout_profile,
        periodo_analise=periodo_analise,
        numero_relatorio=numero_relatorio,
        promotoria=promotoria,
        requester_area=requester_area,
        referencia=referencia,
        solicitacao=solicitacao,
        cidade_emissao=cidade_emissao,
        data_emissao=data_emissao,
        periodo_coleta=periodo_coleta,
        equipe_tecnica=equipe_tecnica,
        relatorio_contabil_referencia=relatorio_contabil_referencia,
    )


@router.get("/analyses", response_model=list[AnalysisListItem])
def list_analyses(
    limit: int = 8,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> list[AnalysisListItem]:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Use limit entre 1 e 50.")
    return analysis_store.list_recent_analyses(limit=limit, owner_user_id=current_user.id)


@router.post("/analysis/intake", response_model=StoredAnalysisResponse, dependencies=[Depends(require_trusted_origin)])
async def analysis_intake(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    parser_profile: str = Form(default="auto"),
    allowed_groups: Optional[str] = Form(default=None),
    allowed_status: Optional[str] = Form(default=None),
    checklist_sheet_name: Optional[str] = Form(default=None),
    metadata_row: Optional[int] = Form(default=None),
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
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> StoredAnalysisResponse:
    uploads = resolve_workbook_uploads(file, files)
    temp_paths = await store_uploads(uploads)
    source_names = [upload.filename or temp_path.name for upload, temp_path in zip(uploads, temp_paths)]
    source_label = source_names[0] if len(source_names) == 1 else f"{source_names[0]} + {len(source_names) - 1} arquivo(s)"
    try:
        parsed = analysis_workflow_service.parse_and_apply_metadata(
            workbook_path=temp_paths[0],
            parse_request=_build_parse_request(
                source_name=source_label,
                source_names=source_names,
                parser_profile=parser_profile,
                allowed_groups=allowed_groups,
                allowed_status=allowed_status,
                checklist_sheet_name=checklist_sheet_name,
                metadata_row=metadata_row,
            ),
            metadata=_build_metadata_input(
                orgao=orgao,
                tipo_orgao=tipo_orgao,
                layout_profile=layout_profile,
                periodo_analise=periodo_analise,
                numero_relatorio=numero_relatorio,
                promotoria=promotoria,
                requester_area=requester_area,
                referencia=referencia,
                solicitacao=solicitacao,
                cidade_emissao=cidade_emissao,
                data_emissao=data_emissao,
                periodo_coleta=periodo_coleta,
                equipe_tecnica=equipe_tecnica,
                relatorio_contabil_referencia=relatorio_contabil_referencia,
            ),
            owner_user_id=current_session.user.id,
            workbook_paths=temp_paths,
        )
        return analysis_workflow_service.create_intake(
            parsed=parsed,
            source_filename=source_label,
            owner_user_id=current_session.user.id,
            session_public_id=current_session.session_id,
        )
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


@router.get("/analysis/{analysis_id}", response_model=StoredAnalysisResponse)
def get_analysis(
    analysis_id: int,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> StoredAnalysisResponse:
    parsed = analysis_workflow_service.get_analysis_or_404(analysis_id, owner_user_id=current_user.id)
    return StoredAnalysisResponse(analysis_id=analysis_id, parsed=parsed)


@router.get("/analysis/{analysis_id}/review", response_model=AnalysisReviewResponse)
def get_analysis_review(
    analysis_id: int,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> AnalysisReviewResponse:
    parsed = analysis_workflow_service.get_analysis_or_404(analysis_id, owner_user_id=current_user.id)
    return analysis_workflow_service.build_review_response(analysis_id, parsed)


@router.post(
    "/analysis/{analysis_id}/warehouse/sync",
    response_model=FinancialWarehouseSyncResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def sync_analysis_financial_warehouse(
    analysis_id: int,
    force: bool = True,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FinancialWarehouseSyncResponse:
    return analysis_workflow_service.sync_financial_warehouse_snapshot(
        analysis_id=analysis_id,
        owner_user_id=current_user.id,
        force=force,
    )


@router.post(
    "/analyses/warehouse/backfill",
    response_model=FinancialWarehouseBackfillResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def backfill_financial_warehouse(
    limit: int = 200,
    force: bool = False,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FinancialWarehouseBackfillResponse:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Use limit entre 1 e 1000.")
    return analysis_workflow_service.backfill_financial_warehouse_snapshots(
        owner_user_id=current_user.id,
        limit=limit,
        force=force,
    )


@router.get("/analysis/{analysis_id}/financial-entries", response_model=list[FinancialEntryTraceItem])
def get_analysis_financial_entries(
    analysis_id: int,
    limit: int = 80,
    client_name: Optional[str] = None,
    contract_label: Optional[str] = None,
    period_label: Optional[str] = None,
    entry_type: Optional[str] = None,
    source_kind: Optional[str] = None,
    reconciliation_status: Optional[str] = None,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> list[FinancialEntryTraceItem]:
    if limit < 1 or limit > 300:
        raise HTTPException(status_code=400, detail="Use limit entre 1 e 300.")
    return analysis_workflow_service.list_financial_entries(
        analysis_id=analysis_id,
        owner_user_id=current_user.id,
        limit=limit,
        client_name=client_name,
        contract_label=contract_label,
        period_label=period_label,
        entry_type=entry_type,
        source_kind=source_kind,
        reconciliation_status=reconciliation_status,
    )


@router.get("/financial-aliases", response_model=FinancialAliasCatalogResponse)
def list_financial_aliases(
    limit: int = 80,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FinancialAliasCatalogResponse:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="Use limit entre 1 e 200.")
    warehouse = _require_financial_warehouse()
    return FinancialAliasCatalogResponse(
        clients=warehouse.list_canonical_aliases(
            owner_user_id=current_user.id,
            kind="client",
            limit=limit,
        ),
        contracts=warehouse.list_canonical_aliases(
            owner_user_id=current_user.id,
            kind="contract",
            limit=limit,
        ),
    )


@router.post("/financial-aliases", response_model=FinancialAliasItem, dependencies=[Depends(require_trusted_origin)])
def create_financial_alias(
    payload: FinancialAliasUpsertRequest,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FinancialAliasItem:
    warehouse = _require_financial_warehouse()
    try:
        return warehouse.add_canonical_alias(
            owner_user_id=current_user.id,
            kind=payload.kind,
            entity_id=payload.entity_id,
            alias=payload.alias,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/financial-aliases", response_model=FinancialAliasItem, dependencies=[Depends(require_trusted_origin)])
def delete_financial_alias(
    payload: FinancialAliasDeleteRequest,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FinancialAliasItem:
    warehouse = _require_financial_warehouse()
    try:
        return warehouse.remove_canonical_alias(
            owner_user_id=current_user.id,
            kind=payload.kind,
            entity_id=payload.entity_id,
            alias=payload.alias,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/analysis/review", response_model=AnalysisReviewResponse, dependencies=[Depends(require_trusted_origin)])
async def review_analysis(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    parser_profile: str = Form(default="auto"),
    allowed_groups: Optional[str] = Form(default=None),
    allowed_status: Optional[str] = Form(default=None),
    checklist_sheet_name: Optional[str] = Form(default=None),
    metadata_row: Optional[int] = Form(default=None),
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
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> AnalysisReviewResponse:
    uploads = resolve_workbook_uploads(file, files)
    temp_paths = await store_uploads(uploads)
    source_names = [upload.filename or temp_path.name for upload, temp_path in zip(uploads, temp_paths)]
    source_label = source_names[0] if len(source_names) == 1 else f"{source_names[0]} + {len(source_names) - 1} arquivo(s)"
    try:
        parsed = analysis_workflow_service.parse_and_apply_metadata(
            workbook_path=temp_paths[0],
            parse_request=_build_parse_request(
                source_name=source_label,
                source_names=source_names,
                parser_profile=parser_profile,
                allowed_groups=allowed_groups,
                allowed_status=allowed_status,
                checklist_sheet_name=checklist_sheet_name,
                metadata_row=metadata_row,
            ),
            metadata=_build_metadata_input(
                orgao=orgao,
                tipo_orgao=tipo_orgao,
                layout_profile=layout_profile,
                periodo_analise=periodo_analise,
                numero_relatorio=numero_relatorio,
                promotoria=promotoria,
                requester_area=requester_area,
                referencia=referencia,
                solicitacao=solicitacao,
                cidade_emissao=cidade_emissao,
                data_emissao=data_emissao,
                periodo_coleta=periodo_coleta,
                equipe_tecnica=equipe_tecnica,
                relatorio_contabil_referencia=relatorio_contabil_referencia,
            ),
            owner_user_id=current_session.user.id,
            workbook_paths=temp_paths,
        )
        return analysis_workflow_service.create_review(
            parsed,
            source_filename=source_label,
            owner_user_id=current_session.user.id,
            session_public_id=current_session.session_id,
        )
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


@router.post("/analysis/{analysis_id}/scrape", response_model=StoredAnalysisResponse, dependencies=[Depends(require_trusted_origin)])
def scrape_analysis(
    analysis_id: int,
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> StoredAnalysisResponse:
    parsed = analysis_workflow_service.get_analysis_or_404(analysis_id, owner_user_id=current_session.user.id)
    return analysis_workflow_service.refresh_scrape(
        analysis_id,
        parsed,
        session_public_id=current_session.session_id,
    )


@router.get("/analysis/{analysis_id}/context", response_model=AnalysisContextResponse)
def get_analysis_context(
    analysis_id: int,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> AnalysisContextResponse:
    parsed = analysis_workflow_service.get_analysis_or_404(analysis_id, owner_user_id=current_user.id)
    return analysis_workflow_service.build_context_response(analysis_id, parsed)


@router.get("/analysis/{analysis_id}/generations", response_model=list[GenerationTrace])
def get_analysis_generations(
    analysis_id: int,
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> list[GenerationTrace]:
    return analysis_workflow_service.list_generations(analysis_id, owner_user_id=current_user.id)


@router.post("/checklist/upload", response_model=ChecklistParseResult, dependencies=[Depends(require_trusted_origin)])
async def upload_checklist(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    parser_profile: str = Form(default="auto"),
    allowed_groups: Optional[str] = Form(default=None),
    allowed_status: Optional[str] = Form(default=None),
    checklist_sheet_name: Optional[str] = Form(default=None),
    metadata_row: Optional[int] = Form(default=None),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> ChecklistParseResult:
    uploads = resolve_workbook_uploads(file, files)
    temp_paths = await store_uploads(uploads)
    source_names = [upload.filename or temp_path.name for upload, temp_path in zip(uploads, temp_paths)]
    source_label = source_names[0] if len(source_names) == 1 else f"{source_names[0]} + {len(source_names) - 1} arquivo(s)"
    try:
        return analysis_workflow_service.parse_and_apply_metadata(
            workbook_path=temp_paths[0],
            parse_request=_build_parse_request(
                source_name=source_label,
                source_names=source_names,
                parser_profile=parser_profile,
                allowed_groups=allowed_groups,
                allowed_status=allowed_status,
                checklist_sheet_name=checklist_sheet_name,
                metadata_row=metadata_row,
            ),
            metadata=_build_metadata_input(
                orgao=orgao,
                tipo_orgao=tipo_orgao,
                periodo_analise=periodo_analise,
            ),
            owner_user_id=current_user.id,
            workbook_paths=temp_paths,
        )
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


@router.post("/prompt/build", response_model=PromptResponse, dependencies=[Depends(require_trusted_origin)])
def build_prompt(
    payload: ChecklistParseResult,
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> PromptResponse:
    prompt = prompt_builder.build(payload)
    return PromptResponse(prompt=prompt)


@router.post("/pipeline/run", response_model=PipelineRunResponse, dependencies=[Depends(require_trusted_origin)])
async def run_pipeline(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    parser_profile: str = Form(default="auto"),
    allowed_groups: Optional[str] = Form(default=None),
    allowed_status: Optional[str] = Form(default=None),
    checklist_sheet_name: Optional[str] = Form(default=None),
    metadata_row: Optional[int] = Form(default=None),
    orgao: Optional[str] = Form(default=None),
    tipo_orgao: Optional[str] = Form(default=None),
    periodo_analise: Optional[str] = Form(default=None),
    current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> PipelineRunResponse:
    uploads = resolve_workbook_uploads(file, files)
    temp_paths = await store_uploads(uploads)
    source_names = [upload.filename or temp_path.name for upload, temp_path in zip(uploads, temp_paths)]
    source_label = source_names[0] if len(source_names) == 1 else f"{source_names[0]} + {len(source_names) - 1} arquivo(s)"
    try:
        parsed = analysis_workflow_service.parse_and_apply_metadata(
            workbook_path=temp_paths[0],
            parse_request=_build_parse_request(
                source_name=source_label,
                source_names=source_names,
                parser_profile=parser_profile,
                allowed_groups=allowed_groups,
                allowed_status=allowed_status,
                checklist_sheet_name=checklist_sheet_name,
                metadata_row=metadata_row,
            ),
            metadata=_build_metadata_input(
                orgao=orgao,
                tipo_orgao=tipo_orgao,
                periodo_analise=periodo_analise,
            ),
            owner_user_id=current_user.id,
            workbook_paths=temp_paths,
        )
        prompt = prompt_builder.build(parsed)
        return PipelineRunResponse(parsed=parsed, prompt=prompt)
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)
