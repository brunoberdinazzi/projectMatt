from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from ..models import ScrapedLink, ScrapePageResult


CATEGORY_RULES = (
    ("esic", ("e-sic", "esic", "pedido de informacao", "pedido de informacao", "sic")),
    ("portal_transparencia", ("portal da transparencia", "transparencia", "transparencia publica")),
    ("licitacoes", ("licitacao", "licitacoes", "pregao", "edital", "pncp", "contratacao")),
    ("contratos", ("contrato", "contratos", "ata de registro", "aditivo")),
    ("obras", ("obra", "obras", "engenharia")),
    ("despesas", ("despesa", "despesas", "empenho", "pagamento", "credor")),
    ("receitas", ("receita", "receitas", "arrecadacao")),
    ("servidores", ("servidor", "servidores", "folha", "remuneracao", "cargo")),
    ("legislacao", ("lei", "legislacao", "decreto", "norma", "regulamento")),
    ("institucional", ("secretaria", "organograma", "estrutura", "competencia", "institucional")),
    ("ouvidoria", ("ouvidoria", "fale conosco", "contato", "telefone")),
    ("faq", ("perguntas frequentes", "faq")),
)

FILE_TYPE_MAP = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".xls": "planilha",
    ".xlsx": "planilha",
    ".ods": "planilha",
    ".doc": "documento",
    ".docx": "documento",
    ".odt": "documento",
    ".zip": "arquivo",
}


@dataclass
class LinkScraperConfig:
    timeout_seconds: float = 20.0
    max_links: int = 60
    user_agent: str = (
        "MattLinkScraper/0.1 (+https://localhost; projeto de avaliacao de portais da transparencia)"
    )


