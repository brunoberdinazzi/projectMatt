from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from ..models import ChecklistItem, ChecklistParseResult, ScrapedLink, ScrapedPageRecord, WorkbookContextLayer
from .report_terms import entity_display_name, entity_type_label, source_label


class AnalysisContextBuilder:
    def build_summary(self, parsed: ChecklistParseResult) -> str:
        if parsed.financial_analysis is not None:
            return self._build_financial_summary(parsed)

        parts = [
            self._build_header(parsed),
            self._build_items_block(parsed.itens_processados),
            self._build_context_layers_block(parsed.context_layers),
            self._build_scraping_block(parsed.scraped_pages),
        ]

        warning_block = self._build_warning_block(parsed.warnings)
        if warning_block:
            parts.append(warning_block)

        return "\n\n".join(part for part in parts if part)

    def _build_header(self, parsed: ChecklistParseResult) -> str:
        entity_name = entity_display_name(parsed.orgao, parsed.tipo_orgao)
        lines = [
            f"Analise registrada para {entity_name}.",
            f"Tipo de entidade: {entity_type_label(parsed.tipo_orgao) or 'nao informado'}.",
            f"Periodo da analise: {parsed.periodo_analise or 'nao informado'}.",
            f"SAT: {parsed.sat_numero or 'nao identificado'}.",
            (
                "Escopo do parser: perfil "
                f"{parsed.parser_options.profile}, grupos {', '.join(parsed.parser_options.allowed_groups)}, "
                f"status {', '.join(parsed.parser_options.allowed_status)}."
            ),
        ]
        if parsed.parser_options.checklist_sheet_names:
            lines.append(
                "Abas consolidadas: "
                + ", ".join(parsed.parser_options.checklist_sheet_names)
                + "."
            )
        source_lines = []
        if parsed.site_url:
            source_lines.append(f"{source_label('site_orgao')}: {parsed.site_url}")
        if parsed.portal_url:
            source_lines.append(f"{source_label('portal_transparencia')}: {parsed.portal_url}")
        if parsed.esic_url:
            source_lines.append(f"{source_label('esic')}: {parsed.esic_url}")
        if source_lines:
            lines.append("Fontes principais: " + " | ".join(source_lines) + ".")
        if parsed.reference_links:
            selected_count = sum(1 for link in parsed.reference_links if link.selected_for_crawl)
            lines.append(
                f"Links referenciais do workbook: {len(parsed.reference_links)} identificado(s), "
                f"{selected_count} usado(s) como semente do crawler."
            )
        return " ".join(lines)

    def _build_items_block(self, items: list[ChecklistItem]) -> str:
        if not items:
            return "Achados do checklist: nao foram encontrados itens elegiveis no recorte atual."

        grouped: dict[str, list[ChecklistItem]] = defaultdict(list)
        for item in items:
            grouped[item.fonte].append(item)

        blocks = ["Achados do checklist por fonte:"]
        for source_key, source_items in grouped.items():
            item_summaries = []
            for item in source_items:
                chunk = f"{item.item_codigo} ({item.status})"
                if item.observacao:
                    chunk += f": {self._normalize_text(item.observacao, 220)}"
                item_summaries.append(chunk)
            blocks.append(f"- {source_label(source_key)}: " + " | ".join(item_summaries))
        return "\n".join(blocks)

    def _build_scraping_block(self, pages: list[ScrapedPageRecord]) -> str:
        if not pages:
            return "Contexto do scraper: nenhuma pagina foi raspada para esta analise."

        lines = ["Contexto do scraper por fonte:"]
        for page in pages:
            category_counter = Counter(link.category for link in page.links)
            top_categories = ", ".join(
                f"{category} ({count})"
                for category, count in category_counter.most_common(4)
            ) or "sem categorias relevantes"
            notable_links = self._notable_links(page.links)
            page_origin = self._page_origin(page)
            line = (
                f"- {source_label(page.fonte)}{page_origin}: {page.summary} "
                f"Categorias principais: {top_categories}."
            )
            if notable_links:
                line += " Evidencias priorizadas: " + " | ".join(notable_links) + "."
            lines.append(line)
        return "\n".join(lines)

    def _build_context_layers_block(self, layers: list[WorkbookContextLayer]) -> str:
        if not layers:
            return "Camadas complementares do workbook: nenhuma camada estruturada foi extraida nesta analise."

        lines = ["Camadas complementares do workbook:"]
        for layer in layers[:8]:
            chunk = f"- {layer.title} [{layer.sheet_name}]: {self._normalize_text(layer.summary, 220)}"
            if layer.details:
                chunk += " Evidencias-chave: " + " | ".join(
                    self._normalize_text(detail, 100) for detail in layer.details[:3]
                ) + "."
            lines.append(chunk)
        return "\n".join(lines)

    def _build_warning_block(self, warnings: list[str]) -> str:
        if not warnings:
            return ""
        normalized = [self._normalize_text(warning, 220) for warning in warnings[:8]]
        return "Alertas e observacoes: " + " | ".join(normalized)

    def _notable_links(self, links: list[ScrapedLink]) -> list[str]:
        selected = []
        ordered_links = sorted(links, key=lambda link: (-link.score, link.label.lower()))
        for link in ordered_links:
            if link.category in {"portal_transparencia", "esic", "licitacoes", "contratos", "institucional"}:
                chunk = f"{link.label} [{link.score}]"
                if link.evidence_summary:
                    chunk += f": {link.evidence_summary}"
                selected.append(chunk)
            if len(selected) >= 4:
                break
        return selected

    def _normalize_text(self, text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def _page_origin(self, page: ScrapedPageRecord) -> str:
        if page.discovery_depth <= 0:
            return ""
        parts = [f" (profundidade {page.discovery_depth}"]
        if page.discovered_from_label:
            parts.append(f", via '{self._normalize_text(page.discovered_from_label, 80)}'")
        if page.page_score:
            parts.append(f", score {page.page_score}")
        parts.append(")")
        return "".join(parts)

    def _build_financial_summary(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        if analysis is None:
            return ""

        parts = [
            self._build_financial_header(parsed),
            self._build_financial_dre_block(parsed),
            self._build_financial_period_block(parsed),
            self._build_financial_client_block(parsed),
            self._build_financial_contract_block(parsed),
            self._build_context_layers_block(parsed.context_layers),
            self._build_scraping_block(parsed.scraped_pages),
        ]

        warning_block = self._build_warning_block(parsed.warnings)
        if warning_block:
            parts.append(warning_block)

        return "\n\n".join(part for part in parts if part)

    def _build_financial_header(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        if analysis is None:
            return ""
        warehouse_overview = parsed.warehouse_overview
        entity_name = entity_display_name(parsed.orgao, parsed.tipo_orgao)
        lines = [
            f"Analise financeira registrada para {entity_name}.",
            f"Arquivos fonte consolidados: {analysis.source_workbook_count}.",
            f"Periodo consolidado: {parsed.periodo_analise or 'nao informado'}.",
            f"Abas consolidadas: {', '.join(parsed.parser_options.checklist_sheet_names) or 'nao informadas'}.",
            f"Periodos identificados: {len(analysis.months)}.",
            f"Lancamentos estruturados: {analysis.entry_count}.",
        ]
        if warehouse_overview and warehouse_overview.snapshot_available:
            lines.append(
                "Warehouse canônico disponível: "
                f"{warehouse_overview.client_count} cliente(s), "
                f"{warehouse_overview.contract_count} contrato(s) e "
                f"{warehouse_overview.entry_count} lançamento(s) rastreáveis."
            )
        if analysis.detected_entities:
            lines.append("Entidades ou centros recorrentes: " + ", ".join(analysis.detected_entities[:8]) + ".")
        if parsed.reference_links:
            selected_count = sum(1 for link in parsed.reference_links if link.selected_for_crawl)
            lines.append(
                f"Links referenciais do workbook: {len(parsed.reference_links)} identificado(s), "
                f"{selected_count} usado(s) como semente do crawler."
            )
        return " ".join(lines)

    def _build_financial_dre_block(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        if analysis is None or not analysis.dre_lines:
            return "DRE consolidada: nenhum demonstrativo estruturado foi calculado."

        lines = ["DRE consolidada:"]
        for line in analysis.dre_lines:
            suffix = ""
            if line.share_of_gross_revenue is not None:
                suffix = f" ({self._format_percent(line.share_of_gross_revenue)} da receita bruta)"
            lines.append(f"- {line.label}: {self._format_currency(line.amount)}{suffix}")
        return "\n".join(lines)

    def _build_financial_period_block(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        if analysis is None or not analysis.months:
            return "Fechamentos mensais: nenhum periodo foi estruturado."

        lines = ["Fechamento por periodo:"]
        for month in analysis.months[:12]:
            lines.append(
                f"- {month.period_label}: receita base {self._format_currency(self._normalize_financial_amount(month.receivables_total))}, "
                f"custos e despesas {self._format_currency(self._normalize_financial_amount(month.global_expenses_total))}, "
                f"resultado {self._format_currency(month.net_result)}, "
                f"pendencias {month.pending_entry_count}."
            )
        return "\n".join(lines)

    def _build_financial_client_block(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        warehouse_overview = parsed.warehouse_overview
        if warehouse_overview and warehouse_overview.top_clients:
            lines = ["Recebimentos por cliente (warehouse canônico):"]
            for client in warehouse_overview.top_clients[:10]:
                lines.append(
                    f"- {client.client_name}: recebido {self._format_currency(client.total_received_amount)}, "
                    f"previsto {self._format_currency(client.total_expected_amount)}, "
                    f"pendente {self._format_currency(client.total_pending_amount)}, "
                    f"contratos {client.contract_count}."
                )
            if analysis is not None and analysis.client_period_rollups:
                lines.append("")
                lines.append("Recebimentos por cliente e periodo:")
                for entry in analysis.client_period_rollups[:18]:
                    lines.append(
                        f"- {entry.client_name} | {entry.period_label}: recebido {self._format_currency(entry.total_received_amount)}, "
                        f"previsto {self._format_currency(entry.total_expected_amount)}, "
                        f"pendente {self._format_currency(entry.total_pending_amount)}."
                    )
            return "\n".join(lines)

        if analysis is None or not analysis.client_rollups:
            return "Recebimentos por cliente: nenhum agrupamento foi estruturado."

        lines = ["Recebimentos por cliente:"]
        for client in analysis.client_rollups[:10]:
            lines.append(
                f"- {client.client_name}: recebido {self._format_currency(client.total_received_amount)}, "
                f"previsto {self._format_currency(client.total_expected_amount)}, "
                f"pendente {self._format_currency(client.total_pending_amount)}, "
                f"contratos {client.contract_count}."
            )
        if analysis.client_period_rollups:
            lines.append("")
            lines.append("Recebimentos por cliente e periodo:")
            for entry in analysis.client_period_rollups[:18]:
                lines.append(
                    f"- {entry.client_name} | {entry.period_label}: recebido {self._format_currency(entry.total_received_amount)}, "
                    f"previsto {self._format_currency(entry.total_expected_amount)}, "
                    f"pendente {self._format_currency(entry.total_pending_amount)}."
                )
        return "\n".join(lines)

    def _build_financial_contract_block(self, parsed: ChecklistParseResult) -> str:
        analysis = parsed.financial_analysis
        warehouse_overview = parsed.warehouse_overview
        if warehouse_overview and warehouse_overview.top_contracts:
            lines = ["Recebimentos por contrato (warehouse canônico):"]
            for contract in warehouse_overview.top_contracts[:12]:
                client_suffix = f" | cliente {contract.client_name}" if contract.client_name else ""
                lines.append(
                    f"- {contract.contract_label}{client_suffix}: recebido {self._format_currency(contract.total_received_amount)}, "
                    f"previsto {self._format_currency(contract.total_expected_amount)}, "
                    f"pendente {self._format_currency(contract.total_pending_amount)}."
                )
            return "\n".join(lines)

        if analysis is None or not analysis.contract_rollups:
            return "Recebimentos por contrato: nenhum agrupamento contratual foi estruturado."

        lines = ["Recebimentos por contrato:"]
        for contract in analysis.contract_rollups[:12]:
            client_suffix = f" | cliente {contract.client_name}" if contract.client_name else ""
            lines.append(
                f"- {contract.contract_label}{client_suffix}: recebido {self._format_currency(contract.total_received_amount)}, "
                f"previsto {self._format_currency(contract.total_expected_amount)}, "
                f"pendente {self._format_currency(contract.total_pending_amount)}."
            )
        return "\n".join(lines)

    def _normalize_financial_amount(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return abs(float(value))

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value * 100:.1f}%".replace(".", ",")

    def _format_currency(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
