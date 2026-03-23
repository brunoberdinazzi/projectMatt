from __future__ import annotations

import json
import os
import re
from time import perf_counter
from typing import Optional

import httpx

from ..models import (
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .financial_report_content_builder import FinancialReportContentBuilder
from .report_metadata import build_report_title
from .report_terms import SOURCE_ORDER, entity_display_name, source_section_title


class OllamaReportContentBuilder:
    FINANCIAL_SECTION_TITLES = (
        "VISAO EXECUTIVA",
        "DRE CONSOLIDADA",
        "RECEBIMENTOS POR CLIENTE",
        "RECEBIMENTOS POR CONTRATO",
        "RESULTADO POR PERIODO",
        "CUSTOS E DESPESAS RELEVANTES",
        "OBSERVACOES OPERACIONAIS",
    )
    PREFERRED_MODELS = (
        "deepseek-r1:8b",
        "deepseek-r1:7b",
        "qwen2.5:7b",
        "llama3.1:8b",
        "gemma3:12b",
        "qwen2.5:3b",
        "llama3.2:3b",
        "llama3.2:1b",
    )

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
            "options": self._build_generation_options(model_name),
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "15m"),
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/generate", json=body)
            response.raise_for_status()
            data = response.json()

        raw_text = data.get("response", "").strip()
        parsed = self._parse_json(self._strip_reasoning_trace(raw_text))

        sections = [ReportSection(**section) for section in parsed["secoes"]]
        if payload.financial_analysis is not None:
            sections = self._normalize_financial_sections(payload, sections)

        report = ReportBuildRequest(
            titulo_relatorio=build_report_title(payload),
            orgao=payload.orgao,
            tipo_orgao=payload.tipo_orgao,
            periodo_analise=payload.periodo_analise,
            secoes=sections,
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
        if payload.financial_analysis is not None:
            return self._build_financial_prompt(payload)

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
                "Nao exponha cadeia de raciocinio, planejamento intermediario, comentarios internos ou tags como <think>.",
                "Retorne apenas o objeto JSON final compativel com o schema recebido.",
                "",
                "Use estes titulos de secao exatamente como informados abaixo:",
                json.dumps(sections, ensure_ascii=False, indent=2),
                "",
                "Dados do caso:",
                json.dumps(context, ensure_ascii=False, indent=2),
            ]
        )

    def _build_financial_prompt(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None:
            raise RuntimeError("Analise financeira nao encontrada para montagem do prompt.")

        return "\n".join(
            [
                "Voce vai redigir um relatorio financeiro gerencial em portugues com base em DRE consolidada, leitura mensal e agrupamentos por cliente e contrato.",
                "Escreva em portugues formal, tecnica, objetiva e impessoal.",
                "Use exclusivamente os dados fornecidos. Nao invente fatos.",
                "Mostre explicitamente o rendimento acumulado de cada cliente no recorte, a distribuicao por periodo quando houver dados e o rendimento total acumulado de cada contrato relevante.",
                "Quando houver diferenca entre recebido, previsto e pendente, deixe isso claro.",
                "Nao presuma regime contabil, enquadramento fiscal ou classificacoes externas nao informadas.",
                "Nao repita o enunciado, nao explique o formato e nao use markdown.",
                "Nao exponha cadeia de raciocinio, planejamento intermediario, comentarios internos ou tags como <think>.",
                "Use apenas JSON valido: chaves e textos com aspas duplas, virgulas entre todos os campos e nenhum comentario.",
                "Retorne apenas o objeto JSON final compativel com o schema recebido.",
                "",
                "Use exatamente estas secoes, todas com fonte=nao_informada:",
                "- VISAO EXECUTIVA",
                "- DRE CONSOLIDADA",
                "- RECEBIMENTOS POR CLIENTE",
                "- RECEBIMENTOS POR CONTRATO",
                "- RESULTADO POR PERIODO",
                "- CUSTOS E DESPESAS RELEVANTES",
                "- OBSERVACOES OPERACIONAIS",
                "",
                "Modelo valido de resposta:",
                json.dumps(
                    {
                        "titulo_relatorio": "Demonstrativo Financeiro e DRE",
                        "secoes": [
                            {"fonte": "nao_informada", "titulo": "VISAO EXECUTIVA", "texto": "Resumo executivo."},
                            {"fonte": "nao_informada", "titulo": "DRE CONSOLIDADA", "texto": "Leitura da DRE."},
                            {"fonte": "nao_informada", "titulo": "RECEBIMENTOS POR CLIENTE", "texto": "Clientes e valores."},
                            {"fonte": "nao_informada", "titulo": "RECEBIMENTOS POR CONTRATO", "texto": "Contratos e valores."},
                            {"fonte": "nao_informada", "titulo": "RESULTADO POR PERIODO", "texto": "Fechamentos mensais."},
                            {"fonte": "nao_informada", "titulo": "CUSTOS E DESPESAS RELEVANTES", "texto": "Custos principais."},
                            {"fonte": "nao_informada", "titulo": "OBSERVACOES OPERACIONAIS", "texto": "Alertas e observacoes."},
                        ],
                    },
                    ensure_ascii=False,
                ),
                "",
                f"Entidade analisada: {entity_display_name(payload.orgao, payload.tipo_orgao)}",
                f"Periodo consolidado: {payload.periodo_analise or 'Nao informado'}",
                f"Arquivos fonte: {', '.join(analysis.source_workbook_names) or 'Nao informados'}",
                f"Periodos identificados: {len(analysis.months)}",
                f"Lancamentos estruturados: {analysis.entry_count}",
                "",
                *(
                    ["Resumo persistido no banco:", payload.database_summary, ""]
                    if payload.database_summary
                    else []
                ),
                "Linhas consolidadas da DRE:",
                *self._build_compact_dre_lines(analysis),
                "",
                "Recebimentos por cliente:",
                *self._build_compact_client_lines(analysis),
                "",
                "Recebimentos por cliente e periodo:",
                *self._build_compact_client_period_lines(analysis),
                "",
                "Recebimentos por contrato:",
                *self._build_compact_contract_lines(analysis),
                "",
                "Resultado por periodo:",
                *self._build_compact_month_lines(analysis),
                "",
                "Observacoes do parser e do contexto:",
                *self._build_compact_note_lines(payload),
            ]
        )

    def _parse_json(self, raw_text: str) -> dict:
        cleaned = self._extract_json_text(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = json.loads(self._repair_common_json_issues(cleaned))
        normalized = self._normalize_payload(data)
        if "secoes" not in normalized or not isinstance(normalized["secoes"], list):
            raise RuntimeError("Resposta do Ollama nao retornou 'secoes' no formato esperado.")
        return normalized

    def _normalize_financial_sections(
        self,
        payload: ChecklistParseResult,
        sections: list[ReportSection],
    ) -> list[ReportSection]:
        fallback_sections = {
            section.titulo: section
            for section in FinancialReportContentBuilder().build(payload).secoes
        }
        normalized: dict[str, ReportSection] = {}
        for section in sections:
            target_title = self._map_financial_section_title(section.titulo)
            if target_title is None:
                continue
            existing = normalized.get(target_title)
            if existing is None:
                normalized[target_title] = section.model_copy(
                    update={"fonte": "nao_informada", "titulo": target_title}
                )
                continue
            normalized[target_title] = existing.model_copy(
                update={
                    "texto": "\n\n".join(
                        chunk for chunk in (existing.texto, section.texto) if chunk.strip()
                    )
                }
            )

        resolved_sections: list[ReportSection] = []
        for title in self.FINANCIAL_SECTION_TITLES:
            section = normalized.get(title) or fallback_sections.get(title)
            if section is None:
                continue
            resolved_sections.append(
                section if section.titulo == title else section.model_copy(update={"titulo": title, "fonte": "nao_informada"})
            )
        return resolved_sections

    def _map_financial_section_title(self, title: str) -> Optional[str]:
        normalized = (title or "").strip().lower()
        if not normalized:
            return None
        if any(token in normalized for token in ("visao", "visão", "executiv", "sumario", "sumário", "resumo")):
            return "VISAO EXECUTIVA"
        if "cliente" in normalized:
            return "RECEBIMENTOS POR CLIENTE"
        if "contrato" in normalized:
            return "RECEBIMENTOS POR CONTRATO"
        if any(token in normalized for token in ("mensal", "periodo", "período", "performance")):
            return "RESULTADO POR PERIODO"
        if any(token in normalized for token in ("custo", "despesa")):
            return "CUSTOS E DESPESAS RELEVANTES"
        if any(token in normalized for token in ("observ", "alerta", "importante")):
            return "OBSERVACOES OPERACIONAIS"
        if any(token in normalized for token in ("dre", "demonstracao", "demonstração", "resultado")):
            return "DRE CONSOLIDADA"
        return None

    def _strip_reasoning_trace(self, raw_text: str) -> str:
        cleaned = raw_text.strip()

        # DeepSeek-R1 and similar reasoning models may emit an explicit thought block
        # before the JSON payload. We strip it to keep schema parsing deterministic.
        cleaned = re.sub(r"(?is)<think>.*?</think>", "", cleaned)

        lowered = cleaned.lower()
        if lowered.startswith("<think"):
            closing_tag = lowered.rfind("</think>")
            if closing_tag != -1:
                cleaned = cleaned[closing_tag + len("</think>") :].strip()

        return cleaned

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

    def _repair_common_json_issues(self, raw_text: str) -> str:
        cleaned = raw_text.strip()
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        cleaned = re.sub(r"(?m)^\s*//.*$", "", cleaned)
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

    def recommended_model(self) -> Optional[str]:
        models = self._list_models()
        return self._pick_preferred_model(models)

    def diagnostics(self) -> dict:
        started_at = perf_counter()
        with httpx.Client(timeout=5.0) as client:
            tags_response = client.get(f"{self.base_url}/api/tags")
            tags_response.raise_for_status()
            tags_payload = tags_response.json()

            ps_response = client.get(f"{self.base_url}/api/ps")
            ps_response.raise_for_status()
            ps_payload = ps_response.json()

        latency_ms = int(round((perf_counter() - started_at) * 1000))
        installed_models = [model.get("name") for model in tags_payload.get("models", []) if model.get("name")]
        loaded_models = [
            {
                "name": model.get("name"),
                "size_vram": model.get("size_vram"),
                "context_length": model.get("context_length"),
                "expires_at": model.get("expires_at"),
            }
            for model in ps_payload.get("models", [])
            if model.get("name")
        ]
        recommended_model = self._pick_preferred_model(installed_models)
        active_model = loaded_models[0]["name"] if loaded_models else None

        if active_model and recommended_model and active_model == recommended_model:
            message = f"{recommended_model} esta carregado no Ollama e pronto para o fluxo local."
        elif active_model:
            message = f"Ollama online com {active_model} carregado no momento."
        elif recommended_model:
            message = f"{recommended_model} esta instalado e sera priorizado na selecao automatica."
        elif installed_models:
            message = "Ollama online com modelos locais instalados."
        else:
            message = "Ollama respondeu, mas nenhum modelo local foi encontrado."

        return {
            "available": True,
            "latency_ms": latency_ms,
            "base_url": self.base_url,
            "recommended_model": recommended_model,
            "active_model": active_model,
            "installed_model_count": len(installed_models),
            "loaded_model_count": len(loaded_models),
            "loaded_models": loaded_models,
            "message": message,
        }

    def _build_generation_options(self, model_name: str) -> dict:
        options = {
            "temperature": 0.2,
            "num_predict": 1400,
        }

        normalized = (model_name or "").strip().lower()
        if normalized.startswith("deepseek-r1"):
            # Reasoning models are more stable here with lower randomness.
            options["temperature"] = 0
            options["top_p"] = 0.9
            options["repeat_penalty"] = 1.05
            options["num_ctx"] = 4096
            options["num_predict"] = 1200
        elif normalized.startswith("llama3.2:1b"):
            options["num_ctx"] = 3072
            options["num_predict"] = 900
        else:
            options["num_ctx"] = 4096

        return options

    def _build_compact_dre_lines(self, analysis) -> list[str]:
        lines: list[str] = []
        for line in analysis.dre_lines[:10]:
            suffix = ""
            if line.share_of_gross_revenue is not None:
                suffix = f" ({self._format_percent(line.share_of_gross_revenue)} da receita bruta)"
            lines.append(f"- {line.label}: {self._format_currency(line.amount)}{suffix}")
        return lines or ["- Nenhuma linha de DRE consolidada."]

    def _build_compact_client_lines(self, analysis) -> list[str]:
        lines: list[str] = []
        for client in analysis.client_rollups[:12]:
            lines.append(
                f"- {client.client_name}: rendimento {self._format_currency(client.total_received_amount)} | "
                f"previsto {self._format_currency(client.total_expected_amount)} | "
                f"pendente {self._format_currency(client.total_pending_amount)} | "
                f"contratos {client.contract_count}"
            )
        return lines or ["- Nenhum agrupamento por cliente."]

    def _build_compact_client_period_lines(self, analysis) -> list[str]:
        lines: list[str] = []
        for entry in analysis.client_period_rollups[:28]:
            lines.append(
                f"- {entry.client_name} | {entry.period_label}: rendimento {self._format_currency(entry.total_received_amount)} | "
                f"previsto {self._format_currency(entry.total_expected_amount)} | "
                f"pendente {self._format_currency(entry.total_pending_amount)} | "
                f"contratos {entry.contract_count}"
            )
        return lines or ["- Nenhum agrupamento cliente x periodo."]

    def _build_compact_contract_lines(self, analysis) -> list[str]:
        lines: list[str] = []
        for contract in analysis.contract_rollups[:16]:
            lines.append(
                f"- {contract.contract_label}: recebido {self._format_currency(contract.total_received_amount)} | "
                f"previsto {self._format_currency(contract.total_expected_amount)} | "
                f"pendente {self._format_currency(contract.total_pending_amount)} | "
                f"cliente {contract.client_name or '-'} | "
                f"status {contract.latest_status or '-'}"
            )
        return lines or ["- Nenhum agrupamento por contrato."]

    def _build_compact_month_lines(self, analysis) -> list[str]:
        lines: list[str] = []
        for month in analysis.months[:12]:
            lines.append(
                f"- {month.period_label}: receita base {self._format_currency(month.receivables_total)} | "
                f"custos e despesas {self._format_currency(month.global_expenses_total)} | "
                f"resultado {self._format_currency(month.net_result)} | "
                f"pendencias {month.pending_entry_count}"
            )
        return lines or ["- Nenhum fechamento mensal estruturado."]

    def _build_compact_note_lines(self, payload: ChecklistParseResult) -> list[str]:
        notes: list[str] = []
        analysis = payload.financial_analysis
        if analysis is not None:
            notes.extend(f"- {note}" for note in analysis.summary_notes[:8])
        notes.extend(f"- {warning}" for warning in payload.warnings[:8])
        notes.extend(f"- {layer.title}: {layer.summary}" for layer in payload.context_layers[:5])
        deduped: list[str] = []
        seen: set[str] = set()
        for note in notes:
            if note in seen:
                continue
            seen.add(note)
            deduped.append(note)
        return deduped or ["- Nenhuma observacao adicional."]

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value * 100:.1f}%".replace(".", ",")

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

        preferred_model = self._pick_preferred_model(models)
        if preferred_model:
            return preferred_model

        return models[0]

    def _pick_preferred_model(self, models: list[str]) -> Optional[str]:
        for preferred in self.PREFERRED_MODELS:
            if preferred in models:
                return preferred
        return None

    def _list_models(self) -> list[str]:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
        return [model.get("name") for model in payload.get("models", []) if model.get("name")]
