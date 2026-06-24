from __future__ import annotations

import shutil
import subprocess
import re
from datetime import datetime
from typing import Callable

from core.app_logger import AppLogger
from core.diagnostics import diagnostic_hint
from core.models import (
    AvailableUpdate,
    InstalledProgram,
    MaintenanceResult,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
)

LogCallback = Callable[[str], None]
ResultCallback = Callable[[MaintenanceResult], None]
SCAN_TIMEOUT_SECONDS = 180


def build_uninstall_command(program: InstalledProgram, scope: str) -> list[str]:
    command = ["winget", "uninstall"]
    if program.package_id:
        command.extend(["--id", program.package_id])
    else:
        command.extend(["--name", program.name])
    command.extend(["--silent", "--accept-source-agreements"])
    if scope in {"user", "machine"}:
        command.extend(["--scope", scope])
    return command


def build_upgrade_command(update: AvailableUpdate, scope: str | None = None) -> list[str]:
    command = [
        "winget",
        "upgrade",
        "--id",
        update.package_id,
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    if scope in {"user", "machine"}:
        command.extend(["--scope", scope])
    return command


def parse_winget_list(output: str) -> list[InstalledProgram]:
    rows = _parse_winget_table(output)
    programs: list[InstalledProgram] = []
    for index, row in enumerate(rows):
        name = _row_value(row, "Name").strip()
        package_id = _row_value(row, "Id", "ID").strip()
        version = _row_value(row, "Version").strip()
        source = _row_value(row, "Source", "Quelle").strip()
        if not name:
            continue
        key = package_id or f"name:{name}:{index}"
        programs.append(InstalledProgram(key=key, name=name, package_id=package_id, version=version, source=source))
    return programs


def parse_winget_upgrade(output: str) -> list[AvailableUpdate]:
    rows = _parse_winget_table(output)
    updates: list[AvailableUpdate] = []
    for index, row in enumerate(rows):
        name = _row_value(row, "Name").strip()
        package_id = _row_value(row, "Id", "ID").strip()
        current = _row_value(row, "Version").strip()
        available = _row_value(row, "Available", "Verfügbar", "Verfuegbar").strip()
        source = _row_value(row, "Source", "Quelle").strip()
        if not name or not package_id:
            continue
        updates.append(
            AvailableUpdate(
                key=package_id or f"update:{name}:{index}",
                name=name,
                package_id=package_id,
                current_version=current,
                available_version=available,
                source=source,
            )
        )
    return updates


def _parse_winget_table(output: str) -> list[dict[str, str]]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    separator_index = _find_table_separator(lines)
    if separator_index is None or separator_index == 0:
        return []

    header = lines[separator_index - 1]
    starts = [match.start() for match in re.finditer(r"\S+", header)]
    columns: list[tuple[str, int, int | None]] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else None
        name = header[start:end].strip()
        if name:
            columns.append((name, start, end))

    if len(columns) <= 1:
        header_names = re.split(r"\s{2,}", header.strip())
        rows: list[dict[str, str]] = []
        for line in lines[separator_index + 1 :]:
            values = re.split(r"\s{2,}", line.strip())
            if len(values) >= len(header_names):
                rows.append(dict(zip(header_names, values)))
        return rows

    rows: list[dict[str, str]] = []
    for line in lines[separator_index + 1 :]:
        normalized_line = _normalize_column_name(line)
        if (
            normalized_line.startswith("the following")
            or "upgrades available" in normalized_line
            or "aktualisierungen verfuegbar" in normalized_line
            or "aktualisierung verfuegbar" in normalized_line
        ):
            continue
        row = {name: line[start:end].strip() if end is not None else line[start:].strip() for name, start, end in columns}
        if any(row.values()):
            rows.append(row)
    return rows


def _find_table_separator(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or set(stripped) - {"-", " "}:
            continue
        if index == 0:
            continue
        header = lines[index - 1].lower()
        if "name" in header and (" id" in f" {header}" or "id " in header):
            return index
    return None


def _row_value(row: dict[str, str], *names: str) -> str:
    normalized = {_normalize_column_name(key): value for key, value in row.items()}
    for name in names:
        value = normalized.get(_normalize_column_name(name))
        if value is not None:
            return value
    for key, value in normalized.items():
        if any(key.startswith(_normalize_column_name(name)) for name in names):
            return value
    return ""


def _normalize_column_name(name: str) -> str:
    return (
        name.casefold()
        .replace("ü", "ue")
        .replace("Ã¼", "ue")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .strip()
    )


class WingetMaintenance:
    def __init__(
        self,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        winget_lookup: Callable[[str], str | None] = shutil.which,
        logger: AppLogger | None = None,
    ) -> None:
        self._popen_factory = popen_factory
        self._runner = runner
        self._winget_lookup = winget_lookup
        self._logger = logger
        self.last_scan_warning: str | None = None
        self.last_raw_output_excerpt: str | None = None

    def scan_installed(self, scope: str = "user") -> list[InstalledProgram]:
        self.last_scan_warning = None
        self.last_raw_output_excerpt = None
        self._ensure_winget()
        command = ["winget", "list", "--accept-source-agreements"]
        if scope in {"user", "machine"}:
            command.extend(["--scope", scope])
        if self._logger:
            self._logger.info(f"Uninstall-Scan gestartet: scope={scope}")
            self._logger.info(f"Befehl: {' '.join(command)}")
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"winget list Timeout nach {SCAN_TIMEOUT_SECONDS} Sekunden. "
                "Winget/App Installer blockiert moeglicherweise; spaeter erneut scannen."
            ) from exc
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        if completed.returncode != 0:
            raise RuntimeError(f"winget list Exit-Code {completed.returncode}: {output.strip()}")
        programs = parse_winget_list(output)
        self._record_empty_parse_warning("Uninstall-Scan", programs, output)
        if self._logger:
            self._logger.success(f"Uninstall-Scan abgeschlossen: {len(programs)} Programme.")
        return programs

    def scan_updates(self, scope: str = "user") -> list[AvailableUpdate]:
        self.last_scan_warning = None
        self.last_raw_output_excerpt = None
        self._ensure_winget()
        if self._logger:
            self._logger.info(f"Update-Scan gestartet: scope={scope}")
        command = ["winget", "upgrade", "--accept-source-agreements"]
        if scope in {"user", "machine"}:
            command.extend(["--scope", scope])
        if self._logger:
            self._logger.info(f"Befehl: {' '.join(command)}")
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"winget upgrade Timeout nach {SCAN_TIMEOUT_SECONDS} Sekunden. "
                "Winget/App Installer blockiert moeglicherweise; spaeter erneut scannen."
            ) from exc
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"winget upgrade Exit-Code {completed.returncode}: {output.strip()}")
        updates = parse_winget_upgrade(output)
        self._record_empty_parse_warning("Update-Scan", updates, output)
        if self._logger:
            self._logger.success(f"Update-Scan abgeschlossen: {len(updates)} Updates.")
        return updates

    def uninstall(
        self,
        programs: list[InstalledProgram],
        scope: str,
        on_log: LogCallback,
        on_result: ResultCallback,
    ) -> list[MaintenanceResult]:
        return self._run_many(
            [MaintenanceResult(name=p.name, package_id=p.package_id, operation="uninstall", command=build_uninstall_command(p, scope)) for p in programs],
            on_log,
            on_result,
        )

    def upgrade(
        self,
        updates: list[AvailableUpdate],
        scope: str,
        on_log: LogCallback,
        on_result: ResultCallback,
    ) -> list[MaintenanceResult]:
        return self._run_many(
            [MaintenanceResult(name=u.name, package_id=u.package_id, operation="update", command=build_upgrade_command(u, scope)) for u in updates],
            on_log,
            on_result,
        )

    def _run_many(self, results: list[MaintenanceResult], on_log: LogCallback, on_result: ResultCallback) -> list[MaintenanceResult]:
        self._ensure_winget()
        total = len(results)
        for index, result in enumerate(results, start=1):
            result.status = STATUS_RUNNING
            result.started_at = datetime.now().isoformat(timespec="seconds")
            on_result(result)
            if self._logger:
                self._logger.info(f"{result.operation} gestartet: {result.name}")
                self._logger.info(f"Befehl: {' '.join(result.command)}")
            on_log(f"{index}/{total}: {result.operation} {result.name}")
            on_log(f"Befehl: {' '.join(result.command)}")
            try:
                process = self._popen_factory(
                    result.command,
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
                result.status = STATUS_FAILED
                result.error = f"Unerwarteter Fehler: {exc}"
                if self._logger:
                    self._logger.error(f"{result.operation} fehlgeschlagen: {result.name}", exc)
            else:
                if result.exit_code == 0:
                    result.status = STATUS_SUCCESS
                    if self._logger:
                        self._logger.success(f"{result.operation} erfolgreich: {result.name}")
                else:
                    result.status = STATUS_FAILED
                    hint = diagnostic_hint(result.exit_code, result.output)
                    result.error = f"Exit-Code {result.exit_code}: {hint}" if hint else f"Exit-Code {result.exit_code}"
                    if self._logger:
                        self._logger.error(f"{result.operation} fehlgeschlagen: {result.name} ({result.error})")
            finally:
                result.finished_at = datetime.now().isoformat(timespec="seconds")
                on_result(result)
        return results

    def _ensure_winget(self) -> None:
        if not self._winget_lookup("winget"):
            raise RuntimeError("winget wurde nicht gefunden. Bitte App Installer/Microsoft Store pruefen.")

    def _record_empty_parse_warning(self, label: str, rows: list, output: str) -> None:
        if rows or not output.strip():
            return
        excerpt = _raw_excerpt(output)
        self.last_raw_output_excerpt = excerpt
        self.last_scan_warning = f"{label}: winget-Ausgabe konnte nicht als Tabelle gelesen werden. Auszug: {excerpt}"
        if self._logger:
            self._logger.warning(self.last_scan_warning)


def _raw_excerpt(output: str, limit: int = 900) -> str:
    compact = " ".join(line.strip() for line in output.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
