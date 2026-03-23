from __future__ import annotations

from ..models import ChecklistParseResult


DEFAULT_REPORT_TITLE = (
    "Relatorio Tecnico de Analise Estruturada"
)


def build_report_title(payload: ChecklistParseResult) -> str:
    if payload.financial_analysis is not None:
        return "Demonstrativo Financeiro e DRE"
    return DEFAULT_REPORT_TITLE
