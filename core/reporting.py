from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from core.alerting import DailyReportSummary
from core.auto_analysis import AutoAnalysisSnapshot
from core.app_config import SESSION_REPORT_PREFIX, SETUP_REPORT_PREFIX
from core.configuration import DevHubConfig
from core.diagnostics import DiagnosticFinding, diagnostic_hint, output_excerpt
from core.guardforge import GuardRiskFinding
from core.models import APP_NAME, APP_VERSION, ActionPlan, MaintenanceResult, RunReport, TuningResult
from core.offline_cache import CacheSummary
from core.recovery import RecoverySummary
from core.risk_engine import RiskSummary
from core.system_info import SystemInfoExportResult


def create_report(plan: ActionPlan, reports_dir: Path, started_at: str) -> RunReport:
    finished_at = datetime.now().isoformat(timespec="seconds")
    report = RunReport(
        app_name=APP_NAME,
        app_version=APP_VERSION,
        profile=plan.profile,
        actions=plan.actions,
        folders=plan.folders,
        started_at=started_at,
        finished_at=finished_at,
    )
    write_report(report, reports_dir)
    return report


def write_report(report: RunReport, reports_dir: Path) -> RunReport:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{SETUP_REPORT_PREFIX}-{timestamp}"
    json_path = reports_dir / f"{base}.json"
    txt_path = reports_dir / f"{base}.txt"

    json_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    txt_path.write_text(_render_text_report(report), encoding="utf-8")

    report.json_path = json_path
    report.txt_path = txt_path
    return report


def write_session_report(
    reports_dir: Path,
    setup_report: RunReport | None = None,
    tuning_results: list[TuningResult] | None = None,
    maintenance_results: list[MaintenanceResult] | None = None,
    scan_warnings: list[str] | None = None,
    diagnostic_findings: list[DiagnosticFinding] | None = None,
    guard_findings: list[GuardRiskFinding] | None = None,
    imported_profile_name: str | None = None,
    imported_profile_path: str | None = None,
    exported_profile_path: str | None = None,
    profile_import_warnings: list[str] | None = None,
    auto_analysis: AutoAnalysisSnapshot | None = None,
    offline_cache: CacheSummary | None = None,
    recovery: RecoverySummary | None = None,
    risk_summary: RiskSummary | None = None,
    daily_report: DailyReportSummary | None = None,
    devhub_config: DevHubConfig | None = None,
    system_info: SystemInfoExportResult | None = None,
    started_at: str | None = None,
) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{SESSION_REPORT_PREFIX}-{timestamp}"
    json_path = reports_dir / f"{base}.json"
    txt_path = reports_dir / f"{base}.txt"

    finished_at = datetime.now().isoformat(timespec="seconds")
    payload = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "started_at": started_at or finished_at,
        "finished_at": finished_at,
        "setup": _setup_payload(setup_report),
        "tuning": [_tuning_payload(result) for result in tuning_results or []],
        "maintenance": [_maintenance_payload(result) for result in maintenance_results or []],
        "scan_warnings": scan_warnings or [],
        "diagnostics": [finding.to_dict() for finding in diagnostic_findings or []],
        "guardforge": [finding.to_dict() for finding in guard_findings or []],
        "profile_io": {
            "imported_profile": imported_profile_name,
            "import_path": imported_profile_path,
            "export_path": exported_profile_path,
            "warnings": profile_import_warnings or [],
        },
        "auto_analysis": auto_analysis.to_dict() if auto_analysis else None,
        "offline_cache": offline_cache.to_dict() if offline_cache else None,
        "recovery": recovery.to_dict() if recovery else None,
        "risk_engine": risk_summary.to_dict() if risk_summary else None,
        "daily_report": daily_report.to_dict() if daily_report else None,
        "configuration": devhub_config.to_dict() if devhub_config else None,
        "system_info": system_info.to_dict() if system_info else None,
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    txt_path.write_text(_render_session_text(payload), encoding="utf-8")
    return json_path, txt_path


def _render_text_report(report: RunReport) -> str:
    lines = [
        f"{report.app_name} {report.app_version}",
        "=" * 40,
        f"Profil: {report.profile.name}",
        f"Start: {report.started_at}",
        f"Ende: {report.finished_at}",
        "",
        "Geplante Ordner:",
    ]
    lines.extend(f"- {folder}" for folder in report.folders)
    lines.extend(["", "Pakete:"])

    for action in report.actions:
        lines.append(f"- {action.package.name}: {action.status}")
        if action.status == "dry_run":
            lines.append("  Testmodus: nicht ausgefuehrt")
        if action.error:
            lines.append(f"  Fehler: {action.error}")
        if action.exit_code is not None:
            lines.append(f"  Exit-Code: {action.exit_code}")

    failures = report.failures
    lines.extend(["", f"Fehler: {len(failures)}"])
    return "\n".join(lines) + "\n"


