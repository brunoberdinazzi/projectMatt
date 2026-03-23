from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from ..models import AuthUserResponse, ReportBuildRequest
from ..runtime import (
    analysis_report_service,
    analysis_workflow_service,
    report_builder,
    require_authenticated_session,
    require_authenticated_user,
    resolve_workbook_uploads,
    store_template_upload,
    store_uploads,
)
from ..services.analysis_report_service import ReportGenerationRequest
from ..services.analysis_workflow_service import AnalysisMetadataInput, ParseWorkbookRequest
from ..services.auth_service import AuthenticatedSession


router = APIRouter()


@router.post("/analysis/{analysis_id}/report")
async def generate_report_from_analysis(
    analysis_id: int,
    background_tasks: BackgroundTasks,
    template_file: Optional[UploadFile] = File(default=None),
    output_format: str = Form(default="docx"),
    generation_mode: str = Form(default="auto"),
    local_model: Optional[str] = Form(default=None),
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> FileResponse:
    parsed = analysis_workflow_service.get_analysis_or_404(analysis_id, owner_user_id=current_session.user.id)

    template_path = await store_template_upload(template_file)
    try:
        return analysis_report_service.generate_file_response(
            background_tasks=background_tasks,
            parsed=parsed,
            analysis_id=analysis_id,
            request=ReportGenerationRequest(
                output_format=output_format,
                generation_mode=generation_mode,
                local_model=local_model,
                template_path=template_path,
            ),
            session_public_id=current_session.session_id,
        )
    finally:
        if template_path:
            template_path.unlink(missing_ok=True)


@router.post("/report/build")
def build_report(
    payload: ReportBuildRequest,
    background_tasks: BackgroundTasks,
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> FileResponse:
    report_path = report_builder.build(payload)
    background_tasks.add_task(report_path.unlink, True)
    filename = report_path.name
    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.post("/report/generate")
async def generate_report(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(default=None),
    files: Optional[list[UploadFile]] = File(default=None),
    template_file: Optional[UploadFile] = File(default=None),
    output_format: str = Form(default="docx"),
    generation_mode: str = Form(default="auto"),
    local_model: Optional[str] = Form(default=None),
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
) -> FileResponse:
    generation_request = ReportGenerationRequest(
        output_format=output_format,
        generation_mode=generation_mode,
        local_model=local_model,
    )
    analysis_report_service.validate_request(generation_request)

    uploads = resolve_workbook_uploads(file, files)
    temp_paths = await store_uploads(uploads)
    source_names = [upload.filename or temp_path.name for upload, temp_path in zip(uploads, temp_paths)]
    source_label = source_names[0] if len(source_names) == 1 else f"{source_names[0]} + {len(source_names) - 1} arquivo(s)"
    template_path = await store_template_upload(template_file)
    try:
        generation_request = ReportGenerationRequest(
            output_format=output_format,
            generation_mode=generation_mode,
            local_model=local_model,
            template_path=template_path,
        )
        parsed = analysis_workflow_service.parse_and_apply_metadata(
            workbook_path=temp_paths[0],
            parse_request=ParseWorkbookRequest(
                source_name=source_label,
                source_names=source_names,
                parser_profile=parser_profile,
                allowed_groups=allowed_groups,
                allowed_status=allowed_status,
                checklist_sheet_name=checklist_sheet_name,
                metadata_row=metadata_row,
            ),
            metadata=AnalysisMetadataInput(
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
        analysis_id = analysis_workflow_service.prepare_analysis_for_generation(
            parsed=parsed,
            source_filename=source_label,
            generation_mode=generation_mode,
            output_format=output_format,
            owner_user_id=current_session.user.id,
            session_public_id=current_session.session_id,
        )
        return analysis_report_service.generate_file_response(
            background_tasks=background_tasks,
            parsed=parsed,
            analysis_id=analysis_id,
            request=generation_request,
            session_public_id=current_session.session_id,
        )
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)
        if template_path:
            template_path.unlink(missing_ok=True)
