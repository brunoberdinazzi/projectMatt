from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Optional

from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..models import ChecklistParseResult, GeneratedReportPayload
from .analysis_store import AnalysisStore
from .financial_report_content_builder import FinancialReportContentBuilder
from .financial_warehouse_store import FinancialWarehouseStore
from .ollama_report_content_builder import OllamaReportContentBuilder
from .openai_report_content_builder import OpenAIReportContentBuilder
from .report_builder import ReportBuilder
from .report_content_builder import ReportContentBuilder
from .technical_report_composer import TechnicalReportComposer


@dataclass
class ReportGenerationRequest:
    output_format: str = "docx"
    generation_mode: str = "auto"
    local_model: Optional[str] = None
    template_path: Optional[Path] = None


class AnalysisReportService:
    def __init__(
        self,
        analysis_store: AnalysisStore,
        report_content_builder: ReportContentBuilder,
        financial_report_content_builder: FinancialReportContentBuilder,
        financial_warehouse_store: Optional[FinancialWarehouseStore],
        openai_report_content_builder: OpenAIReportContentBuilder,
        ollama_report_content_builder: OllamaReportContentBuilder,
        technical_report_composer: TechnicalReportComposer,
        report_builder: ReportBuilder,
    ) -> None:
        self.analysis_store = analysis_store
        self.report_content_builder = report_content_builder
        self.financial_report_content_builder = financial_report_content_builder
        self.financial_warehouse_store = financial_warehouse_store
        self.openai_report_content_builder = openai_report_content_builder
        self.ollama_report_content_builder = ollama_report_content_builder
        self.technical_report_composer = technical_report_composer
        self.report_builder = report_builder

    def validate_request(self, request: ReportGenerationRequest) -> None:
        if request.output_format not in {"docx", "pdf"}:
            raise HTTPException(status_code=400, detail="Formato de saida invalido. Use docx ou pdf.")
        if request.generation_mode not in {"auto", "ai", "local", "rules"}:
            raise HTTPException(status_code=400, detail="Modo de geracao invalido. Use auto, ai, local ou rules.")

    def generate_file_response(
        self,
        background_tasks: BackgroundTasks,
        parsed: ChecklistParseResult,
        analysis_id: int,
        request: ReportGenerationRequest,
        session_public_id: Optional[str] = None,
    ) -> FileResponse:
        self.validate_request(request)
        resolved_parsed = self._resolve_financial_payload(parsed, analysis_id)

        generation_started_at = perf_counter()
        dynamic_payload = self._build_generated_report(
            resolved_parsed,
            request.generation_mode,
            request.output_format,
            local_model=request.local_model,
        )
        generation_duration_ms = int(round((perf_counter() - generation_started_at) * 1000))
        report_payload = (
            self.financial_report_content_builder.decorate_report(dynamic_payload.report, resolved_parsed)
            if resolved_parsed.financial_analysis is not None
            else self.technical_report_composer.compose(resolved_parsed, dynamic_payload.report)
        )
        report_path = self.report_builder.build(
            report_payload,
            output_format=request.output_format,
            template_path=request.template_path,
        )
        background_tasks.add_task(report_path.unlink, True)
        self.analysis_store.update_analysis(
            analysis_id,
            resolved_parsed,
            generation_mode=request.generation_mode,
            output_format=request.output_format,
            session_public_id=session_public_id,
        )

        trace = dynamic_payload.trace.model_copy(
            update={
                "requested_mode": request.generation_mode,
                "output_format": request.output_format,
                "duration_ms": generation_duration_ms,
            }
        )
        generation_event_id = self.analysis_store.record_generation(
            analysis_id,
            trace,
            session_public_id=session_public_id,
        )

        filename = self._build_output_filename(resolved_parsed.orgao, request.output_format)
        media_type = (
            "application/pdf"
            if request.output_format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        headers = {
            "X-Analysis-ID": str(analysis_id),
            "X-Generation-Event-ID": str(generation_event_id),
            "X-Generation-Mode": trace.used_mode,
            "X-Generation-Provider": trace.provider,
            "X-Generation-Duration-Ms": str(trace.duration_ms or 0),
        }
        if trace.model_name:
            headers["X-Generation-Model"] = trace.model_name

        return FileResponse(
            report_path,
            media_type=media_type,
            filename=filename,
            headers=headers,
        )

    def _resolve_financial_payload(self, parsed: ChecklistParseResult, analysis_id: int) -> ChecklistParseResult:
        if self.financial_warehouse_store is None:
            return parsed

        try:
            canonical_analysis = self.financial_warehouse_store.load_financial_analysis(analysis_id)
            canonical_summary = self.financial_warehouse_store.summarize_analysis(analysis_id)
        except Exception:
            return parsed

        if canonical_analysis is None and canonical_summary is None:
            return parsed

        merged_analysis = self.financial_warehouse_store.merge_financial_analysis(
            parsed.financial_analysis,
            canonical_analysis,
        )
        if merged_analysis is None:
            return parsed.model_copy(
                update={
                    "database_summary": canonical_summary or parsed.database_summary,
                }
            )

        return parsed.model_copy(
            update={
                "financial_analysis": merged_analysis,
                "database_summary": canonical_summary or parsed.database_summary,
            }
        )

    def _build_generated_report(
        self,
        parsed: ChecklistParseResult,
        generation_mode: str,
        output_format: str,
        local_model: Optional[str] = None,
    ) -> GeneratedReportPayload:
        if parsed.financial_analysis is not None:
            if generation_mode == "rules":
                generated = self.financial_report_content_builder.build_with_trace(parsed)
                return generated.model_copy(
                    update={
                        "trace": generated.trace.model_copy(
                            update={"requested_mode": "rules", "output_format": output_format}
                        )
                    }
                )

            if generation_mode == "local":
                if not self.ollama_report_content_builder.is_configured(local_model):
                    raise HTTPException(
                        status_code=400,
                        detail="Modo local solicitado, mas o Ollama nao esta disponivel com o modelo configurado.",
                    )
                try:
                    generated = self.ollama_report_content_builder.build_with_trace(parsed, model_override=local_model)
                    return generated.model_copy(
                        update={
                            "trace": generated.trace.model_copy(
                                update={"requested_mode": "local", "output_format": output_format}
                            )
                        }
                    )
                except Exception as exc:
                    raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via Ollama: {exc}") from exc

            if generation_mode == "ai":
                if not self.openai_report_content_builder.is_configured():
                    raise HTTPException(
                        status_code=400,
                        detail="Modo IA solicitado, mas OPENAI_API_KEY nao esta configurada no servidor.",
                    )
                try:
                    generated = self.openai_report_content_builder.build_with_trace(parsed)
                    return generated.model_copy(
                        update={
                            "trace": generated.trace.model_copy(
                                update={"requested_mode": "ai", "output_format": output_format}
                            )
                        }
                    )
                except Exception as exc:
                    raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via IA: {exc}") from exc

            fallback_messages: list[str] = []
            if self.ollama_report_content_builder.is_configured(local_model):
                try:
                    generated = self.ollama_report_content_builder.build_with_trace(parsed, model_override=local_model)
                    return generated.model_copy(
                        update={
                            "trace": generated.trace.model_copy(
                                update={"requested_mode": "auto", "output_format": output_format}
                            )
                        }
                    )
                except Exception as exc:
                    fallback_messages.append(f"Ollama indisponivel: {exc}")

            if self.openai_report_content_builder.is_configured():
                try:
                    generated = self.openai_report_content_builder.build_with_trace(parsed)
                    fallback_reason = "; ".join(fallback_messages) if fallback_messages else None
                    return generated.model_copy(
                        update={
                            "trace": generated.trace.model_copy(
                                update={
                                    "requested_mode": "auto",
                                    "output_format": output_format,
                                    "fallback_reason": fallback_reason,
                                }
                            )
                        }
                    )
                except Exception as exc:
                    fallback_messages.append(f"OpenAI indisponivel: {exc}")

            generated = self.financial_report_content_builder.build_with_trace(parsed)
            return generated.model_copy(
                update={
                    "trace": generated.trace.model_copy(
                        update={
                            "requested_mode": "auto",
                            "output_format": output_format,
                            "fallback_reason": "; ".join(fallback_messages) if fallback_messages else None,
                        }
                    )
                }
            )

        if not parsed.itens_processados:
            fallback_payload = self.report_content_builder.build_with_trace(parsed)
            return fallback_payload.model_copy(
                update={
                    "trace": fallback_payload.trace.model_copy(
                        update={
                            "requested_mode": generation_mode,
                            "output_format": output_format,
                            "fallback_reason": "Nenhum item elegivel encontrado no recorte atual.",
                        }
                    )
                }
            )

        if generation_mode == "rules":
            generated = self.report_content_builder.build_with_trace(parsed)
            return generated.model_copy(
                update={
                    "trace": generated.trace.model_copy(
                        update={"requested_mode": "rules", "output_format": output_format}
                    )
                }
            )

        if generation_mode == "local":
            if not self.ollama_report_content_builder.is_configured(local_model):
                raise HTTPException(
                    status_code=400,
                    detail="Modo local solicitado, mas o Ollama nao esta disponivel com o modelo configurado.",
                )
            try:
                generated = self.ollama_report_content_builder.build_with_trace(parsed, model_override=local_model)
                return generated.model_copy(
                    update={
                        "trace": generated.trace.model_copy(
                            update={"requested_mode": "local", "output_format": output_format}
                        )
                    }
                )
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via Ollama: {exc}") from exc

        if generation_mode == "ai":
            if not self.openai_report_content_builder.is_configured():
                raise HTTPException(
                    status_code=400,
                    detail="Modo IA solicitado, mas OPENAI_API_KEY nao esta configurada no servidor.",
                )
            try:
                generated = self.openai_report_content_builder.build_with_trace(parsed)
                return generated.model_copy(
                    update={
                        "trace": generated.trace.model_copy(
                            update={"requested_mode": "ai", "output_format": output_format}
                        )
                    }
                )
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Falha ao gerar o relatorio via IA: {exc}") from exc

        fallback_messages: list[str] = []
        if self.ollama_report_content_builder.is_configured(local_model):
            try:
                generated = self.ollama_report_content_builder.build_with_trace(parsed, model_override=local_model)
                return generated.model_copy(
                    update={
                        "trace": generated.trace.model_copy(
                            update={"requested_mode": "auto", "output_format": output_format}
                        )
                    }
                )
            except Exception as exc:
                fallback_messages.append(f"Ollama indisponivel: {exc}")

        if self.openai_report_content_builder.is_configured():
            try:
                generated = self.openai_report_content_builder.build_with_trace(parsed)
                fallback_reason = "; ".join(fallback_messages) if fallback_messages else None
                return generated.model_copy(
                    update={
                        "trace": generated.trace.model_copy(
                            update={
                                "requested_mode": "auto",
                                "output_format": output_format,
                                "fallback_reason": fallback_reason,
                            }
                        )
                    }
                )
            except Exception as exc:
                fallback_messages.append(f"OpenAI indisponivel: {exc}")

        generated = self.report_content_builder.build_with_trace(parsed)
        return generated.model_copy(
            update={
                "trace": generated.trace.model_copy(
                    update={
                        "requested_mode": "auto",
                        "output_format": output_format,
                        "fallback_reason": "; ".join(fallback_messages) if fallback_messages else None,
                    }
                )
            }
        )

    @staticmethod
    def _build_output_filename(orgao: Optional[str], output_format: str) -> str:
        base_name = orgao or "relatorio-tecnico"
        slug = "".join(char.lower() if char.isalnum() else "-" for char in base_name).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        slug = slug or "relatorio-tecnico"
        return f"{slug}.{output_format}"
