from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.models import Package, Profile


PROFILE_FIELDS = {"id", "name", "description", "packages", "folders", "notes"}


class ProfileError(ValueError):
    pass


def load_profiles(directory: Path, packages: list[Package]) -> list[Profile]:
    package_ids = {package.id for package in packages}
    profiles = [_parse_profile(path, package_ids) for path in sorted(directory.glob("*.json"))]
    if not profiles:
        raise ProfileError("Es wurden keine Profile gefunden.")

    ids = [profile.id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise ProfileError("Die Profile enthalten doppelte IDs.")
    return profiles


def _parse_profile(path: Path, package_ids: set[str]) -> Profile:
    item: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    missing = PROFILE_FIELDS - set(item)
    if missing:
        raise ProfileError(f"Profil {path.name} enthaelt fehlende Felder: {', '.join(sorted(missing))}")

    referenced = [str(value) for value in item["packages"]]
    unknown = sorted(set(referenced) - package_ids)
    if unknown:
        raise ProfileError(f"Profil {path.name} referenziert unbekannte Pakete: {', '.join(unknown)}")

    return Profile(
        id=str(item["id"]),
        name=str(item["name"]),
        description=str(item["description"]),
        packages=referenced,
        folders=[str(value) for value in item["folders"]],
        notes=[str(value) for value in item["notes"]],
    )
