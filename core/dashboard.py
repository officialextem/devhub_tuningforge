from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.app_settings import AppSettings, PRESET_IMPORTED
from core.alerting import DailyReportSummary
from core.auto_analysis import AUTO_COMPLETED, AUTO_FAILED, AUTO_RUNNING, AutoAnalysisSnapshot
from core.configuration import DevHubConfig
from core.diagnostics import DiagnosticFinding, diagnostic_hint
from core.guardforge import GuardRiskFinding
from core.models import AvailableUpdate, InstalledProgram, MaintenanceResult, Profile, TuningResult
from core.offline_cache import CacheSummary
from core.recovery import RecoverySummary
from core.risk_engine import RISK_HIGH, RISK_MEDIUM, RiskSummary
from core.system_info import SYSTEM_INFO_STATUS_FAILED, SYSTEM_INFO_STATUS_SUCCESS, SystemInfoExportResult


@dataclass(frozen=True)
class DashboardCard:
    title: str
    value: str
    detail: str
    level: str


@dataclass(frozen=True)
class DashboardModule:
    id: str
    title: str
    status: str
    detail: str
    page_id: int
    level: str = "info"


@dataclass(frozen=True)
class DashboardSnapshot:
    cards: list[DashboardCard]
    modules: list[DashboardModule]
    recommendations: list[str]


