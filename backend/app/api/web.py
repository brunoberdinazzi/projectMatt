from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..runtime import FRONTEND_DIST_DIR


router = APIRouter()


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="pt-BR">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Draux Inc. | Frontend nao encontrado</title>
                <style>
                  body {
                    margin: 0;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                    background: #0c1726;
                    color: #f6efe4;
                    font-family: system-ui, sans-serif;
                  }
                  main {
                    width: min(640px, calc(100% - 32px));
                    padding: 24px;
                    border-radius: 20px;
                    background: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                  }
                  code {
                    display: inline-block;
                    margin-top: 12px;
                    padding: 8px 10px;
                    border-radius: 10px;
                    background: rgba(255, 255, 255, 0.08);
                  }
                </style>
              </head>
              <body>
                <main>
                  <h1>Build do frontend nao encontrado.</h1>
                  <p>Execute o build do app React antes de abrir a interface pelo FastAPI.</p>
                  <code>npm --prefix frontend install && npm --prefix frontend run build</code>
                </main>
              </body>
            </html>
            """,
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    return HTMLResponse(
        index_path.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {"status": "ok"}
