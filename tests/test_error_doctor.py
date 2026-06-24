from pathlib import Path

from core.diagnostics import ErrorDoctor


def _problems(text: str) -> set[str]:
    return {finding.problem for finding in ErrorDoctor().analyze_texts([text])}


def test_error_doctor_detects_tcl_tk_error() -> None:
    problems = _problems("TclError: Can't find a usable init.tcl in this Python installation")

    assert "Tcl/Tk-Installation defekt" in problems


def test_error_doctor_detects_windowsapps_python_alias() -> None:
    problems = _problems(r"C:\Users\info\AppData\Local\Microsoft\WindowsApps\python.exe konnte nicht starten")

    assert "WindowsApps Python-Alias erkannt" in problems


def test_error_doctor_detects_winget_missing() -> None:
    problems = _problems("winget wurde nicht gefunden. Bitte App Installer/Microsoft Store pruefen.")

    assert "winget nicht erreichbar" in problems


def test_error_doctor_detects_admin_and_access_problem() -> None:
    problems = _problems("Administratorrechte erforderlich. PermissionError: Zugriff verweigert")

    assert "Admin- oder Zugriffsproblem" in problems


def test_error_doctor_detects_pyinstaller_build_error() -> None:
    problems = _problems("PyInstaller failed with error while bundling tkinter")

    assert "PyInstaller-Buildfehler" in problems


def test_error_doctor_detects_pip_timeout() -> None:
    problems = _problems("pip build-isolation timeout while installing dependency")

    assert "pip Timeout oder Build-Isolation haengt" in problems


def test_error_doctor_detects_pytest_temp_lock() -> None:
    problems = _problems("PermissionError WinError 5 Zugriff verweigert: work/pytest-tmp")

    assert "pytest Temp-Ordner gesperrt" in problems


def test_error_doctor_detects_local_python_blocker(tmp_path: Path) -> None:
    (tmp_path / "python").write_text("", encoding="utf-8")

    findings = ErrorDoctor().analyze_project_state(tmp_path, is_admin=True, winget_available=True)

    assert findings[0].problem == "Lokale Python-Stoerdatei erkannt"
    assert findings[0].can_auto_fix is False
    assert findings[0].safe_to_auto_fix is False


def test_error_doctor_reads_files(tmp_path: Path) -> None:
    log = tmp_path / "startup-error.log"
    log.write_text("Can't find a usable init.tcl", encoding="utf-8")

    findings = ErrorDoctor().analyze_files([log])

    assert findings
    assert findings[0].problem == "Tcl/Tk-Installation defekt"


def test_error_doctor_marks_old_startup_error_as_historical_after_successful_start(tmp_path: Path) -> None:
    startup = tmp_path / "startup-error.log"
    app_log = tmp_path / "tuningforge.log"
    startup.write_text(
        "[2026-06-17 19:37:26] DEVHub TuningForge konnte nicht starten.\n"
        "TclError: Can't find a usable init.tcl",
        encoding="utf-8",
    )
    app_log.write_text(
        "[2026-06-18 01:59:31] [INFO] DEVHub TuningForge 0.1.10 gestartet.\n",
        encoding="utf-8",
    )

    findings = ErrorDoctor().analyze_runtime_logs(startup, app_log)

    tcl_finding = next(finding for finding in findings if finding.problem == "Tcl/Tk-Installation defekt")
    assert tcl_finding.status == "historical"
    assert tcl_finding.source == str(startup)
    assert tcl_finding.source_timestamp == "2026-06-17 19:37:26"
    assert tcl_finding.last_success_timestamp == "2026-06-18 01:59:31"


def test_error_doctor_keeps_new_startup_error_active_without_later_success(tmp_path: Path) -> None:
    startup = tmp_path / "startup-error.log"
    app_log = tmp_path / "tuningforge.log"
    startup.write_text(
        "[2026-06-18 02:05:00] DEVHub TuningForge konnte nicht starten.\n"
        "TclError: Can't find a usable init.tcl",
        encoding="utf-8",
    )
    app_log.write_text(
        "[2026-06-18 01:59:31] [INFO] DEVHub TuningForge 0.1.10 gestartet.\n",
        encoding="utf-8",
    )

    findings = ErrorDoctor().analyze_runtime_logs(startup, app_log)

    tcl_finding = next(finding for finding in findings if finding.problem == "Tcl/Tk-Installation defekt")
    assert tcl_finding.status == "active"
    assert tcl_finding.last_success_timestamp == "2026-06-18 01:59:31"
