import json
from pathlib import Path

import pytest

from core.app_config import APP_VERSION
from core.profile_io import (
    PROFILE_EXTENSION,
    DevHubProfileError,
    build_profile,
    read_profile,
    write_profile,
)


def test_export_writes_valid_devhub_profile_json(tmp_path: Path) -> None:
    profile = build_profile(
        name="Arbeitsprofil",
        description="Lokaler Export",
        selected_packages={"git", "vscode"},
        selected_tuning_actions={"dns"},
        guardforge_enabled_paths=["C:/Users/info/Documents"],
    )
    path = tmp_path / f"arbeitsprofil{PROFILE_EXTENSION}"

    write_profile(profile, path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["devhub_profile_version"] == "1"
    assert data["name"] == "Arbeitsprofil"
    assert data["selected_packages"] == ["git", "vscode"]
    assert data["selected_tuning_actions"] == ["dns"]
    assert data["guardforge_enabled_paths"] == ["C:/Users/info/Documents"]
    assert data["app_version"] == APP_VERSION


def test_import_sets_known_packages_tuning_and_guard_paths(tmp_path: Path) -> None:
    profile = build_profile(
        name="Import",
        description="Bekannte IDs",
        selected_packages={"git"},
        selected_tuning_actions={"dns"},
        guardforge_enabled_paths=["C:/Users/info/Desktop"],
    )
    path = tmp_path / f"import{PROFILE_EXTENSION}"
    write_profile(profile, path)

    imported = read_profile(path, known_package_ids={"git", "vscode"}, known_tuning_ids={"dns", "winsock"})

    assert imported.selected_packages == {"git"}
    assert imported.selected_tuning_actions == {"dns"}
    assert imported.guardforge_enabled_paths == ["C:/Users/info/Desktop"]
    assert imported.warnings == []


def test_import_ignores_unknown_ids_and_reports_warnings(tmp_path: Path) -> None:
    payload = {
        "devhub_profile_version": "1",
        "name": "Teilimport",
        "description": "Mit unbekannten IDs",
        "selected_packages": ["git", "unknown-package"],
        "selected_tuning_actions": ["dns", "unknown-tuning"],
        "guardforge_enabled_paths": ["C:/Users/info/Documents"],
        "created_at": "2026-06-18T02:00:00",
        "app_version": APP_VERSION,
    }
    path = tmp_path / f"teilimport{PROFILE_EXTENSION}"
    path.write_text(json.dumps(payload), encoding="utf-8")

    imported = read_profile(path, known_package_ids={"git"}, known_tuning_ids={"dns"})

    assert imported.selected_packages == {"git"}
    assert imported.selected_tuning_actions == {"dns"}
    assert imported.warnings == [
        "Unbekannte Paket-ID ignoriert: unknown-package",
        "Unbekannte Tuning-Aktion-ID ignoriert: unknown-tuning",
    ]


def test_invalid_json_is_rejected_cleanly(tmp_path: Path) -> None:
    path = tmp_path / f"broken{PROFILE_EXTENSION}"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(DevHubProfileError, match="ungueltig"):
        read_profile(path, known_package_ids=set(), known_tuning_ids=set())


def test_profile_schema_rejects_unknown_fields_remote_urls_and_scripts(tmp_path: Path) -> None:
    payload = {
        "devhub_profile_version": "1",
        "name": "Unsicher",
        "description": "Keine Aktion",
        "selected_packages": [],
        "selected_tuning_actions": [],
        "guardforge_enabled_paths": ["C:/Users/info/Desktop/run.ps1"],
        "created_at": "2026-06-18T02:00:00",
        "app_version": APP_VERSION,
    }
    path = tmp_path / f"script{PROFILE_EXTENSION}"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DevHubProfileError, match="Script"):
        read_profile(path, known_package_ids=set(), known_tuning_ids=set())

    payload["guardforge_enabled_paths"] = []
    payload["command"] = "winget install"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DevHubProfileError, match="unbekannte Felder"):
        read_profile(path, known_package_ids=set(), known_tuning_ids=set())
