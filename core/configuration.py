from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.app_config import APP_VERSION


CONFIG_VERSION = "1"
CONFIG_EXTENSION = ".devhub-config.json"
DEFAULT_ENABLED_MODULES = [
    "controldeck",
    "tuningforge",
    "guardforge",
    "offline_cache",
    "recoveryforge",
    "risk_engine",
    "daily_report",
    "systeminfo",
    "errordoctor",
    "reports",
]
KNOWN_MODULE_IDS = set(DEFAULT_ENABLED_MODULES)
REPORT_MODE_SESSION = "session"
REPORT_MODE_VERBOSE = "verbose"


class DevHubConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DevHubConfig:
    config_version: str = CONFIG_VERSION
    dry_run_enabled: bool = False
    auto_analysis_enabled: bool = True
    remember_last_preset: bool = True
    default_report_mode: str = REPORT_MODE_SESSION
    enabled_modules: list[str] = field(default_factory=lambda: list(DEFAULT_ENABLED_MODULES))
    app_version: str = APP_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def default_config_path(runtime_root: Path) -> Path:
    return runtime_root / "config" / "devhub-config.json"


def load_config(path: Path) -> DevHubConfig:
    if not path.exists():
        return DevHubConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DevHubConfig()
    try:
        return config_from_dict(payload)
    except DevHubConfigError:
        return DevHubConfig()


def save_config(path: Path, config: DevHubConfig) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_config(path: Path) -> DevHubConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DevHubConfigError("Konfigurationsdatei wurde nicht gefunden.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DevHubConfigError(f"Konfiguration konnte nicht gelesen werden: {exc}") from exc
    return config_from_dict(payload)


def write_config(config: DevHubConfig, path: Path) -> Path:
    if not path.name.endswith(CONFIG_EXTENSION):
        path = path.with_name(f"{path.name}{CONFIG_EXTENSION}")
    return save_config(path, config)


def config_from_dict(payload: object) -> DevHubConfig:
    if not isinstance(payload, dict):
        raise DevHubConfigError("Konfiguration muss ein JSON-Objekt sein.")
    allowed = {
        "config_version",
        "dry_run_enabled",
        "auto_analysis_enabled",
        "remember_last_preset",
        "default_report_mode",
        "enabled_modules",
        "app_version",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise DevHubConfigError(f"Unbekannte Konfigurationsfelder: {', '.join(sorted(unknown))}")
    if payload.get("config_version") != CONFIG_VERSION:
        raise DevHubConfigError("Konfigurationsversion wird nicht unterstuetzt.")

    enabled_modules = _string_list(payload.get("enabled_modules", DEFAULT_ENABLED_MODULES), "enabled_modules")
    unknown_modules = set(enabled_modules) - KNOWN_MODULE_IDS
    if unknown_modules:
        raise DevHubConfigError(f"Unbekannte Modul-IDs: {', '.join(sorted(unknown_modules))}")
    report_mode = _string_value(payload.get("default_report_mode", REPORT_MODE_SESSION), "default_report_mode")
    if report_mode not in {REPORT_MODE_SESSION, REPORT_MODE_VERBOSE}:
        raise DevHubConfigError("default_report_mode muss session oder verbose sein.")
    return DevHubConfig(
        config_version=CONFIG_VERSION,
        dry_run_enabled=_bool_value(payload.get("dry_run_enabled", False), "dry_run_enabled"),
        auto_analysis_enabled=_bool_value(payload.get("auto_analysis_enabled", True), "auto_analysis_enabled"),
        remember_last_preset=_bool_value(payload.get("remember_last_preset", True), "remember_last_preset"),
        default_report_mode=report_mode,
        enabled_modules=enabled_modules,
        app_version=_string_value(payload.get("app_version", APP_VERSION), "app_version"),
    )


def _bool_value(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise DevHubConfigError(f"{key} muss true oder false sein.")
    return value


def _string_value(value: object, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise DevHubConfigError(f"{key} muss ein nicht-leerer Textwert sein.")
    if "://" in value:
        raise DevHubConfigError(f"{key} darf keine Remote-URL enthalten.")
    return value


def _string_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        raise DevHubConfigError(f"{key} muss eine Liste sein.")
    result: list[str] = []
    for item in value:
        text = _string_value(item, key)
        if text not in result:
            result.append(text)
    return result
