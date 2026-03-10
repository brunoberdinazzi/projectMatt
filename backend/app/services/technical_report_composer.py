from __future__ import annotations

from collections import defaultdict

from ..models import ChecklistItem, ChecklistParseResult, ReportBuildRequest, ReportSection
from .report_metadata import build_report_title


SOURCE_ORDER = ("site_orgao", "portal_transparencia", "esic", "nao_informada")

DEFAULT_TEAM = (
    "Matheus Cordoba Caramalac - Chefe do Nucleo de Apoio Tecnologico - "
    "Engenheiro de Controle e Automacao"
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
                titulo="EQUIPE TECNICA DO MINISTERIO PUBLICO ESTADUAL",
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
        promotoria = parsed.promotoria or "Promotoria nao informada"
        referencia = parsed.referencia
        orgao_entity = self._orgao_entity(parsed)

        text = (
            f"Atender a {solicitacao or 'solicitacao tecnica nao informada'}, formulada pela {promotoria}, "
            f"para constatacao de conformidade com as legislacoes pertinentes sobre Acesso a Informacao "
            f"por parte da {orgao_entity}, apresentando resposta a 01 (um) quesito padrao."
        )
        if referencia:
            text += f" A presente analise esta relacionada ao expediente identificado como {referencia}."
        return text

    def _build_object(self, parsed: ChecklistParseResult) -> str:
        orgao_label = self._orgao_entity(parsed)
        return (
            f"Analise da divulgacao de informacoes por parte da {orgao_label} em seus sitios eletronicos "
            "oficiais, a luz da legislacao aplicavel, mediante utilizacao de criterios de apresentacao, "
            "funcionalidade e acessibilidade das informacoes disponibilizadas."
        )

    def _build_team(self, parsed: ChecklistParseResult) -> str:
        return parsed.equipe_tecnica or DEFAULT_TEAM

    def _build_methodology(self, parsed: ChecklistParseResult) -> str:
        orgao_label = self._orgao_entity(parsed)
        paragraphs = [
            (
                "O presente relatorio, visando atender aos quesitos propostos a este Nucleo, e parte "
                "integrante do Projeto Limpando as Vidracas, atualmente em execucao pela Secretaria DAEX, "
                "por meio da parceria entre o Corpo Tecnico de Contabilidade e Economia e o Nucleo de Apoio Tecnologico."
            ),
            (
                f"Nesse contexto, procedeu-se a coleta e a analise das informacoes disponibilizadas pela {orgao_label} "
                "em seus sitios eletronicos oficiais, levando em consideracao criterios de apresentacao, "
                "funcionalidade e acessibilidade."
            ),
            (
                "Iniciou-se esta analise mediante coleta de informacoes nos referidos sitios, utilizando como "
                "referencia o checklist institucional elaborado no ambito do projeto, o qual lista obrigacoes "
                "legais, meios de disponibilizacao e formatos adequados de acesso as informacoes pela sociedade."
            ),
        ]
        if parsed.relatorio_contabil_referencia:
            paragraphs.append(
                "Para a analise qualitativa dos dados e o preenchimento do checklist, consulte tambem "
                f"{parsed.relatorio_contabil_referencia}."
            )
        paragraphs.append(
            "Portanto, o presente parecer encontra-se organizado em secoes tematicas, a fim de "
            "propiciar melhor compreensao dos fatos e das recomendacoes tecnicas apresentadas."
        )
        return "\n\n".join(paragraphs)

    def _build_collection(self, parsed: ChecklistParseResult) -> str:
        sources = self._available_sources(parsed)
        count = len(sources) or 1
        period_text = parsed.periodo_coleta or "periodo nao informado pelo usuario"
        paragraphs = [
            (
                f"A coleta de dados foi efetuada em {self._count_as_words(count)} sitio(s) eletronico(s) distinto(s), "
                f"todos sob responsabilidade da Administracao Municipal, no {period_text}."
            )
        ]
        if "site_orgao" in sources:
            site_text = (
                f"Inicialmente, procedeu-se a analise do site oficial da {self._orgao_entity(parsed)}"
            )
            if parsed.site_url:
                site_text += f", acessivel pelo endereco eletronico {parsed.site_url}"
            site_text += "."
            paragraphs.append(site_text)

        if "portal_transparencia" in sources:
            portal_text = "O segundo ambiente analisado corresponde ao Portal da Transparencia utilizado pelo ente"
            if parsed.portal_url:
                portal_text += f", com acesso identificado em {parsed.portal_url}"
            else:
                portal_text += ", conforme referencia constante da planilha e das evidencias coletadas"
            portal_text += "."
            paragraphs.append(portal_text)

        if "esic" in sources:
            esic_text = "Por fim, foi analisado o sistema e-SIC disponibilizado para atendimento ao cidadao"
            if parsed.esic_url:
                esic_text += f", com acesso identificado em {parsed.esic_url}"
            else:
                esic_text += ", conforme referencia constante da planilha e das evidencias coletadas"
            esic_text += "."
            paragraphs.append(esic_text)

        paragraphs.append(
            "Destaca-se que esta analise se restringe aos criterios de apresentacao, funcionalidade e "
            "acessibilidade das informacoes disponibilizadas nos ambientes eletronicos avaliados."
        )
        return "\n\n".join(paragraphs)

    def _build_recommendations_intro(self, parsed: ChecklistParseResult) -> str:
        return (
            "Caso sejam entendidas necessarias e beneficas, serao apresentadas recomendacoes pertinentes "
            "para o aprimoramento dos sistemas de disponibilizacao de informacoes, com fundamento nas "
            "legislacoes vigentes e em boas praticas de apresentacao de dados ao cidadao."
        )

    def _build_results_intro(self, parsed: ChecklistParseResult) -> str:
        if not parsed.itens_processados:
            return (
                "No recorte automatizado considerado nesta versao, nao foram identificados apontamentos "
                "classificados como Nao ou Parcialmente que demandem registro analitico especifico."
            )
        return (
            "Por meio das tecnicas e metodos descritos anteriormente, verificaram-se os fatos relevantes "
            "relacionados a disponibilizacao de informacoes para a sociedade por parte da Administracao "
            "Publica em seus diferentes sitios eletronicos."
            "\n\n"
            "Com o objetivo de garantir a melhor compreensao dos fatos apresentados, os apontamentos "
            "foram organizados por ambiente eletronico de sua ocorrencia."
        )

    def _build_recommendations_heading_text(self, parsed: ChecklistParseResult) -> str:
        if not parsed.itens_processados:
            return "Diante da ausencia de apontamentos no recorte automatizado, nao ha recomendacoes tecnicas especificas."
        return (
            "Com base nas informacoes coletadas, foi produzida serie de recomendacoes voltadas ao "
            "aprimoramento da usabilidade dos recursos tecnologicos e da conformidade com as leis e "
            "normas vigentes. Para favorecer a integral compreensao dos fatos, as irregularidades e "
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
            "A partir da coleta de dados disponibilizados no(s) sitio(s) eletronico(s) oficial(is) do ente, "
            "realizada por meio da aplicacao do checklist, ha necessidade de recomendacoes tecnicas? Se sim, detalhar?"
        )
        if not parsed.itens_processados:
            answer = (
                "No recorte automatizado atualmente adotado, nao foram identificadas inconformidades "
                "nos grupos e status considerados para formulacao de recomendacoes tecnicas especificas."
            )
        else:
            parts = [
                "Apos verificacao realizada nos sitios eletronicos oficiais do ente, foi constatada a "
                "presenca de irregularidades e ausencias de informacao que justificam a expedicao de "
                "recomendacoes tecnicas, sintetizadas da seguinte forma, caso entendidas pertinentes:"
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
                f"Este relatorio apresentou analise quanto a funcionalidade, apresentacao e disponibilidade "
                f"das informacoes prestadas pela {self._orgao_entity(parsed)} em seus sitios eletronicos "
                "oficiais, bem como recomendacoes de melhorias e correcoes para melhor disponibilizacao "
                "de informacoes aos cidadaos."
            )

        paragraphs.append(
            "O atendimento a presente solicitacao integra o Projeto Limpando as Vidracas, executado "
            "pela Secretaria DAEX. Assim, alem do objetivo principal mencionado, o presente parecer "
            "contribui para a padronizacao das analises tecnicas desenvolvidas por esta Secretaria."
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
                f"Anexo {self._roman_numeral(next_index)} - Tela inicial do site oficial da {self._orgao_entity(parsed)}."
            )
            next_index += 1
        if "portal_transparencia" in self._available_sources(parsed):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Acesso ao Portal da Transparencia utilizado pelo ente."
            )
            next_index += 1
        if "esic" in self._available_sources(parsed):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Acesso ao sistema e-SIC municipal."
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
                f"Anexo {self._roman_numeral(next_index)} - Demonstracao de publicacao incompleta de informacoes sobre a estrutura organizacional do municipio."
            )
            next_index += 1
        if item_codes.intersection({"5.4", "5.5", "5.6", "5.7", "5.8"}):
            lines.append(
                f"Anexo {self._roman_numeral(next_index)} - Demonstracao das ausencias de informacoes e funcionalidades no sistema e-SIC."
            )
        if len(lines) == 1:
            lines.append("Anexo II - Documentacao complementar da avaliacao realizada.")
        return "\n\n".join(lines)

    def _source_heading(self, parsed: ChecklistParseResult, source_key: str) -> str:
        orgao = parsed.orgao or "orgao nao informado"
        if source_key == "site_orgao":
            if (parsed.tipo_orgao or "").lower() == "camara":
                return f"Site Oficial da Camara Municipal de {orgao}"
            return f"Site Oficial da Prefeitura Municipal de {orgao}"
        if source_key == "portal_transparencia":
            return f"Portal da Transparencia Municipal de {orgao}"
        if source_key == "esic":
            return "Sistema e-SIC Municipal"
        return "Outros Apontamentos"

    def _orgao_label(self, parsed: ChecklistParseResult, include_article: bool = True) -> str:
        orgao = parsed.orgao or "orgao nao informado"
        tipo = (parsed.tipo_orgao or "").lower()
        if tipo == "camara":
            base = f"Camara Municipal de {orgao}"
        else:
            base = f"Prefeitura Municipal de {orgao}"
        if include_article:
            return f"a {base}"
        return base

    def _orgao_entity(self, parsed: ChecklistParseResult) -> str:
        return self._orgao_label(parsed, include_article=False)

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
