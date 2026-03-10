from __future__ import annotations

from collections import defaultdict

from ..models import ChecklistItem, ChecklistParseResult, ReportBuildRequest, ReportSection
from .report_metadata import build_report_title
from .report_terms import SOURCE_ORDER, entity_display_name, source_label

DEFAULT_TEAM = (
    "Equipe tecnica responsavel nao informada."
)


class TechnicalReportComposer:
    def compose(self, parsed: ChecklistParseResult, dynamic_report: ReportBuildRequest) -> ReportBuildRequest:
        grouped_items = self._group_by_source(parsed.itens_processados)
        result_map = self._extract_dynamic_sections(dynamic_report, prefix="resultados obtidos")
        recommendation_map = self._extract_dynamic_sections(dynamic_report, prefix="recomendacoes")
        summary_text = self._extract_single_section(dynamic_report, "quesito")
        conclusion_text = self._extract_single_section(dynamic_report, "conclusao")

        sections: list[ReportSection] = [
            ReportSection(
                fonte="nao_informada",
                titulo="OBJETIVO DA ANALISE",
                texto=self._build_objective(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="OBJETO",
                texto=self._build_object(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="EQUIPE TECNICA RESPONSAVEL",
                texto=self._build_team(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="METODOLOGIA APLICADA",
                texto=self._build_methodology(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="Coleta de Informacoes",
                texto=self._build_collection(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="Recomendacoes Pertinentes",
                texto=self._build_recommendations_intro(parsed),
            ),
            ReportSection(
                fonte="nao_informada",
                titulo="RESULTADOS OBTIDOS",
                texto=self._build_results_intro(parsed),
            ),
        ]

        for source_key in SOURCE_ORDER:
            items = grouped_items.get(source_key, [])
            if not items:
                continue
            text = result_map.get(source_key)
            if not text:
                continue
            sections.append(
                ReportSection(
                    fonte=source_key,
                    titulo=self._source_heading(parsed, source_key),
                    texto=text,
                )
            )

        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="RECOMENDACOES",
                texto=self._build_recommendations_heading_text(parsed),
            )
        )

        for source_key in SOURCE_ORDER:
            items = grouped_items.get(source_key, [])
            if not items:
                continue
            text = recommendation_map.get(source_key)
            if not text:
                continue
            sections.append(
                ReportSection(
                    fonte=source_key,
                    titulo=self._source_heading(parsed, source_key),
                    texto=text,
                )
            )

        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="QUESITOS",
                texto=self._build_quesitos(parsed, summary_text, grouped_items, recommendation_map),
            )
        )
        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="CONCLUSAO",
                texto=self._build_conclusion(parsed, conclusion_text),
            )
        )
        sections.append(
            ReportSection(
                fonte="nao_informada",
                titulo="ANEXOS",
                texto=self._build_annexes(parsed, grouped_items),
            )
        )

        return ReportBuildRequest(
            titulo_relatorio=build_report_title(parsed),
            orgao=parsed.orgao,
            tipo_orgao=parsed.tipo_orgao,
            periodo_analise=parsed.periodo_analise,
            sat_numero=parsed.sat_numero,
            numero_relatorio=parsed.numero_relatorio,
            promotoria=parsed.promotoria,
            referencia=parsed.referencia,
            solicitacao=parsed.solicitacao or self._fallback_solicitacao(parsed),
            cidade_emissao=parsed.cidade_emissao,
            data_emissao=parsed.data_emissao,
            periodo_coleta=parsed.periodo_coleta,
            equipe_tecnica=parsed.equipe_tecnica or DEFAULT_TEAM,
            relatorio_contabil_referencia=parsed.relatorio_contabil_referencia,
            site_url=parsed.site_url,
            portal_url=parsed.portal_url,
            esic_url=parsed.esic_url,
            secoes=sections,
        )

    def _group_by_source(self, items: list[ChecklistItem]) -> dict[str, list[ChecklistItem]]:
        grouped: dict[str, list[ChecklistItem]] = defaultdict(list)
        for item in items:
            grouped[item.fonte].append(item)
        return grouped

    def _extract_dynamic_sections(self, report: ReportBuildRequest, prefix: str) -> dict[str, str]:
        extracted: dict[str, str] = {}
        prefix_normalized = prefix.lower()
        for section in report.secoes:
            title = section.titulo.lower()
            if not title.startswith(prefix_normalized):
                continue
            source_key = section.fonte if section.fonte != "nao_informada" else self._infer_source_from_title(title)
            extracted[source_key] = section.texto.strip()
        return extracted

    def _extract_single_section(self, report: ReportBuildRequest, contains: str) -> str:
        needle = contains.lower()
        for section in report.secoes:
            if needle in section.titulo.lower():
                return section.texto.strip()
        return ""

    def _build_objective(self, parsed: ChecklistParseResult) -> str:
        solicitacao = parsed.solicitacao or self._fallback_solicitacao(parsed)
        solicitante = parsed.promotoria or "solicitante nao informado"
        referencia = parsed.referencia
        entity_name = self._entity_name(parsed)

        if solicitacao:
            text = (
                f"Atender a {solicitacao}, encaminhada por {solicitante}, mediante avaliacao tecnica "
                f"dos registros, evidencias e apontamentos relacionados a {entity_name}."
            )
        else:
            text = (
                f"Registrar avaliacao tecnica dos registros, evidencias e apontamentos relacionados "
                f"a {entity_name}, conforme demanda recebida de {solicitante}."
            )
        if referencia:
            text += f" A presente analise esta relacionada ao expediente identificado como {referencia}."
        return text

    def _build_object(self, parsed: ChecklistParseResult) -> str:
        entity_name = self._entity_name(parsed)
        return (
            f"Analise dos registros, informacoes e evidencias disponibilizados por {entity_name} "
            "nos canais e materiais considerados nesta avaliacao, com foco nos criterios definidos "
            "pelo checklist e nos apontamentos consolidados pelo sistema."
        )

    def _build_team(self, parsed: ChecklistParseResult) -> str:
        return parsed.equipe_tecnica or DEFAULT_TEAM

    def _build_methodology(self, parsed: ChecklistParseResult) -> str:
        paragraphs = [
            (
                "O presente relatorio foi elaborado a partir da leitura estruturada da planilha fornecida, "
                "da selecao automatizada dos apontamentos elegiveis e da consolidacao das evidencias "
                "textuais associadas a cada item."
            ),
            (
                "A analise considerou o perfil do parser adotado, os grupos monitorados, os status "
                "selecionados e as observacoes registradas no material de entrada."
            ),
            (
                "Sempre que disponivel, o contexto recuperado por scraping foi utilizado apenas como apoio "
                "para contextualizacao, sem substituir os achados estruturados do checklist."
            ),
        ]
        if parsed.relatorio_contabil_referencia:
            paragraphs.append(
                "Para complementar a leitura qualitativa dos dados e o preenchimento do checklist, "
                "foi consultado tambem "
                f"{parsed.relatorio_contabil_referencia}."
            )
        paragraphs.append(
            "O documento foi organizado em secoes tematicas para facilitar a revisao dos resultados, "
            "das recomendacoes e das conclusoes apresentadas."
        )
        return "\n\n".join(paragraphs)

    def _build_collection(self, parsed: ChecklistParseResult) -> str:
        sources = self._available_sources(parsed)
        count = len(sources) or 1
        period_text = parsed.periodo_coleta or "periodo nao informado pelo usuario"
        paragraphs = [
            (
                f"A coleta de dados considerou {self._count_as_words(count)} fonte(s) ou ambiente(s) digital(is) "
                f"distinto(s), no {period_text}."
            )
        ]
        if "site_orgao" in sources:
            site_text = f"Inicialmente, foi considerada a fonte classificada como {source_label('site_orgao')}"
            if parsed.site_url:
                site_text += f", acessivel pelo endereco {parsed.site_url}"
            site_text += "."
            paragraphs.append(site_text)

        if "portal_transparencia" in sources:
            portal_text = f"Tambem foi considerado o ambiente classificado como {source_label('portal_transparencia')}"
            if parsed.portal_url:
                portal_text += f", com acesso identificado em {parsed.portal_url}"
            else:
                portal_text += ", conforme referencia constante da planilha e das evidencias coletadas"
            portal_text += "."
            paragraphs.append(portal_text)

        if "esic" in sources:
            esic_text = f"Por fim, foi considerado o ambiente classificado como {source_label('esic')}"
            if parsed.esic_url:
                esic_text += f", com acesso identificado em {parsed.esic_url}"
            else:
                esic_text += ", conforme referencia constante da planilha e das evidencias coletadas"
            esic_text += "."
            paragraphs.append(esic_text)

        paragraphs.append(
            "Destaca-se que esta analise se restringe aos criterios observados no checklist e aos "
            "registros efetivamente disponibilizados nos ambientes avaliados."
        )
        return "\n\n".join(paragraphs)

    def _build_recommendations_intro(self, parsed: ChecklistParseResult) -> str:
        return (
            "Quando consideradas pertinentes, as recomendacoes tecnicas abaixo visam orientar ajustes "
            "de processo, conteudo, disponibilizacao ou organizacao das informacoes avaliadas, com base "
            "nos achados consolidados nesta analise."
        )

    def _build_results_intro(self, parsed: ChecklistParseResult) -> str:
        if not parsed.itens_processados:
            return (
                "No recorte automatizado considerado nesta versao, nao foram identificados apontamentos "
                f"classificados nos status {self._status_scope_text(parsed)} para os grupos {self._group_scope_text(parsed)} "
                "que demandem registro analitico especifico."
            )
        return (
            "Por meio das tecnicas e metodos descritos anteriormente, verificaram-se os fatos relevantes "
            "relacionados aos registros avaliados nos diferentes ambientes considerados."
            "\n\n"
            "Com o objetivo de garantir a melhor compreensao dos fatos apresentados, os apontamentos "
            "foram organizados por fonte de ocorrencia."
        )

    def _build_recommendations_heading_text(self, parsed: ChecklistParseResult) -> str:
        if not parsed.itens_processados:
            return (
                "Diante da ausencia de apontamentos no recorte automatizado, nao ha recomendacoes tecnicas "
                f"especificas para os grupos {self._group_scope_text(parsed)}."
            )
        return (
            "Com base nas informacoes coletadas, foi produzida serie de recomendacoes voltadas ao "
            "aprimoramento da consistencia das informacoes, da usabilidade dos recursos avaliados e "
            "da resolucao das inconformidades observadas. Para favorecer a compreensao dos fatos, as "
            "falhas identificadas sao apresentadas em conjunto com as respectivas providencias sugeridas."
        )

    def _build_quesitos(
        self,
        parsed: ChecklistParseResult,
        summary_text: str,
        grouped_items: dict[str, list[ChecklistItem]],
        recommendation_map: dict[str, str],
    ) -> str:
        question = (
            "A partir da aplicacao do checklist e da consolidacao das evidencias reunidas, ha necessidade "
            "de recomendacoes tecnicas? Se sim, detalhar."
        )
        if not parsed.itens_processados:
            answer = (
                "No recorte automatizado atualmente adotado, nao foram identificadas inconformidades "
                f"nos grupos {self._group_scope_text(parsed)} e status {self._status_scope_text(parsed)} "
                "para formulacao de recomendacoes tecnicas especificas."
            )
        else:
            parts = [
                "Apos a verificacao das fontes e registros considerados nesta analise, foram constatadas "
                "inconformidades e lacunas de informacao que justificam a formulacao de recomendacoes "
                "tecnicas, sintetizadas da seguinte forma:"
            ]
            synthesized = self._build_quesitos_recommendations(parsed, grouped_items, recommendation_map)
            if synthesized:
                parts.append(synthesized)
            elif summary_text:
                parts.append(summary_text)
            else:
                total = sum(len(items) for items in grouped_items.values())
                parts.append(
                    f"Foram identificados {total} apontamento(s) relevantes, os quais demandam providencias "
                    "tecnicas e administrativas descritas nas secoes anteriores."
                )
            answer = "\n\n".join(parts)
        return "\n\n".join([question, answer])

    def _build_conclusion(self, parsed: ChecklistParseResult, conclusion_text: str) -> str:
        paragraphs = []
        if conclusion_text and not self._is_generic_conclusion(conclusion_text):
            paragraphs.append(conclusion_text)
        else:
            paragraphs.append(
                f"Este relatorio apresentou a analise dos registros e evidencias associados a "
                f"{self._entity_name(parsed)}, bem como recomendacoes de melhoria e correcoes para os "
                "pontos identificados ao longo da avaliacao."
            )

        paragraphs.append(
            "As conclusoes acima sintetizam os achados relevantes do recorte analisado e devem ser "
            "lidas em conjunto com as secoes anteriores, nas quais constam o detalhamento dos fatos "
            "e das providencias recomendadas."
        )
        paragraphs.append("Colocamo-nos a disposicao para quaisquer esclarecimentos.")
        if parsed.cidade_emissao or parsed.data_emissao:
            location_line = ", ".join(part for part in [parsed.cidade_emissao, parsed.data_emissao] if part)
            paragraphs.append(location_line.strip() + ".")
        paragraphs.append(parsed.equipe_tecnica or DEFAULT_TEAM)
        return "\n\n".join(paragraphs)

    def _build_annexes(
        self,
        parsed: ChecklistParseResult,
        grouped_items: dict[str, list[ChecklistItem]],
    ) -> str:
        lines = ["Anexo I - Checklist utilizado como base para pesquisa de informacoes."]
        next_index = 2

        if "site_orgao" in self._available_sources(parsed):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Registro do ambiente classificado como {source_label('site_orgao')}."
            )
            next_index += 1
        if "portal_transparencia" in self._available_sources(parsed):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Registro do ambiente classificado como {source_label('portal_transparencia')}."
            )
            next_index += 1
        if "esic" in self._available_sources(parsed):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Registro do ambiente classificado como {source_label('esic')}."
            )
            next_index += 1

        item_codes = {item.item_codigo for items in grouped_items.values() for item in items}
        if "1.4" in item_codes:
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Problemas encontrados nos relatorios fornecidos em formatos eletronicos."
            )
            next_index += 1
        if "5.3" in item_codes:
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Demonstracao de publicacao incompleta de informacoes institucionais."
            )
            next_index += 1
        if item_codes.intersection({"5.4", "5.5", "5.6", "5.7", "5.8"}):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Demonstracao das ausencias de informacoes e funcionalidades no canal de atendimento."
            )
        if len(lines) == 1:
            lines.append("Anexo II - Documentacao complementar da avaliacao realizada.")
        return "\n\n".join(lines)

    def _source_heading(self, parsed: ChecklistParseResult, source_key: str) -> str:
        return source_label(source_key)

    def _orgao_label(self, parsed: ChecklistParseResult, include_article: bool = True) -> str:
        base = entity_display_name(parsed.orgao, parsed.tipo_orgao)
        if include_article:
            return f"a entidade {base}"
        return base

    def _orgao_entity(self, parsed: ChecklistParseResult) -> str:
        return self._orgao_label(parsed, include_article=False)

    def _entity_name(self, parsed: ChecklistParseResult) -> str:
        return entity_display_name(parsed.orgao, parsed.tipo_orgao)

    def _available_sources(self, parsed: ChecklistParseResult) -> list[str]:
        sources: list[str] = []
        for source in parsed.fontes_disponiveis:
            if source not in sources:
                sources.append(source)
        if parsed.site_url or any(item.fonte == "site_orgao" for item in parsed.itens_processados):
            if "site_orgao" not in sources:
                sources.append("site_orgao")
        if parsed.portal_url or any(item.fonte == "portal_transparencia" for item in parsed.itens_processados):
            if "portal_transparencia" not in sources:
                sources.append("portal_transparencia")
        if parsed.esic_url or any(item.fonte == "esic" for item in parsed.itens_processados):
            if "esic" not in sources:
                sources.append("esic")
        if not sources:
            if parsed.site_url:
                sources.append("site_orgao")
            if parsed.portal_url:
                sources.append("portal_transparencia")
            if parsed.esic_url:
                sources.append("esic")
        return sources

    def _fallback_solicitacao(self, parsed: ChecklistParseResult) -> str:
        if parsed.sat_numero:
            return f"SAT n {parsed.sat_numero}"
        return ""

    def _infer_source_from_title(self, title: str) -> str:
        if "site" in title:
            return "site_orgao"
        if "portal" in title and "transpar" in title:
            return "portal_transparencia"
        if "sic" in title:
            return "esic"
        return "nao_informada"

    def _build_quesitos_recommendations(
        self,
        parsed: ChecklistParseResult,
        grouped_items: dict[str, list[ChecklistItem]],
        recommendation_map: dict[str, str],
    ) -> str:
        blocks: list[str] = []
        for source_key in SOURCE_ORDER:
            items = grouped_items.get(source_key, [])
            if not items:
                continue
            recommendation_text = recommendation_map.get(source_key, "")
            lines = self._extract_recommendation_lines(recommendation_text)
            if not lines:
                continue
            block_parts = [self._source_heading(parsed, source_key)]
            block_parts.extend(lines)
            blocks.append("\n\n".join(block_parts))
        return "\n\n".join(blocks)

    def _extract_recommendation_lines(self, text: str) -> list[str]:
        if not text:
            return []
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
        paragraphs_with_marker = [paragraph for paragraph in paragraphs if "Recomenda-se:" in paragraph]
        source_paragraphs = paragraphs_with_marker or paragraphs

        lines: list[str] = []
        for paragraph in source_paragraphs:
            for raw_line in paragraph.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.lower().startswith("considerando os apontamentos"):
                    continue
                if "Recomenda-se:" in line:
                    line = line.split("Recomenda-se:", 1)[1].strip()
                line = line.lstrip("0123456789. ").strip()
                if not line:
                    continue
                lines.append(_imperative_sentence(line))
        return lines

    def _is_generic_conclusion(self, text: str) -> bool:
        normalized = " ".join(text.lower().split())
        return "o processamento automatizado da planilha permitiu consolidar os achados relevantes" in normalized

    def _count_as_words(self, count: int) -> str:
        mapping = {1: "um", 2: "dois", 3: "tres"}
        return mapping.get(count, str(count))

    def _group_scope_text(self, parsed: ChecklistParseResult) -> str:
        groups = parsed.parser_options.allowed_groups or parsed.grupos_permitidos
        return ", ".join(groups)

    def _status_scope_text(self, parsed: ChecklistParseResult) -> str:
        return ", ".join(parsed.parser_options.allowed_status)

    def _roman_numeral(self, number: int) -> str:
        mapping = {
            1: "I",
            2: "II",
            3: "III",
            4: "IV",
            5: "V",
            6: "VI",
            7: "VII",
            8: "VIII",
            9: "IX",
            10: "X",
        }
        return mapping.get(number, str(number))


def _imperative_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if cleaned[-1] not in ".;":
        cleaned += ";"
    if cleaned[:1].islower():
        cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned
