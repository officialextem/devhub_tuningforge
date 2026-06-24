from datetime import datetime, timedelta

from core.app_settings import AppSettings, PRESET_IMPORTED
from core.auto_analysis import AUTO_COMPLETED, AUTO_FAILED, build_auto_analysis_snapshot, failed_auto_analysis
from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.offline_cache import CacheSummary


def test_auto_analysis_snapshot_collects_read_only_status() -> None:
    started_at = datetime.now() - timedelta(seconds=1)
    finding = DiagnosticFinding("winget nicht erreichbar", "error", "missing", "PATH", "Installer pruefen.")
    guard = GuardRiskFinding("mittel", "Viele Loeschungen", ["C:/tmp/a.txt"], "Pruefen.", 3)
    payload = {"setup": {"actions": [{"name": "Git", "status": "failed"}]}, "tuning": [], "maintenance": []}
    cache_summary = CacheSummary("C:/cache/installers", "C:/cache/installers/installer-cache.json", [], ["bad cache"], "2026-06-18T10:00:00")

    snapshot = build_auto_analysis_snapshot(
        started_at=started_at,
        is_admin=False,
        winget_available=False,
        app_settings=AppSettings(last_preset_kind=PRESET_IMPORTED, last_profile_path="C:/missing.devhub-profile.json"),
        latest_session_name="devhub-session.json",
        latest_payload=payload,
        diagnostic_findings=[finding],
        guard_findings=[guard],
        cache_summary=cache_summary,
    )

    assert snapshot.status == AUTO_COMPLETED
    assert snapshot.findings_count == 1
    assert snapshot.guard_findings_count == 1
    assert snapshot.latest_report_failures == 1
    assert snapshot.cache_warnings_count == 1
    assert snapshot.actions_started is False
    assert "Adminrechte fehlen" in snapshot.warnings[0]
    assert "winget" in snapshot.warnings[1]
    assert snapshot.preset_status.startswith("importiertes Preset fehlt")


def test_auto_analysis_tolerates_missing_reports_and_no_preset() -> None:
    snapshot = build_auto_analysis_snapshot(
        started_at=datetime.now(),
        is_admin=True,
        winget_available=True,
        app_settings=AppSettings(),
        latest_session_name=None,
        latest_payload={},
        diagnostic_findings=[],
        guard_findings=[],
    )

    assert snapshot.status == AUTO_COMPLETED
    assert snapshot.warnings == []
    assert snapshot.latest_session_name is None
    assert snapshot.latest_report_failures == 0
    assert snapshot.preset_status == "kein gespeichertes Preset"


def test_failed_auto_analysis_is_reportable_without_actions() -> None:
    snapshot = failed_auto_analysis(datetime.now(), "read failed")

    assert snapshot.status == AUTO_FAILED
    assert snapshot.errors == ["read failed"]
    assert snapshot.actions_started is False
