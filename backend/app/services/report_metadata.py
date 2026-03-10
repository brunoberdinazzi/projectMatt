from __future__ import annotations

from ..models import ChecklistParseResult


DEFAULT_REPORT_TITLE = (
    "Relatorio Tecnico de Analise Estruturada"
)


def build_report_title(payload: ChecklistParseResult) -> str:
    return DEFAULT_REPORT_TITLE
