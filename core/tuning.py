from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.app_logger import AppLogger
from core.models import (
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    TuningAction,
    TuningResult,
)
from core.safety import ALLOWED_RISKS_V01, SafetyGateError, assert_action_allowed

TUNING_FIELDS = {"id", "name", "category", "description", "command", "risk", "enabled_by_default"}
TUNING_OPTIONAL_FIELDS = {"requires_reboot", "duration_hint", "impact"}


class TuningError(ValueError):
    pass


def load_tuning_actions(path: Path) -> list[TuningAction]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TuningError("Der Tuning-Katalog muss eine Liste sein.")

    actions = [_parse_action(item) for item in data]
    ids = [action.id for action in actions]
    if len(ids) != len(set(ids)):
        raise TuningError("Der Tuning-Katalog enthaelt doppelte IDs.")
    return actions


def _parse_action(item: dict) -> TuningAction:
    missing = TUNING_FIELDS - set(item)
    if missing:
        raise TuningError(f"Tuning-Aktion enthaelt fehlende Felder: {', '.join(sorted(missing))}")
    unknown = set(item) - TUNING_FIELDS - TUNING_OPTIONAL_FIELDS
    if unknown:
        raise TuningError(f"Tuning-Aktion enthaelt unbekannte Felder: {', '.join(sorted(unknown))}")
    if not isinstance(item["command"], list) or not item["command"]:
        raise TuningError(f"Tuning-Aktion {item.get('id', '<unbekannt>')} hat keinen gueltigen Befehl.")
    risk = str(item["risk"]).lower()
    if risk not in ALLOWED_RISKS_V01:
        raise TuningError(f"Tuning-Aktion {item.get('id', '<unbekannt>')} hat ein nicht erlaubtes Risiko: {risk}")
    try:
        assert_action_allowed(risk, bool(item["enabled_by_default"]))
    except SafetyGateError as exc:
        raise TuningError(f"Tuning-Aktion {item.get('id', '<unbekannt>')} verletzt SafetyGate: {exc}") from exc

    return TuningAction(
        id=str(item["id"]),
        name=str(item["name"]),
        category=str(item["category"]),
        description=str(item["description"]),
        command=[str(value) for value in item["command"]],
        risk=risk,
        enabled_by_default=bool(item["enabled_by_default"]),
        requires_reboot=bool(item.get("requires_reboot", False)),
        duration_hint=str(item.get("duration_hint", "kurz")),
        impact=str(item.get("impact", "Diagnose oder Reparatur")),
    )


class TuningExecutor:
    def __init__(
        self,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        logger: AppLogger | None = None,
    ) -> None:
        self._popen_factory = popen_factory
        self._logger = logger

    def run(
        self,
        actions: list[TuningAction],
        on_log: Callable[[str], None],
        on_result: Callable[[TuningResult], None],
    ) -> list[TuningResult]:
        results: list[TuningResult] = []
        total = len(actions)
        for index, action in enumerate(actions, start=1):
            result = TuningResult(action=action, status=STATUS_RUNNING)
            result.started_at = datetime.now().isoformat(timespec="seconds")
            on_result(result)
            if self._logger:
                self._logger.info(f"Tuning gestartet: {action.name}")
                self._logger.info(f"Befehl: {' '.join(action.command)}")
            on_log(f"Tuning {index}/{total}: {action.name}")
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
                        result.output.append(clean)
                        on_log(clean)
                result.exit_code = process.wait()
            except Exception as exc:
                result.error = f"Unerwarteter Fehler: {exc}"
                result.status = STATUS_FAILED
                if self._logger:
                    self._logger.error(f"Tuning fehlgeschlagen: {action.name}", exc)
            else:
                if result.exit_code == 0:
                    result.status = STATUS_SUCCESS
                    if self._logger:
                        self._logger.success(f"Tuning erfolgreich: {action.name}")
                else:
                    result.status = STATUS_FAILED
                    result.error = f"Exit-Code {result.exit_code}"
                    if self._logger:
                        self._logger.error(f"Tuning fehlgeschlagen: {action.name} ({result.error})")
            finally:
                result.finished_at = datetime.now().isoformat(timespec="seconds")
                results.append(result)
                on_result(result)
        return results
