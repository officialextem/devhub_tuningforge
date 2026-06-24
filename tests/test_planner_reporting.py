import json
from datetime import datetime
from pathlib import Path

from core.catalog import load_catalog
from core.alerting import AlertItem, DailyReportSummary
from core.app_config import APP_DISPLAY_NAME, SESSION_REPORT_PREFIX, SETUP_REPORT_PREFIX
from core.app_settings import AppSettings
from core.auto_analysis import build_auto_analysis_snapshot
from core.configuration import DevHubConfig
from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.offline_cache import CacheEntry, CacheSummary
from core.planner import build_action_plan
from core.profiles import load_profiles
from core.recovery import RecoverySummary, RecoveryTarget
from core.models import APP_NAME, APP_VERSION, MaintenanceResult, TuningAction, TuningResult
from core.reporting import create_report, write_session_report
from core.risk_engine import RiskFinding, RiskSummary
from core.system_info import SystemInfoExportResult


ROOT = Path(__file__).resolve().parent.parent


def test_preview_plan_reflects_selected_packages() -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    profile = next(p for p in load_profiles(ROOT / "profiles", packages) if p.id == "developer")

    plan = build_action_plan(profile, packages, {"git", "vscode"})

    assert [action.package.id for action in plan.actions] == ["git", "vscode"]
    assert plan.actions[0].command[:4] == ["winget", "install", "--id", "Git.Git"]


def test_report_writer_creates_json_and_txt(tmp_path: Path) -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    profile = next(p for p in load_profiles(ROOT / "profiles", packages) if p.id == "clean")
    plan = build_action_plan(profile, packages, {"firefox"})

    report = create_report(plan, tmp_path, "2026-06-17T12:00:00")

    assert report.json_path and report.json_path.exists()
    assert report.txt_path and report.txt_path.exists()
    data = json.loads(report.json_path.read_text(encoding="utf-8"))
    assert data["app_name"] == APP_DISPLAY_NAME == APP_NAME
    assert data["app_version"] == APP_VERSION
    assert report.json_path.name.startswith(f"{SETUP_REPORT_PREFIX}-")
    assert report.txt_path.name.startswith(f"{SETUP_REPORT_PREFIX}-")
    assert "Mozilla Firefox" in report.txt_path.read_text(encoding="utf-8")


