from core.maintenance import (
    SCAN_TIMEOUT_SECONDS,
    WingetMaintenance,
    build_uninstall_command,
    build_upgrade_command,
    parse_winget_list,
    parse_winget_upgrade,
)
from core.diagnostics import diagnostic_hint
from core.models import STATUS_FAILED, STATUS_SUCCESS, AvailableUpdate, InstalledProgram


LIST_OUTPUT = """Name                Id                   Version  Source
---------------------------------------------------------------
Git                 Git.Git              2.45.0   winget
Visual Studio Code  Microsoft.Visual...  1.90.0   winget
"""

UPGRADE_OUTPUT = """Name  Id       Version  Available  Source
---------------------------------------------
Git   Git.Git  2.44.0   2.45.0     winget
"""

GERMAN_LIST_OUTPUT = """-
\\
|
Name                                    ID                                      Version           Verfügbar     Quelle
-----------------------------------------------------------------------------------------------------------------------
7-Zip 26.01 (x64)                       7zip.7zip                               26.01                           winget
Bitdefender Total Security              ARP\\Machine\\X64\\Bitdefender             27.0.59.334
Docker Desktop                          Docker.DockerDesktop                    4.78.0                           winget
"""

GERMAN_UPGRADE_OUTPUT = """-
\\
|
Name            ID                   Version Verfügbar     Quelle
-----------------------------------------------------------------
Docker Desktop  Docker.DockerDesktop 4.78.0  4.78.0.229452 winget
Python Launcher Python.Launcher      3.12.10 3.13.5        winget
2 Aktualisierungen verfügbar.
"""


class FakeStdout:
    def __iter__(self):
        return iter(["ok\n"])


class FakeProcess:
    stdout = FakeStdout()

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code

    def wait(self) -> int:
        return self.exit_code


def test_parse_winget_list():
    programs = parse_winget_list(LIST_OUTPUT)

    assert programs[0].name == "Git"
    assert programs[0].package_id == "Git.Git"
    assert programs[0].version == "2.45.0"


def test_parse_winget_upgrade():
    updates = parse_winget_upgrade(UPGRADE_OUTPUT)

    assert updates[0].name == "Git"
    assert updates[0].package_id == "Git.Git"
    assert updates[0].current_version == "2.44.0"
    assert updates[0].available_version == "2.45.0"


def test_parse_winget_list_handles_german_headers_and_progress_lines():
    programs = parse_winget_list(GERMAN_LIST_OUTPUT)

    assert [program.name for program in programs] == [
        "7-Zip 26.01 (x64)",
        "Bitdefender Total Security",
        "Docker Desktop",
    ]
    assert programs[0].package_id == "7zip.7zip"
    assert programs[0].source == "winget"


def test_parse_winget_upgrade_handles_german_headers_and_progress_lines():
    updates = parse_winget_upgrade(GERMAN_UPGRADE_OUTPUT)

    assert [update.package_id for update in updates] == ["Docker.DockerDesktop", "Python.Launcher"]
    assert updates[0].available_version == "4.78.0.229452"


def test_uninstall_command_includes_scope():
    program = InstalledProgram("Git.Git", "Git", "Git.Git", "2.45.0", "winget")

    assert build_uninstall_command(program, "user") == [
        "winget",
        "uninstall",
        "--id",
        "Git.Git",
        "--silent",
        "--accept-source-agreements",
        "--scope",
        "user",
    ]


def test_upgrade_command_targets_id():
    update = AvailableUpdate("Git.Git", "Git", "Git.Git", "2.44.0", "2.45.0", "winget")

    assert build_upgrade_command(update)[:4] == ["winget", "upgrade", "--id", "Git.Git"]
    assert build_upgrade_command(update, "machine")[-2:] == ["--scope", "machine"]


def test_device_scope_omits_winget_scope_flag():
    program = InstalledProgram("Git.Git", "Git", "Git.Git", "2.45.0", "winget")
    update = AvailableUpdate("Git.Git", "Git", "Git.Git", "2.44.0", "2.45.0", "winget")

    assert "--scope" not in build_uninstall_command(program, "device")
    assert "--scope" not in build_upgrade_command(update, "device")


