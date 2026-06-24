from dataclasses import dataclass, field

from core.models import (
    ActionPlan,
    AvailableUpdate,
    InstalledProgram,
    MaintenanceResult,
    Package,
    Profile,
    RunReport,
    TuningAction,
    TuningResult,
)
from core.alerting import DailyReportSummary
from core.configuration import DevHubConfig
from core.diagnostics import DiagnosticFinding
from core.auto_analysis import AutoAnalysisSnapshot
from core.guardforge import FileWatchEvent, GuardRiskFinding
from core.offline_cache import CacheSummary
from core.recovery import RecoverySummary
from core.risk_engine import RiskSummary
from core.system_info import SystemInfoExportResult


@dataclass
class WizardState:
    profiles: list[Profile] = field(default_factory=list)
    packages: list[Package] = field(default_factory=list)
    selected_profile_id: str | None = None
    selected_package_ids: set[str] = field(default_factory=set)
    action_plan: ActionPlan | None = None
    report: RunReport | None = None
    tuning_actions: list[TuningAction] = field(default_factory=list)
    selected_tuning_ids: set[str] = field(default_factory=set)
    tuning_results: list[TuningResult] = field(default_factory=list)
    installed_programs: list[InstalledProgram] = field(default_factory=list)
    selected_uninstall_keys: set[str] = field(default_factory=set)
    uninstall_scope: str = "device"
    available_updates: list[AvailableUpdate] = field(default_factory=list)
    selected_update_keys: set[str] = field(default_factory=set)
    update_scope: str = "device"
    maintenance_results: list[MaintenanceResult] = field(default_factory=list)
    scan_warnings: list[str] = field(default_factory=list)
    diagnostic_findings: list[DiagnosticFinding] = field(default_factory=list)
    guard_events: list[FileWatchEvent] = field(default_factory=list)
    guard_findings: list[GuardRiskFinding] = field(default_factory=list)
    auto_analysis: AutoAnalysisSnapshot | None = None
    offline_cache: CacheSummary | None = None
    recovery: RecoverySummary | None = None
    risk_summary: RiskSummary | None = None
    daily_report: DailyReportSummary | None = None
    devhub_config: DevHubConfig = field(default_factory=DevHubConfig)
    system_info: SystemInfoExportResult | None = None
    imported_profile_name: str | None = None
    imported_profile_path: str | None = None
    exported_profile_path: str | None = None
    profile_import_warnings: list[str] = field(default_factory=list)
    guardforge_enabled_paths: list[str] = field(default_factory=list)
    session_report_json_path: str | None = None
    session_report_txt_path: str | None = None

    @property
    def selected_profile(self) -> Profile | None:
        return next((p for p in self.profiles if p.id == self.selected_profile_id), None)

    @property
    def selected_packages(self) -> list[Package]:
        selected = self.selected_package_ids
        return [package for package in self.packages if package.id in selected]

    @property
    def selected_tuning_actions(self) -> list[TuningAction]:
        selected = self.selected_tuning_ids
        return [action for action in self.tuning_actions if action.id in selected]

    @property
    def selected_uninstall_programs(self) -> list[InstalledProgram]:
        selected = self.selected_uninstall_keys
        return [program for program in self.installed_programs if program.key in selected]

    @property
    def selected_updates(self) -> list[AvailableUpdate]:
        selected = self.selected_update_keys
        return [update for update in self.available_updates if update.key in selected]
