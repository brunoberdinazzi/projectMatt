from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Optional

from ..models import ChecklistParseResult, WorkbookContextLayer


class WorkbookContextExtractor:
    def extract(self, workbook, parsed: ChecklistParseResult) -> list[WorkbookContextLayer]:
        layers: list[WorkbookContextLayer] = []
        layers.extend(self._build_checklist_layers(parsed))

        for sheet in workbook.worksheets:
            normalized_title = _normalize_text(sheet.title)
            if "legislacao" in normalized_title:
                layers.extend(self._build_legislation_layers(sheet, parsed.orgao))
                continue
            if normalized_title == "executivo":
                layer = self._build_executive_layer(sheet, parsed.orgao)
                if layer:
                    layers.append(layer)
                continue
            if normalized_title == "resultado":
                layer = self._build_result_layer(sheet, parsed.orgao)
                if layer:
                    layers.append(layer)

        return layers

    def _build_checklist_layers(self, parsed: ChecklistParseResult) -> list[WorkbookContextLayer]:
        layers: list[WorkbookContextLayer] = []
        selected_sheets = parsed.parser_options.checklist_sheet_names or ["Checklist"]

        for sheet_name in selected_sheets:
            sheet_items = [item for item in parsed.itens_processados if item.aba_origem == sheet_name]
            status_counter = Counter(item.status for item in sheet_items)
            source_counter = Counter(item.fonte for item in sheet_items)
            summary = (
                f"A aba consolidou {len(sheet_items)} item(ns) elegivel(is) no recorte atual."
                if sheet_items
                else "A aba foi considerada na leitura, mas nao gerou itens elegiveis no recorte atual."
            )
            if status_counter:
                summary += " Status observados: " + ", ".join(
                    f"{status} ({count})" for status, count in status_counter.items()
                ) + "."
            if source_counter:
                summary += " Fontes predominantes: " + ", ".join(
                    f"{source} ({count})" for source, count in source_counter.items()
                ) + "."

            details = [
                f"{item.item_codigo} [{item.status}] - {item.descricao_item}"
                for item in sheet_items[:8]
            ]
            references = []
            for url in (parsed.site_url, parsed.portal_url, parsed.esic_url):
                if url and url not in references:
                    references.append(url)

            layers.append(
                WorkbookContextLayer(
                    layer_type="checklist_scope",
                    sheet_name=sheet_name,
                    title=f"Camada de checklist: {sheet_name}",
                    summary=summary,
                    details=details,
                    references=references,
                )
            )

        return layers

    def _build_legislation_layers(
        self,
        sheet,
        entity_name: Optional[str],
    ) -> list[WorkbookContextLayer]:
        layers: list[WorkbookContextLayer] = []
        general_details: list[str] = []
        general_refs: list[str] = []

        for row_idx in range(2, (sheet.max_row or 0) + 1):
            row_values = [_clean_value(cell.value) for cell in sheet[row_idx]]
            item = row_values[7] if len(row_values) > 7 else None
            fundamentacao = row_values[8] if len(row_values) > 8 else None
            if not item or not fundamentacao:
                continue
            general_details.append(f"{item}: {fundamentacao}")
            for candidate in (row_values[1], row_values[2], row_values[6]):
                if candidate and candidate not in general_refs:
                    general_refs.append(candidate)
            if len(general_details) >= 8:
                break

        if general_details:
            layers.append(
                WorkbookContextLayer(
                    layer_type="reference_framework",
                    sheet_name=sheet.title,
                    title="Matriz de referencia do workbook",
                    summary=(
                        "A aba agrega referencias e fundamentos associados aos temas analisados, "
                        "funcionando como camada de enquadramento para a interpretacao dos achados."
                    ),
                    details=general_details,
                    references=general_refs[:8],
                )
            )

        if not entity_name:
            return layers

        entity_rows = []
        target = _entity_key(entity_name)
        for row_idx in range(2, (sheet.max_row or 0) + 1):
            row_label = _clean_value(sheet[f"B{row_idx}"].value)
            if _entity_key(row_label) == target:
                entity_rows.append(row_idx)

        if not entity_rows:
            return layers

        details: list[str] = []
        references: list[str] = []
        for row_idx in entity_rows[:6]:
            regulation = _clean_value(sheet[f"C{row_idx}"].value) or "Nao encontrado"
            topic = _clean_value(sheet[f"H{row_idx}"].value) or "Tema nao informado"
            legal_basis = _clean_value(sheet[f"I{row_idx}"].value)
            details.append(f"{topic}: {regulation}")
            if legal_basis and legal_basis not in references:
                references.append(legal_basis)

        layers.append(
            WorkbookContextLayer(
                layer_type="entity_reference",
                sheet_name=sheet.title,
                title=f"Referencias especificas identificadas para {entity_name}",
                summary=(
                    f"A aba registra referencias associadas diretamente a {entity_name}, permitindo "
                    "contextualizar elementos especificos da entidade dentro do workbook."
                ),
                details=details,
                references=references,
            )
        )
        return layers

    def _build_executive_layer(
        self,
        sheet,
        entity_name: Optional[str],
    ) -> Optional[WorkbookContextLayer]:
        if not entity_name:
            return None

        target = _entity_key(entity_name)
        for row_idx in range(2, (sheet.max_row or 0) + 1):
            current_name = _clean_value(sheet[f"C{row_idx}"].value)
            if _entity_key(current_name) != target:
                continue

            ranking = _clean_value(sheet[f"B{row_idx}"].value)
            population = _clean_value(sheet[f"D{row_idx}"].value)
            site_url = _clean_value(sheet[f"E{row_idx}"].value)
            portal_url = _clean_value(sheet[f"F{row_idx}"].value)
            details = [
                f"Posicao na listagem executiva: {ranking or 'Nao informada'}",
                f"Populacao considerada: {population or 'Nao informada'}",
            ]
            if site_url:
                details.append(f"Sitio eletronico: {site_url}")
            if portal_url:
                details.append(f"Portal da transparencia: {portal_url}")
            return WorkbookContextLayer(
                layer_type="registry_snapshot",
                sheet_name=sheet.title,
                title=f"Registro sintese de {entity_name}",
                summary=(
                    "A aba sintetiza dados de identificacao e enderecos de referencia da entidade analisada, "
                    "funcionando como camada cadastral do workbook."
                ),
                details=details,
                references=[value for value in (site_url, portal_url) if value],
            )
        return None

    def _build_result_layer(
        self,
        sheet,
        entity_name: Optional[str],
    ) -> Optional[WorkbookContextLayer]:
        if not entity_name:
            return None

        target = _entity_key(entity_name)
        row_idx = None
        for candidate_idx in range(2, (sheet.max_row or 0) + 1):
            current_name = _clean_value(sheet[f"C{candidate_idx}"].value)
            if _entity_key(current_name) == target:
                row_idx = candidate_idx
                break

        if row_idx is None:
            return None

        column_details: list[str] = []
        for column_idx in range(4, (sheet.max_column or 0) + 1):
            code = _clean_value(sheet.cell(3, column_idx).value)
            if not code:
                continue
            value = _clean_value(sheet.cell(row_idx, column_idx).value)
            if not value:
                continue
            group_label = _clean_value(sheet.cell(2, column_idx).value)
            if group_label:
                column_details.append(f"{code} ({group_label}): {value}")
            else:
                column_details.append(f"{code}: {value}")

        summary = (
            "A matriz de resultado possui consolidacao preenchida para a entidade analisada."
            if column_details
            else "A matriz de resultado localiza a entidade analisada, mas nao apresenta marcadores consolidados preenchidos nas colunas avaliativas."
        )
        return WorkbookContextLayer(
            layer_type="outcome_matrix",
            sheet_name=sheet.title,
            title=f"Matriz consolidada de resultado para {entity_name}",
            summary=summary,
            details=column_details[:12],
            references=[],
        )


def _clean_value(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(value: object) -> str:
    cleaned = _clean_value(value)
    if not cleaned:
        return ""
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(char for char in cleaned if not unicodedata.combining(char))
    cleaned = cleaned.lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _entity_key(value: object) -> str:
    normalized = _normalize_text(value)
    return re.sub(r"[^a-z0-9]+", "", normalized)
