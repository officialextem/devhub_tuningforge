from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    executable = _admin_executable()
    params = " ".join([_quote(arg) for arg in sys.argv])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    return int(result) > 32


def _admin_executable(executable: str | None = None, frozen: bool | None = None) -> str:
    current = Path(executable or sys.executable)
    if frozen if frozen is not None else getattr(sys, "frozen", False):
        return str(current)
    if current.name.lower() == "python.exe":
        pythonw = current.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(current)


def _quote(value: str) -> str:
    escaped = value.replace('"', r'\"')
    return f'"{escaped}"'