def _setup_payload(report: RunReport | None) -> dict:
    if report is None:
        return {"status": "not_run", "profile": None, "actions": []}
    return {
        "status": "failed" if report.failures else "success",
        "profile": report.profile.name,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "json_path": str(report.json_path) if report.json_path else None,
        "txt_path": str(report.txt_path) if report.txt_path else None,
        "actions": [
            {
                "name": action.package.name,
                "package_id": action.package.id,
                "winget_id": action.package.winget_id,
                "status": action.status,
                "command": action.command,
                "exit_code": action.exit_code,
                "error": action.error,
                "diagnostic": diagnostic_hint(action.exit_code, action.output) if action.status == "failed" else None,
                "output_excerpt": output_excerpt(action.output) if action.status == "failed" else "",
                "dry_run": action.status == "dry_run",
                "started_at": action.started_at,
                "finished_at": action.finished_at,
            }
            for action in report.actions
        ],
    }


def _tuning_payload(result: TuningResult) -> dict:
    return {
        "name": result.action.name,
        "action_id": result.action.id,
        "risk": result.action.risk,
        "requires_reboot": result.action.requires_reboot,
        "duration_hint": result.action.duration_hint,
        "impact": result.action.impact,
        "status": result.status,
        "command": result.action.command,
        "exit_code": result.exit_code,
        "error": result.error,
        "diagnostic": diagnostic_hint(result.exit_code, result.output) if result.status == "failed" else None,
        "output_excerpt": output_excerpt(result.output) if result.status == "failed" else "",
        "dry_run": result.status == "dry_run",
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }


def _maintenance_payload(result: MaintenanceResult) -> dict:
    return {
        "name": result.name,
        "package_id": result.package_id,
        "operation": result.operation,
        "status": result.status,
        "command": result.command,
        "exit_code": result.exit_code,
        "error": result.error,
        "diagnostic": diagnostic_hint(result.exit_code, result.output) if result.status == "failed" else None,
        "output_excerpt": output_excerpt(result.output) if result.status == "failed" else "",
        "dry_run": result.status == "dry_run",
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }


