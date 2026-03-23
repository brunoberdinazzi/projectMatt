from __future__ import annotations

from time import perf_counter

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..models import AuthUserResponse, ScrapePageResult
from ..runtime import link_scraper, require_authenticated_user


router = APIRouter()


@router.get("/scrape/links", response_model=ScrapePageResult)
def scrape_links(
    url: str,
    max_links: int = 40,
    crawl_depth: int = 1,
    max_pages: int = 4,
    _current_user: AuthUserResponse = Depends(require_authenticated_user),
) -> ScrapePageResult:
    if max_links < 1 or max_links > 200:
        raise HTTPException(status_code=400, detail="Use max_links entre 1 e 200.")
    if crawl_depth < 0 or crawl_depth > 3:
        raise HTTPException(status_code=400, detail="Use crawl_depth entre 0 e 3.")
    if max_pages < 0 or max_pages > 20:
        raise HTTPException(status_code=400, detail="Use max_pages entre 0 e 20.")

    try:
        started_at = perf_counter()
        result = link_scraper.crawl(
            url=url,
            max_links=max_links,
            max_depth=crawl_depth,
            max_pages=max_pages,
        )
        duration_ms = int(round((perf_counter() - started_at) * 1000))
        return result.model_copy(update={"processing_time_ms": duration_ms})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao acessar a URL informada: {exc}",
        ) from exc