def build_dashboard_snapshot(
    *,
    is_admin: bool,
    winget_available: bool,
    selected_profile: Profile | None,
    selected_package_count: int,
    selected_tuning_count: int,
    installed_programs: list[InstalledProgram],
    available_updates: list[AvailableUpdate],
    maintenance_results: list[MaintenanceResult],
    tuning_results: list[TuningResult],
    scan_warnings: list[str],
    diagnostic_findings: list[DiagnosticFinding],
    guard_findings: list[GuardRiskFinding],
    latest_session_name: str | None,
    latest_log_name: str | None,
    latest_payload: dict,
    app_settings: AppSettings,
    imported_profile_name: str | None = None,
    imported_profile_path: str | None = None,
    exported_profile_path: str | None = None,
    auto_analysis: AutoAnalysisSnapshot | None = None,
    offline_cache: CacheSummary | None = None,
    recovery: RecoverySummary | None = None,
    risk_summary: RiskSummary | None = None,
    daily_report: DailyReportSummary | None = None,
    devhub_config: DevHubConfig | None = None,
    system_info: SystemInfoExportResult | None = None,
) -> DashboardSnapshot:
    active_findings = [finding for finding in diagnostic_findings if finding.status == "active"]
    historical_findings = [finding for finding in diagnostic_findings if finding.status != "active"]
    latest_failures = payload_failures(latest_payload)
    latest_warnings = latest_payload.get("scan_warnings", []) if latest_payload else []
    preset_label = _preset_label(app_settings, selected_profile, imported_profile_name, imported_profile_path)

    cards = [
        DashboardCard("Admin", "OK" if is_admin else "FEHLT", "Erhoehte Rechte aktiv." if is_admin else "Admin-Start erforderlich.", "success" if is_admin else "error"),
        DashboardCard("winget", "OK" if winget_available else "FEHLT", "Paketverwaltung erreichbar." if winget_available else "App Installer pruefen.", "success" if winget_available else "error"),
        DashboardCard("Preset", preset_label, f"{selected_package_count} Programme, {selected_tuning_count} Tuning-Aktionen.", "info"),
        DashboardCard("Inventar", str(len(installed_programs)), "Programme aus letztem Uninstall-Scan.", "info"),
        DashboardCard("Updates", str(len(available_updates)), "Updates aus letztem Update-Scan.", "warning" if available_updates else "success"),
        DashboardCard(
            "Diagnose",
            str(len(active_findings)),
            f"Aktive Findings. Historisch: {len(historical_findings)}.",
            "warning" if active_findings else "info" if historical_findings else "success",
        ),
        DashboardCard("GuardForge", str(len(guard_findings)), "Alpha-Preview ohne Hintergrundueberwachung.", "warning" if guard_findings else "info"),
        _auto_analysis_card(auto_analysis),
        _offline_cache_card(offline_cache),
        _recovery_card(recovery),
        _risk_card(risk_summary),
        _daily_report_card(daily_report),
        _configuration_card(devhub_config),
        _system_info_card(system_info),
        DashboardCard(
            "Reports",
            latest_session_name or "Kein Session-Report",
            f"{len(latest_failures)} Fehler im letzten Report. Log: " + (latest_log_name or "kein Log"),
            "error" if latest_failures else "info",
        ),
    ]

    modules = [
        DashboardModule("profile", "Profile", preset_label, "Preset importieren, exportieren oder wechseln.", 1),
        DashboardModule("tuningforge", "TuningForge", f"{selected_package_count} Pakete", "Setup-Auswahl und sichere Vorschau vorbereiten.", 2),
        DashboardModule("repair", "Repair/Tuning", f"{selected_tuning_count} Aktionen", "Repair-Auswahl pruefen; Start bleibt bestaetigungspflichtig.", 5, "warning" if selected_tuning_count else "info"),
        DashboardModule("guardforge", "GuardForge", f"{len(guard_findings)} Findings", "Preview-only Datei-Event-Risiken.", 15, "warning" if guard_findings else "info"),
        _auto_analysis_module(auto_analysis),
        _offline_cache_module(offline_cache),
        _recovery_module(recovery),
        _risk_module(risk_summary),
        _daily_report_module(daily_report),
        _configuration_module(devhub_config),
        _system_info_module(system_info),
        DashboardModule("errordoctor", "ErrorDoctor", f"{len(active_findings)} aktiv", f"{len(historical_findings)} historische Findings.", 14, "warning" if active_findings else "info"),
        DashboardModule("reports", "Reports", latest_session_name or "Noch keiner", "Session-Berichte, Warnungen und Fehlerauszuege.", 7, "error" if latest_failures else "info"),
    ]

    recommendations = _recommendations(
        winget_available=winget_available,
        available_updates=available_updates,
        installed_programs=installed_programs,
        scan_warnings=scan_warnings,
        guard_findings=guard_findings,
        active_findings=active_findings,
        historical_findings=historical_findings,
        maintenance_results=maintenance_results,
        tuning_results=tuning_results,
        latest_failures=latest_failures,
        latest_warnings=latest_warnings,
        selected_profile=selected_profile,
        imported_profile_name=imported_profile_name,
        exported_profile_path=exported_profile_path,
        latest_session_name=latest_session_name,
        auto_analysis=auto_analysis,
        offline_cache=offline_cache,
        recovery=recovery,
        risk_summary=risk_summary,
        daily_report=daily_report,
        devhub_config=devhub_config,
        system_info=system_info,
    )
    return DashboardSnapshot(cards=cards, modules=modules, recommendations=recommendations)


def payload_failures(payload: dict) -> list[dict]:
    failures: list[dict] = []
    setup = payload.get("setup", {})
    failures.extend(action for action in setup.get("actions", []) if action.get("status") == "failed")
    failures.extend(item for item in payload.get("tuning", []) if item.get("status") == "failed")
    failures.extend(item for item in payload.get("maintenance", []) if item.get("status") == "failed")
    return failures


def _auto_analysis_card(auto_analysis: AutoAnalysisSnapshot | None) -> DashboardCard:
    if auto_analysis is None:
        return DashboardCard("Auto-Analyse", "bereit", "Wartet auf sicheren Startcheck.", "info")
    detail = f"{auto_analysis.findings_count} Findings, {len(auto_analysis.warnings)} Warnungen. Keine Aktionen gestartet."
    return DashboardCard("Auto-Analyse", auto_analysis.status, detail, _auto_analysis_level(auto_analysis))


