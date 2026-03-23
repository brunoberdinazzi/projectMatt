from __future__ import annotations

SOURCE_ORDER = ("site_orgao", "portal_transparencia", "esic", "nao_informada")

SOURCE_LABELS = {
    "site_orgao": "Canal principal",
    "portal_transparencia": "Canal complementar",
    "esic": "Canal de atendimento",
    "nao_informada": "Fonte nao identificada",
}

ENTITY_TYPE_LABELS = {
    "prefeitura": "perfil operacional A",
    "camara": "perfil operacional B",
    "câmara": "perfil operacional B",
}


def source_label(source_key: str) -> str:
    return SOURCE_LABELS.get(source_key, SOURCE_LABELS["nao_informada"])


def source_section_title(prefix: str, source_key: str) -> str:
    return f"{prefix} - {source_label(source_key)}"


def entity_type_label(entity_type: str | None) -> str | None:
    cleaned = (entity_type or "").strip()
    if not cleaned:
        return None
    return ENTITY_TYPE_LABELS.get(cleaned.lower(), cleaned)


def entity_display_name(name: str | None, entity_type: str | None = None) -> str:
    cleaned_name = (name or "").strip()
    cleaned_type = entity_type_label(entity_type) or ""
    if cleaned_name and cleaned_type:
        return f"{cleaned_name} ({cleaned_type})"
    if cleaned_name:
        return cleaned_name
    if cleaned_type:
        return cleaned_type
    return "entidade nao informada"
