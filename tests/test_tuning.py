from pathlib import Path

from core.app_config import LOG_FILE_NAME
from core.models import STATUS_FAILED, STATUS_SUCCESS
from core.tuning import TuningExecutor, load_tuning_actions


ROOT = Path(__file__).resolve().parent.parent


class FakeStdout:
    def __iter__(self):
        return iter(["ok\n"])


class FakeProcess:
    stdout = FakeStdout()

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def wait(self) -> int:
        return self.exit_code


def test_tuning_actions_load() -> None:
    actions = load_tuning_actions(ROOT / "tuning" / "actions.json")

    assert actions
    assert any(action.enabled_by_default for action in actions)
    assert any(action.id == "winget-source-update" for action in actions)
    assert any(action.id == "temp-clean-user" for action in actions)
    assert any(action.requires_reboot for action in actions)
    assert all(action.risk in {"niedrig", "mittel"} for action in actions)
    assert all(not action.enabled_by_default for action in actions if action.risk == "mittel")
    assert all(action.duration_hint for action in actions)
    assert all(action.impact for action in actions)


def test_tuning_actions_include_repair_first_pack() -> None:
    actions = {action.id: action for action in load_tuning_actions(ROOT / "tuning" / "actions.json")}

    expected_ids = {
        "winget-source-update",
        "winget-source-reset",
        "temp-clean-user",
        "system-cache-cleanup",
        "ramboost-idle-tasks",
        "dism-scan-health",
        "dism-restore-health",
        "sfc-verify-only",
        "system-file-check",
        "winsock-catalog-show",
        "winsock-reset",
        "disk-scan-c",
    }
    assert expected_ids.issubset(actions)
    assert actions["winsock-reset"].requires_reboot
    assert actions["dism-restore-health"].risk == "mittel"
    assert actions["temp-clean-user"].risk == "mittel"
    assert not actions["temp-clean-user"].enabled_by_default
    assert actions["ramboost-idle-tasks"].risk == "niedrig"


def test_tuning_executor_success() -> None:
    action = load_tuning_actions(ROOT / "tuning" / "actions.json")[0]
    executor = TuningExecutor(popen_factory=lambda *args, **kwargs: FakeProcess(0))

    results = executor.run([action], lambda message: None, lambda result: None)

    assert len(results) == 1
    assert results[0].status == STATUS_SUCCESS
    assert results[0].output == ["ok"]


def test_tuning_executor_failed_exit_code(tmp_path) -> None:
    from core.app_logger import get_app_logger

    action = load_tuning_actions(ROOT / "tuning" / "actions.json")[0]
    logger = get_app_logger(tmp_path)
    executor = TuningExecutor(popen_factory=lambda *args, **kwargs: FakeProcess(9), logger=logger)

    results = executor.run([action], lambda message: None, lambda result: None)

    assert results[0].status == STATUS_FAILED
    assert results[0].error == "Exit-Code 9"
    assert "[ERROR] Tuning fehlgeschlagen:" in (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
