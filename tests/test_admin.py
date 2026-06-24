from core import admin


def test_quote_wraps_value():
    assert admin._quote("a b") == '"a b"'


def test_admin_executable_prefers_pythonw_for_dev_mode(tmp_path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")

    assert admin._admin_executable(str(python), frozen=False) == str(pythonw)


def test_admin_executable_keeps_frozen_exe(tmp_path):
    app = tmp_path / "DEVHub TuningForge.exe"
    app.write_text("", encoding="utf-8")

    assert admin._admin_executable(str(app), frozen=True) == str(app)
