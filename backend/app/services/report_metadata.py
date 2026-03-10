from __future__ import annotations

from ..models import ChecklistParseResult


DEFAULT_REPORT_TITLE = (
    "Analise de Dados Disponibilizados pela Administracao Publica para Verificacao "
    "de Conformidade com Legislacao de Acesso a Informacao"
)


def build_report_title(payload: ChecklistParseResult) -> str:
    return DEFAULT_REPORT_TITLE
