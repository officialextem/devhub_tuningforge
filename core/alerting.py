from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

from core.auto_analysis import AutoAnalysisSnapshot
from core.risk_engine import RISK_HIGH, RISK_MEDIUM, RiskSummary


ALERT_INFO = "info"
ALERT_WARNING = "warning"
ALERT_CRITICAL = "critical"


@dataclass(frozen=True)
class AlertItem:
    level: str
    source: str
    title: str
    detail: str
    recommendation: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DailyReportSummary:
    report_date: str
    checked_at: str
    actions_total: int
    failures_total: int
    warnings_total: int
    high_risks: int
    medium_risks: int
    latest_report_name: str | None
    alerts: list[AlertItem]
    recommendations: list[str]
    actions_started: bool = False

    @property
    def alert_count(self) -> int:
        return len(self.alerts)

    @property
    def critical_count(self) -> int:
        return sum(1 for alert in self.alerts if alert.level == ALERT_CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for alert in self.alerts if alert.level == ALERT_WARNING)

    def to_dict(self) -> dict:
        return {
            "report_date": self.report_date,
            "checked_at": self.checked_at,
            "actions_total": self.actions_total,
            "failures_total": self.failures_total,
            "warnings_total": self.warnings_total,
            "high_risks": self.high_risks,
            "medium_risks": self.medium_risks,
            "latest_report_name": self.latest_report_name,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommendations": self.recommendations,
            "actions_started": self.actions_started,
            "alert_count": self.alert_count,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
        }


def build_daily_report_summary(
    *,
    report_date: str | None = None,
    session_payloads: list[dict] | None = None,
    risk_summary: RiskSummary | None = None,
    auto_analysis: AutoAnalysisSnapshot | None = None,
    read_warnings: list[str] | None = None,
) -> DailyReportSummary:
    checked_at = datetime.now().isoformat(timespec="seconds")
    target_date = report_date or date.today().isoformat()
    payloads = session_payloads or []
    actions_total = sum(_action_count(payload) for payload in payloads)
    failures_total = sum(len(_payload_failures(payload)) for payload in payloads)
    warnings_total = sum(_warning_count(payload) for payload in payloads) + len(read_warnings or [])
    high_risks = risk_summary.high_count if risk_summary else 0
    medium_risks = risk_summary.medium_count if risk_summary else 0
    latest_report_name = _latest_report_name(payloads)
    alerts = _alerts(
        checked_at=checked_at,
        failures_total=failures_total,
        warnings_total=warnings_total,
        risk_summary=risk_summary,
        auto_analysis=auto_analysis,
        read_warnings=read_warnings or [],
    )
    recommendations = _recommendations(
        alerts=alerts,
        failures_total=failures_total,
        warnings_total=warnings_total,
        actions_total=actions_total,
        risk_summary=risk_summary,
    )
    return DailyReportSummary(
        report_date=target_date,
        checked_at=checked_at,
        actions_total=actions_total,
        failures_total=failures_total,
        warnings_total=warnings_total,
        high_risks=high_risks,
        medium_risks=medium_risks,
        latest_report_name=latest_report_name,
        alerts=alerts,
        recommendations=recommendations,
        actions_started=False,
    )


