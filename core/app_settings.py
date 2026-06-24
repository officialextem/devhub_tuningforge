from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


APP_SETTINGS_VERSION = "1"
PRESET_BUILTIN = "builtin"
PRESET_IMPORTED = "imported"


@dataclass(frozen=True)
class AppSettings:
    settings_version: str = APP_SETTINGS_VERSION
    last_preset_kind: str = PRESET_BUILTIN
    last_profile_id: str | None = None
    last_profile_path: str | None = None


def load_app_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(payload, dict):
        return AppSettings()
    if payload.get("settings_version") != APP_SETTINGS_VERSION:
        return AppSettings()

    kind = payload.get("last_preset_kind", PRESET_BUILTIN)
    profile_id = payload.get("last_profile_id")
    profile_path = payload.get("last_profile_path")
    if kind not in {PRESET_BUILTIN, PRESET_IMPORTED}:
        return AppSettings()
    if profile_id is not None and not isinstance(profile_id, str):
        return AppSettings()
    if profile_path is not None and not isinstance(profile_path, str):
        return AppSettings()
    if profile_path and "://" in profile_path:
        return AppSettings()
    return AppSettings(
        last_preset_kind=kind,
        last_profile_id=profile_id,
        last_profile_path=profile_path,
    )


def save_app_settings(path: Path, settings: AppSettings) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
