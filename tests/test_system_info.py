from __future__ import annotations

import subprocess
from pathlib import Path

from core.system_info import (
    SYSTEM_INFO_STATUS_DRY_RUN,
    SYSTEM_INFO_STATUS_FAILED,
    SYSTEM_INFO_STATUS_SUCCESS,
    SystemInfoError,
    _assert_safe_export_path,
    build_system_info_export_path,
    export_system_info_txt,
    system_info_root,
)


def test_build_system_info_export_path_stays_under_reports_systeminfo(tmp_path: Path) -> None:
    path = build_system_info_export_path(tmp_path)

    assert path.parent == system_info_root(tmp_path)
    assert path.name.startswith("systeminfo-")
    assert path.suffix == ".txt"


def test_system_info_dry_run_does_not_call_runner(tmp_path: Path) -> None:
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("runner must not be called")

    result = export_system_info_txt(tmp_path, dry_run=True, runner=runner)

    assert result.status == SYSTEM_INFO_STATUS_DRY_RUN
    assert result.dry_run is True
    assert result.exit_code == 0
    assert called is False


def test_system_info_success_uses_existing_export_file(tmp_path: Path) -> None:
    def runner(command, **kwargs):
        Path(command[2]).write_text("System Summary", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = export_system_info_txt(tmp_path, runner=runner)

    assert result.status == SYSTEM_INFO_STATUS_SUCCESS
    assert result.size_bytes > 0
    assert Path(result.export_path).exists()
    assert result.error is None


def test_system_info_timeout_returns_failed_result(tmp_path: Path) -> None:
    def runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    result = export_system_info_txt(tmp_path, timeout_seconds=1, runner=runner)

    assert result.status == SYSTEM_INFO_STATUS_FAILED
    assert "Timeout" in (result.error or "")


def test_system_info_rejects_path_outside_report_root(tmp_path: Path) -> None:
    try:
        _assert_safe_export_path(tmp_path, tmp_path.parent / "outside.txt")
    except SystemInfoError as exc:
        assert "ausserhalb" in str(exc)
    else:
        raise AssertionError("unsafe system info path was accepted")
