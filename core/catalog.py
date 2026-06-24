from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.models import Package


PACKAGE_FIELDS = {
    "id",
    "name",
    "category",
    "winget_id",
    "description",
    "recommended_for",
    "requires_admin",
    "enabled_by_default",
}


class CatalogError(ValueError):
    pass


def load_catalog(path: Path) -> list[Package]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise CatalogError("Der Paketkatalog muss eine Liste sein.")

    packages = [_parse_package(item) for item in data]
    ids = [package.id for package in packages]
    if len(ids) != len(set(ids)):
        raise CatalogError("Der Paketkatalog enthaelt doppelte Paket-IDs.")
    return packages


def _parse_package(item: dict[str, Any]) -> Package:
    missing = PACKAGE_FIELDS - set(item)
    if missing:
        raise CatalogError(f"Paket enthaelt fehlende Felder: {', '.join(sorted(missing))}")

    if not isinstance(item["recommended_for"], list):
        raise CatalogError(f"Paket {item.get('id', '<unbekannt>')} hat keine gueltige Empfehlungsliste.")

    return Package(
        id=str(item["id"]),
        name=str(item["name"]),
        category=str(item["category"]),
        winget_id=str(item["winget_id"]),
        description=str(item["description"]),
        recommended_for=[str(value) for value in item["recommended_for"]],
        requires_admin=bool(item["requires_admin"]),
        enabled_by_default=bool(item["enabled_by_default"]),
    )
