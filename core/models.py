from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.app_config import APP_DISPLAY_NAME, APP_VERSION

APP_NAME = APP_DISPLAY_NAME

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_DRY_RUN = "dry_run"


@dataclass(frozen=True)
class Package:
    id: str
    name: str
    category: str
    winget_id: str
    description: str
    recommended_for: list[str]
    requires_admin: bool
    enabled_by_default: bool


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    description: str
    packages: list[str]
    folders: list[str]
    notes: list[str]


@dataclass(frozen=True)
class TuningAction:
    id: str
    name: str
    category: str
    description: str
    command: list[str]
    risk: str
    enabled_by_default: bool
    requires_reboot: bool = False
    duration_hint: str = "kurz"
    impact: str = "Diagnose oder Reparatur"


@dataclass
class PlannedAction:
    package: Package
    status: str = STATUS_PENDING
    command: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    output: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ActionPlan:
    profile: Profile
    actions: list[PlannedAction]
    folders: list[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def package_count(self) -> int:
        return len(self.actions)


@dataclass
class RunReport:
    app_name: str
    app_version: str
    profile: Profile
    actions: list[PlannedAction]
    folders: list[str]
    started_at: str
    finished_at: str
    json_path: Path | None = None
    txt_path: Path | None = None

    @property
    def failures(self) -> list[PlannedAction]:
        return [action for action in self.actions if action.status == STATUS_FAILED]


@dataclass
class TuningResult:
    action: TuningAction
    status: str = STATUS_PENDING
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    output: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class InstalledProgram:
    key: str
    name: str
    package_id: str
    version: str
    source: str


@dataclass(frozen=True)
class AvailableUpdate:
    key: str
    name: str
    package_id: str
    current_version: str
    available_version: str
    source: str


@dataclass
class MaintenanceResult:
    name: str
    package_id: str
    operation: str
    status: str = STATUS_PENDING
    command: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    output: list[str] = field(default_factory=list)
    error: str | None = None
