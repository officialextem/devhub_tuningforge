from pathlib import Path

from core.recovery import (
    RECOVERY_STATUS_INVALID,
    RECOVERY_STATUS_MISSING,
    RECOVERY_STATUS_PRESENT,
    RecoveryTarget,
    default_recovery_targets,
    inspect_recovery_targets,
    recovery_root,
)


def test_recovery_root_is_local_runtime_folder(tmp_path: Path) -> None:
    assert recovery_root(tmp_path) == tmp_path / "recovery"


def test_default_recovery_targets_include_configs_reports_and_cache(tmp_path: Path) -> None:
    targets = {target.id: target for target in default_recovery_targets(tmp_path, tmp_path)}

    assert {"app-state", "profiles", "packages", "tuning", "reports", "logs", "offline-cache-index"}.issubset(targets)
    assert targets["profiles"].kind == "folder"
    assert targets["packages"].required is True


def test_recovery_preview_marks_present_and_missing_targets(tmp_path: Path) -> None:
    present = tmp_path / "config.json"
    present.write_text("{}", encoding="utf-8")
    targets = [
        RecoveryTarget("config", "Config", str(present), "config", True),
        RecoveryTarget("missing", "Missing", str(tmp_path / "missing.json"), "config", True),
    ]

    summary = inspect_recovery_targets(tmp_path, targets)

    assert summary.present_count == 1
    assert summary.missing_count == 1
    assert summary.targets[0].status == RECOVERY_STATUS_PRESENT
    assert summary.targets[1].status == RECOVERY_STATUS_MISSING
    assert summary.warnings


def test_recovery_preview_rejects_remote_and_wrong_kind(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    targets = [
        RecoveryTarget("remote", "Remote", "https://example.test/config.json", "config", True),
        RecoveryTarget("wrong", "Wrong Kind", str(folder), "config", True),
    ]

    summary = inspect_recovery_targets(tmp_path, targets)

    assert summary.invalid_count == 2
    assert all(target.status == RECOVERY_STATUS_INVALID for target in summary.targets)
    assert "Remote" in summary.warnings[0]
