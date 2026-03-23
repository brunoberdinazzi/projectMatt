from .analysis import router as analysis_router
from .auth import router as auth_router
from .providers import router as providers_router
from .reports import router as reports_router
from .scrape import router as scrape_router
from .web import router as web_router

__all__ = [
    "analysis_router",
    "auth_router",
    "providers_router",
    "reports_router",
    "scrape_router",
    "web_router",
]
