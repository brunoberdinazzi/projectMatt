from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from ..models import ScrapedLink, ScrapePageResult, ScrapedPageRecord


CATEGORY_RULES = (
    ("esic", ("e-sic", "esic", "pedido de informacao", "pedido de informação", "sic")),
    ("portal_transparencia", ("portal da transparencia", "portal da transparência", "transparencia", "transparência publica")),
    ("licitacoes", ("licitacao", "licitações", "licitacoes", "pregao", "edital", "pncp", "contratacao")),
    ("contratos", ("contrato", "contratos", "ata de registro", "aditivo")),
    ("obras", ("obra", "obras", "engenharia")),
    ("despesas", ("despesa", "despesas", "empenho", "pagamento", "credor")),
    ("receitas", ("receita", "receitas", "arrecadacao", "arrecadação")),
    ("servidores", ("servidor", "servidores", "folha", "remuneracao", "remuneração", "cargo")),
    ("legislacao", ("lei", "legislacao", "legislação", "decreto", "norma", "regulamento")),
    ("institucional", ("secretaria", "organograma", "estrutura", "competencia", "competência", "institucional")),
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

CATEGORY_PRIORITY = {
    "portal_transparencia": 42,
    "esic": 40,
    "institucional": 28,
    "licitacoes": 24,
    "contratos": 22,
    "despesas": 20,
    "receitas": 20,
    "servidores": 18,
    "legislacao": 18,
    "obras": 16,
    "ouvidoria": 14,
    "faq": 12,
    "outros": 8,
}

FOLLOWABLE_CATEGORIES = {
    "portal_transparencia",
    "esic",
    "institucional",
    "licitacoes",
    "contratos",
    "despesas",
    "receitas",
    "servidores",
    "legislacao",
    "obras",
    "ouvidoria",
    "faq",
}


@dataclass
class LinkScraperConfig:
    timeout_seconds: float = 20.0
    max_links: int = 60
    crawl_depth: int = 1
    crawl_max_pages: int = 4
    follow_score_threshold: int = 38
    user_agent: str = "MattLinkScraper/0.3 (+https://localhost; spreadsheet to report)"


@dataclass
class _FetchResult:
    requested_url: str
    final_url: str
    page_title: Optional[str]
    summary: str
    links: list[ScrapedLink]
    warnings: list[str]


class LinkScraper:
    def __init__(self, config: Optional[LinkScraperConfig] = None) -> None:
        self.config = config or LinkScraperConfig()

    def scrape(self, url: str, max_links: Optional[int] = None) -> ScrapePageResult:
        requested_url = self._normalize_requested_url(url)
        limit = max_links or self.config.max_links
        with self._client() as client:
            root = self._fetch_page(client, requested_url, limit)
        return ScrapePageResult(
            requested_url=root.requested_url,
            final_url=root.final_url,
            page_title=root.page_title,
            summary=root.summary,
            links=root.links,
            warnings=root.warnings,
        )

    def crawl(
        self,
        url: str,
        max_links: Optional[int] = None,
        max_depth: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> ScrapePageResult:
        requested_url = self._normalize_requested_url(url)
        limit = max_links or self.config.max_links
        depth_limit = self.config.crawl_depth if max_depth is None else max(0, max_depth)
        page_limit = self.config.crawl_max_pages if max_pages is None else max(0, max_pages)

        with self._client() as client:
            root = self._fetch_page(client, requested_url, limit)
            discovered_pages = self._crawl_related_pages(
                client=client,
                root=root,
                max_links=limit,
                max_depth=depth_limit,
                max_pages=page_limit,
            )

        summary = root.summary
        if discovered_pages:
            summary += f" Foram aprofundadas {len(discovered_pages)} pagina(s) adicional(is) relevantes."

        return ScrapePageResult(
            requested_url=root.requested_url,
            final_url=root.final_url,
            page_title=root.page_title,
            summary=summary,
            links=root.links,
            discovered_pages=discovered_pages,
            warnings=root.warnings,
        )

    def _crawl_related_pages(
        self,
        client: httpx.Client,
        root: _FetchResult,
        max_links: int,
        max_depth: int,
        max_pages: int,
    ) -> list[ScrapedPageRecord]:
        if max_depth <= 0 or max_pages <= 0:
            return []

        root_host = urlparse(root.final_url).netloc.lower()
        queue = deque(
            (link, 1, root.final_url)
            for link in self._candidate_follow_links(root.links, root_host)
        )
        seen_urls = {root.final_url}
        discovered: list[ScrapedPageRecord] = []

        while queue and len(discovered) < max_pages:
            link, depth, parent_url = queue.popleft()
            if link.url in seen_urls:
                continue
            seen_urls.add(link.url)

            try:
                fetched = self._fetch_page(client, link.url, max_links)
            except httpx.HTTPError:
                continue

            page_record = ScrapedPageRecord(
                requested_url=fetched.requested_url,
                final_url=fetched.final_url,
                page_title=fetched.page_title,
                summary=fetched.summary,
                links=fetched.links,
                warnings=fetched.warnings,
                discovery_depth=depth,
                page_score=link.score,
                discovered_from_url=parent_url,
                discovered_from_label=link.label,
            )
            discovered.append(page_record)

            if depth >= max_depth:
                continue

            next_host = urlparse(fetched.final_url).netloc.lower() or root_host
            for next_link in self._candidate_follow_links(fetched.links, next_host):
                if next_link.url in seen_urls:
                    continue
                queue.append((next_link, depth + 1, fetched.final_url))

        return discovered

    def _candidate_follow_links(self, links: list[ScrapedLink], root_host: str) -> list[ScrapedLink]:
        selected: list[ScrapedLink] = []
        for link in sorted(links, key=self._sort_key):
            if link.destination_type != "pagina":
                continue
            if link.category not in FOLLOWABLE_CATEGORIES:
                continue
            if link.score < self.config.follow_score_threshold:
                continue
            target_host = urlparse(link.url).netloc.lower()
            if target_host and target_host != root_host and link.category not in {"portal_transparencia", "esic"}:
                continue
            selected.append(link)
        return selected

    def _client(self) -> httpx.Client:
        return httpx.Client(
            follow_redirects=True,
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": self.config.user_agent},
        )

    def _fetch_page(self, client: httpx.Client, requested_url: str, limit: int) -> _FetchResult:
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

        return _FetchResult(
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
        results_by_url: dict[str, ScrapedLink] = {}
        base_host = urlparse(base_url).netloc.lower()

        for anchor in soup.find_all("a", href=True):
            href = (anchor.get("href") or "").strip()
            if self._should_skip_href(href):
                continue

            absolute_url = urljoin(base_url, href)
            label = self._link_label(anchor, absolute_url)
            section = self._nearest_section_heading(anchor)
            context = self._context_text(anchor, label)
            category, matched_terms = self._categorize_link(label, absolute_url, context, section)
            destination_type = self._destination_type(absolute_url)
            target_host = urlparse(absolute_url).netloc.lower()
            is_internal = not target_host or target_host == base_host
            score = self._score_link(
                category=category,
                destination_type=destination_type,
                is_internal=is_internal,
                matched_terms=matched_terms,
                section=section,
                context=context,
            )
            candidate = ScrapedLink(
                label=label,
                url=absolute_url,
                category=category,
                destination_type=destination_type,
                context=context,
                section=section,
                is_internal=is_internal,
                score=score,
                matched_terms=matched_terms,
                evidence_summary=self._build_evidence_summary(
                    category=category,
                    destination_type=destination_type,
                    is_internal=is_internal,
                    matched_terms=matched_terms,
                    section=section,
                ),
            )

            existing = results_by_url.get(absolute_url)
            if existing is None or self._is_better_link(candidate, existing):
                results_by_url[absolute_url] = candidate

        results = sorted(results_by_url.values(), key=self._sort_key)
        return results[:limit]

    def _is_better_link(self, candidate: ScrapedLink, existing: ScrapedLink) -> bool:
        if candidate.score != existing.score:
            return candidate.score > existing.score
        if len(candidate.matched_terms) != len(existing.matched_terms):
            return len(candidate.matched_terms) > len(existing.matched_terms)
        return len(candidate.label) > len(existing.label)

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
                if candidate.name in {"body", "html"}:
                    continue
                text = " ".join(candidate.get_text(" ", strip=True).split())
                if text:
                    candidates.append(text)

        for text in candidates:
            if text == label:
                continue
            if label and label not in text:
                continue
            if len(text) > max(180, len(label) + 120):
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
    ) -> tuple[str, list[str]]:
        primary_haystack = " ".join(part for part in [label, absolute_url] if part).lower()
        secondary_haystack = " ".join(part for part in [context or "", section or ""] if part).lower()
        for category, keywords in CATEGORY_RULES:
            matched_terms = [keyword for keyword in keywords if keyword in primary_haystack]
            if matched_terms:
                return category, matched_terms
        for category, keywords in CATEGORY_RULES:
            matched_terms = [keyword for keyword in keywords if keyword in secondary_haystack]
            if matched_terms:
                return category, matched_terms
        return "outros", []

    def _destination_type(self, absolute_url: str) -> str:
        lowered = absolute_url.lower()
        for suffix, label in FILE_TYPE_MAP.items():
            if lowered.endswith(suffix):
                return label
        return "pagina"

    def _score_link(
        self,
        category: str,
        destination_type: str,
        is_internal: bool,
        matched_terms: list[str],
        section: Optional[str],
        context: Optional[str],
    ) -> int:
        score = CATEGORY_PRIORITY.get(category, CATEGORY_PRIORITY["outros"])
        score += 12 if is_internal else 4
        score += min(len(matched_terms) * 4, 12)
        if section:
            score += 5
        if context:
            score += 3
        if destination_type in {"pdf", "csv", "planilha", "documento"}:
            score += 6
        return score

    def _build_evidence_summary(
        self,
        category: str,
        destination_type: str,
        is_internal: bool,
        matched_terms: list[str],
        section: Optional[str],
    ) -> str:
        parts = [
            "link interno" if is_internal else "link externo",
            f"classificado como {self._category_label(category)}",
        ]
        if matched_terms:
            parts.append("termos: " + ", ".join(matched_terms[:3]))
        if section:
            parts.append(f"secao: {section}")
        if destination_type != "pagina":
            parts.append(f"destino: {destination_type}")
        return " | ".join(parts)

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
        top_evidence = " | ".join(f"{link.label} [{link.score}]" for link in links[:3])
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
        if top_evidence:
            base_text += " Evidencias priorizadas: " + top_evidence + "."
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

    def _sort_key(self, link: ScrapedLink) -> tuple[int, int, str, str]:
        return (-link.score, 0 if link.is_internal else 1, link.category, link.label.lower())
