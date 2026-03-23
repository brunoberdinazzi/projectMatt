from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from ..models import ChecklistParseResult, ScrapePageResult, ScrapedLink, ScrapedPageRecord, WorkbookReferenceLink
from .link_scraper import LinkScraper


@dataclass(frozen=True)
class _SeedCrawlRequest:
    source_key: str
    url: str
    seed_label: str


@dataclass
class _SeedCrawlResult:
    request: _SeedCrawlRequest
    response: Optional[ScrapePageResult] = None
    error: Optional[str] = None


class AnalysisScrapeService:
    MAX_CONCURRENT_CRAWLS = 3
    CRAWL_MAX_LINKS = 25
    CRAWL_MAX_DEPTH = 1
    CRAWL_MAX_PAGES = 4

    def __init__(self, link_scraper: LinkScraper) -> None:
        self.link_scraper = link_scraper

    def scrape_pages_for_analysis(self, parsed: ChecklistParseResult) -> list[ScrapedPageRecord]:
        selected_links = self._select_reference_links_for_crawl(parsed)
        pending_queue = [
            _SeedCrawlRequest(
                source_key=link.source_hint,
                url=link.url,
                seed_label=self._build_reference_seed_label(link),
            )
            for link in selected_links
        ]
        pages: list[ScrapedPageRecord] = []
        seen_seed_urls: set[str] = set()
        seen_page_urls: set[str] = set()
        discovered_sources: set[str] = set()

        while pending_queue:
            batch = self._dequeue_seed_batch(pending_queue, seen_seed_urls)
            if not batch:
                continue

            for crawled_seed in self._crawl_seed_batch(batch):
                if crawled_seed.error:
                    parsed.warnings.append(
                        f"Falha ao raspar {crawled_seed.request.source_key} ({crawled_seed.request.url}): {crawled_seed.error}"
                    )
                    continue

                if crawled_seed.response is None:
                    continue

                self._merge_crawled_pages(
                    pages=pages,
                    seen_page_urls=seen_page_urls,
                    crawled_seed=crawled_seed,
                )
                self._collect_discovery_seeds(
                    parsed=parsed,
                    crawled_seed=crawled_seed,
                    pending_queue=pending_queue,
                    seen_seed_urls=seen_seed_urls,
                    discovered_sources=discovered_sources,
                )

        return pages

    def _dequeue_seed_batch(
        self,
        pending_queue: list[_SeedCrawlRequest],
        seen_seed_urls: set[str],
    ) -> list[_SeedCrawlRequest]:
        batch: list[_SeedCrawlRequest] = []

        for request in pending_queue:
            normalized_url = self._normalize_seed_url(request.url)
            if not normalized_url or normalized_url in seen_seed_urls:
                continue
            seen_seed_urls.add(normalized_url)
            batch.append(request)

        pending_queue.clear()
        return batch

    def _crawl_seed_batch(self, batch: list[_SeedCrawlRequest]) -> list[_SeedCrawlResult]:
        if not batch:
            return []

        max_workers = min(len(batch), self.MAX_CONCURRENT_CRAWLS)
        if max_workers <= 1:
            return [self._crawl_single_seed(request) for request in batch]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(self._crawl_single_seed, batch))

    def _crawl_single_seed(self, request: _SeedCrawlRequest) -> _SeedCrawlResult:
        try:
            response = self.link_scraper.crawl(
                url=request.url,
                max_links=self.CRAWL_MAX_LINKS,
                max_depth=self.CRAWL_MAX_DEPTH,
                max_pages=self.CRAWL_MAX_PAGES,
            )
            return _SeedCrawlResult(request=request, response=response)
        except Exception as exc:
            return _SeedCrawlResult(request=request, error=str(exc))

    def _merge_crawled_pages(
        self,
        pages: list[ScrapedPageRecord],
        seen_page_urls: set[str],
        crawled_seed: _SeedCrawlResult,
    ) -> None:
        if crawled_seed.response is None:
            return

        crawled_pages = [
            ScrapedPageRecord(
                fonte=crawled_seed.request.source_key,
                requested_url=crawled_seed.response.requested_url,
                final_url=crawled_seed.response.final_url,
                page_title=crawled_seed.response.page_title,
                summary=crawled_seed.response.summary,
                links=crawled_seed.response.links,
                warnings=crawled_seed.response.warnings,
                discovery_depth=0,
                page_score=0,
                discovered_from_label=crawled_seed.request.seed_label,
            ),
            *[
                page.model_copy(update={"fonte": crawled_seed.request.source_key})
                for page in crawled_seed.response.discovered_pages
            ],
        ]

        for crawled_page in crawled_pages:
            normalized_page_url = self._normalize_seed_url(crawled_page.final_url)
            if normalized_page_url in seen_page_urls:
                continue
            pages.append(crawled_page)
            seen_page_urls.add(normalized_page_url)

    def _collect_discovery_seeds(
        self,
        parsed: ChecklistParseResult,
        crawled_seed: _SeedCrawlResult,
        pending_queue: list[_SeedCrawlRequest],
        seen_seed_urls: set[str],
        discovered_sources: set[str],
    ) -> None:
        if crawled_seed.response is None:
            return

        links_for_discovery = list(crawled_seed.response.links)
        for discovered_page in crawled_seed.response.discovered_pages:
            links_for_discovery.extend(discovered_page.links)

        for link in links_for_discovery:
            self._register_discovery_seed(
                parsed=parsed,
                target_source_key="portal_transparencia",
                current_url=crawled_seed.request.url,
                link=link,
                pending_queue=pending_queue,
                seen_seed_urls=seen_seed_urls,
                discovered_sources=discovered_sources,
            )
            self._register_discovery_seed(
                parsed=parsed,
                target_source_key="esic",
                current_url=crawled_seed.request.url,
                link=link,
                pending_queue=pending_queue,
                seen_seed_urls=seen_seed_urls,
                discovered_sources=discovered_sources,
            )

    def _register_discovery_seed(
        self,
        parsed: ChecklistParseResult,
        target_source_key: str,
        current_url: str,
        link: ScrapedLink,
        pending_queue: list[_SeedCrawlRequest],
        seen_seed_urls: set[str],
        discovered_sources: set[str],
    ) -> None:
        existing_url = parsed.portal_url if target_source_key == "portal_transparencia" else parsed.esic_url
        if existing_url:
            return
        if link.category != target_source_key:
            return
        if target_source_key in discovered_sources:
            return
        if not self._is_discovery_candidate(link, target_source_key, current_url):
            return

        normalized_url = self._normalize_seed_url(link.url)
        if target_source_key == "portal_transparencia":
            parsed.portal_url = link.url
        elif target_source_key == "esic":
            parsed.esic_url = link.url

        if target_source_key not in parsed.fontes_disponiveis:
            parsed.fontes_disponiveis.append(target_source_key)

        if not normalized_url or normalized_url in seen_seed_urls:
            discovered_sources.add(target_source_key)
            return

        pending_queue.append(
            _SeedCrawlRequest(
                source_key=target_source_key,
                url=link.url,
                seed_label="Descoberta automatica durante o crawl",
            )
        )
        discovered_sources.add(target_source_key)

    def _normalize_seed_url(self, url: str) -> str:
        return (url or "").rstrip("/").lower()

    def _select_reference_links_for_crawl(
        self,
        parsed: ChecklistParseResult,
    ) -> list[WorkbookReferenceLink]:
        if not parsed.reference_links:
            parsed.reference_links = self._fallback_reference_links(parsed)

        for link in parsed.reference_links:
            link.selected_for_crawl = False

        selected: list[WorkbookReferenceLink] = []
        seen_urls: set[str] = set()

        primary_links = [link for link in parsed.reference_links if link.link_kind == "primary" and link.crawlable]
        extra_links = [link for link in parsed.reference_links if link.link_kind == "reference" and link.crawlable]
        extra_links.sort(key=self._reference_link_priority, reverse=True)

        for link in [*primary_links, *extra_links[:6]]:
            normalized = link.url.rstrip("/").lower()
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)
            link.selected_for_crawl = True
            selected.append(link)

        return selected

    def _fallback_reference_links(self, parsed: ChecklistParseResult) -> list[WorkbookReferenceLink]:
        fallback_links: list[WorkbookReferenceLink] = []
        for source_hint, url, label in (
            ("site_orgao", parsed.site_url, "Canal principal estruturado"),
            ("portal_transparencia", parsed.portal_url, "Canal complementar estruturado"),
            ("esic", parsed.esic_url, "Canal de atendimento estruturado"),
        ):
            if not url:
                continue
            fallback_links.append(
                WorkbookReferenceLink(
                    url=url,
                    sheet_name="Checklist",
                    label=label,
                    context="Seed estruturado reconstruido para analises antigas.",
                    source_hint=source_hint,
                    link_kind="primary",
                    crawlable=True,
                    selected_for_crawl=False,
                )
            )
        return fallback_links

    def _reference_link_priority(self, link: WorkbookReferenceLink) -> tuple[int, int, int]:
        source_score = {
            "portal_transparencia": 40,
            "esic": 38,
            "site_orgao": 34,
            "nao_informada": 20,
        }.get(link.source_hint, 20)
        sheet_score = 8 if "executivo" in (link.sheet_name or "").lower() else 0
        text = " ".join(part for part in [link.label or "", link.context or "", link.url] if part).lower()
        keyword_score = 0
        if "transpar" in text:
            keyword_score += 6
        if "esic" in text or "e-sic" in text or "sic" in text:
            keyword_score += 6
        if "licit" in text or "contrat" in text or "legisl" in text:
            keyword_score += 3
        return (source_score + sheet_score + keyword_score, -len(link.url), 1 if link.link_kind == "primary" else 0)

    def _build_reference_seed_label(self, link: WorkbookReferenceLink) -> str:
        parts = []
        if link.link_kind == "primary":
            parts.append("Seed estruturado")
        else:
            parts.append("Referencia do workbook")
        if link.sheet_name:
            parts.append(f"aba {link.sheet_name}")
        if link.cell_reference:
            parts.append(f"celula {link.cell_reference}")
        if link.label:
            parts.append(link.label)
        return " | ".join(parts)

    def _is_discovery_candidate(
        self,
        link: ScrapedLink,
        target_source_key: str,
        current_url: str,
    ) -> bool:
        haystack = " ".join(
            part for part in [link.label, link.context or "", link.section or "", link.url] if part
        ).lower()
        current_host = urlparse(current_url).netloc.lower()
        target_host = urlparse(link.url).netloc.lower()

        if target_source_key == "portal_transparencia":
            return (
                "portal da transparencia" in haystack
                or "acesso a informacao" in haystack
                or "transparencia" in target_host
                or (target_host and target_host != current_host and "transpar" in haystack)
            )

        if target_source_key == "esic":
            return (
                "e-sic" in haystack
                or "esic" in haystack
                or "servico de informacao ao cidadao" in haystack
                or "pedido de informacao" in haystack
                or "informacao ao cidadao" in haystack
            )

        return False
