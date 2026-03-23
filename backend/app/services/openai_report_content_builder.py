from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI

from ..models import (
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .report_metadata import build_report_title
from .report_terms import SOURCE_ORDER, entity_display_name, source_section_title


class OpenAIReportContentBuilder:
    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def build(self, payload: ChecklistParseResult) -> ReportBuildRequest:
        return self.build_with_trace(payload).report

    def build_with_trace(self, payload: ChecklistParseResult) -> GeneratedReportPayload:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no servidor.")

        client = OpenAI(api_key=api_key)
        prompt = self._build_prompt(payload)
        response = client.responses.create(
            model=self.model,
            input=prompt,
        )
        raw_text = getattr(response, "output_text", "") or ""
        data = self._parse_json(raw_text)

        report = ReportBuildRequest(
            titulo_relatorio=build_report_title(payload),
            orgao=payload.orgao,
            tipo_orgao=payload.tipo_orgao,
            periodo_analise=payload.periodo_analise,
            secoes=[ReportSection(**section) for section in data["secoes"]],
        )
        return GeneratedReportPayload(
            report=report,
            trace=GenerationTrace(
                requested_mode="ai",
                used_mode="ai",
                provider="openai",
                model_name=self.model,
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

        instructions = {
            "tarefa": "Gerar as secoes variaveis de um relatorio tecnico analitico a partir de checklist estruturado e evidencias complementares.",
            "regras": [
                "Use exclusivamente as informacoes fornecidas.",
                "Nao invente fatos e nao mencione anexos ou figuras nao informados.",
                "Escreva em portugues formal, tecnica, objetiva e impessoal.",
                "Adote tom tecnico profissional, claro e nao promocional.",
                "Nao presuma setor, esfera institucional ou marco regulatorio alem do que estiver explicitamente descrito nos dados.",
                "Considere o contexto recuperado do banco e do scraper apenas como apoio para contextualizacao; os achados do checklist continuam sendo a fonte principal das conclusoes.",
                "Use as camadas complementares do workbook como evidencias estruturadas de enquadramento, sem trata-las como prova conclusiva isolada.",
                "Nas secoes de resultados, utilize formulacoes como 'Constatou-se', 'Verificou-se', 'Cabe destacar' e 'Por fim', quando couber.",
                "Nas secoes de recomendacoes, primeiro contextualize brevemente a irregularidade e depois apresente a providencia com formulacao impessoal e objetiva.",
                "Na secao de quesito, responda de forma sintese se ha necessidade de recomendacoes tecnicas e consolide os pontos por fonte.",
                "Na conclusao, produza texto curto, objetivo e coerente com o contexto informado, sem repetir integralmente os resultados.",
                "Se nao houver achados para uma fonte, informe isso de forma curta.",
                "Retorne somente JSON valido, sem markdown e sem texto fora do JSON.",
            ],
            "json_esperado": {
                "titulo_relatorio": "string",
                "secoes": [
                    {
                        "fonte": "site_orgao | portal_transparencia | esic | nao_informada",
                        "titulo": "string",
                        "texto": "string",
                    }
                ],
            },
            "secoes_obrigatorias": [
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
            ],
            "contexto": {
                "analysis_id": payload.analysis_id,
                "entidade_analisada": entity_name,
                "orgao": payload.orgao,
                "tipo_orgao": payload.tipo_orgao,
                "periodo_analise": payload.periodo_analise,
                "grupos_permitidos": payload.grupos_permitidos,
                "parser_options": payload.parser_options.model_dump(mode="json"),
                "database_summary": payload.database_summary,
                "context_layers": context_layers,
                "scraped_pages": scraped_pages,
                "warnings": payload.warnings,
                "achados": achados,
            },
        }
        return json.dumps(instructions, ensure_ascii=False, indent=2)

    def _build_financial_prompt(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None:
            raise RuntimeError("Analise financeira nao encontrada para montagem do prompt.")

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
        instructions = {
            "tarefa": "Gerar um relatorio financeiro gerencial em portugues com base na DRE consolidada, nos fechamentos mensais e nos agrupamentos por cliente e contrato.",
            "regras": [
                "Use exclusivamente os dados fornecidos.",
                "Nao invente contratos, clientes, recebimentos, custos, despesas ou conclusoes nao amparadas no material.",
                "Escreva em portugues formal, tecnica, objetiva e impessoal.",
                "Mostre explicitamente o rendimento acumulado de cada cliente no recorte, a distribuicao por periodo quando houver dados e o rendimento total acumulado de cada contrato relevante.",
                "Se houver pendencias, diferencie claramente valor recebido, valor previsto e saldo pendente.",
                "Nao presuma regime contabil, enquadramento fiscal ou classificacao externa nao informada.",
                "Retorne somente JSON valido, sem markdown e sem texto fora do JSON.",
            ],
            "json_esperado": {
                "titulo_relatorio": "string",
                "secoes": [
                    {
                        "fonte": "nao_informada",
                        "titulo": "string",
                        "texto": "string",
                    }
                ],
            },
            "secoes_obrigatorias": [
                {"fonte": "nao_informada", "titulo": "VISAO EXECUTIVA"},
                {"fonte": "nao_informada", "titulo": "DRE CONSOLIDADA"},
                {"fonte": "nao_informada", "titulo": "RECEBIMENTOS POR CLIENTE"},
                {"fonte": "nao_informada", "titulo": "RECEBIMENTOS POR CONTRATO"},
                {"fonte": "nao_informada", "titulo": "RESULTADO POR PERIODO"},
                {"fonte": "nao_informada", "titulo": "CUSTOS E DESPESAS RELEVANTES"},
                {"fonte": "nao_informada", "titulo": "OBSERVACOES OPERACIONAIS"},
            ],
            "contexto": {
                "analysis_id": payload.analysis_id,
                "entidade_analisada": entity_display_name(payload.orgao, payload.tipo_orgao),
                "periodo_analise": payload.periodo_analise,
                "database_summary": payload.database_summary,
                "arquivos_fonte": analysis.source_workbook_names,
                "dre_lines": [line.model_dump(mode="json") for line in analysis.dre_lines],
                "months": [month.model_dump(mode="json") for month in analysis.months],
                "client_rollups": [client.model_dump(mode="json") for client in analysis.client_rollups[:20]],
                "client_period_rollups": [
                    client_period.model_dump(mode="json") for client_period in analysis.client_period_rollups[:60]
                ],
                "contract_rollups": [contract.model_dump(mode="json") for contract in analysis.contract_rollups[:30]],
                "summary_notes": analysis.summary_notes,
                "warnings": payload.warnings,
                "context_layers": context_layers,
            },
        }
        return json.dumps(instructions, ensure_ascii=False, indent=2)

    def _parse_json(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        data = json.loads(cleaned)
        if "secoes" not in data or not isinstance(data["secoes"], list):
            raise RuntimeError("Resposta da IA nao retornou 'secoes' no formato esperado.")
        return data
