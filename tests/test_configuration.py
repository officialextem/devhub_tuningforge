import json
from pathlib import Path

from core.configuration import (
    CONFIG_EXTENSION,
    DevHubConfig,
    DevHubConfigError,
    config_from_dict,
    load_config,
    read_config,
    save_config,
    write_config,
)


def test_config_roundtrip_local_json(tmp_path: Path) -> None:
    path = tmp_path / "devhub-config.json"
    config = DevHubConfig(
        dry_run_enabled=True,
        auto_analysis_enabled=False,
        remember_last_preset=False,
        default_report_mode="verbose",
        enabled_modules=["controldeck", "risk_engine"],
    )

    save_config(path, config)
    loaded = read_config(path)

    assert loaded.dry_run_enabled is True
    assert loaded.auto_analysis_enabled is False
    assert loaded.remember_last_preset is False
    assert loaded.default_report_mode == "verbose"
    assert loaded.enabled_modules == ["controldeck", "risk_engine"]


def test_config_rejects_unknown_fields_urls_and_modules() -> None:
    payload = DevHubConfig().to_dict()
    payload["remote_url"] = "https://example.invalid"
    try:
        config_from_dict(payload)
    except DevHubConfigError as exc:
        assert "Unbekannte Konfigurationsfelder" in str(exc)
    else:
        raise AssertionError("unknown config field was accepted")

    payload = DevHubConfig(enabled_modules=["controldeck", "ghost"]).to_dict()
    try:
        config_from_dict(payload)
    except DevHubConfigError as exc:
        assert "Unbekannte Modul-IDs" in str(exc)
    else:
        raise AssertionError("unknown module id was accepted")

    payload = DevHubConfig().to_dict()
    payload["default_report_mode"] = "https://example.invalid"
    try:
        config_from_dict(payload)
    except DevHubConfigError as exc:
        assert "Remote-URL" in str(exc)
    else:
        raise AssertionError("remote config value was accepted")


def test_load_config_falls_back_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.devhub-config.json"
    path.write_text("{bad json", encoding="utf-8")

    assert load_config(path) == DevHubConfig()


def test_write_config_enforces_extension(tmp_path: Path) -> None:
    path = write_config(DevHubConfig(), tmp_path / "export")

    assert path.name.endswith(CONFIG_EXTENSION)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["config_version"] == "1"
