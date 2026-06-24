from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.offline_cache import CACHE_STATUS_INVALID, CACHE_STATUS_MISSING, CACHE_STATUS_STALE, CacheSummary
from core.recovery import RECOVERY_STATUS_INVALID, RECOVERY_STATUS_MISSING, RecoverySummary


RISK_LOW = "niedrig"
RISK_MEDIUM = "mittel"
RISK_HIGH = "hoch"


@dataclass(frozen=True)
class RiskFinding:
    source: str
    risk_level: str
    title: str
    detail: str
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RiskSummary:
    overall_risk: str
    score: int
    findings: list[RiskFinding]
    checked_at: str

    @property
    def low_count(self) -> int:
        return sum(1 for finding in self.findings if finding.risk_level == RISK_LOW)

    @property
    def medium_count(self) -> int:
        return sum(1 for finding in self.findings if finding.risk_level == RISK_MEDIUM)

    @property
    def high_count(self) -> int:
        return sum(1 for finding in self.findings if finding.risk_level == RISK_HIGH)

    def to_dict(self) -> dict:
        return {
            "overall_risk": self.overall_risk,
            "score": self.score,
            "findings": [finding.to_dict() for finding in self.findings],
            "checked_at": self.checked_at,
            "low_count": self.low_count,
            "medium_count": self.medium_count,
            "high_count": self.high_count,
            "actions_started": False,
        }


def build_risk_summary(
    *,
    diagnostic_findings: list[DiagnosticFinding],
    guard_findings: list[GuardRiskFinding],
    offline_cache: CacheSummary | None = None,
    recovery: RecoverySummary | None = None,
    latest_payload: dict | None = None,
    scan_warnings: list[str] | None = None,
) -> RiskSummary:
    findings: list[RiskFinding] = []
    findings.extend(_diagnostic_risks(diagnostic_findings))
    findings.extend(_guard_risks(guard_findings))
    if offline_cache:
        findings.extend(_offline_cache_risks(offline_cache))
    if recovery:
        findings.extend(_recovery_risks(recovery))
    findings.extend(_report_risks(latest_payload or {}))
    findings.extend(_scan_warning_risks(scan_warnings or []))

    score = sum(_risk_score(finding.risk_level) for finding in findings)
    overall = _overall_risk(findings, score)
    return RiskSummary(
        overall_risk=overall,
        score=score,
        findings=findings,
        checked_at=datetime.now().isoformat(timespec="seconds"),
    )


def _diagnostic_risks(diagnostic_findings: list[DiagnosticFinding]) -> list[RiskFinding]:
    risks: list[RiskFinding] = []
    for finding in diagnostic_findings:
        active = finding.status == "active"
        if active and finding.severity == "error":
            level = RISK_HIGH
        elif active:
            level = RISK_MEDIUM
        else:
            level = RISK_LOW
        risks.append(
            RiskFinding(
                source="ErrorDoctor",
                risk_level=level,
                title=finding.problem,
                detail=finding.evidence,
                recommendation=finding.recommended_fix,
            )
        )
    return risks


def _guard_risks(guard_findings: list[GuardRiskFinding]) -> list[RiskFinding]:
    return [
        RiskFinding(
            source="GuardForge",
            risk_level=_normalize_risk(finding.risk_level),
            title=finding.reason,
            detail=f"{finding.event_count} Preview-Events, {len(finding.affected_paths)} betroffene Pfade.",
            recommendation=finding.recommendation,
        )
        for finding in guard_findings
    ]


def _offline_cache_risks(offline_cache: CacheSummary) -> list[RiskFinding]:
    risks: list[RiskFinding] = []
    invalid_or_stale = [entry for entry in offline_cache.entries if entry.status in {CACHE_STATUS_INVALID, CACHE_STATUS_STALE}]
    missing = [entry for entry in offline_cache.entries if entry.status == CACHE_STATUS_MISSING]
    if invalid_or_stale:
        risks.append(
            RiskFinding(
                source="Offline Cache",
                risk_level=RISK_MEDIUM,
                title="Cache-Eintraege ungueltig oder veraltet",
                detail=f"{len(invalid_or_stale)} Eintraege brauchen manuelle Pruefung.",
                recommendation="Cache-Index pruefen; keine Installation aus unbekannten oder abweichenden Dateien starten.",
            )
        )
    elif missing:
        risks.append(
            RiskFinding(
                source="Offline Cache",
                risk_level=RISK_LOW,
                title="Cache-Dateien fehlen",
                detail=f"{len(missing)} geplante Installer sind nicht lokal vorhanden.",
                recommendation="Installer spaeter bewusst in den Cache legen oder Eintraege im Index anpassen.",
            )
        )
    if offline_cache.warnings:
        risks.append(
            RiskFinding(
                source="Offline Cache",
                risk_level=RISK_MEDIUM,
                title="Cache-Warnungen vorhanden",
                detail=f"{len(offline_cache.warnings)} Warnungen im lokalen Cache.",
                recommendation="Warnungen auf der Offline-Cache-Seite pruefen.",
            )
        )
    return risks


