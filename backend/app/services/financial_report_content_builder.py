from __future__ import annotations

import json
from typing import Optional

from ..models import (
    ChecklistParseResult,
    GeneratedReportPayload,
    GenerationTrace,
    ReportBuildRequest,
    ReportSection,
)
from .financial_warehouse_store import FinancialWarehouseStore


class FinancialReportContentBuilder:
    def __init__(self, financial_warehouse_store: Optional[FinancialWarehouseStore] = None) -> None:
        self.financial_warehouse_store = financial_warehouse_store

    def build(self, payload: ChecklistParseResult) -> ReportBuildRequest:
        return self.build_with_trace(payload).report

    def build_with_trace(self, payload: ChecklistParseResult) -> GeneratedReportPayload:
        analysis = payload.financial_analysis
        if analysis is None:
            raise ValueError("Analise financeira nao encontrada no payload informado.")

        report = ReportBuildRequest(
            titulo_relatorio="Demonstrativo Financeiro e DRE",
            orgao=payload.orgao,
            tipo_orgao=payload.tipo_orgao,
            periodo_analise=payload.periodo_analise,
            sat_numero=payload.sat_numero,
            numero_relatorio=payload.numero_relatorio,
            promotoria=payload.promotoria,
            referencia=payload.referencia,
            solicitacao=payload.solicitacao,
            cidade_emissao=payload.cidade_emissao,
            data_emissao=payload.data_emissao,
            periodo_coleta=payload.periodo_coleta,
            equipe_tecnica=payload.equipe_tecnica,
            relatorio_contabil_referencia=payload.relatorio_contabil_referencia,
            secoes=[
                ReportSection(
                    fonte="nao_informada",
                    titulo="VISAO EXECUTIVA",
                    texto=self._build_executive_summary(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="DRE CONSOLIDADA",
                    texto=self._build_dre_text(payload),
                    table_headers=["Linha", "Valor", "% da receita bruta"],
                    table_rows=self._build_dre_table_rows(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="RECEBIMENTOS POR CLIENTE",
                    texto=self._build_client_rollup_text(payload),
                    table_headers=[
                        "Cliente",
                        "Inicio conhecido",
                        "Rendimento no recorte",
                        "Previsto",
                        "Pendente",
                        "Contratos",
                        "Maior contrato",
                        "Periodos",
                    ],
                    table_rows=self._build_client_table_rows(payload),
                ),
                self._build_client_map_section(payload),
                ReportSection(
                    fonte="nao_informada",
                    titulo="RECEBIMENTOS POR CONTRATO",
                    texto=self._build_contract_rollup_text(payload),
                    table_headers=[
                        "Contrato",
                        "Cliente",
                        "Inicio",
                        "Fim",
                        "Recebido",
                        "Previsto",
                        "Pendente",
                        "Status",
                        "Periodos",
                    ],
                    table_rows=self._build_contract_table_rows(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="RESULTADO POR PERIODO",
                    texto=self._build_monthly_text(payload),
                    table_headers=["Periodo", "Receita base", "Custos e despesas", "Resultado", "Pendencias", "Clientes destaque"],
                    table_rows=self._build_month_table_rows(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="CONCILIACAO PLANILHA E EXTRATO",
                    texto=self._build_reconciliation_text(payload),
                    table_headers=["Origem", "Status", "Quantidade", "Valor"],
                    table_rows=self._build_reconciliation_table_rows(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="CUSTOS E DESPESAS RELEVANTES",
                    texto=self._build_cost_structure_text(payload),
                ),
                ReportSection(
                    fonte="nao_informada",
                    titulo="OBSERVACOES OPERACIONAIS",
                    texto=self._build_operational_notes(payload),
                ),
            ],
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

    def decorate_report(self, report: ReportBuildRequest, payload: ChecklistParseResult) -> ReportBuildRequest:
        analysis = payload.financial_analysis
        if analysis is None:
            return report

        section_tables = {
            "DRE CONSOLIDADA": (["Linha", "Valor", "% da receita bruta"], self._build_dre_table_rows(payload)),
            "RECEBIMENTOS POR CLIENTE": (
                [
                    "Cliente",
                    "Inicio conhecido",
                    "Rendimento no recorte",
                    "Previsto",
                    "Pendente",
                    "Contratos",
                    "Maior contrato",
                    "Periodos",
                ],
                self._build_client_table_rows(payload),
            ),
            "RECEBIMENTOS POR CONTRATO": (
                ["Contrato", "Cliente", "Inicio", "Fim", "Recebido", "Previsto", "Pendente", "Status", "Periodos"],
                self._build_contract_table_rows(payload),
            ),
            "RESULTADO POR PERIODO": (
                ["Periodo", "Receita base", "Custos e despesas", "Resultado", "Pendencias", "Clientes destaque"],
                self._build_month_table_rows(payload),
            ),
            "CONCILIACAO PLANILHA E EXTRATO": (
                ["Origem", "Status", "Quantidade", "Valor"],
                self._build_reconciliation_table_rows(payload),
            ),
        }

        decorated_sections = []
        has_client_map = any(section.titulo == "MAPA DE CLIENTES" for section in report.secoes)
        for section in report.secoes:
            headers, rows = section_tables.get(section.titulo, (section.table_headers, section.table_rows))
            decorated_sections.append(
                section.model_copy(
                    update={
                        "table_headers": section.table_headers or headers,
                        "table_rows": section.table_rows or rows,
                    }
                )
            )
            if section.titulo == "RECEBIMENTOS POR CLIENTE" and not has_client_map:
                decorated_sections.append(self._build_client_map_section(payload))

        return report.model_copy(update={"secoes": decorated_sections})

    def _build_executive_summary(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None:
            return "Nenhuma analise financeira foi consolidada."

        periods = len(analysis.months)
        net_result = self._line_amount(analysis, "net_result")
        global_expenses = self._line_amount(analysis, "global_expenses")
        operating_inflows = self._line_amount(analysis, "operating_inflows")
        open_receivables = self._line_amount(analysis, "open_receivables")
        worst_month = min(analysis.months, key=lambda month: month.net_result or 0.0, default=None)
        best_month = max(analysis.months, key=lambda month: month.net_result or 0.0, default=None)
        result_share = self._line_share(analysis, "net_result")
        expense_share = self._line_share(analysis, "global_expenses")
        client_rows = self._list_canonical_client_rows(payload)
        contract_rows = self._list_canonical_contract_rows(payload)
        top_client = client_rows[0] if client_rows else None
        top_contract = contract_rows[0] if contract_rows else None
        client_period_entries = len(analysis.client_period_rollups)

        paragraphs = [
            (
                f"O demonstrativo consolidou {periods} periodo(s) financeiro(s) "
                f"de {analysis.source_workbook_count} arquivo(s) fonte, com entradas "
                f"operacionais de {self._format_currency(operating_inflows)}, custos e despesas de "
                f"{self._format_currency(global_expenses)}"
                f"{self._format_share_suffix(expense_share)} e resultado consolidado de "
                f"{self._format_currency(net_result)}{self._format_share_suffix(result_share)}."
            )
        ]
        if open_receivables is not None:
            paragraphs.append(
                f"A carteira em aberto ao fim do recorte somou {self._format_currency(open_receivables)}."
            )
        if top_client is not None:
            paragraphs.append(
                f"No recorte analisado, o cliente com maior rendimento acumulado foi {top_client['client_name']}, "
                f"com {self._format_currency(top_client['total_received_amount'])} distribuido(s) em {top_client['contract_count']} contrato(s)."
            )
        if top_contract is not None:
            paragraphs.append(
                f"O contrato de maior rendimento identificado foi {top_contract['contract_label']}, "
                f"com recebimento acumulado de {self._format_currency(top_contract['total_received_amount'])} no periodo."
            )
        reconciliation_snapshot = self._build_reconciliation_snapshot(payload)
        if reconciliation_snapshot is not None:
            paragraphs.append(
                "Na conciliacao entre planilha e extrato, "
                f"{reconciliation_snapshot['matched_workbook']} lancamento(s) da planilha ficaram confirmados, "
                f"{reconciliation_snapshot['probable_workbook']} ficaram como provavel(is) e "
                f"{reconciliation_snapshot['unmatched_workbook']} permaneceram sem pareamento suficiente."
            )
            if reconciliation_snapshot["alias_supported_workbook"] or reconciliation_snapshot["alias_supported_bank"]:
                paragraphs.append(
                    f"O dicionario canonico de aliases sustentou {reconciliation_snapshot['alias_supported_workbook']} "
                    f"pareamento(s) da planilha e {reconciliation_snapshot['alias_supported_bank']} do extrato."
                )
        if client_period_entries:
            paragraphs.append(
                f"Foram estruturadas {client_period_entries} entrada(s) de leitura cliente x periodo para detalhar a origem temporal dos recebimentos."
            )
        if best_month is not None and worst_month is not None:
            paragraphs.append(
                (
                    f"O melhor fechamento observado foi {best_month.period_label}, com resultado de "
                    f"{self._format_currency(best_month.net_result)}, enquanto o ponto de maior pressao "
                    f"foi {worst_month.period_label}, com resultado de {self._format_currency(worst_month.net_result)}."
                )
            )
        if analysis.detected_entities:
            paragraphs.append(
                "Os centros, contrapartes ou frentes mais recorrentes extraidos da planilha incluem "
                + ", ".join(analysis.detected_entities[:8])
                + "."
            )
        return "\n\n".join(paragraphs)

    def _build_dre_text(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None or not analysis.dre_lines:
            return "Nenhuma linha consolidada de DRE foi calculada."
        gross_revenue = self._line_amount(analysis, "gross_revenue")
        operating_inflows = self._line_amount(analysis, "operating_inflows")
        global_expenses = self._line_amount(analysis, "global_expenses")
        net_result = self._line_amount(analysis, "net_result")
        open_receivables = self._line_amount(analysis, "open_receivables")
        lines = [
            (
                f"A DRE consolidada abaixo resume receita operacional bruta de {self._format_currency(gross_revenue)}, "
                f"entradas operacionais consideradas de {self._format_currency(operating_inflows)}, "
                f"custos e despesas de {self._format_currency(global_expenses)} e resultado consolidado de "
                f"{self._format_currency(net_result)}."
            )
        ]
        if open_receivables is not None:
            lines.append(
                f"A carteira em aberto apurada ao fim do recorte permaneceu em {self._format_currency(open_receivables)}."
            )
        return "\n\n".join(lines)

    def _build_monthly_text(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None or not analysis.months:
            return "Nenhum periodo financeiro foi identificado."

        client_period_index = self._group_client_periods_by_period(analysis)
        best_month = max(analysis.months, key=lambda month: month.net_result or float("-inf"), default=None)
        worst_month = min(analysis.months, key=lambda month: month.net_result or float("inf"), default=None)
        paragraphs: list[str] = []
        if best_month is not None:
            paragraphs.append(
                f"O melhor fechamento do recorte foi {best_month.period_label}, com resultado de {self._format_currency(best_month.net_result)}."
            )
        if worst_month is not None:
            paragraphs.append(
                f"O periodo de maior pressao foi {worst_month.period_label}, com resultado de {self._format_currency(worst_month.net_result)}."
            )
        highlighted_months = [month for month in analysis.months if month.pending_entry_count or (month.net_result or 0) < 0][:4]
        for month in highlighted_months:
            paragraph = (
                f"{month.period_label}: receita base de {self._format_currency(self._normalize_financial_amount(month.receivables_total))}, "
                f"custos e despesas de {self._format_currency(self._normalize_financial_amount(month.global_expenses_total))} e "
                f"resultado de {self._format_currency(month.net_result)}."
            )
            if month.pending_entry_count:
                paragraph += f" O parser registrou {month.pending_entry_count} pendencia(s) operacional(is) aberta(s)."
            top_client_entries = client_period_index.get(month.period_label, [])[:2]
            if top_client_entries:
                client_summary = "; ".join(
                    f"{entry.client_name}: {self._format_currency(entry.total_received_amount)}"
                    for entry in top_client_entries
                )
                paragraph += f" Entradas relevantes do periodo: {client_summary}."
            trace_entries = self._list_trace_entries(payload, limit=2, period_label=month.period_label)
            if trace_entries:
                paragraph += " Base rastreavel: " + self._format_trace_entries(trace_entries) + "."
            paragraphs.append(paragraph)
        paragraphs.append("A tabela resume o fechamento mensal completo, com receita base, custos, resultado e pendencias.")
        return "\n\n".join(paragraphs)

    def _build_client_rollup_text(self, payload: ChecklistParseResult) -> str:
        client_rows = self._list_canonical_client_rows(payload)
        if not client_rows:
            return "Nenhum agrupamento por cliente foi consolidado."

        contract_index = self._group_contract_rows_by_client(self._list_canonical_contract_rows(payload))
        paragraphs: list[str] = []
        paragraphs.append(
            f"Foram consolidados {len(client_rows)} cliente(s) com rendimento estruturado no recorte. A tabela detalha o rendimento acumulado, o previsto e o pendente por cliente."
        )
        for client in client_rows[:4]:
            contracts = contract_index.get(self._client_row_key(client), [])
            first_start = self._resolve_first_contract_start(contracts)
            top_contract = contracts[0] if contracts else None
            start_suffix = (
                f" O primeiro inicio contratual conhecido foi {first_start}."
                if first_start
                else " O material nao trouxe uma data inicial explicita para todos os contratos desse cliente."
            )
            top_contract_suffix = (
                f" O contrato de maior rendimento foi {top_contract['contract_label']}, com {self._format_currency(top_contract['total_received_amount'])}."
                if top_contract is not None
                else ""
            )
            paragraphs.append(
                (
                    f"{client['client_name']}: gerou rendimento acumulado de {self._format_currency(client['total_received_amount'])} no recorte, "
                    f"com previsao consolidada de {self._format_currency(client['total_expected_amount'])} e saldo pendente "
                    f"de {self._format_currency(client['total_pending_amount'])}. "
                    f"Foram associados {client['contract_count']} contrato(s) ao cliente no recorte."
                    f"{start_suffix}{top_contract_suffix}"
                )
            )
            trace_entries = self._list_trace_entries(
                payload,
                limit=3,
                canonical_client_id=client["canonical_client_id"],
                client_name=client["client_name"],
            )
            if trace_entries:
                paragraphs.append(
                    "Rastreabilidade dos lancamentos: " + self._format_trace_entries(trace_entries) + "."
                )
        return "\n\n".join(paragraphs)

    def _build_contract_rollup_text(self, payload: ChecklistParseResult) -> str:
        contract_rows = self._list_canonical_contract_rows(payload)
        if not contract_rows:
            return "Nenhum agrupamento por contrato foi consolidado."

        paragraphs: list[str] = []
        paragraphs.append(
            f"Foram estruturados {len(contract_rows)} contrato(s) no recorte. A tabela apresenta o rendimento acumulado, o previsto, o pendente e o ultimo status observado."
        )
        for contract in contract_rows[:5]:
            start_label = self._humanize_date(contract["contract_start_date"])
            end_label = self._humanize_date(contract["contract_end_date"])
            start_suffix = (
                f" O inicio contratual conhecido foi {start_label}."
                if start_label
                else ""
            )
            end_suffix = (
                f" O termino contratual conhecido foi {end_label}."
                if end_label
                else ""
            )
            status_suffix = (
                f" O ultimo status observado foi {contract['latest_status']}."
                if contract["latest_status"]
                else ""
            )
            period_suffix = (
                " Periodos com ocorrencia: " + "; ".join(contract["months_covered"][:6]) + "."
                if contract["months_covered"]
                else ""
            )
            paragraphs.append(
                (
                    f"{contract['contract_label']}: rendimento acumulado de {self._format_currency(contract['total_received_amount'])} no recorte, "
                    f"valor previsto de {self._format_currency(contract['total_expected_amount'])} e pendencia de "
                    f"{self._format_currency(contract['total_pending_amount'])}.{start_suffix}{end_suffix}{period_suffix}{status_suffix}"
                )
            )
            trace_entries = self._list_trace_entries(
                payload,
                limit=3,
                canonical_contract_id=contract["canonical_contract_id"],
                contract_label=contract["contract_label"],
            )
            if trace_entries:
                paragraphs.append(
                    "Lancamentos rastreaveis do contrato: " + self._format_trace_entries(trace_entries) + "."
                )
        return "\n\n".join(paragraphs)

    def _build_cost_structure_text(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None or not analysis.months:
            return "A estrutura de custos nao foi consolidada."

        paragraphs: list[str] = []
        for month in analysis.months:
            ranked_sections = sorted(
                (
                    section
                    for section in month.sections
                    if section.total_amount is not None and section.section_key in {"tax", "personnel", "fixed_cost", "operating_cost"}
                ),
                key=lambda section: abs(section.total_amount or 0.0),
                reverse=True,
            )
            if not ranked_sections:
                continue
            details = "; ".join(
                f"{section.title} ({section.owner_label or 'Consolidado'}): {self._format_currency(self._normalize_financial_amount(section.total_amount))}"
                for section in ranked_sections[:4]
            )
            paragraphs.append(f"{month.period_label}: {details}.")
        return "\n\n".join(paragraphs) or "Nenhum bloco de custos estruturado foi encontrado."

    def _build_operational_notes(self, payload: ChecklistParseResult) -> str:
        analysis = payload.financial_analysis
        if analysis is None:
            return "Nenhuma observacao operacional foi consolidada."

        notes = list(analysis.summary_notes)
        notes.extend(payload.warnings)
        if not notes:
            return "O parser nao registrou observacoes adicionais para este demonstrativo."
        return "\n".join(f"- {note}" for note in notes[:16])

    def _build_reconciliation_text(self, payload: ChecklistParseResult) -> str:
        snapshot = self._build_reconciliation_snapshot(payload)
        if snapshot is None:
            return "Este recorte nao trouxe base suficiente para conciliar planilha e extrato bancario no mesmo demonstrativo."

        paragraphs = [
            "A conciliacao compara os lancamentos elegiveis da planilha com os movimentos do extrato no mesmo periodo, considerando valor, tipo, data e proximidade operacional."
        ]
        paragraphs.append(
            f"Base elegivel: {snapshot['eligible_workbook']} lancamento(s) da planilha e {snapshot['eligible_bank']} movimento(s) do extrato."
        )
        paragraphs.append(
            f"Resultado da planilha: {snapshot['matched_workbook']} confirmado(s), {snapshot['probable_workbook']} provavel(is), "
            f"{snapshot['unmatched_workbook']} sem pareamento e {snapshot['excluded_workbook']} fora do escopo."
        )
        paragraphs.append(
            f"Resultado do extrato: {snapshot['matched_bank']} confirmado(s), {snapshot['probable_bank']} provavel(is), "
            f"{snapshot['unmatched_bank']} sem pareamento e {snapshot['excluded_bank']} fora do escopo."
        )
        if snapshot["alias_supported_workbook"] or snapshot["alias_supported_bank"]:
            paragraphs.append(
                f"O dicionario canonico de aliases apoiou {snapshot['alias_supported_workbook']} pareamento(s) da planilha "
                f"e {snapshot['alias_supported_bank']} do extrato, ajudando a vincular nomes bancarios ao cliente ou contrato correto."
            )
        if snapshot["matched_samples"]:
            paragraphs.append("Amostras confirmadas: " + "; ".join(snapshot["matched_samples"]) + ".")
        if snapshot["alias_supported_samples"]:
            paragraphs.append(
                "Amostras apoiadas por alias canônico: " + "; ".join(snapshot["alias_supported_samples"]) + "."
            )
        if snapshot["unmatched_samples"]:
            paragraphs.append("Amostras sem pareamento: " + "; ".join(snapshot["unmatched_samples"]) + ".")
        return "\n\n".join(paragraphs)

    def _build_client_map_section(self, payload: ChecklistParseResult) -> ReportSection:
        return ReportSection(
            fonte="nao_informada",
            titulo="MAPA DE CLIENTES",
            texto=self._build_client_map_text(payload),
            table_headers=[
                "Cliente",
                "Inicio conhecido",
                "Rendimento no recorte",
                "Maior contrato",
                "Rendimento do maior contrato",
                "Periodos ativos",
            ],
            table_rows=self._build_client_map_table_rows(payload),
        )

    def _build_client_map_text(self, payload: ChecklistParseResult) -> str:
        client_rows = self._list_canonical_client_rows(payload)
        if not client_rows:
            return "Nenhum cliente elegivel foi consolidado para o mapa analitico."

        contract_index = self._group_contract_rows_by_client(self._list_canonical_contract_rows(payload))
        paragraphs = [
            "O mapa de clientes resume, para cada cliente relevante, quando a locacao passou a aparecer na base, quanto o cliente rendeu no recorte e qual contrato concentrou o maior rendimento."
        ]
        for client in client_rows[:6]:
            contracts = contract_index.get(self._client_row_key(client), [])
            first_start = self._resolve_first_contract_start(contracts) or "nao identificado"
            top_contract = contracts[0] if contracts else None
            top_contract_label = top_contract["contract_label"] if top_contract is not None else "nao identificado"
            top_contract_amount = (
                self._format_currency(top_contract["total_received_amount"]) if top_contract is not None else "-"
            )
            active_periods = self._compress_labels(client["months_covered"], limit=5)
            paragraphs.append(
                (
                    f"{client['client_name']}: inicio conhecido em {first_start}; rendimento acumulado de "
                    f"{self._format_currency(client['total_received_amount'])} no recorte; maior contrato "
                    f"{top_contract_label}, com {top_contract_amount}; periodos ativos {active_periods}."
                )
            )
            trace_entries = self._list_trace_entries(
                payload,
                limit=2,
                canonical_client_id=client["canonical_client_id"],
                client_name=client["client_name"],
            )
            if trace_entries:
                paragraphs.append(
                    "Amostras de lancamento: " + self._format_trace_entries(trace_entries) + "."
                )
            alias_trace_entries = [entry for entry in trace_entries if entry.get("reconciliation_alias_label")]
            if alias_trace_entries:
                paragraphs.append(
                    "Pareamentos apoiados por alias canônico: "
                    + self._format_alias_trace_entries(alias_trace_entries)
                    + "."
                )
        return "\n\n".join(paragraphs)

    def _build_dre_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        analysis = payload.financial_analysis
        if analysis is None:
            return []
        return [
            [
                line.label,
                self._format_currency(line.amount),
                self._format_percent(line.share_of_gross_revenue),
            ]
            for line in analysis.dre_lines
        ]

    def _build_client_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        client_rows = self._list_canonical_client_rows(payload)
        contract_index = self._group_contract_rows_by_client(self._list_canonical_contract_rows(payload))
        return [
            [
                client["client_name"],
                self._resolve_first_contract_start(contract_index.get(self._client_row_key(client), [])) or "-",
                self._format_currency(client["total_received_amount"]),
                self._format_currency(client["total_expected_amount"]),
                self._format_currency(client["total_pending_amount"]),
                str(client["contract_count"]),
                self._format_top_contract_label(contract_index.get(self._client_row_key(client), [])),
                self._compress_labels(client["months_covered"], limit=4),
            ]
            for client in client_rows[:20]
        ]

    def _build_contract_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        contract_rows = self._list_canonical_contract_rows(payload)
        return [
            [
                contract["contract_label"],
                contract["client_name"] or "-",
                self._humanize_date(contract["contract_start_date"]) or "-",
                self._humanize_date(contract["contract_end_date"]) or "-",
                self._format_currency(contract["total_received_amount"]),
                self._format_currency(contract["total_expected_amount"]),
                self._format_currency(contract["total_pending_amount"]),
                contract["latest_status"] or "-",
                self._compress_labels(contract["months_covered"], limit=4),
            ]
            for contract in contract_rows[:24]
        ]

    def _build_month_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        analysis = payload.financial_analysis
        if analysis is None:
            return []
        client_period_index = self._group_client_periods_by_period(analysis)
        rows: list[list[str]] = []
        for month in analysis.months:
            top_clients = client_period_index.get(month.period_label, [])[:2]
            rows.append(
                [
                    month.period_label,
                    self._format_currency(self._normalize_financial_amount(month.receivables_total)),
                    self._format_currency(self._normalize_financial_amount(month.global_expenses_total)),
                    self._format_currency(month.net_result),
                    str(month.pending_entry_count),
                    self._compress_labels(
                        [f"{entry.client_name} ({self._format_currency(entry.total_received_amount)})" for entry in top_clients],
                        limit=2,
                    ),
                ]
            )
        return rows

    def _build_reconciliation_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        snapshot = self._build_reconciliation_snapshot(payload)
        if snapshot is None:
            return []
        rows = [
            ["Planilha", "Confirmado", str(snapshot["matched_workbook"]), self._format_currency(snapshot["matched_workbook_amount"])],
            ["Planilha", "Provável", str(snapshot["probable_workbook"]), self._format_currency(snapshot["probable_workbook_amount"])],
            ["Planilha", "Sem pareamento", str(snapshot["unmatched_workbook"]), self._format_currency(snapshot["unmatched_workbook_amount"])],
            ["Planilha", "Fora do escopo", str(snapshot["excluded_workbook"]), self._format_currency(snapshot["excluded_workbook_amount"])],
            ["Extrato", "Confirmado", str(snapshot["matched_bank"]), self._format_currency(snapshot["matched_bank_amount"])],
            ["Extrato", "Provável", str(snapshot["probable_bank"]), self._format_currency(snapshot["probable_bank_amount"])],
            ["Extrato", "Sem pareamento", str(snapshot["unmatched_bank"]), self._format_currency(snapshot["unmatched_bank_amount"])],
            ["Extrato", "Fora do escopo", str(snapshot["excluded_bank"]), self._format_currency(snapshot["excluded_bank_amount"])],
        ]
        if snapshot["alias_supported_workbook"] or snapshot["alias_supported_bank"]:
            rows.extend(
                [
                    [
                        "Planilha",
                        "Com alias canônico",
                        str(snapshot["alias_supported_workbook"]),
                        self._format_currency(snapshot["alias_supported_workbook_amount"]),
                    ],
                    [
                        "Extrato",
                        "Com alias canônico",
                        str(snapshot["alias_supported_bank"]),
                        self._format_currency(snapshot["alias_supported_bank_amount"]),
                    ],
                ]
            )
        return rows

    def _build_client_map_table_rows(self, payload: ChecklistParseResult) -> list[list[str]]:
        client_rows = self._list_canonical_client_rows(payload)
        contract_index = self._group_contract_rows_by_client(self._list_canonical_contract_rows(payload))
        rows: list[list[str]] = []
        for client in client_rows[:20]:
            contracts = contract_index.get(self._client_row_key(client), [])
            top_contract = contracts[0] if contracts else None
            rows.append(
                [
                    client["client_name"],
                    self._resolve_first_contract_start(contracts) or "-",
                    self._format_currency(client["total_received_amount"]),
                    top_contract["contract_label"] if top_contract is not None else "-",
                    self._format_currency(top_contract["total_received_amount"] if top_contract is not None else None),
                    self._compress_labels(client["months_covered"], limit=5),
                ]
            )
        return rows

    def _list_trace_entries(
        self,
        payload: ChecklistParseResult,
        limit: int,
        client_name: Optional[str] = None,
        contract_label: Optional[str] = None,
        period_label: Optional[str] = None,
        canonical_client_id: Optional[int] = None,
        canonical_contract_id: Optional[int] = None,
    ) -> list[dict[str, object]]:
        if self.financial_warehouse_store is None or payload.analysis_id is None:
            return []
        try:
            return self.financial_warehouse_store.list_entries(
                payload.analysis_id,
                limit=limit,
                client_name=client_name,
                contract_label=contract_label,
                period_label=period_label,
                canonical_client_id=canonical_client_id,
                canonical_contract_id=canonical_contract_id,
            )
        except Exception:
            return []

    def _list_reconciliation_entries(self, payload: ChecklistParseResult) -> list:
        if self.financial_warehouse_store is not None and payload.analysis_id is not None:
            try:
                rows = self.financial_warehouse_store.list_entries(payload.analysis_id, limit=10000)
            except Exception:
                rows = []
            if rows:
                return rows

        analysis = payload.financial_analysis
        if analysis is None:
            return []

        entries: list = []
        for month in analysis.months:
            for section in month.sections:
                entries.extend(section.entries)
        return entries

    def _build_reconciliation_snapshot(self, payload: ChecklistParseResult) -> Optional[dict[str, object]]:
        entries = self._list_reconciliation_entries(payload)
        if not entries:
            return None

        workbook_entries = []
        bank_entries = []
        for entry in entries:
            source_kind = self._entry_value(entry, "source_kind") or self._source_kind_from_tags(
                self._entry_value(entry, "tags") or []
            )
            if source_kind == "workbook":
                workbook_entries.append(entry)
            elif source_kind == "bank_statement":
                bank_entries.append(entry)

        if not workbook_entries or not bank_entries:
            return None

        snapshot = {
            "eligible_workbook": 0,
            "eligible_bank": 0,
            "matched_workbook": 0,
            "probable_workbook": 0,
            "unmatched_workbook": 0,
            "excluded_workbook": 0,
            "matched_bank": 0,
            "probable_bank": 0,
            "unmatched_bank": 0,
            "excluded_bank": 0,
            "matched_workbook_amount": 0.0,
            "probable_workbook_amount": 0.0,
            "unmatched_workbook_amount": 0.0,
            "excluded_workbook_amount": 0.0,
            "matched_bank_amount": 0.0,
            "probable_bank_amount": 0.0,
            "unmatched_bank_amount": 0.0,
            "excluded_bank_amount": 0.0,
            "alias_supported_workbook": 0,
            "alias_supported_bank": 0,
            "alias_supported_workbook_amount": 0.0,
            "alias_supported_bank_amount": 0.0,
            "matched_samples": [],
            "alias_supported_samples": [],
            "unmatched_samples": [],
        }

        self._accumulate_reconciliation_side(snapshot, workbook_entries, "workbook")
        self._accumulate_reconciliation_side(snapshot, bank_entries, "bank")

        return snapshot

    def _accumulate_reconciliation_side(self, snapshot: dict[str, object], entries: list, side: str) -> None:
        samples_key = "matched_samples" if side == "workbook" else None
        alias_samples_key = "alias_supported_samples" if side == "workbook" else None
        unmatched_samples_key = "unmatched_samples" if side == "workbook" else None
        for entry in entries:
            status = self._entry_value(entry, "reconciliation_status") or "excluded"
            amount = self._normalize_financial_amount(self._entry_value(entry, "amount")) or 0.0
            alias_label = self._entry_value(entry, "reconciliation_alias_label")
            if status != "excluded":
                snapshot[f"eligible_{side}"] = int(snapshot[f"eligible_{side}"]) + 1
            snapshot[f"{status}_{side}"] = int(snapshot.get(f"{status}_{side}", 0)) + 1
            snapshot[f"{status}_{side}_amount"] = float(snapshot.get(f"{status}_{side}_amount", 0.0)) + amount
            if alias_label and status in {"matched", "probable"}:
                snapshot[f"alias_supported_{side}"] = int(snapshot.get(f"alias_supported_{side}", 0)) + 1
                snapshot[f"alias_supported_{side}_amount"] = float(
                    snapshot.get(f"alias_supported_{side}_amount", 0.0)
                ) + amount

            if samples_key and status == "matched" and len(snapshot[samples_key]) < 3:
                snapshot[samples_key].append(self._format_reconciliation_sample(entry))
            if alias_samples_key and alias_label and status in {"matched", "probable"} and len(snapshot[alias_samples_key]) < 3:
                snapshot[alias_samples_key].append(self._format_alias_supported_sample(entry))
            if unmatched_samples_key and status == "unmatched" and len(snapshot[unmatched_samples_key]) < 3:
                snapshot[unmatched_samples_key].append(self._format_reconciliation_sample(entry))

    def _format_reconciliation_sample(self, entry) -> str:
        label = (
            self._entry_value(entry, "counterparty")
            or self._entry_value(entry, "contract_label")
            or self._entry_value(entry, "description")
            or "-"
        )
        return f"{label} ({self._format_currency(self._entry_value(entry, 'amount'))})"

    def _format_alias_supported_sample(self, entry) -> str:
        base = self._format_reconciliation_sample(entry)
        alias_label = self._entry_value(entry, "reconciliation_alias_label") or "-"
        return f"{base} via alias '{alias_label}'"

    def _source_kind_from_tags(self, tags: list[str]) -> Optional[str]:
        for tag in tags or []:
            if tag.startswith("source_kind:"):
                return tag.split(":", 1)[1]
        return None

    def _entry_value(self, entry, key: str):
        if isinstance(entry, dict):
            return entry.get(key)
        return getattr(entry, key, None)

    def _format_trace_entries(self, entries: list[dict[str, object]]) -> str:
        chunks: list[str] = []
        for entry in entries:
            description = str(entry.get("description") or "-")
            period_label = str(entry.get("period_label") or "-")
            amount = self._format_currency(entry.get("amount"))
            counterparty = str(entry.get("counterparty") or "").strip()
            prefix = f"{period_label} - "
            if counterparty and counterparty.lower() not in description.lower():
                prefix += f"{counterparty}: "
            chunks.append(prefix + f"{description} ({amount})")
        return "; ".join(chunks)

    def _format_alias_trace_entries(self, entries: list[dict[str, object]]) -> str:
        chunks: list[str] = []
        for entry in entries:
            description = str(entry.get("description") or "-")
            period_label = str(entry.get("period_label") or "-")
            amount = self._format_currency(entry.get("amount"))
            alias_label = str(entry.get("reconciliation_alias_label") or "-")
            chunks.append(f"{period_label} - {description} ({amount}) via alias '{alias_label}'")
        return "; ".join(chunks)

    def _group_client_periods_by_client(self, analysis) -> dict[str, list]:
        by_client: dict[str, list] = {}
        for entry in analysis.client_period_rollups:
            by_client.setdefault(entry.client_name.casefold(), []).append(entry)
        return by_client

    def _list_canonical_client_rows(self, payload: ChecklistParseResult) -> list[dict[str, object]]:
        if self.financial_warehouse_store is not None and payload.analysis_id is not None:
            try:
                rows = self.financial_warehouse_store.list_top_clients(payload.analysis_id, limit=500)
            except Exception:
                rows = []
            if rows:
                return [self._normalize_client_row(row) for row in rows]

        analysis = payload.financial_analysis
        if analysis is None:
            return []
        return [
            self._normalize_client_row(
                {
                    "canonical_client_id": client.canonical_client_id,
                    "canonical_client_name": client.canonical_client_name,
                    "client_name": client.client_name,
                    "total_received_amount": client.total_received_amount,
                    "total_expected_amount": client.total_expected_amount,
                    "total_pending_amount": client.total_pending_amount,
                    "contract_count": client.contract_count,
                    "months_covered_json": client.months_covered,
                    "contract_labels_json": client.contract_labels,
                }
            )
            for client in analysis.client_rollups
        ]

    def _list_canonical_contract_rows(self, payload: ChecklistParseResult) -> list[dict[str, object]]:
        if self.financial_warehouse_store is not None and payload.analysis_id is not None:
            try:
                rows = self.financial_warehouse_store.list_top_contracts(payload.analysis_id, limit=500)
            except Exception:
                rows = []
            if rows:
                return [self._normalize_contract_row(row) for row in rows]

        analysis = payload.financial_analysis
        if analysis is None:
            return []
        return [
            self._normalize_contract_row(
                {
                    "canonical_client_id": contract.canonical_client_id,
                    "canonical_client_name": contract.canonical_client_name,
                    "canonical_contract_id": contract.canonical_contract_id,
                    "canonical_contract_name": contract.canonical_contract_name,
                    "contract_label": contract.contract_label,
                    "client_name": contract.client_name,
                    "unit": contract.unit,
                    "contract_start_date": contract.contract_start_date,
                    "contract_end_date": contract.contract_end_date,
                    "latest_status": contract.latest_status,
                    "total_received_amount": contract.total_received_amount,
                    "total_expected_amount": contract.total_expected_amount,
                    "total_pending_amount": contract.total_pending_amount,
                    "entry_count": contract.entry_count,
                    "months_covered_json": contract.months_covered,
                    "source_sheet_names_json": contract.source_sheet_names,
                }
            )
            for contract in analysis.contract_rollups
        ]

    def _normalize_client_row(self, row: dict[str, object]) -> dict[str, object]:
        client_name = str(row.get("canonical_client_name") or row.get("client_name") or "-")
        return {
            "canonical_client_id": row.get("canonical_client_id"),
            "client_name": client_name,
            "raw_client_name": str(row.get("client_name") or client_name),
            "total_received_amount": float(row.get("total_received_amount") or 0.0),
            "total_expected_amount": float(row.get("total_expected_amount") or 0.0),
            "total_pending_amount": float(row.get("total_pending_amount") or 0.0),
            "contract_count": int(row.get("contract_count") or 0),
            "months_covered": self._parse_json_list(row.get("months_covered_json")),
            "contract_labels": self._parse_json_list(row.get("contract_labels_json")),
        }

    def _normalize_contract_row(self, row: dict[str, object]) -> dict[str, object]:
        client_name = str(row.get("canonical_client_name") or row.get("client_name") or "-")
        contract_name = str(row.get("canonical_contract_name") or row.get("contract_label") or "-")
        return {
            "canonical_client_id": row.get("canonical_client_id"),
            "client_name": client_name,
            "raw_client_name": str(row.get("client_name") or client_name),
            "canonical_contract_id": row.get("canonical_contract_id"),
            "contract_label": contract_name,
            "raw_contract_label": str(row.get("contract_label") or contract_name),
            "unit": row.get("unit"),
            "contract_start_date": row.get("contract_start_date"),
            "contract_end_date": row.get("contract_end_date"),
            "latest_status": row.get("latest_status"),
            "total_received_amount": float(row.get("total_received_amount") or 0.0),
            "total_expected_amount": float(row.get("total_expected_amount") or 0.0),
            "total_pending_amount": float(row.get("total_pending_amount") or 0.0),
            "entry_count": int(row.get("entry_count") or 0),
            "months_covered": self._parse_json_list(row.get("months_covered_json")),
            "source_sheet_names": self._parse_json_list(row.get("source_sheet_names_json")),
        }

    def _parse_json_list(self, raw_value: object) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return [str(value) for value in raw_value if value not in {None, ""}]
        if isinstance(raw_value, str):
            cleaned = raw_value.strip()
            if not cleaned:
                return []
            if cleaned.startswith("["):
                try:
                    parsed = json.loads(cleaned)
                except (TypeError, ValueError):
                    return [cleaned]
                if isinstance(parsed, list):
                    return [str(value) for value in parsed if value not in {None, ""}]
            return [cleaned]
        return [str(raw_value)]

    def _client_row_key(self, row: dict[str, object]) -> str:
        canonical_id = row.get("canonical_client_id")
        if canonical_id is not None:
            return f"id:{canonical_id}"
        return str(row.get("client_name") or "-").casefold()

    def _group_contract_rows_by_client(self, contract_rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
        by_client: dict[str, list[dict[str, object]]] = {}
        for contract in contract_rows:
            by_client.setdefault(self._client_row_key(contract), []).append(contract)
        for key, contracts in by_client.items():
            by_client[key] = sorted(
                contracts,
                key=lambda item: (-float(item["total_received_amount"]), str(item["contract_start_date"] or ""), str(item["contract_label"]).lower()),
            )
        return by_client

    def _group_client_periods_by_period(self, analysis) -> dict[str, list]:
        by_period: dict[str, list] = {}
        for entry in analysis.client_period_rollups:
            by_period.setdefault(entry.period_label, []).append(entry)
        for key, entries in by_period.items():
            by_period[key] = sorted(
                entries,
                key=lambda item: (-item.total_received_amount, -item.total_expected_amount, item.client_name.lower()),
            )
        return by_period

    def _compress_labels(self, labels: list[str], limit: int = 3) -> str:
        cleaned = [label for label in labels if label]
        if not cleaned:
            return "-"
        if len(cleaned) <= limit:
            return "; ".join(cleaned)
        remaining = len(cleaned) - limit
        return "; ".join(cleaned[:limit]) + f" (+{remaining})"

    def _resolve_first_contract_start(self, contracts: list) -> Optional[str]:
        dated_contracts = [str(contract["contract_start_date"]) for contract in contracts if contract.get("contract_start_date")]
        if not dated_contracts:
            return None
        sortable = []
        for value in dated_contracts:
            sort_key = self._parse_date_sort_key(value)
            sortable.append((sort_key, value))
        sortable.sort(key=lambda item: item[0])
        return self._humanize_date(sortable[0][1])

    def _format_top_contract_label(self, contracts: list) -> str:
        if not contracts:
            return "-"
        top_contract = contracts[0]
        return f"{top_contract['contract_label']} ({self._format_currency(top_contract['total_received_amount'])})"

    def _parse_date_sort_key(self, value: str) -> tuple[int, int, int, str]:
        cleaned = self._normalize_date_text(value)
        if not cleaned:
            return (9999, 99, 99, "")
        if "-" in cleaned:
            parts = cleaned.split("-")
            if len(parts) == 3 and all(part.isdigit() for part in parts):
                year, month, day = parts
                return (int(year), int(month), int(day), cleaned)
        if "/" in cleaned:
            parts = cleaned.split("/")
            if len(parts) == 3 and all(part.isdigit() for part in parts):
                day, month, year = parts
                return (int(year), int(month), int(day), cleaned)
        return (9999, 99, 99, cleaned.lower())

    def _humanize_date(self, value: Optional[str]) -> Optional[str]:
        cleaned = self._normalize_date_text(value)
        if not cleaned:
            return None
        if "-" in cleaned:
            parts = cleaned.split("-")
            if len(parts) == 3 and all(part.isdigit() for part in parts):
                year, month, day = parts
                return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        if "/" in cleaned:
            parts = cleaned.split("/")
            if len(parts) == 3 and all(part.isdigit() for part in parts):
                day, month, year = parts
                return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        return cleaned

    def _normalize_date_text(self, value: Optional[str]) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        if "/" in cleaned:
            parts = cleaned.split("/")
            if len(parts) == 3:
                day, month, year = parts
                if day.isdigit() and month.isdigit() and year.isdigit():
                    normalized_month = str(int(month)).zfill(2)
                    normalized_day = str(int(day)).zfill(2)
                    return f"{normalized_day}/{normalized_month}/{year}"
        return cleaned

    def _line_amount(self, analysis, key: str) -> Optional[float]:
        for line in analysis.dre_lines:
            if line.key == key:
                return line.amount
        return None

    def _line_share(self, analysis, key: str) -> Optional[float]:
        for line in analysis.dre_lines:
            if line.key == key:
                return line.share_of_gross_revenue
        return None

    def _normalize_financial_amount(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return abs(float(value))

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value * 100:.1f}%".replace(".", ",")

    def _format_share_suffix(self, value: Optional[float]) -> str:
        if value is None:
            return ""
        return f" ({self._format_percent(value)} da receita bruta)"

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
