from __future__ import annotations

from datetime import datetime

from core.maintenance import build_uninstall_command, build_upgrade_command
from core.models import (
    AvailableUpdate,
    InstalledProgram,
    MaintenanceResult,
    PlannedAction,
    STATUS_DRY_RUN,
    TuningAction,
    TuningResult,
)


DRY_RUN_MESSAGE = "Testmodus aktiv: Aktion wurde simuliert und nicht ausgefuehrt."


def simulate_setup_actions(actions: list[PlannedAction]) -> list[PlannedAction]:
    timestamp = _timestamp()
    for action in actions:
        action.status = STATUS_DRY_RUN
        action.started_at = timestamp
        action.finished_at = timestamp
        action.exit_code = 0
        action.error = None
        action.output = [DRY_RUN_MESSAGE, f"Geplantes Kommando: {_format_command(action.command)}"]
    return actions


def simulate_tuning_actions(actions: list[TuningAction]) -> list[TuningResult]:
    timestamp = _timestamp()
    return [
        TuningResult(
            action=action,
            status=STATUS_DRY_RUN,
            started_at=timestamp,
            finished_at=timestamp,
            exit_code=0,
            output=[DRY_RUN_MESSAGE, f"Geplantes Kommando: {_format_command(action.command)}"],
            error=None,
        )
        for action in actions
    ]


def simulate_uninstall(programs: list[InstalledProgram], scope: str) -> list[MaintenanceResult]:
    timestamp = _timestamp()
    return [
        MaintenanceResult(
            name=program.name,
            package_id=program.package_id,
            operation="uninstall",
            status=STATUS_DRY_RUN,
            command=build_uninstall_command(program, scope),
            started_at=timestamp,
            finished_at=timestamp,
            exit_code=0,
            output=[DRY_RUN_MESSAGE, f"Geplantes Kommando: {_format_command(build_uninstall_command(program, scope))}"],
        )
        for program in programs
    ]


def simulate_updates(updates: list[AvailableUpdate], scope: str) -> list[MaintenanceResult]:
    timestamp = _timestamp()
    return [
        MaintenanceResult(
            name=update.name,
            package_id=update.package_id,
            operation="update",
            status=STATUS_DRY_RUN,
            command=build_upgrade_command(update, scope),
            started_at=timestamp,
            finished_at=timestamp,
            exit_code=0,
            output=[DRY_RUN_MESSAGE, f"Geplantes Kommando: {_format_command(build_upgrade_command(update, scope))}"],
        )
        for update in updates
    ]


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _format_command(command: list[str]) -> str:
    return " ".join(command) if command else "kein Kommando"
