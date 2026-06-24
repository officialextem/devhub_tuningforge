from core.alerting import AlertItem, DailyReportSummary
from core.app_settings import AppSettings, PRESET_IMPORTED
from core.configuration import DevHubConfig
from core.auto_analysis import running_auto_analysis
from core.dashboard import build_dashboard_snapshot, payload_failures
from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.models import AvailableUpdate, MaintenanceResult, Profile, TuningAction, TuningResult
from core.offline_cache import CacheSummary
from core.recovery import RecoverySummary
from core.risk_engine import RiskFinding, RiskSummary
from core.system_info import SystemInfoExportResult


def test_dashboard_snapshot_includes_preset_modules_and_report_failures() -> None:
    profile = Profile("developer", "Developer", "Dev tools", ["git"], [], [])
    payload = {
        "setup": {"actions": [{"name": "Git", "status": "failed", "diagnostic": "Installer blockiert."}]},
        "tuning": [],
        "maintenance": [],
        "scan_warnings": ["winget output clipped"],
    }

    snapshot = build_dashboard_snapshot(
        is_admin=True,
        winget_available=True,
        selected_profile=profile,
        selected_package_count=3,
        selected_tuning_count=2,
        installed_programs=[],
        available_updates=[],
        maintenance_results=[],
        tuning_results=[],
        scan_warnings=[],
        diagnostic_findings=[],
        guard_findings=[],
        latest_session_name="devhub-session-20260618.txt",
        latest_log_name="tuningforge.log",
        latest_payload=payload,
        app_settings=AppSettings(),
        auto_analysis=running_auto_analysis("2026-06-18T10:00:00"),
        offline_cache=CacheSummary("C:/cache/installers", "C:/cache/installers/installer-cache.json", [], [], "2026-06-18T10:00:00"),
        recovery=RecoverySummary("C:/recovery", [], [], "2026-06-18T10:00:00"),
        risk_summary=RiskSummary("mittel", 3, [RiskFinding("Reports", "mittel", "Fehler", "1 Fehler", "Report pruefen.")], "2026-06-18T10:00:00"),
        daily_report=DailyReportSummary(
            "2026-06-18",
            "2026-06-18T10:00:00",
            2,
            1,
            1,
            0,
            1,
            "devhub-session.json",
            [AlertItem("warning", "Reports", "Fehler", "1 Fehler", "Report pruefen.", "2026-06-18T10:00:00")],
            ["Report pruefen."],
        ),
        devhub_config=DevHubConfig(dry_run_enabled=True, auto_analysis_enabled=False, remember_last_preset=False),
        system_info=SystemInfoExportResult("success", "C:/reports/systeminfo/systeminfo.txt", 2048),
    )

    cards = {card.title: card for card in snapshot.cards}
    modules = {module.id: module for module in snapshot.modules}
    assert cards["Preset"].value == "Developer"
    assert cards["Auto-Analyse"].value == "laeuft"
    assert cards["Offline Cache"].value == "0"
    assert cards["RecoveryForge"].value == "0"
    assert cards["Risk Engine"].value == "mittel"
    assert cards["Tagesbericht"].value == "2026-06-18"
    assert cards["Konfiguration"].value == "Testmodus"
    assert cards["SystemInfo"].value == "success"
    assert cards["Reports"].level == "error"
    assert modules["auto_analysis"].page_id == 0
    assert modules["offline_cache"].page_id == 16
    assert modules["recoveryforge"].page_id == 17
    assert modules["risk_engine"].page_id == 18
    assert modules["daily_report"].page_id == 19
    assert modules["configuration"].page_id == 20
    assert modules["systeminfo"].page_id == 21
    assert modules["profile"].page_id == 1
    assert modules["tuningforge"].page_id == 2
    assert modules["guardforge"].page_id == 15
    assert any("Letzter Report: Git fehlgeschlagen" in item for item in snapshot.recommendations)


def test_dashboard_counts_active_historical_diagnostics_and_guard_findings() -> None:
    active = DiagnosticFinding("winget nicht erreichbar", "error", "missing", "PATH", "Installer pruefen.")
    historical = DiagnosticFinding(
        "Tcl/Tk-Installation defekt",
        "error",
        "old traceback",
        "Python defekt",
        "Python reparieren.",
        status="historical",
    )
    guard = GuardRiskFinding("mittel", "Viele Loeschungen", ["C:/tmp/a.txt"], "Pruefen.", 3)

    snapshot = build_dashboard_snapshot(
        is_admin=False,
        winget_available=False,
        selected_profile=None,
        selected_package_count=0,
        selected_tuning_count=0,
        installed_programs=[],
        available_updates=[AvailableUpdate("git", "Git", "Git.Git", "1", "2", "winget")],
        maintenance_results=[],
        tuning_results=[],
        scan_warnings=[],
        diagnostic_findings=[active, historical],
        guard_findings=[guard],
        latest_session_name=None,
        latest_log_name=None,
        latest_payload={},
        app_settings=AppSettings(last_preset_kind=PRESET_IMPORTED, last_profile_path="C:/preset.devhub-profile.json"),
    )

    cards = {card.title: card for card in snapshot.cards}
    modules = {module.id: module for module in snapshot.modules}
    assert cards["Admin"].level == "error"
    assert cards["Diagnose"].value == "1"
    assert cards["GuardForge"].value == "1"
    assert modules["errordoctor"].status == "1 aktiv"
    assert modules["guardforge"].level == "warning"
    assert any("Noch kein Session-Bericht" in item for item in snapshot.recommendations)


def test_dashboard_recommendations_include_failed_runtime_results() -> None:
    tuning = TuningResult(
        action=TuningAction("dns", "DNS Cache leeren", "Repair", "desc", ["ipconfig"], "niedrig", True),
        status="failed",
        exit_code=1,
        error="DNS fehlgeschlagen",
    )
    maintenance = MaintenanceResult(
        name="Git",
        package_id="Git.Git",
        operation="update",
        status="failed",
        exit_code=1603,
        error="Installerfehler",
    )

    snapshot = build_dashboard_snapshot(
        is_admin=True,
        winget_available=True,
        selected_profile=None,
        selected_package_count=0,
        selected_tuning_count=1,
        installed_programs=[],
        available_updates=[],
        maintenance_results=[maintenance],
        tuning_results=[tuning],
        scan_warnings=[],
        diagnostic_findings=[],
        guard_findings=[],
        latest_session_name="devhub-session.txt",
        latest_log_name=None,
        latest_payload={},
        app_settings=AppSettings(),
    )

    assert any("update fehlgeschlagen: Git" in item for item in snapshot.recommendations)
    assert any("Tuning fehlgeschlagen: DNS Cache leeren" in item for item in snapshot.recommendations)


def test_payload_failures_reads_all_session_categories() -> None:
    payload = {
        "setup": {"actions": [{"status": "failed"}, {"status": "success"}]},
        "tuning": [{"status": "failed"}],
        "maintenance": [{"status": "failed"}],
    }

    assert len(payload_failures(payload)) == 3
