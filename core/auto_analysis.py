from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core.app_settings import AppSettings, PRESET_IMPORTED
from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.offline_cache import CacheSummary


AUTO_READY = "bereit"
AUTO_RUNNING = "laeuft"
AUTO_COMPLETED = "abgeschlossen"
AUTO_FAILED = "fehlgeschlagen"


@dataclass(frozen=True)
class AutoAnalysisSnapshot:
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float = 0.0
    findings_count: int = 0
    warnings: list[str] = None
    errors: list[str] = None
    latest_session_name: str | None = None
    latest_report_failures: int = 0
    preset_status: str = "kein gespeichertes Preset"
    guard_findings_count: int = 0
    cache_present_count: int = 0
    cache_planned_count: int = 0
    cache_warnings_count: int = 0
    actions_started: bool = False

    def __post_init__(self) -> None:
        if self.warnings is None:
            object.__setattr__(self, "warnings", [])
        if self.errors is None:
            object.__setattr__(self, "errors", [])

    def to_dict(self) -> dict:
        return asdict(self)


def ready_auto_analysis() -> AutoAnalysisSnapshot:
    return AutoAnalysisSnapshot(status=AUTO_READY)


def running_auto_analysis(started_at: str | None = None) -> AutoAnalysisSnapshot:
    return AutoAnalysisSnapshot(status=AUTO_RUNNING, started_at=started_at or datetime.now().isoformat(timespec="seconds"))


def build_auto_analysis_snapshot(
    *,
    started_at: datetime,
    is_admin: bool,
    winget_available: bool,
    app_settings: AppSettings,
    latest_session_name: str | None,
    latest_payload: dict,
    diagnostic_findings: list[DiagnosticFinding],
    guard_findings: list[GuardRiskFinding],
    cache_summary: CacheSummary | None = None,
    error: str | None = None,
) -> AutoAnalysisSnapshot:
    finished_at = datetime.now()
    warnings: list[str] = []
    errors: list[str] = []
    if not is_admin:
        warnings.append("Adminrechte fehlen; Systemaktionen bleiben blockiert.")
    if not winget_available:
        warnings.append("winget wurde nicht gefunden.")
    preset_status = _preset_status(app_settings)
    if error:
        errors.append(error)
    latest_failures = len(_payload_failures(latest_payload))
    return AutoAnalysisSnapshot(
        status=AUTO_FAILED if errors else AUTO_COMPLETED,
        started_at=started_at.isoformat(timespec="seconds"),
        finished_at=finished_at.isoformat(timespec="seconds"),
        duration_seconds=round((finished_at - started_at).total_seconds(), 3),
        findings_count=len(diagnostic_findings),
        warnings=warnings,
        errors=errors,
        latest_session_name=latest_session_name,
        latest_report_failures=latest_failures,
        preset_status=preset_status,
        guard_findings_count=len(guard_findings),
        cache_present_count=cache_summary.present_count if cache_summary else 0,
        cache_planned_count=cache_summary.planned_count if cache_summary else 0,
        cache_warnings_count=len(cache_summary.warnings) if cache_summary else 0,
        actions_started=False,
    )


def failed_auto_analysis(started_at: datetime, message: str) -> AutoAnalysisSnapshot:
    return build_auto_analysis_snapshot(
        started_at=started_at,
        is_admin=False,
        winget_available=False,
        app_settings=AppSettings(),
        latest_session_name=None,
        latest_payload={},
        diagnostic_findings=[],
        guard_findings=[],
        error=message,
    )


def _preset_status(app_settings: AppSettings) -> str:
    if app_settings.last_preset_kind == PRESET_IMPORTED and app_settings.last_profile_path:
        path = Path(app_settings.last_profile_path)
        return f"importiert: {path.name}" if path.exists() else f"importiertes Preset fehlt: {path.name}"
    if app_settings.last_profile_id:
        return f"eingebaut: {app_settings.last_profile_id}"
    return "kein gespeichertes Preset"


def _payload_failures(payload: dict) -> list[dict]:
    failures: list[dict] = []
    setup = payload.get("setup", {})
    failures.extend(action for action in setup.get("actions", []) if action.get("status") == "failed")
    failures.extend(item for item in payload.get("tuning", []) if item.get("status") == "failed")
    failures.extend(item for item in payload.get("maintenance", []) if item.get("status") == "failed")
    return failures