class LinkScraper:
    def __init__(self, config: Optional[LinkScraperConfig] = None) -> None:
        self.config = config or LinkScraperConfig()

    def scrape(self, url: str, max_links: Optional[int] = None) -> ScrapePageResult:
        requested_url = self._normalize_requested_url(url)
        limit = max_links or self.config.max_links

        headers = {"User-Agent": self.config.user_agent}
        with httpx.Client(
            follow_redirects=True,
            timeout=self.config.timeout_seconds,
            headers=headers,
        ) as client:
            response = client.get(requested_url)
            response.raise_for_status()

        final_url = str(response.url)
        content_type = (response.headers.get("content-type") or "").lower()
        warnings: list[str] = []
        if "html" not in content_type:
            warnings.append(
                "O recurso analisado nao retornou HTML; a contextualizacao pode ficar limitada."
            )

        soup = BeautifulSoup(response.text, "html.parser")
        page_title = self._page_title(soup)
        links = self._extract_links(soup, final_url, limit)
        summary = self._build_summary(links, page_title, final_url)
        if not links:
            warnings.append("Nenhum link navegavel foi identificado na pagina informada.")

        return ScrapePageResult(
            requested_url=requested_url,
            final_url=final_url,
            page_title=page_title,
            summary=summary,
            links=links,
            warnings=warnings,
        )

    def _normalize_requested_url(self, url: str) -> str:
        cleaned = " ".join((url or "").split())
        if not cleaned:
            raise ValueError("Informe uma URL para analise.")
        if "://" not in cleaned:
            cleaned = f"https://{cleaned}"
        return cleaned

    def _page_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title and soup.title.string:
            return " ".join(soup.title.string.split())
        h1 = soup.find("h1")
        if h1:
            return " ".join(h1.get_text(" ", strip=True).split())
        return None

    def _extract_links(self, soup: BeautifulSoup, base_url: str, limit: int) -> list[ScrapedLink]:
        results: list[ScrapedLink] = []
        seen: set[tuple[str, str]] = set()
        base_host = urlparse(base_url).netloc.lower()

        for anchor in soup.find_all("a", href=True):
            href = (anchor.get("href") or "").strip()
            if self._should_skip_href(href):
                continue

            absolute_url = urljoin(base_url, href)
            label = self._link_label(anchor, absolute_url)
            dedupe_key = (absolute_url, label.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            section = self._nearest_section_heading(anchor)
            context = self._context_text(anchor, label)
            category = self._categorize_link(label, absolute_url, context, section)
            destination_type = self._destination_type(absolute_url)
            target_host = urlparse(absolute_url).netloc.lower()

            results.append(
                ScrapedLink(
                    label=label,
                    url=absolute_url,
                    category=category,
                    destination_type=destination_type,
                    context=context,
                    section=section,
                    is_internal=(not target_host or target_host == base_host),
                )
            )

            if len(results) >= limit:
                break

        results.sort(key=self._sort_key)
        return results

    def _should_skip_href(self, href: str) -> bool:
        lowered = href.lower()
        return (
            not href
            or lowered.startswith("#")
            or lowered.startswith("javascript:")
            or lowered.startswith("mailto:")
            or lowered.startswith("tel:")
        )

    def _link_label(self, anchor: Tag, absolute_url: str) -> str:
        for candidate in (
            anchor.get_text(" ", strip=True),
            anchor.get("title"),
            anchor.get("aria-label"),
            anchor.get("alt"),
        ):
            normalized = " ".join((candidate or "").split())
            if normalized:
                return normalized

        parsed = urlparse(absolute_url)
        tail = parsed.path.rstrip("/").split("/")[-1]
        return tail or parsed.netloc or absolute_url

    def _nearest_section_heading(self, anchor: Tag) -> Optional[str]:
        current: Optional[Tag] = anchor
        while current is not None:
            if not isinstance(current, Tag):
                current = current.parent
                continue

            for heading_name in ("h1", "h2", "h3", "h4"):
                heading = current.find_previous(heading_name)
                if heading:
                    text = " ".join(heading.get_text(" ", strip=True).split())
                    if text:
                        return text[:160]
            current = current.parent
        return None

    def _context_text(self, anchor: Tag, label: str) -> Optional[str]:
        candidates = []
        for candidate in (anchor.parent, anchor.parent.parent if anchor.parent else None):
            if isinstance(candidate, Tag):
                text = " ".join(candidate.get_text(" ", strip=True).split())
                if text:
                    candidates.append(text)

        for text in candidates:
            if text == label:
                continue
            if len(text) > 260:
                text = text[:257].rstrip() + "..."
            return text
        return None

    def _categorize_link(
        self,
        label: str,
        absolute_url: str,
        context: Optional[str],
        section: Optional[str],
    ) -> str:
        haystack = " ".join(
            part for part in [label, absolute_url, context or "", section or ""] if part
        ).lower()
        for category, keywords in CATEGORY_RULES:
            if any(keyword in haystack for keyword in keywords):
                return category
        return "outros"

    def _destination_type(self, absolute_url: str) -> str:
        lowered = absolute_url.lower()
        for suffix, label in FILE_TYPE_MAP.items():
            if lowered.endswith(suffix):
                return label
        return "pagina"

    def _build_summary(
        self,
        links: list[ScrapedLink],
        page_title: Optional[str],
        final_url: str,
    ) -> str:
        if not links:
            if page_title:
                return f"A pagina '{page_title}' foi carregada, mas nao apresentou links navegaveis no HTML analisado."
            return f"A pagina {final_url} foi carregada, mas nao apresentou links navegaveis no HTML analisado."

        category_counter = Counter(link.category for link in links)
        top_categories = [
            f"{self._category_label(name)} ({count})"
            for name, count in category_counter.most_common(4)
        ]
        internal_count = sum(1 for link in links if link.is_internal)
        external_count = len(links) - internal_count
        base_text = (
            f"Foram identificados {len(links)} link(s) navegaveis na pagina analisada, "
            f"sendo {internal_count} interno(s) e {external_count} externo(s)."
        )
        if page_title:
            base_text = f"Na pagina '{page_title}', {base_text[0].lower()}{base_text[1:]}"
        if top_categories:
            base_text += " Principais contextos encontrados: " + ", ".join(top_categories) + "."
        return base_text

    def _category_label(self, category: str) -> str:
        labels = {
            "esic": "e-SIC",
            "portal_transparencia": "portal da transparencia",
            "licitacoes": "licitacoes",
            "contratos": "contratos",
            "obras": "obras",
            "despesas": "despesas",
            "receitas": "receitas",
            "servidores": "servidores",
            "legislacao": "legislacao",
            "institucional": "institucional",
            "ouvidoria": "ouvidoria/contato",
            "faq": "FAQ",
            "outros": "outros",
        }
        return labels.get(category, category)

    def _sort_key(self, link: ScrapedLink) -> tuple[int, str, str]:
        priority = 0 if link.is_internal else 1
        return (priority, link.category, link.label.lower())
