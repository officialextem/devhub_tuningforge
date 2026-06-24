from core.diagnostics import DiagnosticFinding
from core.guardforge import GuardRiskFinding
from core.offline_cache import CacheEntry, CacheSummary
from core.recovery import RecoverySummary, RecoveryTarget
from core.risk_engine import RISK_HIGH, RISK_LOW, RISK_MEDIUM, build_risk_summary


def test_empty_risk_summary_is_low_and_read_only() -> None:
    summary = build_risk_summary(diagnostic_findings=[], guard_findings=[])

    assert summary.overall_risk == RISK_LOW
    assert summary.score == 0
    assert summary.findings == []
    assert summary.to_dict()["actions_started"] is False


def test_active_error_diagnostic_creates_high_risk() -> None:
    summary = build_risk_summary(
        diagnostic_findings=[
            DiagnosticFinding("winget nicht erreichbar", "error", "missing", "PATH", "App Installer pruefen.")
        ],
        guard_findings=[],
    )

    assert summary.overall_risk == RISK_HIGH
    assert summary.high_count == 1
    assert summary.findings[0].source == "ErrorDoctor"


def test_medium_sources_are_aggregated_without_actions() -> None:
    cache = CacheSummary(
        "C:/cache/installers",
        "C:/cache/installers/installer-cache.json",
        [CacheEntry("git", "Git", "manual", "git.exe", status="stale", note="Hash weicht ab.")],
        ["Git: Hash weicht ab."],
        "2026-06-18T10:00:00",
    )
    recovery = RecoverySummary(
        "C:/recovery",
        [RecoveryTarget("profiles", "Profilordner", "C:/profiles", "folder", True, "missing", 0, "Pfad fehlt.")],
        ["Profilordner: Pfad fehlt."],
        "2026-06-18T10:00:00",
    )
    summary = build_risk_summary(
        diagnostic_findings=[],
        guard_findings=[GuardRiskFinding("mittel", "Viele Loeschungen", ["C:/a.txt"], "Pruefen.", 3)],
        offline_cache=cache,
        recovery=recovery,
        latest_payload={"setup": {"actions": [{"name": "Git", "status": "failed"}]}},
        scan_warnings=["winget output clipped"],
    )

    assert summary.overall_risk in {RISK_MEDIUM, RISK_HIGH}
    assert summary.medium_count >= 4
    assert any(finding.source == "GuardForge" for finding in summary.findings)
    assert any(finding.source == "Offline Cache" for finding in summary.findings)
    assert any(finding.source == "RecoveryForge" for finding in summary.findings)
    assert any(finding.source == "Reports" for finding in summary.findings)
    assert "command" not in summary.to_dict()


def test_historical_diagnostic_stays_low_risk() -> None:
    summary = build_risk_summary(
        diagnostic_findings=[
            DiagnosticFinding(
                "Tcl/Tk-Installation defekt",
                "error",
                "old traceback",
                "Python defekt",
                "Python reparieren.",
                status="historical",
            )
        ],
        guard_findings=[],
    )

    assert summary.overall_risk == RISK_LOW
    assert summary.low_count == 1