def test_device_scan_omits_user_scope_flag():
    calls = []

    class Completed:
        returncode = 0
        stdout = LIST_OUTPUT
        stderr = ""

    def runner(command, *args, **kwargs):
        calls.append(command)
        return Completed()

    maintenance = WingetMaintenance(runner=runner, winget_lookup=lambda name: "winget")
    maintenance.scan_installed("device")

    assert calls
    assert "--scope" not in calls[0]


def test_scan_passes_timeout_to_runner():
    kwargs_seen = {}

    class Completed:
        returncode = 0
        stdout = LIST_OUTPUT
        stderr = ""

    def runner(command, *args, **kwargs):
        kwargs_seen.update(kwargs)
        return Completed()

    maintenance = WingetMaintenance(runner=runner, winget_lookup=lambda name: "winget")
    maintenance.scan_installed("device")

    assert kwargs_seen["timeout"] == SCAN_TIMEOUT_SECONDS


def test_scan_timeout_returns_actionable_error():
    def timeout_runner(command, *args, **kwargs):
        import subprocess

        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    maintenance = WingetMaintenance(runner=timeout_runner, winget_lookup=lambda name: "winget")

    try:
        maintenance.scan_updates("device")
    except RuntimeError as exc:
        assert "Timeout" in str(exc)
        assert "spaeter erneut scannen" in str(exc)
    else:
        raise AssertionError("scan_updates should raise RuntimeError on timeout")


def test_maintenance_continues_after_failed_uninstall():
    programs = [
        InstalledProgram("bad", "Bad", "Bad.App", "1", "winget"),
        InstalledProgram("good", "Good", "Good.App", "1", "winget"),
    ]
    calls = {"count": 0}

    def popen(*args, **kwargs):
        calls["count"] += 1
        return FakeProcess(7 if calls["count"] == 1 else 0)

    maintenance = WingetMaintenance(popen_factory=popen, winget_lookup=lambda name: "winget")
    results = maintenance.uninstall(programs, "user", lambda message: None, lambda result: None)

    assert [result.status for result in results] == [STATUS_FAILED, STATUS_SUCCESS]


def test_scan_records_warning_when_table_parse_returns_no_rows():
    class Completed:
        returncode = 0
        stdout = "winget returned a changed layout that is not a table"
        stderr = ""

    maintenance = WingetMaintenance(runner=lambda *args, **kwargs: Completed(), winget_lookup=lambda name: "winget")
    programs = maintenance.scan_installed("user")

    assert programs == []
    assert maintenance.last_scan_warning is not None
    assert "konnte nicht als Tabelle gelesen werden" in maintenance.last_scan_warning


def test_run_many_logs_item_count_and_command():
    program = InstalledProgram("Git.Git", "Git", "Git.Git", "2.45.0", "winget")
    messages = []

    maintenance = WingetMaintenance(popen_factory=lambda *args, **kwargs: FakeProcess(0), winget_lookup=lambda name: "winget")
    maintenance.uninstall([program], "user", messages.append, lambda result: None)

    assert any("1/1" in message for message in messages)
    assert any("winget uninstall" in message for message in messages)


def test_known_winget_exit_code_gets_actionable_hint():
    hint = diagnostic_hint(2316632070, [])

    assert hint is not None
    assert "Neustart" in hint


def test_failed_maintenance_result_includes_diagnostic_hint():
    program = InstalledProgram("docker", "Docker Desktop", "Docker.DockerDesktop", "1", "winget")

    maintenance = WingetMaintenance(popen_factory=lambda *args, **kwargs: FakeProcess(2316632070), winget_lookup=lambda name: "winget")
    results = maintenance.uninstall([program], "device", lambda message: None, lambda result: None)

    assert results[0].status == STATUS_FAILED
    assert "Neustart" in results[0].error
