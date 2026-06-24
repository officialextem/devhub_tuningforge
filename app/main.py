from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path


def _startup_log_path() -> Path:
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parent.parent
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / "startup-error.log"


def _write_startup_error(exc: BaseException) -> None:
    path = _startup_log_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    path.write_text(
        f"[{timestamp}] DEVHub TuningForge konnte nicht starten.\n\n{details}\n",
        encoding="utf-8",
    )
    print("DEVHub TuningForge konnte nicht starten.")
    print(f"Fehler: {exc.__class__.__name__}: {exc}")
    print(f"Details: {path}")
    print("Hinweis: Wenn Tcl/Tk oder customtkinter fehlt, Python reparieren und Tcl/Tk mitinstallieren.")


def main() -> None:
    try:
        from app.ui import TuningForgeApp

        app = TuningForgeApp()
        app.mainloop()
    except Exception as exc:
        _write_startup_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
