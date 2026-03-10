from __future__ import annotations

from collections import defaultdict

from ..models import (
    ChecklistItem,
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .report_metadata import build_report_title


SOURCE_LABELS = {
    "site_orgao": "Site Oficial do Orgao",
    "portal_transparencia": "Portal da Transparencia",
    "esic": "Sistema e-SIC",
    "nao_informada": "Fonte nao identificada",
}

SOURCE_ORDER = ("site_orgao", "portal_transparencia", "esic", "nao_informada")

RECOMMENDATION_BY_ITEM = {
    "1.3": (
        "Disponibilizar ferramenta de pesquisa de conteudo que permita localizar, de forma simples, "
        "as informacoes publicadas no sitio oficial e no Portal da Transparencia."
    ),
    "1.4": (
        "Assegurar a plena funcionalidade de geracao de relatorios em diversos formatos eletronicos, "
        "garantindo que todos os arquivos exportados apresentem as informacoes de forma completa e legivel."
    ),
    "1.5": (
        "Remover limitadores indevidos de acesso automatizado, de modo a preservar a consulta publica "
        "e a reutilizacao automatizada das informacoes disponibilizadas."
    ),
    "1.6": (
        "Disponibilizar recursos adequados de acessibilidade, assegurando o acesso ao conteudo por "
        "pessoas com deficiencia, em conformidade com a legislacao aplicavel."
    ),
    "5.1": (
        "Implantar e regulamentar formalmente o Servico de Informacao ao Cidadao, com indicacao clara "
        "do instrumento normativo correspondente."
    ),
    "5.2": (
        "Indicar, em local de facil acesso, os canais e instrucoes necessarios para a comunicacao "
        "eletronica entre o cidadao e a administracao."
    ),
    "5.3": (
        "Publicar integralmente as informacoes institucionais da administracao, incluindo estrutura "
        "organizacional, competencias, enderecos, telefones e horarios de atendimento."
    ),
    "5.4": (
        "Assegurar funcionalidade de acompanhamento posterior dos pedidos de informacao, permitindo "
        "ao usuario consultar o andamento das solicitacoes realizadas."
    ),
    "5.5": (
        "Disponibilizar relacao atualizada de perguntas e respostas frequentes, em linguagem clara "
        "e com acesso facilitado ao usuario."
    ),
    "5.6": (
        "Divulgar estatisticas das solicitacoes recebidas, atendidas e indeferidas, mantendo os "
        "indicadores atualizados e acessiveis ao publico."
    ),
    "5.7": (
        "Disponibilizar a relacao anual de informacoes desclassificadas quanto ao sigilo. Caso nao "
        "existam registros, informar expressamente sua inexistencia."
    ),
    "5.8": (
        "Disponibilizar a relacao anual de documentos classificados quanto ao sigilo por grau de "
        "sigilo. Caso nao existam registros, informar expressamente sua inexistencia."
    ),
}

ITEM_SUBJECT_BY_CODE = {
    "1.3": "existencia de ferramenta de pesquisa de conteudo",
    "1.4": "geracao de relatorios em diversos formatos eletronicos",
    "1.5": "inexistencia de limitadores indevidos de acesso automatizado",
    "1.6": "acessibilidade do conteudo disponibilizado",
    "5.1": "implantacao e regulamentacao do Servico de Informacao ao Cidadao",
    "5.2": "indicacao de canais e instrucoes para comunicacao eletronica com o cidadao",
    "5.3": "divulgacao de informacoes institucionais",
    "5.4": "acompanhamento posterior das solicitacoes de informacao",
    "5.5": "divulgacao de perguntas e respostas frequentes",
    "5.6": "divulgacao de estatisticas das solicitacoes recebidas, atendidas e indeferidas",
    "5.7": "divulgacao da relacao anual de informacoes desclassificadas quanto ao sigilo",
    "5.8": "divulgacao da relacao anual de documentos classificados quanto ao sigilo por grau de sigilo",
}


class ReportContentBuilder:
    def build(self, payload: ChecklistParseResult) -> ReportBuildRequest:
        return self.build_with_trace(payload).report

    def build_with_trace(self, payload: ChecklistParseResult) -> GeneratedReportPayload:
        grouped = self._group_by_source(payload.itens_processados)
        sections: list[ReportSection] = []

        for source_key in SOURCE_ORDER:
            sections.append(
                ReportSection(
                    fonte=source_key,
                    titulo=f"Resultados Obtidos - {SOURCE_LABELS[source_key]}",
                    texto=self._build_results_text(source_key, grouped.get(source_key, [])),
                )
            )

        for source_key in SOURCE_ORDER:
            sections.append(
                ReportSection(
                    fonte=source_key,
                    titulo=f"Recomendacoes - {SOURCE_LABELS[source_key]}",
                    texto=self._build_recommendations_text(source_key, grouped.get(source_key, [])),
                )
            )

        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="Quesito - Sintese das Recomendacoes",
                texto=self._build_summary_text(grouped),
            )
        )
        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="Conclusao",
                texto=self._build_conclusion_text(payload),
            )
        )

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
                requested_mode="rules",
                used_mode="rules",
                provider="rules",
                model_name=None,
                output_format="docx",
                prompt_snapshot=None,
                raw_response=None,
                fallback_reason=None,
            ),
        )

    def _group_by_source(self, items: list[ChecklistItem]) -> dict[str, list[ChecklistItem]]:
        grouped: dict[str, list[ChecklistItem]] = defaultdict(list)
        for item in items:
            grouped[item.fonte].append(item)
        return grouped

    def _build_results_text(self, source_key: str, items: list[ChecklistItem]) -> str:
        if not items:
            return (
                f"Nao foram identificados, no ambito de {SOURCE_LABELS[source_key]}, apontamentos classificados como Nao "
                "ou Parcialmente no recorte automatizado dos grupos 1 e 5."
            )

        specialized_text = self._build_specialized_results_text(source_key, items)
        if specialized_text:
            return specialized_text

        paragraphs = [self._build_finding_paragraph(item) for item in items]
        return "\n\n".join(paragraphs)

    def _build_recommendations_text(self, source_key: str, items: list[ChecklistItem]) -> str:
        actionable_items = [item for item in items if item.status not in {"Sim", "Nao se aplica"}]
        if not actionable_items:
            return (
                f"Nao se identificaram recomendacoes tecnicas especificas para "
                f"{SOURCE_LABELS[source_key]} no recorte automatizado atual."
            )

        specialized_text = self._build_specialized_recommendations_text(source_key, actionable_items)
        if specialized_text:
            return specialized_text

        paragraphs = [self._build_recommendation_paragraph(item) for item in actionable_items]
        return "\n\n".join(paragraphs)

    def _build_summary_text(self, grouped: dict[str, list[ChecklistItem]]) -> str:
        all_items = [item for source_key in SOURCE_ORDER for item in grouped.get(source_key, [])]
        actionable_items = [item for item in all_items if item.status not in {"Sim", "Nao se aplica"}]
        if not actionable_items:
            return (
                "No recorte automatizado vigente, nao foram identificados apontamentos "
                "que demandem recomendacoes tecnicas corretivas."
            )

        source_summaries = []
        for source_key in SOURCE_ORDER:
            items = [item for item in grouped.get(source_key, []) if item.status not in {"Sim", "Nao se aplica"}]
            if not items:
                continue
            source_summaries.append(
                f"{SOURCE_LABELS[source_key]}: {len(items)} apontamento(s) relevante(s)"
            )

        return (
            "A partir da verificacao realizada nos ambientes eletronicos oficiais do ente, constatou-se "
            "a necessidade de adocao de medidas corretivas e de aprimoramento, sintetizadas nos "
            "seguintes eixos: "
            + "; ".join(source_summaries)
            + "."
        )

    def _build_conclusion_text(self, payload: ChecklistParseResult) -> str:
        if not payload.itens_processados:
            base_text = (
                "No recorte considerado por esta versao do sistema, nao foram identificados nos grupos 1 "
                "e 5 itens com classificacao Nao ou Parcialmente. Ainda assim, recomenda-se manter a "
                "verificacao manual do checklist completo para fins de controle institucional."
            )
            scoped_warnings = [
                warning
                for warning in payload.warnings
                if "fora do escopo automatizado atual" in warning or "grupos 1 e 5" in warning
            ]
            if scoped_warnings:
                return base_text + " " + " ".join(scoped_warnings)
            return base_text

        return (
            "O processamento automatizado da planilha permitiu consolidar os achados relevantes do "
            "checklist e organiza-los em linguagem tecnica compatível com a elaboracao do relatorio "
            "institucional. Recomenda-se, todavia, revisao final pela equipe responsavel antes da "
            "emissao formal do parecer."
        )

    def _build_finding_paragraph(self, item: ChecklistItem) -> str:
        description = self._subject_text(item)
        intro = (
            f"Quanto ao item {item.item_codigo}, relativo a {description}, verificou-se "
            f"classificacao {item.status} no exercicio de "
            f"{item.ano_referencia or 'referencia nao informada'}."
        )
        issue_text = self._build_issue_text(item)
        if issue_text:
            return f"{intro} {issue_text}".strip()
        return intro

    def _build_issue_text(self, item: ChecklistItem) -> str:
        parts: list[str] = []
        observation_text = _ensure_sentence(item.observacao) if item.observacao else ""
        detail_text = self._build_detail_text(item)
        if observation_text:
            parts.append(observation_text)
        if detail_text:
            parts.append(detail_text)
        return " ".join(parts).strip()

    def _build_detail_text(self, item: ChecklistItem) -> str:
        if not item.detalhes:
            return ""

        problem_details = [
            detail.descricao
            for detail in item.detalhes
            if detail.status.lower() not in {"sim"}
        ]
        if not problem_details:
            return ""

        joined = ", ".join(problem_details)
        return f"Nos subitens avaliados, observou-se insuficiencia especialmente quanto a: {joined}."

    def _build_recommendation_paragraph(self, item: ChecklistItem) -> str:
        description = self._subject_text(item)
        issue_text = self._build_issue_text(item)
        recommendation = _ensure_sentence(self._build_recommendation(item))
        base = (
            f"No que se refere ao item {item.item_codigo}, relacionado a {description}, "
        )
        if issue_text:
            base += issue_text + " "
        base += f"Recomenda-se: {recommendation}"
        return base.strip()

    def _build_specialized_results_text(self, source_key: str, items: list[ChecklistItem]) -> str:
        item_map = {item.item_codigo: item for item in items}
        item_codes = set(item_map)

        if source_key == "site_orgao" and item_codes == {"5.3"}:
            return self._build_site_results_text(item_map["5.3"])
        if source_key == "portal_transparencia":
            return self._build_portal_results_text(items)
        if source_key == "esic" and item_codes.issubset({"5.4", "5.5", "5.6", "5.7", "5.8"}):
            return self._build_esic_results_text(items)
        return ""

    def _build_specialized_recommendations_text(self, source_key: str, items: list[ChecklistItem]) -> str:
        item_map = {item.item_codigo: item for item in items}
        item_codes = set(item_map)

        if source_key == "site_orgao" and item_codes == {"5.3"}:
            return self._build_site_recommendations_text(item_map["5.3"])
        if source_key == "portal_transparencia":
            return self._build_portal_recommendations_text(items)
        if source_key == "esic" and item_codes.issubset({"5.4", "5.5", "5.6", "5.7", "5.8"}):
            return self._build_esic_recommendations_text(items)
        return ""

    def _build_site_results_text(self, item: ChecklistItem) -> str:
        paragraphs = [
            "No site oficial do ente, verificou-se divulgacao apenas parcial das informacoes institucionais exigidas pela legislacao aplicavel."
        ]
        if item.observacao:
            paragraphs.append(_ensure_sentence(item.observacao))

        missing_details = self._missing_detail_descriptions(item)
        if missing_details:
            paragraphs.append(
                "Cabe ressaltar que algumas das informacoes disponibilizadas nao se apresentam de forma completa, "
                f"especialmente quanto a {self._join_with_conjunction(missing_details)}."
            )
        return "\n\n".join(paragraphs)

    def _build_portal_results_text(self, items: list[ChecklistItem]) -> str:
        summarized_subjects = [self._subject_text(item) for item in items]
        paragraphs = [
            "No Portal da Transparencia, foram identificadas inconformidades relacionadas a "
            f"{self._join_with_conjunction(summarized_subjects)}."
        ]
        for item in items:
            issue_text = self._build_issue_text(item)
            if issue_text:
                paragraphs.append(issue_text)
            else:
                paragraphs.append(
                    f"No item {item.item_codigo}, registrou-se classificacao {item.status} "
                    f"no exercicio de {item.ano_referencia or 'referencia nao informada'}."
                )
        return "\n\n".join(paragraphs)

    def _build_esic_results_text(self, items: list[ChecklistItem]) -> str:
        issue_phrases = []
        paragraphs: list[str] = []
        for item in items:
            phrase = self._esic_issue_phrase(item)
            if phrase:
                issue_phrases.append(phrase)
            if item.observacao:
                paragraphs.append(_ensure_sentence(item.observacao))

        if issue_phrases:
            paragraphs.insert(
                0,
                "No sistema e-SIC, verificou-se a ausencia de disponibilizacao de "
                f"{self._join_with_conjunction(issue_phrases)}."
            )
        if not paragraphs:
            paragraphs.append(
                "No sistema e-SIC, foram identificadas ausencias de informacoes e funcionalidades "
                "relacionadas ao atendimento das exigencias legais aplicaveis."
            )
        return "\n\n".join(paragraphs)

    def _build_site_recommendations_text(self, item: ChecklistItem) -> str:
        paragraphs = []
        issue_text = self._build_issue_text(item)
        if issue_text:
            paragraphs.append(issue_text)
        paragraphs.append(
            "Recomenda-se: "
            + _ensure_sentence(self._build_recommendation(item))
        )
        return "\n\n".join(paragraphs)

    def _build_portal_recommendations_text(self, items: list[ChecklistItem]) -> str:
        paragraphs = [
            "No Portal da Transparencia, as recomendacoes abaixo visam corrigir os problemas "
            "identificados no recorte automatizado do checklist."
        ]
        paragraphs.extend(self._build_recommendation_paragraph(item) for item in items)
        return "\n\n".join(paragraphs)

    def _build_esic_recommendations_text(self, items: list[ChecklistItem]) -> str:
        intro_phrases = [
            self._esic_issue_phrase(item)
            for item in items
            if self._esic_issue_phrase(item)
        ]
        paragraphs = []
        if intro_phrases:
            paragraphs.append(
                "No sistema e-SIC, identificou-se necessidade de adequacao quanto a "
                f"{self._join_with_conjunction(intro_phrases)}."
            )
        for item in items:
            paragraphs.append(f"Recomenda-se: {_ensure_sentence(self._build_recommendation(item))}")
        return "\n\n".join(paragraphs)

    def _missing_detail_descriptions(self, item: ChecklistItem) -> list[str]:
        return [
            detail.descricao.lower()
            for detail in item.detalhes
            if detail.status.lower() in {"nao", "parcialmente", "parcial"}
        ]

    def _esic_issue_phrase(self, item: ChecklistItem) -> str:
        phrase_map = {
            "5.4": "mecanismos de acompanhamento posterior das solicitacoes de informacao",
            "5.5": "perguntas e respostas frequentes",
            "5.6": "estatisticas das solicitacoes recebidas, atendidas e indeferidas",
            "5.7": "relacao anual de informacoes desclassificadas quanto ao sigilo",
            "5.8": "relacao anual de documentos classificados quanto ao sigilo por grau de sigilo",
        }
        return phrase_map.get(item.item_codigo, self._subject_text(item))

    def _join_with_conjunction(self, values: list[str]) -> str:
        cleaned = [" ".join(value.split()) for value in values if value]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} e {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"

    def _build_recommendation(self, item: ChecklistItem) -> str:
        specific = RECOMMENDATION_BY_ITEM.get(item.item_codigo)
        if specific:
            return specific

        description = self._subject_text(item)
        return (
            f"Adequar a disponibilizacao de informacoes referente a {description}, sanando as "
            "inconsistencias registradas no checklist e assegurando acesso claro ao usuario."
        )

    def _subject_text(self, item: ChecklistItem) -> str:
        mapped = ITEM_SUBJECT_BY_CODE.get(item.item_codigo)
        if mapped:
            return mapped
        return self._normalize_description(item.descricao_item)

    def _normalize_description(self, description: str) -> str:
        normalized = description.strip()
        if normalized.endswith("?"):
            normalized = normalized[:-1]
        if normalized:
            normalized = normalized[0].lower() + normalized[1:]
        return normalized


def _ensure_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _format_numbered_line(index: int, text: str) -> str:
    return f"{index}. {text}"
