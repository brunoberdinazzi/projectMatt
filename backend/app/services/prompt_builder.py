from __future__ import annotations

from collections import defaultdict

from ..models import ChecklistItem, ChecklistParseResult


FONTE_LABELS = {
    "site_orgao": "Site do orgao",
    "portal_transparencia": "Portal da Transparencia",
    "esic": "e-SIC",
    "nao_informada": "Fonte nao identificada",
}


class PromptBuilder:
    def build(self, payload: ChecklistParseResult) -> str:
        grouped = self._group_by_source(payload.itens_processados)

        metadata_lines = [
            "Voce e um redator tecnico responsavel por redigir trechos de um relatorio tecnico sobre transparencia publica.",
            "Use exclusivamente as informacoes fornecidas abaixo.",
            "Nao invente fatos, nao complemente dados ausentes e nao afirme cumprimento quando o registro indicar problema.",
            "Escreva em portugues formal, objetiva, impessoal e compatível com relatórios técnicos administrativos.",
            "Organize a resposta por fonte de consulta.",
            "Considere apenas apontamentos com status Nao ou Parcialmente.",
            "Quando houver observacao, ela deve ser o principal fundamento do texto.",
            "Quando nao houver observacao, redija de forma conservadora com base apenas na descricao do item e no status.",
            "Nao cite anexos, figuras ou evidencias visuais que nao tenham sido fornecidos no prompt.",
            "",
            f"Orgao analisado: {payload.orgao or 'Nao informado'}",
            f"Tipo de orgao: {payload.tipo_orgao or 'Nao informado'}",
            f"Periodo da analise: {payload.periodo_analise or 'Nao informado'}",
            f"Grupos considerados: {', '.join(payload.grupos_permitidos)}",
            "",
            "Formato de saida desejado:",
            "1. RESULTADOS OBTIDOS",
            "   - Subsecao Site do orgao",
            "   - Subsecao Portal da Transparencia",
            "   - Subsecao Sistema e-SIC",
            "2. RECOMENDACOES",
            "   - Organizadas pelas mesmas fontes",
            "3. QUESITO - RESUMO",
            "   - Sintetize as recomendacoes em tom objetivo",
            "",
            "Para cada fonte, redija texto corrido sintetizando os problemas encontrados.",
            "Transforme cada apontamento em linguagem narrativa, sem repetir mecanicamente o checklist.",
            "Nas recomendacoes, utilize verbos no imperativo tecnico, como publicar, corrigir, disponibilizar, assegurar, unificar.",
            "Se uma fonte estiver vazia, informe apenas que nao ha apontamentos para aquela fonte.",
            "",
            "Apontamentos estruturados:",
        ]

        sections: list[str] = []
        for source_key in ("site_orgao", "portal_transparencia", "esic", "nao_informada"):
            items = grouped.get(source_key, [])
            sections.append(f"## {FONTE_LABELS[source_key]}")
            if not items:
                sections.append("- Sem apontamentos.")
                continue

            for item in items:
                sections.extend(self._format_item(item))

            sections.append("")

        return "\n".join(metadata_lines + sections).strip()

    def _group_by_source(self, items: list[ChecklistItem]) -> dict[str, list[ChecklistItem]]:
        grouped: dict[str, list[ChecklistItem]] = defaultdict(list)
        for item in items:
            grouped[item.fonte].append(item)
        return grouped

    def _format_item(self, item: ChecklistItem) -> list[str]:
        lines = [
            f"- Codigo do item: {item.item_codigo}",
            f"- Grupo: {item.grupo}",
            f"  Linha: {item.linha_referencia}",
            f"  Status: {item.status}",
            f"  Ano de referencia: {item.ano_referencia or 'Nao informado'}",
            f"  Item: {item.descricao_item}",
        ]
        if item.fonte_texto:
            lines.append(f"  Local disponibilizado: {item.fonte_texto}")
        if item.status_2024 or item.status_2025:
            lines.append(
                f"  Historico: 2024={item.status_2024 or 'N/A'} | 2025={item.status_2025 or 'N/A'}"
            )
        if item.observacao:
            lines.append(f"  Observacao: {item.observacao}")
        if item.detalhes:
            lines.append("  Detalhes:")
            for detail in item.detalhes:
                lines.append(f"    - {detail.descricao}: {detail.status}")
        if item.fundamentacao:
            lines.append(f"  Fundamentacao: {item.fundamentacao}")
        if item.aba_origem:
            lines.append(f"  Aba: {item.aba_origem}")
        return lines