def _auto_analysis_module(auto_analysis: AutoAnalysisSnapshot | None) -> DashboardModule:
    if auto_analysis is None:
        return DashboardModule("auto_analysis", "Auto-Analyse", "bereit", "Sichere lokale Startchecks ohne Auto-Aktionen.", 0)
    timestamp = auto_analysis.finished_at or auto_analysis.started_at or "noch nicht"
    detail = f"Letzte Analyse: {timestamp}. Keine Aktionen automatisch gestartet."
    return DashboardModule("auto_analysis", "Auto-Analyse", auto_analysis.status, detail, 0, _auto_analysis_level(auto_analysis))


def _auto_analysis_level(auto_analysis: AutoAnalysisSnapshot) -> str:
    if auto_analysis.status == AUTO_FAILED or auto_analysis.errors:
        return "error"
    if auto_analysis.status == AUTO_RUNNING:
        return "warning"
    if auto_analysis.status == AUTO_COMPLETED:
        return "success" if not auto_analysis.warnings else "warning"
    return "info"


def _offline_cache_card(offline_cache: CacheSummary | None) -> DashboardCard:
    if offline_cache is None:
        return DashboardCard("Offline Cache", "nicht geprueft", "Lokaler Installer-Cache noch nicht ausgewertet.", "info")
    detail = f"{offline_cache.present_count}/{offline_cache.planned_count} vorhanden, {len(offline_cache.warnings)} Warnungen."
    level = "warning" if offline_cache.warnings or offline_cache.missing_count else "success"
    return DashboardCard("Offline Cache", str(offline_cache.present_count), detail, level)


def _offline_cache_module(offline_cache: CacheSummary | None) -> DashboardModule:
    if offline_cache is None:
        return DashboardModule("offline_cache", "Offline Cache", "nicht geprueft", "Lokale Installer-Dateien read-only pruefen.", 16)
    detail = f"Cache-Root: {offline_cache.root}"
    level = "warning" if offline_cache.warnings or offline_cache.missing_count else "success"
    return DashboardModule("offline_cache", "Offline Cache", f"{offline_cache.present_count}/{offline_cache.planned_count} vorhanden", detail, 16, level)


def _recovery_card(recovery: RecoverySummary | None) -> DashboardCard:
    if recovery is None:
        return DashboardCard("RecoveryForge", "nicht geprueft", "Recovery-Preview noch nicht ausgewertet.", "info")
    detail = f"{recovery.present_count}/{recovery.planned_count} Ziele vorhanden, {len(recovery.warnings)} Warnungen."
    level = "warning" if recovery.warnings else "success"
    return DashboardCard("RecoveryForge", str(recovery.present_count), detail, level)


def _recovery_module(recovery: RecoverySummary | None) -> DashboardModule:
    if recovery is None:
        return DashboardModule("recoveryforge", "RecoveryForge", "nicht geprueft", "Backup-/Recovery-Ziele read-only pruefen.", 17)
    detail = f"Recovery-Root: {recovery.recovery_root}"
    level = "warning" if recovery.warnings else "success"
    return DashboardModule("recoveryforge", "RecoveryForge", f"{recovery.present_count}/{recovery.planned_count} Ziele", detail, 17, level)


def _risk_card(risk_summary: RiskSummary | None) -> DashboardCard:
    if risk_summary is None:
        return DashboardCard("Risk Engine", "nicht geprueft", "Zentrale Risiko-Bewertung noch nicht ausgefuehrt.", "info")
    detail = (
        f"Score {risk_summary.score}, {len(risk_summary.findings)} Findings. "
        "Keine Aktionen gestartet."
    )
    return DashboardCard("Risk Engine", risk_summary.overall_risk, detail, _risk_level(risk_summary))


def _risk_module(risk_summary: RiskSummary | None) -> DashboardModule:
    if risk_summary is None:
        return DashboardModule("risk_engine", "Risk Engine", "nicht geprueft", "Read-only Bewertung aus lokalen Modulen.", 18)
    detail = (
        f"{risk_summary.high_count} hoch, {risk_summary.medium_count} mittel, "
        f"{risk_summary.low_count} niedrig. Keine Auto-Aktionen."
    )
    return DashboardModule("risk_engine", "Risk Engine", f"Risiko {risk_summary.overall_risk}", detail, 18, _risk_level(risk_summary))