def test_session_report_includes_all_action_categories(tmp_path: Path) -> None:
    packages = load_catalog(ROOT / "packages" / "catalog.json")
    profile = next(p for p in load_profiles(ROOT / "profiles", packages) if p.id == "clean")
    plan = build_action_plan(profile, packages, {"firefox"})
    setup_report = create_report(plan, tmp_path, "2026-06-17T12:00:00")
    tuning_result = TuningResult(
        action=TuningAction(
            "dns",
            "DNS Cache leeren",
            "Repair",
            "desc",
            ["ipconfig", "/flushdns"],
            "niedrig",
            True,
            True,
            "kurz",
            "Netzwerk reparieren",
        ),
        status="success",
        exit_code=0,
    )
    dry_tuning_result = TuningResult(
        action=TuningAction(
            "noop",
            "Dry-Run Beispiel",
            "Repair",
            "desc",
            ["cmd", "/c", "echo", "noop"],
            "niedrig",
            False,
        ),
        status="dry_run",
        exit_code=0,
        output=["Testmodus aktiv: Aktion wurde simuliert und nicht ausgefuehrt."],
    )
    maintenance_result = MaintenanceResult(
        name="Git",
        package_id="Git.Git",
        operation="update",
        status="failed",
        command=["winget", "upgrade", "--id", "Git.Git"],
        exit_code=2316632070,
        error="Exit-Code 2316632070",
        output=["line one", "line two"],
    )

    json_path, txt_path = write_session_report(
        tmp_path,
        setup_report=setup_report,
        tuning_results=[tuning_result, dry_tuning_result],
        maintenance_results=[maintenance_result],
        scan_warnings=["raw output excerpt"],
        diagnostic_findings=[
            DiagnosticFinding(
                problem="pytest Temp-Ordner gesperrt",
                severity="warning",
                evidence="PermissionError pytest-tmp",
                likely_cause="Windows-Dateisperre",
                recommended_fix="Frischen basetemp verwenden.",
                status="historical",
                source="logs/startup-error.log",
                source_timestamp="2026-06-17 19:37:26",
                last_success_timestamp="2026-06-18 01:59:31",
            )
        ],
        guard_findings=[
            GuardRiskFinding(
                risk_level="mittel",
                reason="Viele Loeschungen in kurzer Zeit erkannt.",
                affected_paths=["C:/Users/info/Documents/a.txt"],
                recommendation="Aenderungen pruefen.",
                event_count=3,
            )
        ],
        imported_profile_name="Arbeitsprofil",
        imported_profile_path="C:/Users/info/Desktop/arbeitsprofil.devhub-profile.json",
        exported_profile_path="C:/Users/info/Desktop/export.devhub-profile.json",
        profile_import_warnings=["Unbekannte Paket-ID ignoriert: ghost"],
        auto_analysis=build_auto_analysis_snapshot(
            started_at=datetime.now(),
            is_admin=True,
            winget_available=True,
            app_settings=AppSettings(),
            latest_session_name="devhub-session-old.json",
            latest_payload={},
            diagnostic_findings=[],
            guard_findings=[],
        ),
        offline_cache=CacheSummary(
            root="C:/cache/installers",
            index_path="C:/cache/installers/installer-cache.json",
            entries=[CacheEntry("git", "Git", "manual", "git.exe", status="missing", note="Datei fehlt.")],
            warnings=["Git: Datei fehlt."],
            checked_at="2026-06-18T10:00:00",
        ),
        recovery=RecoverySummary(
            recovery_root="C:/recovery",
            targets=[RecoveryTarget("profiles", "Profilordner", "C:/profiles", "folder", True, "missing", 0, "Pfad fehlt.")],
            warnings=["Profilordner: Pfad fehlt."],
            checked_at="2026-06-18T10:00:00",
        ),
        risk_summary=RiskSummary(
            overall_risk="mittel",
            score=3,
            findings=[RiskFinding("RecoveryForge", "mittel", "Recovery-Ziele unvollstaendig", "1 Ziel fehlt.", "Preview pruefen.")],
            checked_at="2026-06-18T10:00:00",
        ),
        daily_report=DailyReportSummary(
            report_date="2026-06-18",
            checked_at="2026-06-18T10:00:00",
            actions_total=3,
            failures_total=1,
            warnings_total=2,
            high_risks=0,
            medium_risks=1,
            latest_report_name="devhub-session-old.json",
            alerts=[AlertItem("warning", "Reports", "Fehler im Tagesverlauf", "1 Fehler", "Reports pruefen.", "2026-06-18T10:00:00")],
            recommendations=["Reports pruefen."],
        ),
        devhub_config=DevHubConfig(dry_run_enabled=True, auto_analysis_enabled=False, remember_last_preset=False),
        system_info=SystemInfoExportResult(
            status="dry_run",
            export_path="C:/reports/systeminfo/systeminfo-20260618.txt",
            size_bytes=0,
            duration_seconds=0.0,
            exit_code=0,
            dry_run=True,
        ),
    )

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["app_name"] == APP_DISPLAY_NAME
    assert json_path.name.startswith(f"{SESSION_REPORT_PREFIX}-")
    assert txt_path.name.startswith(f"{SESSION_REPORT_PREFIX}-")
    assert data["setup"]["actions"][0]["name"] == "Mozilla Firefox"
    assert data["tuning"][0]["name"] == "DNS Cache leeren"
    assert data["tuning"][0]["requires_reboot"] is True
    assert data["tuning"][0]["duration_hint"] == "kurz"
    assert data["tuning"][0]["impact"] == "Netzwerk reparieren"
    assert data["tuning"][1]["dry_run"] is True
    assert data["maintenance"][0]["operation"] == "update"
    assert data["maintenance"][0]["diagnostic"]
    assert data["maintenance"][0]["output_excerpt"] == "line one\nline two"
    assert data["scan_warnings"] == ["raw output excerpt"]
    assert data["diagnostics"][0]["problem"] == "pytest Temp-Ordner gesperrt"
    assert data["diagnostics"][0]["status"] == "historical"
    assert data["diagnostics"][0]["last_success_timestamp"] == "2026-06-18 01:59:31"
    assert data["guardforge"][0]["risk_level"] == "mittel"
    assert data["profile_io"]["imported_profile"] == "Arbeitsprofil"
    assert data["profile_io"]["export_path"].endswith("export.devhub-profile.json")
    assert data["profile_io"]["warnings"] == ["Unbekannte Paket-ID ignoriert: ghost"]
    assert data["auto_analysis"]["status"] == "abgeschlossen"
    assert data["auto_analysis"]["actions_started"] is False
    assert data["offline_cache"]["missing_count"] == 1
    assert data["offline_cache"]["warnings"] == ["Git: Datei fehlt."]
    assert data["recovery"]["missing_count"] == 1
    assert data["recovery"]["warnings"] == ["Profilordner: Pfad fehlt."]
    assert data["risk_engine"]["overall_risk"] == "mittel"
    assert data["risk_engine"]["actions_started"] is False
    assert data["daily_report"]["report_date"] == "2026-06-18"
    assert data["daily_report"]["actions_started"] is False
    assert data["configuration"]["dry_run_enabled"] is True
    assert data["configuration"]["auto_analysis_enabled"] is False
    assert data["system_info"]["status"] == "dry_run"
    assert data["system_info"]["dry_run"] is True
    text = txt_path.read_text(encoding="utf-8")
    assert "Maintenance" in text
    assert "Diagnose" in text
    assert "Historisch" in text
    assert "Letzter erfolgreicher Start: 2026-06-18 01:59:31" in text
    assert "Frischen basetemp verwenden" in text
    assert "GuardForge" in text
    assert "Viele Loeschungen" in text
    assert "Profilimport/-export" in text
    assert "Unbekannte Paket-ID ignoriert: ghost" in text
    assert "Auto-Analyse" in text
    assert "Automatische Aktionen gestartet: nein" in text
    assert "Offline Cache" in text
    assert "Git: Datei fehlt" in text
    assert "RecoveryForge" in text
    assert "Automatische Backups/Restore-Aktionen gestartet: nein" in text
    assert "Risk Engine" in text
    assert "Automatische Aktionen gestartet: nein" in text
    assert "Tagesbericht Preview" in text
    assert "Fehler im Tagesverlauf" in text
    assert "Konfiguration" in text
    assert "Testmodus: aktiv" in text
    assert "SystemInfo / MSINFO32" in text
    assert "Agent-Auswertung vorbereitet: ja" in text
    assert "Ausgabe-Auszug" in text
    assert "Neustart empfohlen" in text
    assert "Testmodus: nicht ausgefuehrt" in text
