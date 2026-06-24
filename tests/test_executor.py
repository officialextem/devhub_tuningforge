from core.executor import WingetExecutor, build_winget_command
from core.app_config import LOG_FILE_NAME
from core.models import Package, PlannedAction, STATUS_FAILED, STATUS_SUCCESS


class FakeStdout:
    def __iter__(self):
        return iter(["line 1\n", "line 2\n"])


class FakeProcess:
    stdout = FakeStdout()

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def wait(self) -> int:
        return self.exit_code


def package() -> Package:
    return Package(
        id="git",
        name="Git",
        category="Entwicklung",
        winget_id="Git.Git",
        description="Git",
        recommended_for=["developer"],
        requires_admin=False,
        enabled_by_default=True,
    )


def test_build_winget_command() -> None:
    assert build_winget_command("Git.Git") == [
        "winget",
        "install",
        "--id",
        "Git.Git",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]


def test_executor_success() -> None:
    action = PlannedAction(package=package(), command=build_winget_command("Git.Git"))
    logs: list[str] = []

    executor = WingetExecutor(
        popen_factory=lambda *args, **kwargs: FakeProcess(0),
        winget_lookup=lambda name: "C:/Windows/winget.exe",
    )
    executor.run([action], logs.append, lambda action: None)

    assert action.status == STATUS_SUCCESS
    assert action.output == ["line 1", "line 2"]


def test_executor_missing_winget_marks_failed() -> None:
    action = PlannedAction(package=package(), command=build_winget_command("Git.Git"))
    logs: list[str] = []

    executor = WingetExecutor(winget_lookup=lambda name: None)
    executor.run([action], logs.append, lambda action: None)

    assert action.status == STATUS_FAILED
    assert "winget wurde nicht gefunden" in logs[0]


def test_executor_missing_winget_logs_error(tmp_path) -> None:
    from core.app_logger import get_app_logger

    action = PlannedAction(package=package(), command=build_winget_command("Git.Git"))
    logger = get_app_logger(tmp_path)

    executor = WingetExecutor(winget_lookup=lambda name: None, logger=logger)
    executor.run([action], lambda message: None, lambda action: None)

    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "[ERROR] winget wurde nicht gefunden" in content


def test_executor_failed_exit_code() -> None:
    action = PlannedAction(package=package(), command=build_winget_command("Git.Git"))

    executor = WingetExecutor(
        popen_factory=lambda *args, **kwargs: FakeProcess(7),
        winget_lookup=lambda name: "C:/Windows/winget.exe",
    )
    executor.run([action], lambda message: None, lambda action: None)

    assert action.status == STATUS_FAILED
    assert action.error == "winget Exit-Code 7"


def test_executor_failed_exit_code_logs_error(tmp_path) -> None:
    from core.app_logger import get_app_logger

    action = PlannedAction(package=package(), command=build_winget_command("Git.Git"))
    logger = get_app_logger(tmp_path)

    executor = WingetExecutor(
        popen_factory=lambda *args, **kwargs: FakeProcess(7),
        winget_lookup=lambda name: "C:/Windows/winget.exe",
        logger=logger,
    )
    executor.run([action], lambda message: None, lambda action: None)

    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "[ERROR] Installation fehlgeschlagen: Git (winget Exit-Code 7)" in content