def _risk_level(risk_summary: RiskSummary) -> str:
    if risk_summary.overall_risk == RISK_HIGH:
        return "error"
    if risk_summary.overall_risk == RISK_MEDIUM:
        return "warning"
    return "success"


def _daily_report_card(daily_report: DailyReportSummary | None) -> DashboardCard:
    if daily_report is None:
        return DashboardCard("Tagesbericht", "nicht geprueft", "Lokale Tagesuebersicht noch nicht berechnet.", "info")
    detail = (
        f"{daily_report.actions_total} Aktionen, {daily_report.failures_total} Fehler, "
        f"{daily_report.alert_count} Hinweise. Keine Aktionen gestartet."
    )
    return DashboardCard("Tagesbericht", daily_report.report_date, detail, _daily_report_level(daily_report))


def _daily_report_module(daily_report: DailyReportSummary | None) -> DashboardModule:
    if daily_report is None:
        return DashboardModule("daily_report", "Tagesbericht", "nicht geprueft", "Lokale Hinweise und Tageszusammenfassung.", 19)
    detail = (
        f"{daily_report.critical_count} kritisch, {daily_report.warning_count} Warnungen, "
        f"{daily_report.warnings_total} Report-Hinweise."
    )
    return DashboardModule("daily_report", "Tagesbericht", f"{daily_report.alert_count} Hinweise", detail, 19, _daily_report_level(daily_report))


def _daily_report_level(daily_report: DailyReportSummary) -> str:
    if daily_report.critical_count:
        return "error"
    if daily_report.warning_count:
        return "warning"
    return "info" if daily_report.alert_count else "success"


def _configuration_card(devhub_config: DevHubConfig | None) -> DashboardCard:
    if devhub_config is None:
        return DashboardCard("Konfiguration", "Standard", "Lokale DEVHub-Konfiguration noch nicht geladen.", "info")
    value = "Testmodus" if devhub_config.dry_run_enabled else "Aktiv"
    detail = (
        f"Auto-Analyse: {'an' if devhub_config.auto_analysis_enabled else 'aus'}, "
        f"Preset merken: {'an' if devhub_config.remember_last_preset else 'aus'}."
    )
    return DashboardCard("Konfiguration", value, detail, "warning" if devhub_config.dry_run_enabled else "info")


def _configuration_module(devhub_config: DevHubConfig | None) -> DashboardModule:
    if devhub_config is None:
        return DashboardModule("configuration", "Konfiguration", "Standard", "Lokale Einstellungen verwalten.", 20)
    status = "Testmodus aktiv" if devhub_config.dry_run_enabled else "normal"
    detail = f"{len(devhub_config.enabled_modules)} Module aktiviert, Reportmodus: {devhub_config.default_report_mode}."
    return DashboardModule("configuration", "Konfiguration", status, detail, 20, "warning" if devhub_config.dry_run_enabled else "info")


def _system_info_card(system_info: SystemInfoExportResult | None) -> DashboardCard:
    if system_info is None:
        return DashboardCard("SystemInfo", "bereit", "MSINFO32 TXT-Export noch nicht gestartet.", "info")
    detail = f"{Path(system_info.export_path).name}, {system_info.size_bytes} Bytes. Agent-Auswertung vorbereitet."
    return DashboardCard("SystemInfo", system_info.status, detail, _system_info_level(system_info))


def _system_info_module(system_info: SystemInfoExportResult | None) -> DashboardModule:
    if system_info is None:
        return DashboardModule("systeminfo", "SystemInfo", "bereit", "MSINFO32 TXT-Export manuell starten.", 21)
    detail = f"Export: {system_info.export_path}"
    return DashboardModule("systeminfo", "SystemInfo", system_info.status, detail, 21, _system_info_level(system_info))


