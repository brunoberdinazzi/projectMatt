from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..models import (
    ChecklistItem,
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .report_metadata import build_report_title
from .report_terms import SOURCE_ORDER, source_label, source_section_title


RECOMMENDATION_BY_ITEM = {
    "2.1": (
        "Publicar o Plano Plurianual vigente em local de facil acesso, com arquivo legivel e identificacao clara do periodo de vigencia."
    ),
    "2.2": (
        "Publicar a Lei de Diretrizes Orcamentarias vigente em local de facil acesso, com integridade documental e referencia clara ao exercicio correspondente."
    ),
    "2.3": (
        "Publicar a Lei Orcamentaria Anual vigente em local de facil acesso, com integridade documental e referencia clara ao exercicio correspondente."
    ),
    "2.4": (
        "Disponibilizar integralmente e de forma tempestiva os anexos do Relatorio Resumido da Execucao Orcamentaria, observando a periodicidade legal aplicavel."
    ),
    "2.5": (
        "Disponibilizar integralmente e de forma tempestiva os Relatorios de Gestao Fiscal, observando a periodicidade legal aplicavel."
    ),
    "2.6": (
        "Publicar integralmente os registros de prestacao de contas ou equivalentes referidos no material analisado, em formato legivel e com identificacao clara do periodo correspondente."
    ),
    "2.7": (
        "Publicar os pareceres, validacoes ou manifestacoes formais vinculados aos registros analisados, com referencia clara ao periodo correspondente."
    ),
    "3.1": (
        "Divulgar informacoes pormenorizadas sobre as receitas, com detalhamento suficiente para permitir consulta e controle social."
    ),
    "3.2": (
        "Divulgar informacoes pormenorizadas sobre as despesas, com detalhamento suficiente para permitir consulta e controle social."
    ),
    "3.3": (
        "Assegurar atualizacao em tempo real das informacoes de receitas e despesas, observando a tempestividade exigida pela legislacao."
    ),
    "3.4": (
        "Divulgar os repasses e as transferencias de recursos financeiros com identificacao clara da origem, destino, valores e datas correspondentes."
    ),
    "3.5": (
        "Divulgar informacoes completas e atualizadas sobre programas, acoes, projetos e obras, com dados suficientes para acompanhamento publico."
    ),
    "3.6": (
        "Divulgar os procedimentos licitatorios com seus respectivos documentos, fases, resultados e anexos essenciais para consulta publica."
    ),
    "3.7": (
        "Divulgar relacao atualizada dos contratos celebrados, acompanhada dos instrumentos e documentos pertinentes."
    ),
    "3.8": (
        "Divulgar relacao atualizada dos convenios celebrados, acompanhada dos instrumentos e documentos pertinentes."
    ),
    "4.1": (
        "Divulgar relacao atualizada de servidores com informacoes suficientes para consulta publica e controle social."
    ),
    "4.2": (
        "Divulgar a remuneracao dos servidores de forma clara, individualizada e acessivel ao usuario."
    ),
    "4.3": (
        "Divulgar as diarias recebidas pelos servidores com informacoes claras sobre beneficiario, valor, periodo e motivo."
    ),
    "1.3": (
        "Disponibilizar ferramenta de pesquisa de conteudo que permita localizar, de forma simples, "
        "as informacoes publicadas nos canais monitorados e nos materiais disponibilizados para consulta."
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
    "2.1": "disponibilizacao do Plano Plurianual",
    "2.2": "disponibilizacao da Lei de Diretrizes Orcamentarias",
    "2.3": "disponibilizacao da Lei Orcamentaria Anual",
    "2.4": "disponibilizacao do Relatorio Resumido da Execucao Orcamentaria",
    "2.5": "disponibilizacao do Relatorio de Gestao Fiscal",
    "2.6": "disponibilizacao dos registros de prestacao de contas ou equivalentes",
    "2.7": "disponibilizacao dos pareceres, validacoes ou manifestacoes formais vinculadas aos registros analisados",
    "3.1": "divulgacao pormenorizada das receitas",
    "3.2": "divulgacao pormenorizada das despesas",
    "3.3": "atualizacao em tempo real de receitas e despesas",
    "3.4": "divulgacao dos repasses ou transferencias de recursos financeiros",
    "3.5": "divulgacao de programas, acoes, projetos e obras",
    "3.6": "divulgacao dos procedimentos licitatorios",
    "3.7": "divulgacao da relacao dos contratos celebrados",
    "3.8": "divulgacao da relacao dos convenios celebrados",
    "4.1": "divulgacao da relacao de servidores",
    "4.2": "divulgacao da remuneracao dos servidores",
    "4.3": "divulgacao das diarias recebidas pelos servidores",
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
                    titulo=source_section_title("Resultados Obtidos", source_key),
                    texto=self._build_results_text(payload, source_key, grouped.get(source_key, [])),
                )
            )

        for source_key in SOURCE_ORDER:
            sections.append(
                ReportSection(
                    fonte=source_key,
                    titulo=source_section_title("Recomendacoes", source_key),
                    texto=self._build_recommendations_text(source_key, grouped.get(source_key, [])),
                )
            )

        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="Quesito - Sintese das Recomendacoes",
                texto=self._build_summary_text(payload, grouped),
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

    def _build_results_text(
        self,
        payload: ChecklistParseResult,
        source_key: str,
        items: list[ChecklistItem],
    ) -> str:
        if not items:
            return (
                f"Nao foram identificados, no ambito de {source_label(source_key)}, apontamentos classificados "
                f"nos status monitorados ({self._status_scope_text(payload)}) para os grupos {self._group_scope_text(payload)}."
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
                f"{source_label(source_key)} no recorte automatizado atual."
            )

        specialized_text = self._build_specialized_recommendations_text(source_key, actionable_items)
        if specialized_text:
            return specialized_text

        paragraphs = [self._build_recommendation_paragraph(item) for item in actionable_items]
        return "\n\n".join(paragraphs)

    def _build_summary_text(
        self,
        payload: ChecklistParseResult,
        grouped: dict[str, list[ChecklistItem]],
    ) -> str:
        all_items = [item for source_key in SOURCE_ORDER for item in grouped.get(source_key, [])]
        actionable_items = [item for item in all_items if item.status not in {"Sim", "Nao se aplica"}]
        if not actionable_items:
            return (
                "No recorte automatizado vigente, nao foram identificados apontamentos "
                f"que demandem recomendacoes tecnicas corretivas para os grupos {self._group_scope_text(payload)}."
            )

        source_summaries = []
        for source_key in SOURCE_ORDER:
            items = [item for item in grouped.get(source_key, []) if item.status not in {"Sim", "Nao se aplica"}]
            if not items:
                continue
            source_summaries.append(
                f"{source_label(source_key)}: {len(items)} apontamento(s) relevante(s)"
            )

        return (
            "A partir da verificacao realizada nas fontes consideradas nesta analise, constatou-se "
            "a necessidade de adocao de medidas corretivas e de aprimoramento, sintetizadas nos "
            "seguintes eixos: "
            + "; ".join(source_summaries)
            + "."
        )

    def _build_conclusion_text(self, payload: ChecklistParseResult) -> str:
        if not payload.itens_processados:
            base_text = (
                f"No recorte considerado por esta versao do sistema, nao foram identificados nos grupos "
                f"{self._group_scope_text(payload)} itens com classificacao {self._status_scope_text(payload)}. "
                "Ainda assim, recomenda-se manter a "
                "verificacao manual do checklist completo para fins de validacao final."
            )
            scoped_warnings = [
                warning
                for warning in payload.warnings
                if "fora do escopo automatizado atual" in warning or "grupos " in warning
            ]
            if scoped_warnings:
                return base_text + " " + " ".join(scoped_warnings)
            return base_text

        return (
            "O processamento automatizado da planilha permitiu consolidar os achados relevantes do "
            "checklist e organiza-los em linguagem tecnica compativel com a elaboracao do relatorio "
            "final. Recomenda-se, todavia, revisao final pela equipe responsavel antes da "
            "emissao da versao definitiva."
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
            if detail.status.lower() in {"nao", "parcialmente", "parcial"}
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
            f"Na fonte classificada como {source_label('site_orgao')}, verificou-se divulgacao apenas parcial das informacoes institucionais esperadas para o recorte analisado."
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
            f"Na fonte classificada como {source_label('portal_transparencia')}, foram identificadas inconformidades relacionadas a "
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
                f"Na fonte classificada como {source_label('esic')}, verificou-se a ausencia de disponibilizacao de "
                f"{self._join_with_conjunction(issue_phrases)}."
            )
        if not paragraphs:
            paragraphs.append(
                f"Na fonte classificada como {source_label('esic')}, foram identificadas ausencias de informacoes "
                "e funcionalidades relacionadas ao recorte analisado."
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
            f"Na fonte classificada como {source_label('portal_transparencia')}, as recomendacoes abaixo visam corrigir os problemas "
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
                f"Na fonte classificada como {source_label('esic')}, identificou-se necessidade de adequacao quanto a "
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
        normalized_description = self._normalize_description(item.descricao_item)
        if normalized_description:
            return normalized_description
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
        normalized_description = self._normalize_description(item.descricao_item)
        specific = RECOMMENDATION_BY_ITEM.get(item.item_codigo) if not normalized_description else None
        if specific:
            return specific

        description = self._subject_text(item)
        return (
            f"Adequar a disponibilizacao de informacoes referente a {description}, sanando as "
            "inconsistencias registradas no checklist e assegurando acesso claro ao publico-alvo."
        )

    def _subject_text(self, item: ChecklistItem) -> str:
        normalized_description = self._normalize_description(item.descricao_item)
        if normalized_description:
            return normalized_description
        mapped = ITEM_SUBJECT_BY_CODE.get(item.item_codigo)
        if mapped:
            return mapped
        return normalized_description

    def _normalize_description(self, description: str) -> str:
        normalized = description.strip()
        if normalized.endswith("?"):
            normalized = normalized[:-1]
        if normalized:
            normalized = normalized[0].lower() + normalized[1:]
        return normalized

    def _group_scope_text(self, payload: Optional[ChecklistParseResult] = None) -> str:
        parser_payload = payload or ChecklistParseResult()
        groups = parser_payload.parser_options.allowed_groups or parser_payload.grupos_permitidos
        return ", ".join(groups)

    def _status_scope_text(self, payload: Optional[ChecklistParseResult] = None) -> str:
        parser_payload = payload or ChecklistParseResult()
        statuses = parser_payload.parser_options.allowed_status
        return ", ".join(statuses)


def _ensure_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _format_numbered_line(index: int, text: str) -> str:
    return f"{index}. {text}"
