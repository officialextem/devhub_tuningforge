from __future__ import annotations

from dataclasses import dataclass


LOW_RISK = "niedrig"
MEDIUM_RISK = "mittel"
HIGH_RISK = "hoch"
BLOCKED_RISK = "blocked"
ALLOWED_RISKS_V01 = {LOW_RISK, MEDIUM_RISK}
BLOCKED_RISKS_V01 = {HIGH_RISK, BLOCKED_RISK}


class SafetyGateError(ValueError):
    pass


@dataclass(frozen=True)
class SafetyDecision:
    risk: str
    allowed: bool
    requires_second_confirmation: bool
    reason: str


def decide_action_safety(risk: str, enabled_by_default: bool = False) -> SafetyDecision:
    normalized = str(risk).lower()
    if normalized in BLOCKED_RISKS_V01:
        return SafetyDecision(
            risk=normalized,
            allowed=False,
            requires_second_confirmation=True,
            reason="High-Risk- oder blockierte Aktionen sind in v0.1.x nicht aktiv.",
        )
    if normalized not in ALLOWED_RISKS_V01:
        return SafetyDecision(
            risk=normalized,
            allowed=False,
            requires_second_confirmation=True,
            reason=f"Unbekanntes Risiko: {normalized}",
        )
    if normalized == MEDIUM_RISK:
        if enabled_by_default:
            return SafetyDecision(
                risk=normalized,
                allowed=False,
                requires_second_confirmation=True,
                reason="Mittlere Risiken duerfen nicht vorausgewaehlt sein.",
            )
        return SafetyDecision(
            risk=normalized,
            allowed=True,
            requires_second_confirmation=True,
            reason="Mittlere Risiken brauchen eine zweite Bestaetigung.",
        )
    return SafetyDecision(
        risk=normalized,
        allowed=True,
        requires_second_confirmation=False,
        reason="Niedriges Risiko ist mit Vorschau und explizitem Start erlaubt.",
    )


def assert_action_allowed(risk: str, enabled_by_default: bool = False) -> None:
    decision = decide_action_safety(risk, enabled_by_default)
    if not decision.allowed:
        raise SafetyGateError(decision.reason)
