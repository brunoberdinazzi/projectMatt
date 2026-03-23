from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..models import ChecklistItem, ChecklistParseResult
from .report_terms import SOURCE_ORDER, entity_display_name, entity_type_label, source_label


class PromptBuilder:
    def build(self, payload: ChecklistParseResult) -> str:
        if payload.financial_analysis is not None:
            return self._build_financial_prompt(payload)

        grouped = self._group_by_source(payload.itens_processados)
        allowed_status = ", ".join(payload.parser_options.allowed_status)
        entity_name = entity_display_name(payload.orgao, payload.tipo_orgao)

        metadata_lines = [
            "Voce e um redator tecnico encarregado de redigir trechos de um relatorio tecnico analitico.",
            "Use exclusivamente as informacoes fornecidas abaixo.",
            "Nao invente fatos, nao complemente dados ausentes e nao afirme cumprimento quando o registro indicar problema.",
            "Escreva em portugues formal, objetiva, impessoal e compativel com relatorios tecnicos profissionais.",
            "Nao presuma setor, esfera institucional ou obrigacoes regulatorias que nao estejam explicitamente descritas nos dados.",
            "Organize a resposta por fonte de consulta.",
            f"Considere apenas apontamentos com status: {allowed_status}.",
            "Quando houver observacao, ela deve ser o principal fundamento do texto.",
            "Quando nao houver observacao, redija de forma conservadora com base apenas na descricao do item e no status.",
            "Nao cite anexos, figuras ou evidencias visuais que nao tenham sido fornecidos no prompt.",
            "Use as camadas complementares do workbook apenas como contexto estruturado de apoio, sem substituir os achados elegiveis do checklist.",
            "",
            f"Entidade analisada: {entity_name}",
            f"Tipo de entidade: {entity_type_label(payload.tipo_orgao) or 'Nao informado'}",
            f"Periodo da analise: {payload.periodo_analise or 'Nao informado'}",
            f"Grupos considerados: {', '.join(payload.grupos_permitidos)}",
            (
                "Abas consolidadas: "
                + ", ".join(payload.parser_options.checklist_sheet_names)
                if payload.parser_options.checklist_sheet_names
                else "Abas consolidadas: nao informadas"
            ),
            "",
            "Formato de saida desejado:",
            "1. RESULTADOS OBTIDOS",
            "   - Subsecao por fonte monitorada",
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
            "Camadas complementares do workbook:",
            *self._format_context_layers(payload),
            "",
            "Apontamentos estruturados:",
        ]

        sections: list[str] = []
        for source_key in SOURCE_ORDER:
            items = grouped.get(source_key, [])
            sections.append(f"## {source_label(source_key)}")
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

    def _format_context_layers(self, payload: ChecklistParseResult) -> list[str]:
        if not payload.context_layers:
            return ["- Nenhuma camada complementar estruturada foi extraida do workbook."]

        lines: list[str] = []
        for layer in payload.context_layers:
            lines.append(
                f"- {layer.title} | tipo={layer.layer_type} | aba={layer.sheet_name} | resumo={layer.summary}"
            )
            for detail in layer.details[:4]:
                lines.append(f"  detalhe: {detail}")
            for reference in layer.references[:4]:
                lines.append(f"  referencia: {reference}")
        return lines

    def _build_financial_prompt(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None:
            return ""

        lines = [
            "Voce e um analista financeiro encarregado de redigir um demonstrativo gerencial em portugues.",
            "Use apenas os dados consolidados abaixo.",
            "Nao invente receitas, despesas, saldos, centros de custo ou justificativas que nao estejam no material.",
            "Nao presuma regime contabil, enquadramento fiscal ou classificacoes externas nao informadas.",
            "Estruture a resposta com foco em DRE gerencial, leitura mensal e observacoes operacionais.",
            "",
            f"Entidade analisada: {entity_display_name(payload.orgao, payload.tipo_orgao)}",
            f"Arquivos fonte consolidados: {analysis.source_workbook_count}",
            f"Periodo consolidado: {payload.periodo_analise or 'Nao informado'}",
            (
                "Abas consolidadas: "
                + ", ".join(payload.parser_options.checklist_sheet_names)
                if payload.parser_options.checklist_sheet_names
                else "Abas consolidadas: nao informadas"
            ),
            f"Periodos identificados: {len(analysis.months)}",
            f"Lancamentos estruturados: {analysis.entry_count}",
            "",
            "Formato de saida desejado:",
            "1. VISAO EXECUTIVA",
            "2. DRE CONSOLIDADA",
            "3. RECEBIMENTOS POR CLIENTE",
            "4. RECEBIMENTOS POR CONTRATO",
            "5. RESULTADO POR PERIODO",
            "6. CUSTOS E DESPESAS RELEVANTES",
            "7. OBSERVACOES OPERACIONAIS",
            "",
            "Ao descrever cliente e contrato, deixe explicitos o rendimento acumulado do cliente no recorte, a distribuicao por periodo quando houver dados e o rendimento total acumulado por contrato.",
            "",
            "Linhas consolidadas da DRE:",
        ]

        if payload.database_summary:
            lines.extend(["Resumo persistido no banco:", payload.database_summary, ""])

        for line in analysis.dre_lines:
            suffix = ""
            if line.share_of_gross_revenue is not None:
                suffix = f" ({self._format_percent(line.share_of_gross_revenue)} da receita bruta)"
            lines.append(f"- {line.label}: {self._format_currency(line.amount)}{suffix}")

        lines.extend(
            [
                "",
                "Fechamento por periodo:",
            ]
        )
        for month in analysis.months:
            lines.append(
                f"- {month.period_label}: receita_base={self._format_currency(self._normalize_financial_amount(month.receivables_total))} | "
                f"custos_despesas={self._format_currency(self._normalize_financial_amount(month.global_expenses_total))} | "
                f"resultado={self._format_currency(month.net_result)} | pendencias={month.pending_entry_count}"
            )
            for section in month.sections[:8]:
                lines.append(
                    f"  secao: {section.title} | owner={section.owner_label or 'Consolidado'} | "
                    f"total={self._format_currency(section.total_amount)} | itens={section.entry_count}"
                )

        if analysis.client_rollups:
            lines.extend(["", "Rendimento por cliente:"])
            for client in analysis.client_rollups[:15]:
                lines.append(
                    f"- cliente={client.client_name} | rendimento={self._format_currency(client.total_received_amount)} | "
                    f"previsto={self._format_currency(client.total_expected_amount)} | "
                    f"pendente={self._format_currency(client.total_pending_amount)} | "
                    f"contratos={client.contract_count}"
                )

        if analysis.client_period_rollups:
            lines.extend(["", "Rendimento por cliente e periodo:"])
            for entry in analysis.client_period_rollups[:40]:
                lines.append(
                    f"- cliente={entry.client_name} | periodo={entry.period_label} | "
                    f"rendimento={self._format_currency(entry.total_received_amount)} | "
                    f"previsto={self._format_currency(entry.total_expected_amount)} | "
                    f"pendente={self._format_currency(entry.total_pending_amount)} | "
                    f"contratos={entry.contract_count}"
                )

        if analysis.contract_rollups:
            lines.extend(["", "Recebimentos por contrato:"])
            for contract in analysis.contract_rollups[:20]:
                lines.append(
                    f"- contrato={contract.contract_label} | cliente={contract.client_name or '-'} | "
                    f"recebido={self._format_currency(contract.total_received_amount)} | "
                    f"previsto={self._format_currency(contract.total_expected_amount)} | "
                    f"pendente={self._format_currency(contract.total_pending_amount)} | "
                    f"status={contract.latest_status or '-'} | "
                    f"periodos={', '.join(contract.months_covered[:6]) or '-'}"
                )

        if analysis.summary_notes:
            lines.extend(["", "Notas do parser financeiro:"])
            lines.extend(f"- {note}" for note in analysis.summary_notes[:12])

        lines.extend(["", "Camadas complementares do workbook:"])
        lines.extend(self._format_context_layers(payload))
        return "\n".join(lines).strip()

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _normalize_financial_amount(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return abs(float(value))

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value * 100:.1f}%".replace(".", ",")
