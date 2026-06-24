from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


RECOVERY_STATUS_PRESENT = "present"
RECOVERY_STATUS_MISSING = "missing"
RECOVERY_STATUS_INVALID = "invalid"


class RecoveryError(ValueError):
    pass


@dataclass(frozen=True)
class RecoveryTarget:
    id: str
    name: str
    path: str
    kind: str
    required: bool = False
    status: str = RECOVERY_STATUS_MISSING
    size_bytes: int = 0
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RecoverySummary:
    recovery_root: str
    targets: list[RecoveryTarget]
    warnings: list[str]
    checked_at: str

    @property
    def planned_count(self) -> int:
        return len(self.targets)

    @property
    def present_count(self) -> int:
        return sum(1 for target in self.targets if target.status == RECOVERY_STATUS_PRESENT)

    @property
    def missing_count(self) -> int:
        return sum(1 for target in self.targets if target.status == RECOVERY_STATUS_MISSING)

    @property
    def invalid_count(self) -> int:
        return sum(1 for target in self.targets if target.status == RECOVERY_STATUS_INVALID)

    def to_dict(self) -> dict:
        return {
            "recovery_root": self.recovery_root,
            "targets": [target.to_dict() for target in self.targets],
            "warnings": self.warnings,
            "checked_at": self.checked_at,
            "planned_count": self.planned_count,
            "present_count": self.present_count,
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
        }


def recovery_root(runtime_root: Path) -> Path:
    return runtime_root / "recovery"


def default_recovery_targets(runtime_root: Path, resource_root: Path) -> list[RecoveryTarget]:
    return [
        RecoveryTarget("app-state", "App-State", str(runtime_root / "config" / "app-state.json"), "config", True),
        RecoveryTarget("profiles", "Profilordner", str(resource_root / "profiles"), "folder", True),
        RecoveryTarget("packages", "Paketkatalog", str(resource_root / "packages" / "catalog.json"), "config", True),
        RecoveryTarget("tuning", "Tuning-Aktionen", str(resource_root / "tuning" / "actions.json"), "config", True),
        RecoveryTarget("reports", "Reports", str(runtime_root / "reports"), "folder", False),
        RecoveryTarget("logs", "Logs", str(runtime_root / "logs"), "folder", False),
        RecoveryTarget("offline-cache-index", "Offline-Cache-Index", str(runtime_root / "cache" / "installers" / "installer-cache.json"), "config", False),
    ]


def inspect_recovery_targets(runtime_root: Path, targets: list[RecoveryTarget] | None = None) -> RecoverySummary:
    checked_at = datetime.now().isoformat(timespec="seconds")
    source_targets = targets if targets is not None else default_recovery_targets(runtime_root, runtime_root)
    inspected = [_inspect_target(target) for target in source_targets]
    warnings = [
        f"{target.name}: {target.note}"
        for target in inspected
        if target.status == RECOVERY_STATUS_INVALID or (target.required and target.status == RECOVERY_STATUS_MISSING)
    ]
    return RecoverySummary(
        recovery_root=str(recovery_root(runtime_root)),
        targets=inspected,
        warnings=warnings,
        checked_at=checked_at,
    )


def _inspect_target(target: RecoveryTarget) -> RecoveryTarget:
    if "://" in target.path:
        return _replace_target(target, RECOVERY_STATUS_INVALID, 0, "Remote-Pfade sind nicht erlaubt.")
    path = Path(target.path)
    try:
        resolved = path.resolve()
    except OSError as exc:
        return _replace_target(target, RECOVERY_STATUS_INVALID, 0, f"Pfad ungueltig: {exc}")
    if not resolved.exists():
        return _replace_target(target, RECOVERY_STATUS_MISSING, 0, "Pfad fehlt.")
    if target.kind == "folder" and not resolved.is_dir():
        return _replace_target(target, RECOVERY_STATUS_INVALID, 0, "Erwartet wurde ein Ordner.")
    if target.kind != "folder" and not resolved.is_file():
        return _replace_target(target, RECOVERY_STATUS_INVALID, 0, "Erwartet wurde eine Datei.")
    size = resolved.stat().st_size if resolved.is_file() else 0
    return _replace_target(target, RECOVERY_STATUS_PRESENT, size, "Lokal vorhanden.")


def _replace_target(target: RecoveryTarget, status: str, size_bytes: int, note: str) -> RecoveryTarget:
    return RecoveryTarget(
        id=target.id,
        name=target.name,
        path=target.path,
        kind=target.kind,
        required=target.required,
        status=status,
        size_bytes=size_bytes,
        note=note,
    )
