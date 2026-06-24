from core.dry_run import DRY_RUN_MESSAGE, simulate_setup_actions, simulate_tuning_actions, simulate_uninstall, simulate_updates
from core.executor import build_winget_command
from core.models import AvailableUpdate, InstalledProgram, Package, PlannedAction, STATUS_DRY_RUN, TuningAction


def test_simulate_setup_marks_planned_actions_without_execution() -> None:
    package = Package("git", "Git", "Entwicklung", "Git.Git", "Git", ["developer"], False, True)
    action = PlannedAction(package=package, command=build_winget_command("Git.Git"))

    simulate_setup_actions([action])

    assert action.status == STATUS_DRY_RUN
    assert action.exit_code == 0
    assert DRY_RUN_MESSAGE in action.output[0]
    assert "winget install" in action.output[1]


def test_simulate_tuning_returns_dry_run_results() -> None:
    action = TuningAction("dns", "DNS Cache leeren", "Repair", "desc", ["ipconfig", "/flushdns"], "niedrig", True)

    results = simulate_tuning_actions([action])

    assert results[0].status == STATUS_DRY_RUN
    assert results[0].exit_code == 0
    assert "ipconfig /flushdns" in results[0].output[1]


def test_simulate_maintenance_returns_uninstall_and_update_results() -> None:
    program = InstalledProgram("git", "Git", "Git.Git", "1.0", "winget")
    update = AvailableUpdate("Git.Git", "Git", "Git.Git", "1.0", "2.0", "winget")

    uninstall = simulate_uninstall([program], "device")
    updates = simulate_updates([update], "device")

    assert uninstall[0].status == STATUS_DRY_RUN
    assert uninstall[0].operation == "uninstall"
    assert uninstall[0].command[:3] == ["winget", "uninstall", "--id"]
    assert updates[0].status == STATUS_DRY_RUN
    assert updates[0].operation == "update"
    assert updates[0].command[:4] == ["winget", "upgrade", "--id", "Git.Git"]
