from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core.app_config import APP_VERSION


PROFILE_VERSION = "1"
PROFILE_EXTENSION = ".devhub-profile.json"
PROFILE_KEYS = {
    "devhub_profile_version",
    "name",
    "description",
    "selected_packages",
    "selected_tuning_actions",
    "guardforge_enabled_paths",
    "created_at",
    "app_version",
}
SCRIPT_SUFFIXES = (".bat", ".cmd", ".ps1", ".vbs", ".js", ".py", ".exe", ".msi")


class DevHubProfileError(ValueError):
    pass


@dataclass(frozen=True)
class DevHubProfile:
    devhub_profile_version: str
    name: str
    description: str
    selected_packages: list[str]
    selected_tuning_actions: list[str]
    guardforge_enabled_paths: list[str]
    created_at: str
    app_version: str


@dataclass(frozen=True)
class ImportedProfile:
    profile: DevHubProfile
    selected_packages: set[str]
    selected_tuning_actions: set[str]
    guardforge_enabled_paths: list[str]
    warnings: list[str]


def build_profile(
    name: str,
    description: str,
    selected_packages: set[str] | list[str],
    selected_tuning_actions: set[str] | list[str],
    guardforge_enabled_paths: list[str],
) -> DevHubProfile:
    profile = DevHubProfile(
        devhub_profile_version=PROFILE_VERSION,
        name=name.strip() or "DEVHub Profil",
        description=description.strip(),
        selected_packages=sorted(set(selected_packages)),
        selected_tuning_actions=sorted(set(selected_tuning_actions)),
        guardforge_enabled_paths=list(dict.fromkeys(guardforge_enabled_paths)),
        created_at=datetime.now().isoformat(timespec="seconds"),
        app_version=APP_VERSION,
    )
    _validate_profile(profile)
    return profile


def write_profile(profile: DevHubProfile, path: Path) -> Path:
    _validate_profile(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_profile(path: Path, known_package_ids: set[str], known_tuning_ids: set[str]) -> ImportedProfile:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DevHubProfileError(f"Profil-JSON ist ungueltig: {exc}") from exc
    except OSError as exc:
        raise DevHubProfileError(f"Profil konnte nicht gelesen werden: {exc}") from exc

    profile = _profile_from_payload(raw)
    _validate_profile(profile)

    warnings: list[str] = []
    selected_packages = _known_selection(
        profile.selected_packages,
        known_package_ids,
        "Paket",
        warnings,
    )
    selected_tuning_actions = _known_selection(
        profile.selected_tuning_actions,
        known_tuning_ids,
        "Tuning-Aktion",
        warnings,
    )

    return ImportedProfile(
        profile=profile,
        selected_packages=selected_packages,
        selected_tuning_actions=selected_tuning_actions,
        guardforge_enabled_paths=profile.guardforge_enabled_paths,
        warnings=warnings,
    )


def _profile_from_payload(payload: object) -> DevHubProfile:
    if not isinstance(payload, dict):
        raise DevHubProfileError("Profil muss ein JSON-Objekt sein.")
    unknown_keys = set(payload) - PROFILE_KEYS
    missing_keys = PROFILE_KEYS - set(payload)
    if unknown_keys:
        raise DevHubProfileError(f"Profil enthaelt unbekannte Felder: {', '.join(sorted(unknown_keys))}")
    if missing_keys:
        raise DevHubProfileError(f"Profil enthaelt fehlende Felder: {', '.join(sorted(missing_keys))}")

    return DevHubProfile(
        devhub_profile_version=_required_string(payload, "devhub_profile_version"),
        name=_required_string(payload, "name"),
        description=_required_string(payload, "description"),
        selected_packages=_required_string_list(payload, "selected_packages"),
        selected_tuning_actions=_required_string_list(payload, "selected_tuning_actions"),
        guardforge_enabled_paths=_required_string_list(payload, "guardforge_enabled_paths"),
        created_at=_required_string(payload, "created_at"),
        app_version=_required_string(payload, "app_version"),
    )


def _validate_profile(profile: DevHubProfile) -> None:
    if profile.devhub_profile_version != PROFILE_VERSION:
        raise DevHubProfileError(f"Profilversion nicht unterstuetzt: {profile.devhub_profile_version}")
    for label, value in (
        ("name", profile.name),
        ("description", profile.description),
        ("created_at", profile.created_at),
        ("app_version", profile.app_version),
    ):
        _reject_unsafe_string(label, value)
    for field_name, values in (
        ("selected_packages", profile.selected_packages),
        ("selected_tuning_actions", profile.selected_tuning_actions),
        ("guardforge_enabled_paths", profile.guardforge_enabled_paths),
    ):
        for value in values:
            _reject_unsafe_string(field_name, value)
    for path in profile.guardforge_enabled_paths:
        if Path(path).suffix.casefold() in SCRIPT_SUFFIXES:
            raise DevHubProfileError("GuardForge-Pfade duerfen keine Script- oder Installer-Dateien sein.")


def _reject_unsafe_string(label: str, value: str) -> None:
    if "://" in value:
        raise DevHubProfileError(f"{label} darf keine Remote-URL enthalten.")
    if "\x00" in value:
        raise DevHubProfileError(f"{label} enthaelt ungueltige Steuerzeichen.")


def _required_string(payload: dict, key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise DevHubProfileError(f"{key} muss ein Textwert sein.")
    return value


def _required_string_list(payload: dict, key: str) -> list[str]:
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DevHubProfileError(f"{key} muss eine Liste aus Textwerten sein.")
    return value


def _known_selection(values: list[str], known_ids: set[str], label: str, warnings: list[str]) -> set[str]:
    selected: set[str] = set()
    for value in values:
        if value in known_ids:
            selected.add(value)
        else:
            warnings.append(f"Unbekannte {label}-ID ignoriert: {value}")
    return selected
