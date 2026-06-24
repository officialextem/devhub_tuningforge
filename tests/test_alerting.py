from core.alerting import ALERT_CRITICAL, ALERT_INFO, ALERT_WARNING, build_daily_report_summary
from core.risk_engine import RiskFinding, RiskSummary


def test_daily_report_empty_state_is_read_only() -> None:
    summary = build_daily_report_summary(report_date="2026-06-18", session_payloads=[])

    assert summary.report_date == "2026-06-18"
    assert summary.actions_total == 0
    assert summary.alert_count == 0
    assert summary.actions_started is False
    assert "Noch keine heutigen Session-Daten" in summary.recommendations[0]


def test_daily_report_counts_actions_failures_and_warnings() -> None:
    payload = {
        "report_name": "devhub-session-20260618.json",
        "setup": {"actions": [{"status": "success"}, {"status": "failed"}]},
        "tuning": [{"status": "failed"}],
        "maintenance": [{"status": "success"}],
        "scan_warnings": ["winget clipped"],
        "profile_io": {"warnings": ["unknown package"]},
    }

    summary = build_daily_report_summary(report_date="2026-06-18", session_payloads=[payload])

    assert summary.actions_total == 4
    assert summary.failures_total == 2
    assert summary.warnings_total == 2
    assert summary.latest_report_name == "devhub-session-20260618.json"
    assert any(alert.level == ALERT_WARNING and alert.source == "Reports" for alert in summary.alerts)
    assert any(alert.level == ALERT_INFO and alert.source == "Reports" for alert in summary.alerts)


def test_daily_report_promotes_high_risk_to_critical_alert() -> None:
    risk = RiskSummary(
        "hoch",
        6,
        [RiskFinding("ErrorDoctor", "hoch", "winget fehlt", "missing", "App Installer pruefen.")],
        "2026-06-18T10:00:00",
    )

    summary = build_daily_report_summary(report_date="2026-06-18", risk_summary=risk)

    assert summary.high_risks == 1
    assert summary.critical_count == 1
    assert summary.alerts[0].level == ALERT_CRITICAL
    assert "Risk Engine zuerst" in summary.recommendations[0]