def _render_session_text(payload: dict) -> str:
    lines = [
        f"{payload['app_name']} {payload['app_version']}",
        "=" * 40,
        f"Start: {payload['started_at']}",
        f"Ende: {payload['finished_at']}",
        "",
        f"Setup: {payload['setup']['status']}",
    ]
    if payload["setup"].get("profile"):
        lines.append(f"Profil: {payload['setup']['profile']}")
    for action in payload["setup"].get("actions", []):
        lines.append(f"- {action['name']}: {action['status']}")
        if action.get("error"):
            lines.append(f"  Fehler: {action['error']}")
        if action.get("dry_run"):
            lines.append("  Testmodus: nicht ausgefuehrt")
        if action.get("diagnostic"):
            lines.append(f"  Hinweis: {action['diagnostic']}")
        if action.get("output_excerpt"):
            lines.append("  Ausgabe-Auszug:")
            lines.extend(f"    {line}" for line in action["output_excerpt"].splitlines())

    profile_io = payload.get("profile_io", {})
    if any(profile_io.get(key) for key in ("imported_profile", "import_path", "export_path")) or profile_io.get("warnings"):
        lines.extend(["", "Profilimport/-export:"])
        if profile_io.get("imported_profile"):
            lines.append(f"- Importiertes Profil: {profile_io['imported_profile']}")
        if profile_io.get("import_path"):
            lines.append(f"- Importpfad: {profile_io['import_path']}")
        if profile_io.get("export_path"):
            lines.append(f"- Exportpfad: {profile_io['export_path']}")
        if profile_io.get("warnings"):
            lines.append("- Import-Warnungen:")
            lines.extend(f"  - {warning}" for warning in profile_io["warnings"])

    auto_analysis = payload.get("auto_analysis")
    if auto_analysis:
        lines.extend(["", "Auto-Analyse:"])
        lines.append(f"- Status: {auto_analysis.get('status')}")
        lines.append(f"- Start: {auto_analysis.get('started_at') or 'n/a'}")
        lines.append(f"- Ende: {auto_analysis.get('finished_at') or 'n/a'}")
        lines.append(f"- Findings: {auto_analysis.get('findings_count', 0)}")
        lines.append(f"- Warnungen: {len(auto_analysis.get('warnings', []))}")
        lines.append(f"- Letzter Session-Report: {auto_analysis.get('latest_session_name') or 'keiner'}")
        lines.append("- Automatische Aktionen gestartet: nein")
        for warning in auto_analysis.get("warnings", []):
            lines.append(f"  Warnung: {warning}")
        for error in auto_analysis.get("errors", []):
            lines.append(f"  Fehler: {error}")

    offline_cache = payload.get("offline_cache")
    if offline_cache:
        lines.extend(["", "Offline Cache:"])
        lines.append(f"- Root: {offline_cache.get('root')}")
        lines.append(f"- Vorhanden: {offline_cache.get('present_count', 0)}/{offline_cache.get('planned_count', 0)}")
        lines.append(f"- Fehlend: {offline_cache.get('missing_count', 0)}")
        lines.append(f"- Ungueltig: {offline_cache.get('invalid_count', 0)}")
        for warning in offline_cache.get("warnings", []):
            lines.append(f"  Warnung: {warning}")

    recovery = payload.get("recovery")
    if recovery:
        lines.extend(["", "RecoveryForge:"])
        lines.append(f"- Root: {recovery.get('recovery_root')}")
        lines.append(f"- Vorhanden: {recovery.get('present_count', 0)}/{recovery.get('planned_count', 0)}")
        lines.append(f"- Fehlend: {recovery.get('missing_count', 0)}")
        lines.append(f"- Ungueltig: {recovery.get('invalid_count', 0)}")
        lines.append("- Automatische Backups/Restore-Aktionen gestartet: nein")
        for warning in recovery.get("warnings", []):
            lines.append(f"  Warnung: {warning}")

    risk_engine = payload.get("risk_engine")
    if risk_engine:
        lines.extend(["", "Risk Engine:"])
        lines.append(f"- Gesamt: {risk_engine.get('overall_risk')}")
        lines.append(f"- Score: {risk_engine.get('score', 0)}")
        lines.append(f"- Findings: {len(risk_engine.get('findings', []))}")
        lines.append(f"- Hoch/Mittel/Niedrig: {risk_engine.get('high_count', 0)}/{risk_engine.get('medium_count', 0)}/{risk_engine.get('low_count', 0)}")
        lines.append("- Automatische Aktionen gestartet: nein")
        for finding in risk_engine.get("findings", [])[:10]:
            lines.append(f"  - {finding.get('source')}: {finding.get('title')} ({finding.get('risk_level')})")
            lines.append(f"    Empfehlung: {finding.get('recommendation')}")

    daily_report = payload.get("daily_report")
    if daily_report:
        lines.extend(["", "Tagesbericht Preview:"])
        lines.append(f"- Datum: {daily_report.get('report_date')}")
        lines.append(f"- Aktionen heute: {daily_report.get('actions_total', 0)}")
        lines.append(f"- Fehler heute: {daily_report.get('failures_total', 0)}")
        lines.append(f"- Hinweise/Warnungen: {daily_report.get('alert_count', 0)}")
        lines.append(f"- Kritisch/Warnung: {daily_report.get('critical_count', 0)}/{daily_report.get('warning_count', 0)}")
        lines.append("- Automatische Aktionen gestartet: nein")
        for alert in daily_report.get("alerts", [])[:10]:
            lines.append(f"  - {alert.get('level')}: {alert.get('source')} - {alert.get('title')}")
            lines.append(f"    Empfehlung: {alert.get('recommendation')}")
        for recommendation in daily_report.get("recommendations", []):
            lines.append(f"  Empfehlung: {recommendation}")

    configuration = payload.get("configuration")
    if configuration:
        lines.extend(["", "Konfiguration:"])
        lines.append(f"- Testmodus: {'aktiv' if configuration.get('dry_run_enabled') else 'inaktiv'}")
        lines.append(f"- Auto-Analyse: {'aktiv' if configuration.get('auto_analysis_enabled') else 'inaktiv'}")
        lines.append(f"- Letztes Preset merken: {'aktiv' if configuration.get('remember_last_preset') else 'inaktiv'}")
        lines.append(f"- Reportmodus: {configuration.get('default_report_mode')}")
        lines.append(f"- Aktivierte Module: {len(configuration.get('enabled_modules', []))}")
        lines.append("- Automatische Aktionen gestartet: nein")

    system_info = payload.get("system_info")
    if system_info:
        lines.extend(["", "SystemInfo / MSINFO32:"])
        lines.append(f"- Status: {system_info.get('status')}")
        lines.append(f"- Exportpfad: {system_info.get('export_path')}")
        lines.append(f"- Dateigroesse: {system_info.get('size_bytes', 0)} Bytes")
        lines.append(f"- Dauer: {system_info.get('duration_seconds', 0)} Sekunden")
        lines.append(f"- Testmodus: {'ja' if system_info.get('dry_run') else 'nein'}")
        lines.append("- Agent-Auswertung vorbereitet: ja")
        lines.append("- Automatische Codex-Auswertung gestartet: nein")
        if system_info.get("error"):
            lines.append(f"- Fehler: {system_info.get('error')}")

    lines.extend(["", "Tuning:"])
    if payload["tuning"]:
        if any(item.get("requires_reboot") for item in payload["tuning"]):
            lines.append("Hinweis: Neustart empfohlen.")
        for item in payload["tuning"]:
            lines.append(f"- {item['name']}: {item['status']} (Risiko: {item['risk']})")
            if item.get("dry_run"):
                lines.append("  Testmodus: nicht ausgefuehrt")
            lines.append(f"  Wirkung: {item.get('impact', 'n/a')}")
            lines.append(f"  Dauer: {item.get('duration_hint', 'n/a')}")
            if item.get("requires_reboot"):
                lines.append("  Neustart empfohlen: ja")
            if item.get("error"):
                lines.append(f"  Fehler: {item['error']}")
            if item.get("diagnostic"):
                lines.append(f"  Hinweis: {item['diagnostic']}")
            if item.get("output_excerpt"):
                lines.append("  Ausgabe-Auszug:")
                lines.extend(f"    {line}" for line in item["output_excerpt"].splitlines())
    else:
        lines.append("- nicht ausgefuehrt")

    lines.extend(["", "Maintenance:"])
    if payload["maintenance"]:
        for item in payload["maintenance"]:
            lines.append(f"- {item['operation']} {item['name']}: {item['status']}")
            if item.get("dry_run"):
                lines.append("  Testmodus: nicht ausgefuehrt")
            if item.get("error"):
                lines.append(f"  Fehler: {item['error']}")
            if item.get("diagnostic"):
                lines.append(f"  Hinweis: {item['diagnostic']}")
            if item.get("output_excerpt"):
                lines.append("  Ausgabe-Auszug:")
                lines.extend(f"    {line}" for line in item["output_excerpt"].splitlines())
    else:
        lines.append("- nicht ausgefuehrt")

    if payload["scan_warnings"]:
        lines.extend(["", "Scan-Hinweise:"])
        lines.extend(f"- {warning}" for warning in payload["scan_warnings"])

    lines.extend(["", "Diagnose:"])
    if payload.get("diagnostics"):
        active = [finding for finding in payload["diagnostics"] if finding.get("status", "active") == "active"]
        historical = [finding for finding in payload["diagnostics"] if finding.get("status", "active") != "active"]
        if active:
            lines.append("Aktiv:")
        for finding in active:
            lines.append(f"- {finding['problem']} ({finding['severity']}, {finding.get('status', 'active')})")
            lines.append(f"  Ursache: {finding['likely_cause']}")
            lines.append(f"  Empfehlung: {finding['recommended_fix']}")
            if finding.get("source"):
                lines.append(f"  Quelle: {finding['source']}")
            if finding.get("source_timestamp") or finding.get("last_success_timestamp"):
                lines.append(
                    f"  Fund: {finding.get('source_timestamp') or 'n/a'} | Letzter erfolgreicher Start: {finding.get('last_success_timestamp') or 'n/a'}"
                )
            if finding.get("evidence"):
                lines.append(f"  Beleg: {finding['evidence']}")
        if historical:
            lines.append("Historisch:")
        for finding in historical:
            lines.append(f"- {finding['problem']} ({finding['severity']}, {finding.get('status', 'historical')})")
            lines.append(f"  Ursache: {finding['likely_cause']}")
            lines.append(f"  Empfehlung: {finding['recommended_fix']}")
            if finding.get("source"):
                lines.append(f"  Quelle: {finding['source']}")
            if finding.get("source_timestamp") or finding.get("last_success_timestamp"):
                lines.append(
                    f"  Fund: {finding.get('source_timestamp') or 'n/a'} | Letzter erfolgreicher Start: {finding.get('last_success_timestamp') or 'n/a'}"
                )
            if finding.get("evidence"):
                lines.append(f"  Beleg: {finding['evidence']}")
    else:
        lines.append("- keine Findings")

    lines.extend(["", "GuardForge:"])
    if payload.get("guardforge"):
        for finding in payload["guardforge"]:
            lines.append(f"- {finding['reason']} (Risiko: {finding['risk_level']}, Events: {finding['event_count']})")
            lines.append(f"  Empfehlung: {finding['recommendation']}")
            if finding.get("affected_paths"):
                lines.append("  Betroffene Pfade:")
                lines.extend(f"    {path}" for path in finding["affected_paths"])
    else:
        lines.append("- nicht ausgefuehrt")

    return "\n".join(lines) + "\n"
