from __future__ import annotations

import json
import os
import re
from typing import Optional

import httpx

from ..models import (
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .report_metadata import build_report_title
from .report_terms import SOURCE_ORDER, entity_display_name, source_section_title


class OllamaReportContentBuilder:
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))

    def is_configured(self, model_override: Optional[str] = None) -> bool:
        try:
            self._resolve_model(model_override)
        except Exception:
            return False
        return True

    def build(
        self,
        payload: ChecklistParseResult,
        model_override: Optional[str] = None,
    ) -> ReportBuildRequest:
        return self.build_with_trace(payload, model_override=model_override).report

    def build_with_trace(
        self,
        payload: ChecklistParseResult,
        model_override: Optional[str] = None,
    ) -> GeneratedReportPayload:
        model_name = self._resolve_model(model_override)
        prompt = self._build_prompt(payload)
        body = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": self._response_schema(),
            "options": {
                "temperature": 0.2,
            },
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/generate", json=body)
            response.raise_for_status()
            data = response.json()

        raw_text = data.get("response", "").strip()
        parsed = self._parse_json(raw_text)

        report = ReportBuildRequest(
            titulo_relatorio=build_report_title(payload),
            orgao=payload.orgao,
            tipo_orgao=payload.tipo_orgao,
            periodo_analise=payload.periodo_analise,
            secoes=[ReportSection(**section) for section in parsed["secoes"]],
        )
        return GeneratedReportPayload(
            report=report,
            trace=GenerationTrace(
                requested_mode="local",
                used_mode="local",
                provider="ollama",
                model_name=model_name,
                output_format="docx",
                prompt_snapshot=prompt,
                raw_response=raw_text,
                fallback_reason=None,
            ),
        )

    def _build_prompt(self, payload: ChecklistParseResult) -> str:
        entity_name = entity_display_name(payload.orgao, payload.tipo_orgao)
        achados = []
        for item in payload.itens_processados:
            achados.append(
                {
                    "grupo": item.grupo,
                    "item_codigo": item.item_codigo,
                    "ano_referencia": item.ano_referencia,
                    "status": item.status,
                    "status_2024": item.status_2024,
                    "status_2025": item.status_2025,
                    "fonte": item.fonte,
                    "fonte_texto": item.fonte_texto,
                    "descricao_item": item.descricao_item,
                    "observacao": item.observacao,
                    "fundamentacao": item.fundamentacao,
                    "detalhes": [
                        {"descricao": detail.descricao, "status": detail.status}
                        for detail in item.detalhes
                    ],
                }
            )

        scraped_pages = []
        for page in payload.scraped_pages:
            scraped_pages.append(
                {
                    "fonte": page.fonte,
                    "requested_url": page.requested_url,
                    "final_url": page.final_url,
                    "page_title": page.page_title,
                    "summary": page.summary,
                    "warnings": page.warnings,
                    "links_relevantes": [
                        {
                            "label": link.label,
                            "url": link.url,
                            "category": link.category,
                            "destination_type": link.destination_type,
                            "section": link.section,
                            "context": link.context,
                        }
                        for link in page.links[:12]
                    ],
                }
            )

        context_layers = [
            {
                "layer_type": layer.layer_type,
                "sheet_name": layer.sheet_name,
                "title": layer.title,
                "summary": layer.summary,
                "details": layer.details,
                "references": layer.references,
            }
            for layer in payload.context_layers
        ]

        sections = [
            *[
                {"fonte": source_key, "titulo": source_section_title("Resultados Obtidos", source_key)}
                for source_key in SOURCE_ORDER
            ],
            *[
                {"fonte": source_key, "titulo": source_section_title("Recomendacoes", source_key)}
                for source_key in SOURCE_ORDER
            ],
            {"fonte": "nao_informada", "titulo": "Quesito - Sintese das Recomendacoes"},
            {"fonte": "nao_informada", "titulo": "Conclusao"},
        ]

        context = {
            "analysis_id": payload.analysis_id,
            "entidade_analisada": entity_name,
            "orgao": payload.orgao,
            "tipo_orgao": payload.tipo_orgao,
            "periodo_analise": payload.periodo_analise,
            "parser_options": payload.parser_options.model_dump(mode="json"),
            "database_summary": payload.database_summary,
            "context_layers": context_layers,
            "scraped_pages": scraped_pages,
            "warnings": payload.warnings,
            "achados": achados,
        }

        return "\n".join(
            [
                "Voce vai redigir secoes variaveis de um relatorio tecnico analitico com base em checklist estruturado e evidencias complementares.",
                "Escreva em portugues formal, tecnica, objetiva e impessoal.",
                "Adote tom tecnico profissional, claro e nao promocional.",
                "Use exclusivamente os dados fornecidos. Nao invente fatos.",
                "Nao presuma setor, esfera institucional ou marco regulatorio alem do que estiver explicitamente descrito nos dados.",
                "Considere o contexto recuperado do banco e do scraper apenas para contextualizacao complementar.",
                "Use as camadas complementares do workbook como evidencias estruturadas de enquadramento, sem trata-las como prova conclusiva isolada.",
                "Nas secoes de resultados, prefira formulacoes como 'Constatou-se', 'Verificou-se', 'Cabe destacar' e 'Por fim', quando cabiveis.",
                "Nas secoes de recomendacoes, contextualize a irregularidade e apresente a providencia de forma objetiva.",
                "Na secao de quesito, sintetize a necessidade de recomendacoes tecnicas por fonte.",
                "Na conclusao, produza texto curto, objetivo e coerente com o contexto informado, sem repeticao integral dos resultados.",
                "Nao repita o enunciado, nao explique o formato e nao use markdown.",
                "Retorne apenas o objeto JSON final compativel com o schema recebido.",
                "",
                "Use estes titulos de secao exatamente como informados abaixo:",
                json.dumps(sections, ensure_ascii=False, indent=2),
                "",
                "Dados do caso:",
                json.dumps(context, ensure_ascii=False, indent=2),
            ]
        )

    def _parse_json(self, raw_text: str) -> dict:
        cleaned = self._extract_json_text(raw_text)
        data = json.loads(cleaned)
        normalized = self._normalize_payload(data)
        if "secoes" not in normalized or not isinstance(normalized["secoes"], list):
            raise RuntimeError("Resposta do Ollama nao retornou 'secoes' no formato esperado.")
        return normalized

    def _extract_json_text(self, raw_text: str) -> str:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return match.group(0)

        return cleaned

    def _normalize_payload(self, data: dict) -> dict:
        payload = data
        if "secoes" not in payload:
            for key in ("resultado", "result", "report", "relatorio", "output"):
                nested = payload.get(key)
                if isinstance(nested, dict) and "secoes" in nested:
                    payload = nested
                    break

        if "secoes" not in payload:
            nested = payload.get("json_esperado")
            if isinstance(nested, dict) and "secoes" in nested:
                payload = nested

        sections = payload.get("secoes")
        if not isinstance(sections, list):
            return payload

        normalized_sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            normalized_sections.append(
                {
                    "fonte": self._normalize_source(section.get("fonte")),
                    "titulo": str(section.get("titulo") or "").strip() or "Secao sem titulo",
                    "texto": str(section.get("texto") or "").strip() or "Sem conteudo gerado.",
                }
            )

        return {
            "titulo_relatorio": str(payload.get("titulo_relatorio") or "Relatorio Tecnico de Analise").strip(),
            "secoes": normalized_sections,
        }

    def _normalize_source(self, value: Optional[str]) -> str:
        normalized = (value or "").strip().lower()
        if normalized in {
            "site_orgao",
            "site oficial do orgao",
            "site oficial do órgão",
            "site do orgao",
            "canal principal",
        }:
            return "site_orgao"
        if normalized in {
            "portal_transparencia",
            "portal da transparencia",
            "portal da transparência",
            "canal complementar",
        }:
            return "portal_transparencia"
        if normalized in {"esic", "e-sic", "sistema e-sic", "canal de atendimento"}:
            return "esic"
        return "nao_informada"

    def _response_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "titulo_relatorio": {"type": "string"},
                "secoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fonte": {"type": "string"},
                            "titulo": {"type": "string"},
                            "texto": {"type": "string"},
                        },
                        "required": ["fonte", "titulo", "texto"],
                    },
                },
            },
            "required": ["titulo_relatorio", "secoes"],
        }

    def list_models(self) -> list[str]:
        return self._list_models()

    def _resolve_model(self, model_override: Optional[str] = None) -> str:
        models = self._list_models()
        if not models:
            raise RuntimeError("Nenhum modelo instalado no Ollama.")

        selected_model = model_override or self.model

        if selected_model:
            if selected_model in models:
                return selected_model
            raise RuntimeError(
                "Modelo configurado no Ollama nao encontrado: "
                f"{selected_model}. Modelos disponiveis: {', '.join(models)}"
            )

        for preferred in (
            "qwen2.5:7b",
            "llama3.1:8b",
            "gemma3:12b",
            "qwen2.5:3b",
            "llama3.2:3b",
            "llama3.2:1b",
        ):
            if preferred in models:
                return preferred

        return models[0]

    def _list_models(self) -> list[str]:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
        return [model.get("name") for model in payload.get("models", []) if model.get("name")]
