from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from typing import Callable

from core.app_logger import AppLogger
from core.models import (
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    PlannedAction,
)

LogCallback = Callable[[str], None]
StatusCallback = Callable[[PlannedAction], None]


def build_winget_command(winget_id: str) -> list[str]:
    return [
        "winget",
        "install",
        "--id",
        winget_id,
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]


class WingetExecutor:
    def __init__(
        self,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        winget_lookup: Callable[[str], str | None] = shutil.which,
        logger: AppLogger | None = None,
    ) -> None:
        self._popen_factory = popen_factory
        self._winget_lookup = winget_lookup
        self._logger = logger
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self, actions: list[PlannedAction], on_log: LogCallback, on_status: StatusCallback) -> None:
        if not self._winget_lookup("winget"):
            message = "winget wurde nicht gefunden. Bitte App Installer/Microsoft Store pruefen."
            if self._logger:
                self._logger.error(message)
            on_log(message)
            for action in actions:
                action.status = STATUS_FAILED
                action.error = message
                action.finished_at = datetime.now().isoformat(timespec="seconds")
                on_status(action)
            return

        total = len(actions)
        for index, action in enumerate(actions, start=1):
            if self.cancel_requested:
                action.status = STATUS_SKIPPED
                action.error = "Installation wurde vom Benutzer abgebrochen."
                action.finished_at = datetime.now().isoformat(timespec="seconds")
                if self._logger:
                    self._logger.warning(f"Installation uebersprungen: {action.package.name}")
                on_status(action)
                continue

            on_log(f"Paket {index}/{total}: {action.package.name}")
            self._run_action(action, on_log, on_status)

    def _run_action(self, action: PlannedAction, on_log: LogCallback, on_status: StatusCallback) -> None:
        action.status = STATUS_RUNNING
        action.started_at = datetime.now().isoformat(timespec="seconds")
        on_status(action)
        if self._logger:
            self._logger.info(f"Installation gestartet: {action.package.name}")
            self._logger.info(f"Befehl: {' '.join(action.command)}")
        on_log(f"Starte Installation: {action.package.name}")
        on_log(f"Befehl: {' '.join(action.command)}")

        try:
            process = self._popen_factory(
                action.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                clean = line.rstrip()
                if clean:
                    action.output.append(clean)
                    on_log(clean)
            action.exit_code = process.wait()
        except FileNotFoundError as exc:
            action.exit_code = None
            action.error = str(exc)
            action.status = STATUS_FAILED
            if self._logger:
                self._logger.error(f"Installation fehlgeschlagen: {action.package.name}", exc)
        except Exception as exc:
            action.exit_code = None
            action.error = f"Unerwarteter Fehler: {exc}"
            action.status = STATUS_FAILED
            if self._logger:
                self._logger.error(f"Installation fehlgeschlagen: {action.package.name}", exc)
        else:
            if action.exit_code == 0:
                action.status = STATUS_SUCCESS
                if self._logger:
                    self._logger.success(f"Installation erfolgreich: {action.package.name}")
                on_log(f"Erfolgreich installiert: {action.package.name}")
            else:
                action.status = STATUS_FAILED
                action.error = f"winget Exit-Code {action.exit_code}"
                if self._logger:
                    self._logger.error(f"Installation fehlgeschlagen: {action.package.name} ({action.error})")
                on_log(f"Fehler bei {action.package.name}: {action.error}")
        finally:
            action.finished_at = datetime.now().isoformat(timespec="seconds")
            on_status(action)