def _recovery_risks(recovery: RecoverySummary) -> list[RiskFinding]:
    risks: list[RiskFinding] = []
    required_missing = [
        target for target in recovery.targets if target.required and target.status == RECOVERY_STATUS_MISSING
    ]
    invalid = [target for target in recovery.targets if target.status == RECOVERY_STATUS_INVALID]
    if required_missing or invalid:
        risks.append(
            RiskFinding(
                source="RecoveryForge",
                risk_level=RISK_MEDIUM,
                title="Recovery-Ziele unvollstaendig",
                detail=f"{len(required_missing)} Pflichtziele fehlen, {len(invalid)} Ziele sind ungueltig.",
                recommendation="RecoveryForge Preview pruefen, bevor spaetere Backup- oder Restore-Funktionen aktiviert werden.",
            )
        )
    elif recovery.missing_count:
        risks.append(
            RiskFinding(
                source="RecoveryForge",
                risk_level=RISK_LOW,
                title="Optionale Recovery-Ziele fehlen",
                detail=f"{recovery.missing_count} optionale Ziele sind nicht vorhanden.",
                recommendation="Nur bei Bedarf anlegen; v0.7.0 startet keine Recovery-Aktion.",
            )
        )
    if recovery.warnings:
        risks.append(
            RiskFinding(
                source="RecoveryForge",
                risk_level=RISK_MEDIUM,
                title="Recovery-Warnungen vorhanden",
                detail=f"{len(recovery.warnings)} Warnungen in der Recovery-Preview.",
                recommendation="Warnungen auf der RecoveryForge-Seite pruefen.",
            )
        )
    return risks


def _report_risks(latest_payload: dict) -> list[RiskFinding]:
    failures = _payload_failures(latest_payload)
    if not failures:
        return []
    return [
        RiskFinding(
            source="Reports",
            risk_level=RISK_MEDIUM,
            title="Fehler im letzten Session-Report",
            detail=f"{len(failures)} fehlgeschlagene Aktionen im letzten Report.",
            recommendation="Bericht oeffnen und Ursache pruefen, bevor weitere Aktionen gestartet werden.",
        )
    ]


def _scan_warning_risks(scan_warnings: list[str]) -> list[RiskFinding]:
    if not scan_warnings:
        return []
    return [
        RiskFinding(
            source="Scans",
            risk_level=RISK_LOW,
            title="Scan-Hinweise vorhanden",
            detail=f"{len(scan_warnings)} Hinweise aus lokalen Scan-Ausgaben.",
            recommendation="Hinweise im Session-Report pruefen.",
        )
    ]


def _payload_failures(payload: dict) -> list[dict]:
    setup = payload.get("setup", {}) if isinstance(payload, dict) else {}
    failures = [action for action in setup.get("actions", []) if action.get("status") == "failed"]
    failures.extend(item for item in payload.get("tuning", []) if item.get("status") == "failed")
    failures.extend(item for item in payload.get("maintenance", []) if item.get("status") == "failed")
    return failures


def _normalize_risk(value: str) -> str:
    return value if value in {RISK_LOW, RISK_MEDIUM, RISK_HIGH} else RISK_LOW


def _risk_score(level: str) -> int:
    return {RISK_LOW: 1, RISK_MEDIUM: 3, RISK_HIGH: 6}.get(level, 1)


def _overall_risk(findings: list[RiskFinding], score: int) -> str:
    if any(finding.risk_level == RISK_HIGH for finding in findings) or score >= 9:
        return RISK_HIGH
    if any(finding.risk_level == RISK_MEDIUM for finding in findings) or score >= 3:
        return RISK_MEDIUM
    return RISK_LOW
