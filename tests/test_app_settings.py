import json
from pathlib import Path

from core.app_settings import PRESET_BUILTIN, PRESET_IMPORTED, AppSettings, load_app_settings, save_app_settings


def test_app_settings_roundtrip_last_builtin_preset(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app-state.json"

    save_app_settings(path, AppSettings(last_preset_kind=PRESET_BUILTIN, last_profile_id="developer"))

    loaded = load_app_settings(path)
    assert loaded.last_preset_kind == PRESET_BUILTIN
    assert loaded.last_profile_id == "developer"
    assert loaded.last_profile_path is None


def test_app_settings_roundtrip_last_imported_preset(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app-state.json"
    profile_path = "C:/Users/info/Desktop/work.devhub-profile.json"

    save_app_settings(path, AppSettings(last_preset_kind=PRESET_IMPORTED, last_profile_path=profile_path))

    loaded = load_app_settings(path)
    assert loaded.last_preset_kind == PRESET_IMPORTED
    assert loaded.last_profile_path == profile_path


def test_app_settings_falls_back_on_invalid_or_remote_state(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app-state.json"
    path.parent.mkdir()
    path.write_text("{broken", encoding="utf-8")

    assert load_app_settings(path) == AppSettings()

    path.write_text(
        json.dumps(
            {
                "settings_version": "1",
                "last_preset_kind": PRESET_IMPORTED,
                "last_profile_id": None,
                "last_profile_path": "https://example.test/profile.devhub-profile.json",
            }
        ),
        encoding="utf-8",
    )

    assert load_app_settings(path) == AppSettings()
