from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .api import (
    analysis_router,
    auth_router,
    providers_router,
    reports_router,
    scrape_router,
    web_router,
)
from .runtime import FRONTEND_STATIC_DIR


class CacheControlStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code != 200:
            return response

        if path.endswith((".js", ".css", ".woff2", ".svg", ".png", ".jpg", ".jpeg", ".webp")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response


app = FastAPI(
    title="Draux Inc. Backend",
    version="0.1.0",
    description="Backend inicial para leitura de checklist, montagem de prompt e geracao de relatorio.",
)
app.add_middleware(GZipMiddleware, minimum_size=700)
app.mount("/static", CacheControlStaticFiles(directory=FRONTEND_STATIC_DIR, check_dir=False), name="static")

app.include_router(web_router)
app.include_router(auth_router)
app.include_router(providers_router)
app.include_router(scrape_router)
app.include_router(analysis_router)
app.include_router(reports_router)
