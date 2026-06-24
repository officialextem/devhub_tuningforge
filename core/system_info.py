from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


SYSTEM_INFO_STATUS_PLANNED = "planned"
SYSTEM_INFO_STATUS_SUCCESS = "success"
SYSTEM_INFO_STATUS_FAILED = "failed"
SYSTEM_INFO_STATUS_DRY_RUN = "dry_run"
SYSTEM_INFO_TIMEOUT_SECONDS = 180


class SystemInfoError(ValueError):
    pass


@dataclass(frozen=True)
class SystemInfoExportResult:
    status: str
    export_path: str
    size_bytes: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float = 0.0
    exit_code: int | None = None
    error: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def system_info_root(runtime_root: Path) -> Path:
    return runtime_root / "reports" / "systeminfo"


def build_system_info_export_path(runtime_root: Path, timestamp: datetime | None = None) -> Path:
    root = system_info_root(runtime_root)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return root / f"systeminfo-{stamp}.txt"


def planned_system_info_export(runtime_root: Path, dry_run: bool = False) -> SystemInfoExportResult:
    export_path = build_system_info_export_path(runtime_root)
    return SystemInfoExportResult(
        status=SYSTEM_INFO_STATUS_DRY_RUN if dry_run else SYSTEM_INFO_STATUS_PLANNED,
        export_path=str(export_path),
        dry_run=dry_run,
    )


def export_system_info_txt(
    runtime_root: Path,
    *,
    dry_run: bool = False,
    timeout_seconds: int = SYSTEM_INFO_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> SystemInfoExportResult:
    export_path = build_system_info_export_path(runtime_root)
    _assert_safe_export_path(runtime_root, export_path)
    started = datetime.now()
    if dry_run:
        return SystemInfoExportResult(
            status=SYSTEM_INFO_STATUS_DRY_RUN,
            export_path=str(export_path),
            started_at=started.isoformat(timespec="seconds"),
            finished_at=started.isoformat(timespec="seconds"),
            duration_seconds=0.0,
            exit_code=0,
            dry_run=True,
        )
    export_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["msinfo32", "/report", str(export_path)]
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        finished = datetime.now()
        return SystemInfoExportResult(
            status=SYSTEM_INFO_STATUS_FAILED,
            export_path=str(export_path),
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            error=f"MSINFO32 Timeout nach {timeout_seconds} Sekunden.",
            exit_code=getattr(exc, "returncode", None),
        )
    except OSError as exc:
        finished = datetime.now()
        return SystemInfoExportResult(
            status=SYSTEM_INFO_STATUS_FAILED,
            export_path=str(export_path),
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            duration_seconds=round((finished - started).total_seconds(), 3),
            error=f"MSINFO32 konnte nicht gestartet werden: {exc}",
        )

    finished = datetime.now()
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    exists = export_path.exists() and export_path.is_file()
    size = export_path.stat().st_size if exists else 0
    status = SYSTEM_INFO_STATUS_SUCCESS if completed.returncode == 0 and exists and size > 0 else SYSTEM_INFO_STATUS_FAILED
    error = None if status == SYSTEM_INFO_STATUS_SUCCESS else (output.strip() or "MSINFO32 hat keinen nutzbaren TXT-Report erzeugt.")
    return SystemInfoExportResult(
        status=status,
        export_path=str(export_path),
        size_bytes=size,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        duration_seconds=round((finished - started).total_seconds(), 3),
        exit_code=completed.returncode,
        error=error,
        dry_run=False,
    )


def _assert_safe_export_path(runtime_root: Path, export_path: Path) -> None:
    root = system_info_root(runtime_root).resolve()
    candidate = export_path.resolve()
    if not str(candidate).casefold().startswith(str(root).casefold()):
        raise SystemInfoError("SystemInfo-Exportpfad liegt ausserhalb des lokalen Report-Ordners.")
    if export_path.suffix.casefold() != ".txt":
        raise SystemInfoError("SystemInfo-Export muss eine TXT-Datei sein.")