def _system_info_level(system_info: SystemInfoExportResult) -> str:
    if system_info.status == SYSTEM_INFO_STATUS_FAILED:
        return "error"
    if system_info.status == SYSTEM_INFO_STATUS_SUCCESS:
        return "success"
    return "warning" if system_info.dry_run else "info"


def _preset_label(
    app_settings: AppSettings,
    selected_profile: Profile | None,
    imported_profile_name: str | None,
    imported_profile_path: str | None,
) -> str:
    if imported_profile_name:
        return imported_profile_name
    if app_settings.last_preset_kind == PRESET_IMPORTED and imported_profile_path:
        return Path(imported_profile_path).name
    if selected_profile:
        return selected_profile.name
    return "Kein Profil"


def _recommendations(
    *,
    winget_available: bool,
    available_updates: list[AvailableUpdate],
    installed_programs: list[InstalledProgram],
    scan_warnings: list[str],
    guard_findings: list[GuardRiskFinding],
    active_findings: list[DiagnosticFinding],
    historical_findings: list[DiagnosticFinding],
    maintenance_results: list[MaintenanceResult],
    tuning_results: list[TuningResult],
    latest_failures: list[dict],
    latest_warnings: list[str],
    selected_profile: Profile | None,
    imported_profile_name: str | None,
    exported_profile_path: str | None,
    latest_session_name: str | None,
    auto_analysis: AutoAnalysisSnapshot | None,
    offline_cache: CacheSummary | None,
    recovery: RecoverySummary | None,
    risk_summary: RiskSummary | None,
    daily_report: DailyReportSummary | None,
    devhub_config: DevHubConfig | None,
    system_info: SystemInfoExportResult | None,
) -> list[str]:
    items: list[str] = []
    if system_info:
        if system_info.status == SYSTEM_INFO_STATUS_FAILED:
            items.append(f"SystemInfo: MSINFO32-Export fehlgeschlagen. {system_info.error or 'Details im Session-Report pruefen.'}")
        elif system_info.status == SYSTEM_INFO_STATUS_SUCCESS:
            items.append("SystemInfo: TXT-Export liegt lokal vor und kann spaeter durch Agent/Codex ausgewertet werden.")
        elif system_info.dry_run:
            items.append("SystemInfo: Testmodus aktiv; MSINFO32-Export wurde nur simuliert.")
    if devhub_config and devhub_config.dry_run_enabled:
        items.append("Konfiguration: Testmodus ist aktiv. Systemaendernde Aktionen sollen im naechsten Schnitt simuliert statt ausgefuehrt werden.")
    if devhub_config and not devhub_config.auto_analysis_enabled:
        items.append("Konfiguration: Auto-Analyse ist deaktiviert; Statusdaten werden erst nach manueller Aktualisierung sichtbar.")
    if daily_report:
        if daily_report.critical_count:
            items.append(f"Tagesbericht: {daily_report.critical_count} kritische Hinweise erkannt. Risk Engine und Reports pruefen.")
        elif daily_report.warning_count:
            items.append(f"Tagesbericht: {daily_report.warning_count} Warnungen im heutigen Verlauf.")
        elif daily_report.alert_count:
            items.append(f"Tagesbericht: {daily_report.alert_count} lokale Hinweise vorhanden.")
    if risk_summary:
        if risk_summary.overall_risk == RISK_HIGH:
            items.append(f"Risk Engine: hohes Gesamtrisiko mit Score {risk_summary.score}. Diagnose und Reports zuerst pruefen.")
        elif risk_summary.overall_risk == RISK_MEDIUM:
            items.append(f"Risk Engine: mittleres Gesamtrisiko mit {len(risk_summary.findings)} Findings. Betroffene Module pruefen.")
        elif risk_summary.findings:
            items.append(f"Risk Engine: niedrige Hinweise vorhanden ({len(risk_summary.findings)} Findings).")
    if auto_analysis:
        if auto_analysis.status == AUTO_RUNNING:
            items.append("Auto-Analyse laeuft im Hintergrund. UI bleibt nutzbar; es werden keine Aktionen gestartet.")
        elif auto_analysis.errors:
            items.append(f"Auto-Analyse fehlgeschlagen: {auto_analysis.errors[-1]}")
        elif auto_analysis.status == AUTO_COMPLETED:
            items.append(
                f"Auto-Analyse abgeschlossen: {auto_analysis.findings_count} Findings, "
                f"{len(auto_analysis.warnings)} Warnungen, {auto_analysis.latest_report_failures} Report-Fehler."
            )
    if offline_cache:
        if offline_cache.warnings:
            items.append(f"Offline Cache: {len(offline_cache.warnings)} Warnungen im lokalen Installer-Cache.")
        elif offline_cache.planned_count:
            items.append(f"Offline Cache: {offline_cache.present_count}/{offline_cache.planned_count} Installer lokal vorhanden.")
    if recovery:
        if recovery.warnings:
            items.append(f"RecoveryForge: {len(recovery.warnings)} Warnungen in der Recovery-Preview.")
        elif recovery.planned_count:
            items.append(f"RecoveryForge: {recovery.present_count}/{recovery.planned_count} Recovery-Ziele lokal vorhanden.")
    if not winget_available:
        items.append("winget wurde nicht gefunden. App Installer/Microsoft Store pruefen.")
    if imported_profile_name:
        items.append(f"Preset aktiv: {imported_profile_name}. Vorschau pruefen, bevor Aktionen gestartet werden.")
    elif selected_profile:
        items.append(f"Preset aktiv: {selected_profile.name}. Programme und Tuning-Auswahl bei Bedarf anpassen.")
    if exported_profile_path:
        items.append(f"Letzter Profil-Export: {exported_profile_path}.")
    if available_updates:
        items.append(f"{len(available_updates)} Updates gefunden. Vorschau pruefen und bewusst starten.")
    if installed_programs:
        items.append(f"{len(installed_programs)} Programme im Inventar. Uninstall nur nach Vorschau und Bestaetigung.")
    if scan_warnings:
        items.append(f"{len(scan_warnings)} Scan-Hinweise im Session-Report pruefen.")
    if guard_findings:
        items.append(f"GuardForge Alpha: {len(guard_findings)} Preview-Risiken im Bericht pruefen.")
    if active_findings:
        items.append(f"ErrorDoctor: {len(active_findings)} aktive Diagnose-Findings pruefen.")
    elif historical_findings:
        items.append(f"ErrorDoctor: {len(historical_findings)} historische Findings vorhanden; App startet aktuell erfolgreich.")

    failed_maintenance = [result for result in maintenance_results if result.status == "failed"]
    if failed_maintenance:
        first = failed_maintenance[-1]
        hint = diagnostic_hint(first.exit_code, first.output) or first.error or "Details im Report pruefen."
        items.append(f"{first.operation} fehlgeschlagen: {first.name}. {hint}")

    failed_tuning = [result for result in tuning_results if result.status == "failed"]
    if failed_tuning:
        first = failed_tuning[-1]
        hint = diagnostic_hint(first.exit_code, first.output) or first.error or "Ausgabe-Auszug im Report pruefen."
        items.append(f"Tuning fehlgeschlagen: {first.action.name}. {hint}")

    for failure in latest_failures[:3]:
        hint = failure.get("diagnostic") or diagnostic_hint(failure.get("exit_code"), []) or failure.get("error") or "Details im letzten Report pruefen."
        label = failure.get("name") or failure.get("operation") or "Aktion"
        items.append(f"Letzter Report: {label} fehlgeschlagen. {hint}")
    if latest_warnings and not scan_warnings:
        items.append(f"Letzter Report enthaelt {len(latest_warnings)} Scan-Hinweise.")
    if not latest_session_name:
        items.append("Noch kein Session-Bericht vorhanden. Nach einem Lauf wird hier mehr Kontext sichtbar.")
    if not items:
        items.append("Keine offenen Hinweise. Naechster sinnvoller Schritt: Profil und Vorschau pruefen.")
    return items