def _alerts(
    *,
    checked_at: str,
    failures_total: int,
    warnings_total: int,
    risk_summary: RiskSummary | None,
    auto_analysis: AutoAnalysisSnapshot | None,
    read_warnings: list[str],
) -> list[AlertItem]:
    alerts: list[AlertItem] = []
    if risk_summary and risk_summary.overall_risk == RISK_HIGH:
        alerts.append(
            AlertItem(
                ALERT_CRITICAL,
                "Risk Engine",
                "Hohes Gesamtrisiko",
                f"Score {risk_summary.score}, {risk_summary.high_count} hohe Findings.",
                "Diagnose, Risk Engine und letzten Session-Report pruefen, bevor weitere Aktionen gestartet werden.",
                checked_at,
            )
        )
    elif risk_summary and risk_summary.overall_risk == RISK_MEDIUM:
        alerts.append(
            AlertItem(
                ALERT_WARNING,
                "Risk Engine",
                "Mittleres Gesamtrisiko",
                f"Score {risk_summary.score}, {risk_summary.medium_count} mittlere Findings.",
                "Betroffene Module im ControlDeck pruefen.",
                checked_at,
            )
        )
    if failures_total:
        alerts.append(
            AlertItem(
                ALERT_WARNING,
                "Reports",
                "Fehler im Tagesverlauf",
                f"{failures_total} fehlgeschlagene Aktionen in heutigen Session-Reports.",
                "Reports oeffnen und Ursache klaeren, bevor die gleiche Aktion erneut gestartet wird.",
                checked_at,
            )
        )
    if warnings_total:
        alerts.append(
            AlertItem(
                ALERT_INFO,
                "Reports",
                "Warnungen oder Scan-Hinweise vorhanden",
                f"{warnings_total} Hinweise wurden im Tageskontext erkannt.",
                "Hinweise im Tagesbericht und Session-Report pruefen.",
                checked_at,
            )
        )
    if auto_analysis and auto_analysis.errors:
        alerts.append(
            AlertItem(
                ALERT_WARNING,
                "Auto-Analyse",
                "Auto-Analyse mit Fehler beendet",
                auto_analysis.errors[-1],
                "Diagnose-Seite oeffnen; es wurden keine Auto-Aktionen gestartet.",
                checked_at,
            )
        )
    for warning in read_warnings[:3]:
        alerts.append(
            AlertItem(
                ALERT_INFO,
                "Tagesbericht",
                "Report konnte nicht gelesen werden",
                warning,
                "Datei bei Bedarf manuell pruefen; unlesbare Reports werden ignoriert.",
                checked_at,
            )
        )
    return alerts


def _recommendations(
    *,
    alerts: list[AlertItem],
    failures_total: int,
    warnings_total: int,
    actions_total: int,
    risk_summary: RiskSummary | None,
) -> list[str]:
    if not alerts:
        if actions_total:
            return ["Keine offenen Tageswarnungen. Letzte Session-Reports bleiben im Bericht einsehbar."]
        return ["Noch keine heutigen Session-Daten. Nach Aktionen oder Analyse-Reports wird der Tagesbericht aussagekraeftiger."]
    recommendations: list[str] = []
    if risk_summary and risk_summary.overall_risk in {RISK_HIGH, RISK_MEDIUM}:
        recommendations.append("Risk Engine zuerst pruefen und betroffene Module einzeln oeffnen.")
    if failures_total:
        recommendations.append("Fehlgeschlagene Aktionen nicht blind wiederholen; Diagnosehinweise im Report lesen.")
    if warnings_total:
        recommendations.append("Warnungen priorisieren, aber keine automatische Reparatur ausloesen.")
    return recommendations or ["Hinweise lesen und danach Vorschau/Start weiterhin manuell bestaetigen."]


def _action_count(payload: dict) -> int:
    setup = payload.get("setup", {}) if isinstance(payload, dict) else {}
    return len(setup.get("actions", [])) + len(payload.get("tuning", [])) + len(payload.get("maintenance", []))


def _warning_count(payload: dict) -> int:
    if not isinstance(payload, dict):
        return 0
    profile_io = payload.get("profile_io", {})
    auto_analysis = payload.get("auto_analysis") or {}
    offline_cache = payload.get("offline_cache") or {}
    recovery = payload.get("recovery") or {}
    return (
        len(payload.get("scan_warnings", []))
        + len(profile_io.get("warnings", []))
        + len(auto_analysis.get("warnings", []))
        + len(offline_cache.get("warnings", []))
        + len(recovery.get("warnings", []))
    )


def _payload_failures(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    setup = payload.get("setup", {})
    failures = [action for action in setup.get("actions", []) if action.get("status") == "failed"]
    failures.extend(item for item in payload.get("tuning", []) if item.get("status") == "failed")
    failures.extend(item for item in payload.get("maintenance", []) if item.get("status") == "failed")
    return failures


def _latest_report_name(payloads: list[dict]) -> str | None:
    for payload in reversed(payloads):
        name = payload.get("report_name") if isinstance(payload, dict) else None
        if name:
            return str(name)
    return None
