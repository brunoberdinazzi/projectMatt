from __future__ import annotations

from collections import Counter, defaultdict

from ..models import ChecklistItem, ChecklistParseResult, ScrapedLink, ScrapedPageRecord


SOURCE_LABELS = {
    "site_orgao": "Site oficial",
    "portal_transparencia": "Portal da transparencia",
    "esic": "Sistema e-SIC",
    "nao_informada": "Fonte nao identificada",
}


class AnalysisContextBuilder:
    def build_summary(self, parsed: ChecklistParseResult) -> str:
        parts = [
            self._build_header(parsed),
            self._build_items_block(parsed.itens_processados),
            self._build_scraping_block(parsed.scraped_pages),
        ]

        warning_block = self._build_warning_block(parsed.warnings)
        if warning_block:
            parts.append(warning_block)

        return "\n\n".join(part for part in parts if part)

    def _build_header(self, parsed: ChecklistParseResult) -> str:
        lines = [
            f"Analise registrada para {parsed.orgao or 'orgao nao informado'}.",
            f"Tipo de orgao: {parsed.tipo_orgao or 'nao informado'}.",
            f"Periodo da analise: {parsed.periodo_analise or 'nao informado'}.",
            f"SAT: {parsed.sat_numero or 'nao identificado'}.",
            (
                "Escopo do parser: perfil "
                f"{parsed.parser_options.profile}, grupos {', '.join(parsed.parser_options.allowed_groups)}, "
                f"status {', '.join(parsed.parser_options.allowed_status)}."
            ),
        ]
        source_lines = []
        if parsed.site_url:
            source_lines.append(f"Site oficial: {parsed.site_url}")
        if parsed.portal_url:
            source_lines.append(f"Portal da transparencia: {parsed.portal_url}")
        if parsed.esic_url:
            source_lines.append(f"e-SIC: {parsed.esic_url}")
        if source_lines:
            lines.append("Fontes principais: " + " | ".join(source_lines) + ".")
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
            blocks.append(f"- {SOURCE_LABELS.get(source_key, source_key)}: " + " | ".join(item_summaries))
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
                f"- {SOURCE_LABELS.get(page.fonte, page.fonte)}{page_origin}: {page.summary} "
                f"Categorias principais: {top_categories}."
            )
            if notable_links:
                line += " Evidencias priorizadas: " + " | ".join(notable_links) + "."
            lines.append(line)
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
