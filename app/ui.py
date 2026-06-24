from __future__ import annotations

import threading
import tkinter as tk
import shutil
import json
import sys
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk

import customtkinter as ctk

from app import theme
from app.state import WizardState
from core import admin
from core.alerting import ALERT_CRITICAL, ALERT_WARNING, DailyReportSummary, build_daily_report_summary
from core.app_logger import AppLogger, LogEntry, get_app_logger
from core.app_settings import PRESET_BUILTIN, PRESET_IMPORTED, AppSettings, load_app_settings, save_app_settings
from core.auto_analysis import build_auto_analysis_snapshot, failed_auto_analysis, running_auto_analysis
from core.catalog import load_catalog
from core.configuration import (
    CONFIG_EXTENSION,
    DEFAULT_ENABLED_MODULES,
    DevHubConfig,
    DevHubConfigError,
    default_config_path,
    load_config,
    read_config,
    save_config,
    write_config,
)
from core.dashboard import DashboardSnapshot, build_dashboard_snapshot, payload_failures
from core.diagnostics import ErrorDoctor
from core.dry_run import simulate_setup_actions, simulate_tuning_actions, simulate_uninstall, simulate_updates
from core.executor import WingetExecutor
from core.guardforge import MockFileWatchProvider, default_guard_profile, score_guard_events
from core.maintenance import WingetMaintenance
from core.app_config import APP_DISPLAY_NAME, APP_MODULE, APP_SHORT_NAME, APP_VERSION, LOG_FILE_NAME, SESSION_REPORT_PREFIX
from core.models import MaintenanceResult, Package, PlannedAction, TuningResult
from core.offline_cache import CacheSummary, OfflineCacheError, cache_paths, index_existing_installers, inspect_cache
from core.planner import build_action_plan
from core.profile_io import (
    PROFILE_EXTENSION,
    DevHubProfileError,
    ImportedProfile,
    build_profile,
    read_profile,
    write_profile,
)
from core.profiles import load_profiles
from core.recovery import RecoverySummary, inspect_recovery_targets, recovery_root
from core.reporting import create_report, write_session_report
from core.risk_engine import RISK_HIGH, RISK_MEDIUM, RiskSummary, build_risk_summary
from core.system_info import (
    SYSTEM_INFO_STATUS_FAILED,
    SYSTEM_INFO_STATUS_SUCCESS,
    SystemInfoExportResult,
    export_system_info_txt,
    planned_system_info_export,
    system_info_root,
)
from core.tuning import TuningExecutor, load_tuning_actions


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _resource_root()
RUNTIME_ROOT = _runtime_root()
APP_SETTINGS_PATH = RUNTIME_ROOT / "config" / "app-state.json"
DEVHUB_CONFIG_PATH = default_config_path(RUNTIME_ROOT)
CACHE_ROOT, CACHE_INDEX_PATH = cache_paths(RUNTIME_ROOT)
RECOVERY_ROOT = recovery_root(RUNTIME_ROOT)
SYSTEM_INFO_ROOT = system_info_root(RUNTIME_ROOT)
MAX_CONSOLE_LINES = 500
CONSOLE_PRUNE_LINES = 100
TREE_STYLE = "TuningForge.Treeview"
TREE_HEADING_STYLE = f"{TREE_STYLE}.Heading"
PACKAGE_CATEGORY_ORDER = [
    "Browser",
    "Entwicklung",
    "AI/Codex",
    "System",
    "Gaming",
    "Grafikdesign/Creator",
    "Medien",
    "Office/Finanzen",
    "Trading/Crypto",
    "Produktivitaet/Kommunikation",
]
PACKAGE_RECOMMENDATION_LABELS = {
    "clean": "Clean",
    "developer": "Developer",
    "ai-codex": "AI/Codex",
    "extem": "ExTeM",
    "gaming": "Gaming",
    "creator": "Creator",
    "office": "Office",
    "finance": "Finanzen",
    "trading": "Trading",
    "crypto": "Crypto",
    "personal": "Privat",
}
TUNING_CATEGORY_ORDER = [
    "Schnellfix",
    "Winget Repair",
    "Windows Repair",
    "Netzwerk Repair",
    "Diagnose",
]


class TuningForgeApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=theme.BACKGROUND)

        self.title(f"{APP_DISPLAY_NAME} {APP_VERSION}")
        self.geometry("1060x720")
        self.minsize(940, 640)
        self._maximize_window()

        self.wizard_state = WizardState()
        self.page_index = 0
        self.package_vars: dict[str, ctk.BooleanVar] = {}
        self.package_count_labels: dict[str, ctk.CTkLabel] = {}
        self.package_row_ids: dict[str, str] = {}
        self.profile_var = ctk.StringVar()
        self.package_search_text = ""
        self.tuning_vars: dict[str, ctk.BooleanVar] = {}
        self.executor: WingetExecutor | None = None
        self.tuning_executor: TuningExecutor | None = None
        self.maintenance: WingetMaintenance | None = None
        self.error_doctor = ErrorDoctor()
        self.logger: AppLogger = get_app_logger(RUNTIME_ROOT / "logs")
        self.last_status_var = ctk.StringVar(value="Console bereit")
        self.mode_title_var = ctk.StringVar(value=APP_SHORT_NAME)
        self.mode_subtitle_var = ctk.StringVar(value="DEVHub Setup & Repair")
        self.elapsed_var = ctk.StringVar(value="00:00")
        self.scan_status_var = ctk.StringVar(value="Bereit")
        self.scan_detail_var = ctk.StringVar(value="Noch kein Scan gestartet.")
        self.scan_elapsed_var = ctk.StringVar(value="00:00")
        self.config_report_mode_var = ctk.StringVar(value="session")
        self.config_dry_run_var = ctk.BooleanVar(value=False)
        self.config_auto_analysis_var = ctk.BooleanVar(value=True)
        self.config_remember_preset_var = ctk.BooleanVar(value=True)
        self.config_module_vars: dict[str, ctk.BooleanVar] = {}
        self.run_started_at: datetime | None = None
        self.timer_job: str | None = None
        self.scan_started_at: datetime | None = None
        self.scan_timer_job: str | None = None
        self.scan_running = False
        self.execution_running = False
        self.is_admin = admin.is_admin()
        self.nav_buttons: dict[int, ctk.CTkButton] = {}
        self.uninstall_vars: dict[str, ctk.BooleanVar] = {}
        self.uninstall_row_keys: dict[str, str] = {}
        self.update_vars: dict[str, ctk.BooleanVar] = {}
        self.update_row_keys: dict[str, str] = {}
        self.console_line_count = 0
        self.app_settings_path = APP_SETTINGS_PATH
        self.devhub_config_path = DEVHUB_CONFIG_PATH
        self.app_settings = load_app_settings(self.app_settings_path)
        self.wizard_state.devhub_config = load_config(self.devhub_config_path)

        try:
            self.logger.info(f"{APP_DISPLAY_NAME} {APP_VERSION} gestartet.")
            self.logger.info(f"Admin-Status: {self.is_admin}")
            self._load_data()
            self._build_shell()
            if self.is_admin:
                self._show_page(0)
            else:
                self._show_admin_gate()
            self._schedule_maximize_reapply()
            if self.wizard_state.devhub_config.auto_analysis_enabled:
                self.after(250, self._start_auto_analysis)
            else:
                self.logger.info("Auto-Analyse per Konfiguration deaktiviert.")
        except Exception as exc:
            self.logger.error("App-Initialisierung fehlgeschlagen", exc)
            raise

    def _maximize_window(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            self.geometry("1060x720")

    def _schedule_maximize_reapply(self) -> None:
        for delay_ms in (50, 250, 750, 1500):
            self.after(delay_ms, self._maximize_window)

    def _start_auto_analysis(self) -> None:
        if not self.wizard_state.devhub_config.auto_analysis_enabled:
            self.last_status_var.set("Auto-Analyse deaktiviert")
            self.logger.info("Auto-Analyse per Konfiguration blockiert.")
            return
        if self.wizard_state.auto_analysis and self.wizard_state.auto_analysis.status == "laeuft":
            return
        started_at = datetime.now()
        self.wizard_state.auto_analysis = running_auto_analysis(started_at.isoformat(timespec="seconds"))
        self.last_status_var.set("Auto-Analyse laeuft...")
        self.logger.info("Auto-Analyse gestartet: read-only Startchecks.")
        self._refresh_current_page_if_dashboard()

        def worker() -> None:
            try:
                snapshot, findings, risk_summary = self._collect_auto_analysis_snapshot(started_at)
            except Exception as exc:
                snapshot = failed_auto_analysis(started_at, str(exc))
                findings = []
                risk_summary = None
                self._thread_entry(self.logger.error("Auto-Analyse fehlgeschlagen", exc))
            self.after(0, lambda: self._finish_auto_analysis(snapshot, findings, risk_summary))

        threading.Thread(target=worker, daemon=True).start()

    def _collect_auto_analysis_snapshot(self, started_at: datetime):
        log_dir = RUNTIME_ROOT / "logs"
        findings = []
        findings.extend(
            self.error_doctor.analyze_project_state(
                ROOT,
                is_admin=self.is_admin,
                winget_available=bool(shutil.which("winget")),
            )
        )
        findings.extend(self.error_doctor.analyze_runtime_logs(log_dir / "startup-error.log", log_dir / LOG_FILE_NAME))
        if self.wizard_state.scan_warnings:
            findings.extend(self.error_doctor.analyze_texts(self.wizard_state.scan_warnings))
        latest_session = self._latest_file(RUNTIME_ROOT / "reports", f"{SESSION_REPORT_PREFIX}-*.txt")
        latest_payload = self._latest_session_payload()
        cache_summary = self._inspect_offline_cache(silent=True) if CACHE_ROOT.exists() else None
        recovery_summary = self._inspect_recoveryforge(silent=True)
        risk_summary = build_risk_summary(
            diagnostic_findings=findings,
            guard_findings=self.wizard_state.guard_findings,
            offline_cache=cache_summary,
            recovery=recovery_summary,
            latest_payload=latest_payload,
            scan_warnings=self.wizard_state.scan_warnings,
        )
        snapshot = build_auto_analysis_snapshot(
            started_at=started_at,
            is_admin=self.is_admin,
            winget_available=bool(shutil.which("winget")),
            app_settings=self.app_settings,
            latest_session_name=latest_session.name if latest_session else None,
            latest_payload=latest_payload,
            diagnostic_findings=findings,
            guard_findings=self.wizard_state.guard_findings,
            cache_summary=cache_summary,
        )
        return snapshot, findings, risk_summary

    def _finish_auto_analysis(self, snapshot, findings, risk_summary) -> None:
        self.wizard_state.auto_analysis = snapshot
        self.wizard_state.diagnostic_findings = findings
        self.wizard_state.risk_summary = risk_summary
        self._refresh_daily_report_summary()
        if snapshot.status == "abgeschlossen":
            self.last_status_var.set(f"Auto-Analyse abgeschlossen: {snapshot.findings_count} Findings")
            self.logger.success("Auto-Analyse abgeschlossen.")
        else:
            self.last_status_var.set("Auto-Analyse fehlgeschlagen.")
            self.logger.warning("Auto-Analyse mit Fehlerstatus beendet.")
        self._refresh_current_page_if_dashboard()

    def _refresh_current_page_if_dashboard(self) -> None:
        if self.page_index == 0 and hasattr(self, "content"):
            self._show_page(0)

    def _restore_saved_preset(self, settings: AppSettings) -> bool:
        if settings.last_preset_kind == PRESET_IMPORTED and settings.last_profile_path:
            path = Path(settings.last_profile_path)
            if path.exists():
                known_package_ids = {package.id for package in self.wizard_state.packages}
                known_tuning_ids = {action.id for action in self.wizard_state.tuning_actions}
                try:
                    imported = read_profile(path, known_package_ids, known_tuning_ids)
                except DevHubProfileError as exc:
                    self.logger.warning(f"Gespeichertes Profil konnte nicht geladen werden: {exc}")
                else:
                    self._apply_imported_profile(path, imported, show_dialog=False)
                    self.logger.info(f"Gespeichertes Profil geladen: {path}")
                    return True
        if settings.last_profile_id:
            return self._apply_builtin_profile(settings.last_profile_id, persist=False)
        return False

    def _save_last_builtin_preset(self, profile_id: str) -> None:
        if not self.wizard_state.devhub_config.remember_last_preset:
            self.logger.info("Preset-Merken ist per Konfiguration deaktiviert.")
            return
        save_app_settings(
            self.app_settings_path,
            AppSettings(last_preset_kind=PRESET_BUILTIN, last_profile_id=profile_id),
        )
        self.app_settings = load_app_settings(self.app_settings_path)

    def _save_last_imported_preset(self, path: Path) -> None:
        if not self.wizard_state.devhub_config.remember_last_preset:
            self.logger.info("Preset-Merken ist per Konfiguration deaktiviert.")
            return
        save_app_settings(
            self.app_settings_path,
            AppSettings(last_preset_kind=PRESET_IMPORTED, last_profile_path=str(path)),
        )
        self.app_settings = load_app_settings(self.app_settings_path)

    def _apply_builtin_profile(self, profile_id: str, persist: bool) -> bool:
        profile = next((item for item in self.wizard_state.profiles if item.id == profile_id), None)
        if profile is None:
            return False
        self.wizard_state.selected_profile_id = profile.id
        self.wizard_state.selected_package_ids = set(profile.packages)
        self.wizard_state.imported_profile_name = None
        self.wizard_state.imported_profile_path = None
        self.wizard_state.profile_import_warnings.clear()
        self.wizard_state.guardforge_enabled_paths.clear()
        self.wizard_state.action_plan = None
        self.profile_var.set(profile.id)
        self.package_vars.clear()
        if persist:
            self._save_last_builtin_preset(profile.id)
        return True

    def _load_data(self) -> None:
        self.logger.info("Lade Paketkatalog und Profile.")
        self.wizard_state.packages = load_catalog(ROOT / "packages" / "catalog.json")
        self.wizard_state.profiles = load_profiles(ROOT / "profiles", self.wizard_state.packages)
        self.wizard_state.tuning_actions = load_tuning_actions(ROOT / "tuning" / "actions.json")
        self.wizard_state.selected_tuning_ids = {
            action.id for action in self.wizard_state.tuning_actions if action.enabled_by_default
        }
        if self.wizard_state.devhub_config.remember_last_preset and self._restore_saved_preset(self.app_settings):
            self.logger.info("Gespeichertes Preset per Konfiguration wiederhergestellt.")
        else:
            default_profile = next(
                (profile for profile in self.wizard_state.profiles if profile.id == "developer"),
                self.wizard_state.profiles[0],
            )
            self._apply_builtin_profile(default_profile.id, persist=False)
        self.logger.success(
            f"Daten geladen: {len(self.wizard_state.packages)} Pakete, "
            f"{len(self.wizard_state.profiles)} Profile, "
            f"{len(self.wizard_state.tuning_actions)} Tuning-Aktionen."
        )

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=theme.SURFACE)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(20, 16))
        ctk.CTkLabel(
            brand,
            text="TF",
            width=42,
            height=42,
            corner_radius=10,
            fg_color=theme.PANEL_ALT,
            text_color=theme.ACCENT_CYAN,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(
            brand,
            textvariable=self.mode_title_var,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand, textvariable=self.mode_subtitle_var, text_color=theme.TEXT_MUTED).grid(row=1, column=1, sticky="w")

        nav_items = [
            (0, "ControlDeck"),
            (1, "Profil"),
            (2, "Programme"),
            (3, "Vorschau"),
            (4, "Ausfuehren"),
            (5, "Tuning"),
            (8, "Uninstall"),
            (11, "Updates"),
            (14, "Diagnose"),
            (15, "GuardForge"),
            (16, "Offline Cache"),
            (17, "RecoveryForge"),
            (18, "Risk Engine"),
            (19, "Tagesbericht"),
            (20, "Konfiguration"),
            (21, "SystemInfo"),
            (7, "Bericht"),
        ]
        self.step_labels: list[ctk.CTkButton] = []
        for page_id, label in nav_items:
            widget = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=38,
                corner_radius=8,
                fg_color="transparent",
                hover_color=theme.PANEL_ALT,
                text_color=theme.TEXT_MUTED,
                command=lambda target=page_id: self._navigate_to(target),
            )
            widget.pack(fill="x", padx=18, pady=3)
            self.step_labels.append(widget)
            self.nav_buttons[page_id] = widget

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=22, pady=22)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.footer = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=theme.SURFACE)
        self.footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.footer.grid_columnconfigure(0, weight=1)
        self.status_pill = ctk.CTkLabel(
            self.footer,
            textvariable=self.last_status_var,
            fg_color=theme.PANEL,
            text_color=theme.ACCENT_CYAN,
            corner_radius=8,
            height=38,
            padx=14,
        )
        self.status_pill.grid(row=0, column=0, padx=22, pady=16, sticky="w")
        self.back_button = ctk.CTkButton(
            self.footer,
            text="Zurueck",
            command=self._back,
            width=130,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        )
        self.back_button.grid(row=0, column=1, padx=8, pady=14)
        self.next_button = ctk.CTkButton(
            self.footer,
            text="Weiter",
            command=self._next,
            width=150,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        )
        self.next_button.grid(row=0, column=2, padx=(8, 22), pady=14)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _show_admin_gate(self) -> None:
        self._clear_content()
        self._set_mode_title(False)
        self.last_status_var.set("Administratorrechte erforderlich")
        for button in self.nav_buttons.values():
            button.configure(state="disabled")
        self.back_button.configure(state="disabled")
        self.next_button.configure(state="disabled")

        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(
            frame,
            text="Admin-Start erforderlich",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=theme.ERROR,
        ).pack(padx=34, pady=(42, 12), anchor="w")
        ctk.CTkLabel(
            frame,
            text="Uninstall, Updates und System-Tuning brauchen erhoehte Rechte. Starte die App als Administrator neu.",
            text_color=theme.TEXT_MUTED,
            wraplength=760,
        ).pack(padx=34, pady=(0, 26), anchor="w")
        ctk.CTkButton(
            frame,
            text="Als Administrator neu starten",
            command=self._show_admin_restart_confirmation,
            width=240,
            height=42,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).pack(padx=34, pady=8, anchor="w")

    def _show_admin_restart_confirmation(self) -> None:
        self._clear_content()
        self.last_status_var.set("Admin-Start bereit")
        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(
            frame,
            text="Admin-Fenster starten?",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=34, pady=(42, 12), anchor="w")
        ctk.CTkLabel(
            frame,
            text=(
                "Die aktuelle App bleibt offen. Erst nach deiner Bestaetigung wird Windows "
                "das neue Admin-Fenster anfordern."
            ),
            text_color=theme.TEXT_MUTED,
            wraplength=760,
        ).pack(padx=34, pady=(0, 24), anchor="w")
        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(padx=34, pady=8, anchor="w")
        ctk.CTkButton(
            actions,
            text="Admin-Fenster oeffnen",
            command=self._restart_as_admin,
            width=220,
            height=42,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 12))
        ctk.CTkButton(
            actions,
            text="Abbrechen",
            command=self._show_admin_gate,
            width=140,
            height=42,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1)

    def _restart_as_admin(self) -> None:
        self.logger.info("Admin-Neustart angefordert.")
        if admin.relaunch_as_admin():
            self.logger.success("Admin-Neustart an Windows uebergeben.")
            self.last_status_var.set("Admin-Neustart angefordert")
            self._show_admin_handoff()
        else:
            self.logger.error("Admin-Neustart konnte nicht gestartet werden.")
            messagebox.showerror("Admin-Start fehlgeschlagen", "Windows hat den Admin-Neustart nicht gestartet.")

    def _show_admin_handoff(self) -> None:
        self._clear_content()
        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(
            frame,
            text="Admin-Fenster wurde angefordert",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).pack(padx=34, pady=(42, 12), anchor="w")
        ctk.CTkLabel(
            frame,
            text=(
                "Wenn das neue Admin-Fenster sichtbar ist, kannst du dieses normale Fenster schliessen. "
                "Falls keine UAC-Abfrage oder kein neues Fenster erscheint, bleibt dieses Fenster als Rueckfall offen."
            ),
            text_color=theme.TEXT_MUTED,
            wraplength=760,
        ).pack(padx=34, pady=(0, 24), anchor="w")
        ctk.CTkButton(
            frame,
            text="Dieses Fenster schliessen",
            command=self.destroy,
            width=220,
            height=42,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).pack(padx=34, pady=8, anchor="w")

    def _show_page(self, index: int) -> None:
        if not self.is_admin:
            self._show_admin_gate()
            return
        self.page_index = index
        self._set_mode_title(index >= 5)
        if index not in {4, 6, 10, 13}:
            self._stop_elapsed_timer()
        self.logger.info(f"Wizard-Seite geoeffnet: {index}")
        self._clear_content()
        self._refresh_nav_state()

        pages = {
            0: self._page_welcome,
            1: self._page_profiles,
            2: self._page_packages,
            3: self._page_preview,
            4: self._page_run,
            5: self._page_tuning,
            6: self._page_tuning_run,
            7: self._page_report,
            8: self._page_uninstall,
            9: self._page_uninstall_preview,
            10: self._page_uninstall_run,
            11: self._page_updates,
            12: self._page_updates_preview,
            13: self._page_updates_run,
            14: self._page_diagnostics,
            15: self._page_guardforge,
            16: self._page_offline_cache,
            17: self._page_recoveryforge,
            18: self._page_risk_engine,
            19: self._page_daily_report,
            20: self._page_configuration,
            21: self._page_system_info,
        }
        pages[index]()
        self.back_button.configure(state="disabled" if index == 0 or self._is_busy_page(index) else "normal")
        next_text = {
            3: "Setup starten",
            5: "Tuning starten",
            8: "Uninstall Vorschau",
            9: "Uninstall starten",
            11: "Update Vorschau",
            12: "Updates starten",
            14: "ControlDeck",
            15: "Preview auswerten",
            16: "ControlDeck",
            17: "ControlDeck",
            18: "ControlDeck",
            19: "ControlDeck",
            20: "ControlDeck",
            21: "ControlDeck",
            7: "Fertig",
        }.get(index, "Weiter")
        self.next_button.configure(text=next_text, state="disabled" if self._is_busy_page(index) else "normal")

    def _refresh_nav_state(self) -> None:
        busy = self._is_busy_page(self.page_index)
        for page_id, button in self.nav_buttons.items():
            button.configure(
                state="disabled" if busy else "normal",
                text_color=theme.TEXT if page_id == self.page_index else theme.TEXT_MUTED,
                fg_color=theme.PANEL_ALT if page_id == self.page_index else "transparent",
            )

    def _is_busy_page(self, index: int) -> bool:
        return self.scan_running or self.execution_running

    def _navigate_to(self, index: int) -> None:
        if self._is_busy_page(self.page_index):
            return
        if index == 3:
            profile = self.wizard_state.selected_profile
            if profile:
                self.wizard_state.action_plan = build_action_plan(
                    profile,
                    self.wizard_state.packages,
                    self.wizard_state.selected_package_ids,
                )
        self._show_page(index)

    def _page_welcome(self) -> None:
        frame = self._scroll_panel("ControlDeck")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            frame,
            text="DEVHub ControlDeck",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 4), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Lokaler Status, letzte Ergebnisse und naechste sinnvolle Schritte.",
            font=ctk.CTkFont(size=15),
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="w")

        snapshot = self._dashboard_snapshot()
        self._dashboard_status_table(frame, snapshot)
        self._dashboard_module_table(frame, snapshot)

        recommendations = ctk.CTkFrame(frame, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        recommendations.grid(row=7, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))
        recommendations.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            recommendations,
            text="Empfehlungen",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")
        for row, item in enumerate(snapshot.recommendations, start=1):
            ctk.CTkLabel(
                recommendations,
                text=f"- {item}",
                text_color=theme.TEXT,
                wraplength=820,
                justify="left",
            ).grid(row=row, column=0, padx=18, pady=3, sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=8, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 18))
        actions.grid_columnconfigure(6, weight=1)
        self._dashboard_action(actions, 0, "Profil", lambda: self._show_page(1))
        self._dashboard_action(actions, 1, "Programme", lambda: self._show_page(2))
        self._dashboard_action(actions, 2, "Uninstall", lambda: self._show_page(8))
        self._dashboard_action(actions, 3, "Updates", lambda: self._show_page(11))
        self._dashboard_action(actions, 4, "Diagnose", lambda: self._show_page(14))
        self._dashboard_action(actions, 5, "GuardForge", lambda: self._show_page(15))
        self._dashboard_action(actions, 6, "Offline Cache", lambda: self._show_page(16))
        self._dashboard_action(actions, 0, "RecoveryForge", lambda: self._show_page(17), row=1)
        self._dashboard_action(actions, 1, "Risk Engine", lambda: self._show_page(18), row=1)
        self._dashboard_action(actions, 2, "Tagesbericht", lambda: self._show_page(19), row=1)
        self._dashboard_action(actions, 3, "Konfiguration", lambda: self._show_page(20), row=1)
        self._dashboard_action(actions, 4, "SystemInfo", lambda: self._show_page(21), row=1)
        self._dashboard_action(actions, 5, "Profil importieren", self._import_devhub_profile, row=1)
        self._dashboard_action(actions, 6, "Profil exportieren", self._export_devhub_profile, row=1)

    def _dashboard_status_table(self, parent: ctk.CTkFrame, snapshot: DashboardSnapshot) -> None:
        panel = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 10))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="Statusuebersicht",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")
        tree = ttk.Treeview(
            panel,
            columns=("value", "detail"),
            show="tree headings",
            height=len(snapshot.cards),
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Bereich")
        tree.heading("value", text="Status")
        tree.heading("detail", text="Hinweis")
        tree.column("#0", width=145, minwidth=120, stretch=False)
        tree.column("value", width=140, minwidth=110, stretch=False)
        tree.column("detail", width=620, minwidth=260, stretch=True)
        for card in snapshot.cards:
            tree.insert("", "end", text=card.title, values=(card.value, card.detail), tags=(card.level,))
        tree.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _dashboard_module_table(self, parent: ctk.CTkFrame, snapshot: DashboardSnapshot) -> None:
        panel = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        panel.grid(row=6, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="Modulzentrale",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")
        tree = ttk.Treeview(
            panel,
            columns=("status", "detail"),
            show="tree headings",
            height=len(snapshot.modules),
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Modul")
        tree.heading("status", text="Status")
        tree.heading("detail", text="Hinweis")
        tree.column("#0", width=170, minwidth=130, stretch=False)
        tree.column("status", width=160, minwidth=110, stretch=False)
        tree.column("detail", width=575, minwidth=260, stretch=True)
        self.dashboard_module_pages = {}
        for module in snapshot.modules:
            row_id = tree.insert("", "end", text=module.title, values=(module.status, module.detail), tags=(module.level,))
            self.dashboard_module_pages[row_id] = module.page_id
        tree.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        tree.bind("<Double-1>", lambda _event, widget=tree: self._open_dashboard_module(widget))
        ctk.CTkButton(
            panel,
            text="Ausgewaehltes Modul oeffnen",
            command=lambda widget=tree: self._open_dashboard_module(widget),
            width=210,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=2, column=0, padx=14, pady=(0, 14), sticky="w")

    def _open_dashboard_module(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if not selection:
            return
        page_id = getattr(self, "dashboard_module_pages", {}).get(selection[0])
        if page_id is not None:
            self._show_page(page_id)

    def _dashboard_cards(self) -> list[tuple[str, str, str, str]]:
        return [(card.title, card.value, card.detail, card.level) for card in self._dashboard_snapshot().cards]

    def _dashboard_card(self, parent: ctk.CTkFrame, row: int, column: int, title: str, value: str, detail: str, level: str) -> None:
        color = {
            "success": theme.SUCCESS,
            "warning": theme.WARNING,
            "error": theme.ERROR,
        }.get(level, theme.ACCENT_CYAN)
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        card.grid(row=row, column=column, sticky="nsew", padx=14, pady=8)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title.upper(), text_color=theme.TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")
        ctk.CTkLabel(card, text=value, text_color=color, font=ctk.CTkFont(size=22, weight="bold")).grid(row=1, column=0, padx=14, pady=2, sticky="w")
        ctk.CTkLabel(card, text=detail, text_color=theme.TEXT_MUTED, wraplength=380).grid(row=2, column=0, padx=14, pady=(2, 12), sticky="w")

    def _dashboard_snapshot(self) -> DashboardSnapshot:
        findings = self._refresh_diagnostic_findings()
        latest_session = self._latest_file(RUNTIME_ROOT / "reports", f"{SESSION_REPORT_PREFIX}-*.txt")
        latest_payload = self._latest_session_payload()
        latest_log = self._latest_file(RUNTIME_ROOT / "logs", "*.log")
        return build_dashboard_snapshot(
            is_admin=self.is_admin,
            winget_available=bool(shutil.which("winget")),
            selected_profile=self.wizard_state.selected_profile,
            selected_package_count=len(self.wizard_state.selected_package_ids),
            selected_tuning_count=len(self.wizard_state.selected_tuning_ids),
            installed_programs=self.wizard_state.installed_programs,
            available_updates=self.wizard_state.available_updates,
            maintenance_results=self.wizard_state.maintenance_results,
            tuning_results=self.wizard_state.tuning_results,
            scan_warnings=self.wizard_state.scan_warnings,
            diagnostic_findings=findings,
            guard_findings=self.wizard_state.guard_findings,
            latest_session_name=latest_session.name if latest_session else None,
            latest_log_name=latest_log.name if latest_log else None,
            latest_payload=latest_payload,
            app_settings=self.app_settings,
            imported_profile_name=self.wizard_state.imported_profile_name,
            imported_profile_path=self.wizard_state.imported_profile_path,
            exported_profile_path=self.wizard_state.exported_profile_path,
            auto_analysis=self.wizard_state.auto_analysis,
            offline_cache=self.wizard_state.offline_cache,
            recovery=self.wizard_state.recovery,
            risk_summary=self.wizard_state.risk_summary,
            daily_report=self.wizard_state.daily_report,
            devhub_config=self.wizard_state.devhub_config,
            system_info=self.wizard_state.system_info,
        )

    def _dashboard_recommendations(self) -> list[str]:
        return self._dashboard_snapshot().recommendations

    def _refresh_risk_summary(self) -> RiskSummary:
        findings = self._refresh_diagnostic_findings()
        summary = build_risk_summary(
            diagnostic_findings=findings,
            guard_findings=self.wizard_state.guard_findings,
            offline_cache=self.wizard_state.offline_cache,
            recovery=self.wizard_state.recovery,
            latest_payload=self._latest_session_payload(),
            scan_warnings=self.wizard_state.scan_warnings,
        )
        self.wizard_state.risk_summary = summary
        return summary

    def _refresh_daily_report_summary(self) -> DailyReportSummary:
        risk_summary = self._refresh_risk_summary()
        payloads, read_warnings = self._daily_session_payloads()
        summary = build_daily_report_summary(
            report_date=datetime.now().date().isoformat(),
            session_payloads=payloads,
            risk_summary=risk_summary,
            auto_analysis=self.wizard_state.auto_analysis,
            read_warnings=read_warnings,
        )
        self.wizard_state.daily_report = summary
        return summary

    def _dashboard_action(self, parent: ctk.CTkFrame, column: int, text: str, command, row: int = 0) -> None:
        ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=130,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=row, column=column, padx=(0, 8), pady=(0, 8), sticky="w")

    def _latest_file(self, directory: Path, pattern: str) -> Path | None:
        if not directory.exists():
            return None
        files = [path for path in directory.glob(pattern) if path.is_file()]
        if not files:
            return None
        return max(files, key=lambda path: path.stat().st_mtime)

    def _latest_session_payload(self) -> dict:
        latest_json = self._latest_file(RUNTIME_ROOT / "reports", f"{SESSION_REPORT_PREFIX}-*.json")
        if latest_json is None:
            return {}
        try:
            return json.loads(latest_json.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.warning(f"Session-Report konnte nicht gelesen werden: {exc}")
            return {}

    def _daily_session_payloads(self) -> tuple[list[dict], list[str]]:
        reports_dir = RUNTIME_ROOT / "reports"
        if not reports_dir.exists():
            return [], []
        today = datetime.now().date().isoformat()
        payloads: list[dict] = []
        warnings: list[str] = []
        for path in sorted(reports_dir.glob(f"{SESSION_REPORT_PREFIX}-*.json"), key=lambda item: item.stat().st_mtime):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                warnings.append(f"{path.name}: {exc}")
                continue
            started_at = str(payload.get("started_at") or payload.get("finished_at") or "")
            if started_at.startswith(today):
                payload["report_name"] = path.name
                payloads.append(payload)
        return payloads[-25:], warnings

    def _refresh_diagnostic_findings(self) -> list:
        log_dir = RUNTIME_ROOT / "logs"
        findings = []
        findings.extend(
            self.error_doctor.analyze_project_state(
                ROOT,
                is_admin=self.is_admin,
                winget_available=bool(shutil.which("winget")),
            )
        )
        findings.extend(self.error_doctor.analyze_runtime_logs(log_dir / "startup-error.log", log_dir / LOG_FILE_NAME))
        if self.wizard_state.scan_warnings:
            findings.extend(self.error_doctor.analyze_texts(self.wizard_state.scan_warnings))
        self.wizard_state.diagnostic_findings = findings
        return findings

    def _payload_failures(self, payload: dict) -> list[dict]:
        return payload_failures(payload)

    def _profile_filetypes(self) -> list[tuple[str, str]]:
        return [("DEVHub Profile", f"*{PROFILE_EXTENSION}"), ("JSON", "*.json"), ("Alle Dateien", "*.*")]

    def _current_guardforge_paths(self) -> list[str]:
        if self.wizard_state.guardforge_enabled_paths:
            return self.wizard_state.guardforge_enabled_paths
        return default_guard_profile(ROOT).protected_paths

    def _export_devhub_profile(self) -> None:
        profile = self.wizard_state.selected_profile
        profile_name = self.wizard_state.imported_profile_name or (profile.name if profile else "DEVHub Profil")
        path_value = filedialog.asksaveasfilename(
            title="DEVHub Profil exportieren",
            defaultextension=PROFILE_EXTENSION,
            filetypes=self._profile_filetypes(),
            initialfile="devhub-profile.devhub-profile.json",
        )
        if not path_value:
            return
        path = Path(path_value)
        if not path.name.endswith(PROFILE_EXTENSION):
            path = path.with_name(f"{path.name}{PROFILE_EXTENSION}")
        try:
            devhub_profile = build_profile(
                name=profile_name,
                description="Lokaler DEVHub TuningForge Export",
                selected_packages=self.wizard_state.selected_package_ids,
                selected_tuning_actions=self.wizard_state.selected_tuning_ids,
                guardforge_enabled_paths=self._current_guardforge_paths(),
            )
            write_profile(devhub_profile, path)
        except DevHubProfileError as exc:
            self.logger.error(f"Profil-Export abgelehnt: {exc}")
            messagebox.showerror("Profil exportieren", str(exc))
            return
        self.wizard_state.exported_profile_path = str(path)
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set(f"Profil exportiert: {path}")
        self.logger.success(f"Profil exportiert: {path}")
        messagebox.showinfo("Profil exportieren", f"Profil gespeichert:\n{path}")

    def _apply_imported_profile(self, path: Path, imported: ImportedProfile, show_dialog: bool) -> None:
        self.wizard_state.selected_package_ids = set(imported.selected_packages)
        self.wizard_state.selected_tuning_ids = set(imported.selected_tuning_actions)
        self.wizard_state.guardforge_enabled_paths = list(imported.guardforge_enabled_paths)
        self.wizard_state.imported_profile_name = imported.profile.name
        self.wizard_state.imported_profile_path = str(path)
        self.wizard_state.profile_import_warnings = list(imported.warnings)
        self.wizard_state.action_plan = None
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.profile_var.set("")
        self.package_vars.clear()
        self.tuning_vars.clear()
        self._save_last_imported_preset(path)

        summary = (
            f"Profil importiert: {imported.profile.name}. "
            f"{len(imported.selected_packages)} Pakete, "
            f"{len(imported.selected_tuning_actions)} Tuning-Aktionen."
        )
        self.last_status_var.set(summary)
        self.logger.info(summary)
        if not show_dialog:
            return
        if imported.warnings:
            for warning in imported.warnings:
                self.logger.warning(warning)
            messagebox.showwarning(
                "Profil importieren",
                summary + "\n\nWarnungen:\n" + "\n".join(f"- {warning}" for warning in imported.warnings),
            )
        else:
            messagebox.showinfo(
                "Profil importieren",
                summary + "\n\nKeine Aktion wurde gestartet. Bitte Vorschau pruefen und Start manuell bestaetigen.",
            )

    def _import_devhub_profile(self) -> None:
        path_value = filedialog.askopenfilename(
            title="DEVHub Profil importieren",
            filetypes=self._profile_filetypes(),
        )
        if not path_value:
            return
        path = Path(path_value)
        known_package_ids = {package.id for package in self.wizard_state.packages}
        known_tuning_ids = {action.id for action in self.wizard_state.tuning_actions}
        try:
            imported = read_profile(path, known_package_ids, known_tuning_ids)
        except DevHubProfileError as exc:
            self.logger.error(f"Profil-Import abgelehnt: {exc}")
            messagebox.showerror("Profil importieren", str(exc))
            return

        self._apply_imported_profile(path, imported, show_dialog=True)
        self._show_page(1)

    def _page_profiles(self) -> None:
        frame = self._scroll_panel("Profil waehlen")
        frame.grid(row=0, column=0, sticky="nsew")
        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkButton(
            actions,
            text="Profil importieren",
            command=self._import_devhub_profile,
            width=180,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")
        ctk.CTkButton(
            actions,
            text="Profil exportieren",
            command=self._export_devhub_profile,
            width=180,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).grid(row=0, column=1, sticky="w")
        if self.wizard_state.imported_profile_name:
            ctk.CTkLabel(
                frame,
                text=(
                    f"Import aktiv: {self.wizard_state.imported_profile_name}. "
                    "Auswahl wurde gesetzt; Vorschau und Start bleiben manuell."
                ),
                text_color=theme.ACCENT_CYAN,
                wraplength=820,
            ).pack(fill="x", padx=16, pady=(4, 8), anchor="w")
        if self.wizard_state.profile_import_warnings:
            warning_text = "\n".join(f"- {warning}" for warning in self.wizard_state.profile_import_warnings)
            ctk.CTkLabel(
                frame,
                text=f"Import-Warnungen:\n{warning_text}",
                text_color=theme.WARNING,
                justify="left",
                wraplength=820,
            ).pack(fill="x", padx=16, pady=(0, 10), anchor="w")
        for profile in self.wizard_state.profiles:
            button = ctk.CTkRadioButton(
                frame,
                text=f"{profile.name}\n{profile.description}",
                variable=self.profile_var,
                value=profile.id,
                command=self._apply_profile_selection,
                height=64,
                fg_color=theme.ACCENT_CYAN,
                hover_color=theme.PANEL_ALT,
                border_color=theme.BORDER,
                text_color=theme.TEXT,
            )
            button.pack(fill="x", padx=16, pady=10, anchor="w")

    def _page_packages(self) -> None:
        self._sync_package_vars()
        self.package_count_labels.clear()
        frame = self._scroll_panel("Programme waehlen")
        frame.grid(row=0, column=0, sticky="nsew")

        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.pack(fill="x", padx=14, pady=(14, 10))
        toolbar.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(
            toolbar,
            placeholder_text="Programme suchen: Name, Kategorie, Beschreibung oder Winget-ID",
            fg_color="#070a12",
            border_color=theme.BORDER,
            text_color=theme.TEXT,
        )
        if self.package_search_text:
            search.insert(0, self.package_search_text)
        search.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        search.bind("<Return>", lambda _event, widget=search: self._apply_package_search(widget.get()))
        ctk.CTkButton(
            toolbar,
            text="Suchen",
            command=lambda widget=search: self._apply_package_search(widget.get()),
            width=100,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            toolbar,
            text="Reset",
            command=self._clear_package_search,
            width=90,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2)

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 10))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions,
            text="Alle sichtbaren auswaehlen",
            command=self._select_visible_packages,
            width=190,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        ctk.CTkButton(
            actions,
            text="Sichtbare leeren",
            command=self._clear_visible_packages,
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2, sticky="e")

        packages = self._filtered_packages()
        if not packages:
            ctk.CTkLabel(
                frame,
                text="Keine Programme gefunden.",
                text_color=theme.WARNING,
            ).pack(padx=14, pady=18, anchor="w")
            return
        self._package_table(frame, packages)

    def _ordered_package_categories(self) -> list[str]:
        known = {package.category for package in self.wizard_state.packages}
        ordered = [category for category in PACKAGE_CATEGORY_ORDER if category in known]
        extra = sorted(known - set(ordered))
        return ordered + extra

    def _packages_in_category(self, category: str) -> list[Package]:
        return [package for package in self.wizard_state.packages if package.category == category]

    def _filtered_packages(self) -> list[Package]:
        query = self.package_search_text.strip().casefold()
        category_order = {category: index for index, category in enumerate(PACKAGE_CATEGORY_ORDER)}
        packages = [package for package in self.wizard_state.packages if self._package_matches(package, query)]
        return sorted(packages, key=lambda package: (category_order.get(package.category, 999), package.category, package.name))

    def _package_matches(self, package: Package, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join(
            [
                package.name,
                package.category,
                package.description,
                package.winget_id,
                " ".join(package.recommended_for),
            ]
        ).casefold()
        return query in haystack

    def _package_table(self, parent: ctk.CTkFrame, packages: list[Package]) -> None:
        table_frame = tk.Frame(parent, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.BORDER)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._configure_tree_style()

        columns = ("checked", "name", "category", "id", "badges")
        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=22,
        )
        tree.heading("checked", text="")
        tree.heading("name", text="Programm")
        tree.heading("category", text="Kategorie")
        tree.heading("id", text="Winget-ID")
        tree.heading("badges", text="Hinweise")
        tree.column("checked", width=44, minwidth=44, stretch=False, anchor="center")
        tree.column("name", width=230, minwidth=160, stretch=True)
        tree.column("category", width=150, minwidth=110, stretch=False)
        tree.column("id", width=230, minwidth=160, stretch=True)
        tree.column("badges", width=210, minwidth=140, stretch=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.package_row_ids.clear()
        for index, package in enumerate(packages):
            row_id = f"package_{index}"
            self.package_row_ids[row_id] = package.id
            tree.insert("", "end", iid=row_id, values=self._package_tree_values(package))
        tree.bind("<Button-1>", lambda event, widget=tree: self._toggle_package_tree_checkbox(event, widget))
        tree.bind("<space>", lambda event, widget=tree: self._toggle_focused_package_tree_checkbox(widget))
        self.package_tree = tree

    def _package_tree_values(self, package: Package) -> tuple[str, str, str, str, str]:
        checked = "[x]" if package.id in self.wizard_state.selected_package_ids else "[ ]"
        return (checked, package.name, package.category, package.winget_id, self._package_badges(package))

    def _toggle_package_tree_checkbox(self, event, tree: ttk.Treeview):
        if tree.identify_column(event.x) != "#1":
            return None
        row_id = tree.identify_row(event.y)
        if row_id:
            self._toggle_package_row(tree, row_id)
        return "break"

    def _toggle_focused_package_tree_checkbox(self, tree: ttk.Treeview):
        row_id = tree.focus()
        if row_id:
            self._toggle_package_row(tree, row_id)
        return "break"

    def _toggle_package_row(self, tree: ttk.Treeview, row_id: str) -> None:
        package_id = self.package_row_ids.get(row_id)
        if not package_id:
            return
        if package_id in self.wizard_state.selected_package_ids:
            self.wizard_state.selected_package_ids.remove(package_id)
        else:
            self.wizard_state.selected_package_ids.add(package_id)
        self._refresh_package_tree_row(tree, row_id)

    def _refresh_package_tree_row(self, tree: ttk.Treeview, row_id: str) -> None:
        package_id = self.package_row_ids.get(row_id)
        package = next((item for item in self.wizard_state.packages if item.id == package_id), None)
        if package is not None:
            tree.item(row_id, values=self._package_tree_values(package))

    def _package_category_section(
        self,
        parent: ctk.CTkFrame,
        category: str,
        packages: list[Package],
        row: int,
        column: int,
    ) -> None:
        selected = sum(1 for package in self._packages_in_category(category) if package.id in self.wizard_state.selected_package_ids)
        section = ctk.CTkFrame(parent, fg_color=theme.PANEL, border_color=theme.BORDER, border_width=1, corner_radius=8)
        section.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
        section.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(section, fg_color=theme.PANEL_ALT, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text=f"{category.upper()}  {selected}/{len(self._packages_in_category(category))}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
        self.package_count_labels[category] = header.winfo_children()[-1]
        ctk.CTkButton(
            header,
            text="Alle",
            command=lambda value=category: self._select_package_category(value),
            width=76,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=1, column=0, padx=(10, 6), pady=(0, 10), sticky="w")
        ctk.CTkButton(
            header,
            text="Leeren",
            command=lambda value=category: self._clear_package_category(value),
            width=86,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="w")

        if category == "Trading/Crypto":
            ctk.CTkLabel(
                section,
                text="Hinweis: Trading/Crypto-Tools nur bewusst installieren und Anbieter/Quelle vor dem Start pruefen.",
                text_color=theme.WARNING,
                wraplength=420,
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
            start_row = 2
        else:
            start_row = 1
        for index, package in enumerate(packages, start=start_row):
            self._package_card(section, package, index)

    def _package_card(self, parent: ctk.CTkFrame, package: Package, row: int) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=6)
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=3)
        card.grid_columnconfigure(1, weight=1)
        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            variable=self.package_vars[package.id],
            command=self._apply_package_selection,
            fg_color=theme.ACCENT_CYAN,
            hover_color=theme.ACCENT_PURPLE,
            border_color=theme.BORDER_ACTIVE,
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        ctk.CTkLabel(card, text=package.name, font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.TEXT).grid(
            row=0,
            column=1,
            sticky="w",
            padx=4,
            pady=(8, 0),
        )
        badge_text = self._package_badges(package)
        detail = f"{package.description} | {badge_text}"
        ctk.CTkLabel(card, text=detail, text_color=theme.WARNING if package.requires_admin else theme.TEXT_MUTED, wraplength=360).grid(
            row=1,
            column=1,
            sticky="w",
            padx=4,
            pady=(0, 8),
        )
        ctk.CTkLabel(card, text=package.winget_id, text_color=theme.ACCENT_MINT, wraplength=180).grid(
            row=0,
            column=2,
            rowspan=2,
            sticky="e",
            padx=12,
        )

    def _package_badges(self, package: Package) -> str:
        labels = [
            PACKAGE_RECOMMENDATION_LABELS.get(value, value)
            for value in package.recommended_for
        ]
        badges = [f"Empfohlen: {', '.join(labels)}"] if labels else []
        if package.requires_admin:
            badges.append("Admin")
        return " | ".join(badges) if badges else "Optional"

    def _select_package_category(self, category: str) -> None:
        for package in self._packages_in_category(category):
            self.wizard_state.selected_package_ids.add(package.id)
            if package.id in self.package_vars:
                self.package_vars[package.id].set(True)
        self._refresh_package_category_count(category)

    def _clear_package_category(self, category: str) -> None:
        for package in self._packages_in_category(category):
            self.wizard_state.selected_package_ids.discard(package.id)
            if package.id in self.package_vars:
                self.package_vars[package.id].set(False)
        self._refresh_package_category_count(category)

    def _select_visible_packages(self) -> None:
        visible = set(self.package_row_ids.values())
        self.wizard_state.selected_package_ids.update(visible)
        self._refresh_package_tree()

    def _clear_visible_packages(self) -> None:
        visible = set(self.package_row_ids.values())
        self.wizard_state.selected_package_ids.difference_update(visible)
        self._refresh_package_tree()

    def _refresh_package_tree(self) -> None:
        tree = getattr(self, "package_tree", None)
        if tree is None:
            return
        for row_id in self.package_row_ids:
            self._refresh_package_tree_row(tree, row_id)

    def _refresh_package_category_count(self, category: str) -> None:
        label = self.package_count_labels.get(category)
        if label is None:
            return
        total = len(self._packages_in_category(category))
        selected = sum(1 for package in self._packages_in_category(category) if package.id in self.wizard_state.selected_package_ids)
        label.configure(text=f"{category.upper()}  {selected}/{total}")

    def _clear_package_search(self) -> None:
        self.package_search_text = ""
        self._show_page(2)

    def _apply_package_search(self, value: str) -> None:
        self.package_search_text = value.strip()
        self._show_page(2)

    def _page_preview(self) -> None:
        profile = self.wizard_state.selected_profile
        if profile is None:
            self.logger.error("Vorschau ohne Profil blockiert.")
            messagebox.showerror("Profil fehlt", "Bitte waehle zuerst ein Profil.")
            self._show_page(1)
            return
        self.wizard_state.action_plan = build_action_plan(
            profile,
            self.wizard_state.packages,
            self.wizard_state.selected_package_ids,
        )
        plan = self.wizard_state.action_plan
        self.logger.info(f"Vorschau erstellt: {plan.package_count} Pakete fuer Profil {plan.profile.name}.")

        frame = self._scroll_panel("Vorschau")
        frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(
            frame,
            text=f"Profil: {plan.profile.name}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=14, pady=(14, 8), anchor="w")
        ctk.CTkLabel(
            frame,
            text=f"{plan.package_count} Programme werden installiert. Risiko: Niedrig.",
            text_color=theme.TEXT_MUTED,
        ).pack(padx=14, pady=(0, 14), anchor="w")
        ctk.CTkLabel(
            frame,
            text="Geplante Aktionen",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).pack(padx=14, pady=(10, 6), anchor="w")
        for action in plan.actions:
            ctk.CTkLabel(
                frame,
                text=f"- {action.package.name}: {' '.join(action.command)}",
                anchor="w",
                wraplength=760,
                text_color=theme.TEXT,
            ).pack(padx=24, pady=3, anchor="w")
        ctk.CTkLabel(
            frame,
            text="Ordner aus Profil",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.ACCENT_CYAN,
        ).pack(padx=14, pady=(18, 6), anchor="w")
        for folder in plan.folders:
            ctk.CTkLabel(frame, text=f"- {folder}", anchor="w", text_color=theme.TEXT).pack(
                padx=24,
                pady=3,
                anchor="w",
            )

    def _page_run(self) -> None:
        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text="Ausfuehrung",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, textvariable=self.elapsed_var, text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=2, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(frame, mode="indeterminate", progress_color=theme.ACCENT_CYAN)
        self.progress_bar.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.progress_bar.set(0)
        self.log_box = self._create_console(frame)
        self.log_box.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="nsew")
        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            controls,
            text="Console leeren",
            command=self._clear_console,
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 10), sticky="e")
        ctk.CTkButton(
            controls,
            text="Setup jetzt starten",
            command=self._start_run,
            width=170,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).grid(row=0, column=2, padx=(0, 10), sticky="e")
        ctk.CTkButton(
            controls,
            text="Abbrechen",
            command=self._cancel_run,
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.ERROR,
            border_width=1,
            text_color=theme.ERROR,
        ).grid(row=0, column=3, sticky="e")

    def _page_tuning(self) -> None:
        self._sync_tuning_vars()
        frame = self._scroll_panel("Leistungs-Tuning")
        frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(
            frame,
            text="DEVHub TuningForge",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=14, pady=(16, 4), anchor="w")
        ctk.CTkLabel(
            frame,
            text="Waehle die Tuning- und Repair-Aktionen aus. Jede Aktion wird einzeln geloggt.",
            text_color=theme.TEXT_MUTED,
        ).pack(padx=14, pady=(0, 16), anchor="w")

        known_categories = {action.category for action in self.wizard_state.tuning_actions}
        categories = [category for category in TUNING_CATEGORY_ORDER if category in known_categories]
        categories.extend(sorted(known_categories - set(categories)))
        for category in categories:
            ctk.CTkLabel(
                frame,
                text=category.upper(),
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=theme.ACCENT_CYAN,
            ).pack(padx=14, pady=(18, 6), anchor="w")
            for action in [a for a in self.wizard_state.tuning_actions if a.category == category]:
                card = ctk.CTkFrame(
                    frame,
                    fg_color=theme.CARD,
                    border_color=theme.BORDER,
                    border_width=1,
                    corner_radius=8,
                )
                card.pack(fill="x", padx=12, pady=6)
                card.grid_columnconfigure(1, weight=1)
                checkbox = ctk.CTkCheckBox(
                    card,
                    text="",
                    variable=self.tuning_vars[action.id],
                    command=self._apply_tuning_selection,
                    fg_color=theme.ACCENT_CYAN,
                    hover_color=theme.ACCENT_PURPLE,
                    border_color=theme.BORDER_ACTIVE,
                )
                checkbox.grid(row=0, column=0, rowspan=2, padx=14, pady=14)
                ctk.CTkLabel(
                    card,
                    text=action.name,
                    font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=theme.TEXT,
                ).grid(row=0, column=1, sticky="w", padx=4, pady=(12, 0))
                ctk.CTkLabel(card, text=action.description, text_color=theme.TEXT_MUTED, wraplength=620).grid(
                    row=1,
                    column=1,
                    sticky="w",
                    padx=4,
                    pady=(0, 12),
                )
                detail = f"Wirkung: {action.impact} | Dauer: {action.duration_hint}"
                if action.requires_reboot:
                    detail += " | Neustart empfohlen"
                ctk.CTkLabel(card, text=detail, text_color=theme.TEXT_MUTED, wraplength=620).grid(
                    row=2,
                    column=1,
                    sticky="w",
                    padx=4,
                    pady=(0, 12),
                )
                risk_color = theme.WARNING if action.risk == "mittel" else theme.SUCCESS
                ctk.CTkLabel(card, text=f"Risiko: {action.risk}", text_color=risk_color).grid(
                    row=0,
                    column=2,
                    rowspan=3,
                    sticky="e",
                    padx=14,
                )

    def _page_tuning_run(self) -> None:
        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text="Tuning-Ausfuehrung",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, textvariable=self.elapsed_var, text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=2, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(frame, mode="indeterminate", progress_color=theme.ACCENT_CYAN)
        self.progress_bar.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.progress_bar.set(0)
        selected_actions = self.wizard_state.selected_tuning_actions
        preview = ctk.CTkFrame(frame, fg_color=theme.PANEL, border_color=theme.BORDER, border_width=1, corner_radius=8)
        preview.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="new")
        ctk.CTkLabel(
            preview,
            text="Vorschau vor Start",
            text_color=theme.ACCENT_CYAN,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(padx=12, pady=(10, 4), anchor="w")
        for action in selected_actions[:6]:
            reboot = " | Neustart empfohlen" if action.requires_reboot else ""
            ctk.CTkLabel(
                preview,
                text=f"- {action.name}: {' '.join(action.command)} | Risiko: {action.risk}{reboot}",
                text_color=theme.TEXT_MUTED,
                wraplength=850,
            ).pack(padx=12, pady=2, anchor="w")
        if len(selected_actions) > 6:
            ctk.CTkLabel(
                preview,
                text=f"... plus {len(selected_actions) - 6} weitere Aktionen",
                text_color=theme.TEXT_MUTED,
            ).pack(padx=12, pady=(2, 10), anchor="w")
        self.log_box = self._create_console(frame)
        self.log_box.grid(row=3, column=0, padx=18, pady=(0, 12), sticky="nsew")
        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=4, column=0, padx=18, pady=(0, 18), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            controls,
            text="Console leeren",
            command=self._clear_console,
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            controls,
            text="Tuning jetzt starten",
            command=self._start_tuning_run,
            width=170,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).grid(row=0, column=2, padx=(10, 0), sticky="e")

    def _page_uninstall(self) -> None:
        self._sync_uninstall_vars()
        frame = self._scroll_panel("Uninstall")
        frame.grid(row=0, column=0, sticky="nsew")
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Programme deinstallieren",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Programme suchen",
            command=self._scan_installed_programs,
            width=160,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))
        ctk.CTkLabel(
            frame,
            text="Risiko: Hoch. Geraete-Scan ohne user-Einschraenkung. Vor dem Deinstallieren gibt es Vorschau und zweite Bestaetigung.",
            text_color=theme.WARNING,
            wraplength=780,
        ).pack(padx=14, pady=(0, 12), anchor="w")
        self._scan_status_panel(frame)

        if not self.wizard_state.installed_programs:
            empty_text = "Scan abgeschlossen: keine Programme gefunden." if "abgeschlossen" in self.scan_status_var.get() else "Noch keine Programme gescannt."
            ctk.CTkLabel(frame, text=empty_text, text_color=theme.WARNING).pack(padx=14, pady=12, anchor="w")
            return
        self._selection_buttons(frame, self._select_all_uninstall, self._clear_uninstall_selection)
        self._program_table(frame)

    def _page_uninstall_preview(self) -> None:
        frame = self._scroll_panel("Uninstall Vorschau")
        frame.grid(row=0, column=0, sticky="nsew")
        programs = self.wizard_state.selected_uninstall_programs
        ctk.CTkLabel(frame, text=f"{len(programs)} Programme werden deinstalliert.", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT).pack(padx=14, pady=(16, 10), anchor="w")
        for program in programs:
            from core.maintenance import build_uninstall_command

            ctk.CTkLabel(
                frame,
                text=f"- {program.name}: {' '.join(build_uninstall_command(program, self.wizard_state.uninstall_scope))}",
                text_color=theme.TEXT,
                wraplength=780,
            ).pack(padx=24, pady=4, anchor="w")

    def _page_uninstall_run(self) -> None:
        frame = self._run_panel("Uninstall-Ausfuehrung")
        frame.grid(row=0, column=0, sticky="nsew")
        self._run_start_button(frame, "Uninstall jetzt starten", self._start_uninstall_run)

    def _page_updates(self) -> None:
        self._sync_update_vars()
        frame = self._scroll_panel("Updates")
        frame.grid(row=0, column=0, sticky="nsew")
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Updates suchen",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Updates suchen",
            command=self._scan_updates,
            width=160,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
        ).grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            frame,
            text="Risiko: Mittel. Geraete-Scan ohne user-Einschraenkung. Updates werden erst nach Vorschau ausgefuehrt.",
            text_color=theme.WARNING,
            wraplength=780,
        ).pack(padx=14, pady=(0, 12), anchor="w")
        self._scan_status_panel(frame)
        if not self.wizard_state.available_updates:
            empty_text = "Scan abgeschlossen: keine Updates gefunden." if "abgeschlossen" in self.scan_status_var.get() else "Noch keine Updates gescannt."
            ctk.CTkLabel(frame, text=empty_text, text_color=theme.WARNING).pack(padx=14, pady=12, anchor="w")
            return
        self._selection_buttons(frame, self._select_all_updates, self._clear_update_selection)
        self._update_table(frame)

    def _page_updates_preview(self) -> None:
        frame = self._scroll_panel("Update Vorschau")
        frame.grid(row=0, column=0, sticky="nsew")
        updates = self.wizard_state.selected_updates
        ctk.CTkLabel(frame, text=f"{len(updates)} Updates werden installiert.", font=ctk.CTkFont(size=20, weight="bold"), text_color=theme.TEXT).pack(padx=14, pady=(16, 10), anchor="w")
        from core.maintenance import build_upgrade_command

        for update in updates:
            ctk.CTkLabel(
                frame,
                text=f"- {update.name}: {' '.join(build_upgrade_command(update, self.wizard_state.update_scope))}",
                text_color=theme.TEXT,
                wraplength=780,
            ).pack(padx=24, pady=4, anchor="w")

    def _page_updates_run(self) -> None:
        frame = self._run_panel("Update-Ausfuehrung")
        frame.grid(row=0, column=0, sticky="nsew")
        self._run_start_button(frame, "Updates jetzt starten", self._start_update_run)

    def _page_diagnostics(self) -> None:
        frame = self._scroll_panel("Diagnose")
        frame.grid(row=0, column=0, sticky="nsew")
        findings = self._refresh_diagnostic_findings()
        ctk.CTkLabel(
            frame,
            text="ErrorDoctor",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=18, pady=(18, 6), anchor="w")
        ctk.CTkLabel(
            frame,
            text="Lokale Diagnose aus App-Status, Logs und Scan-Hinweisen. Historische Findings werden getrennt markiert. Es werden keine Auto-Fixes ausgefuehrt.",
            text_color=theme.TEXT_MUTED,
            wraplength=820,
        ).pack(padx=18, pady=(0, 16), anchor="w")
        if not findings:
            ctk.CTkLabel(
                frame,
                text="Keine bekannten Probleme erkannt.",
                text_color=theme.SUCCESS,
            ).pack(padx=18, pady=8, anchor="w")
            return
        for finding in findings:
            is_historical = finding.status != "active"
            color = theme.TEXT_MUTED if is_historical else theme.ERROR if finding.severity == "error" else theme.WARNING
            card = ctk.CTkFrame(frame, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
            card.pack(fill="x", padx=14, pady=8)
            ctk.CTkLabel(
                card,
                text=f"{finding.problem} ({finding.severity}, {finding.status})",
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color=color,
            ).pack(padx=14, pady=(12, 4), anchor="w")
            if is_historical:
                ctk.CTkLabel(
                    card,
                    text="Historisch: Die App wurde nach diesem Fund wieder erfolgreich gestartet.",
                    text_color=theme.SUCCESS,
                    wraplength=790,
                ).pack(padx=14, pady=3, anchor="w")
            ctk.CTkLabel(card, text=f"Ursache: {finding.likely_cause}", text_color=theme.TEXT, wraplength=790).pack(padx=14, pady=3, anchor="w")
            ctk.CTkLabel(card, text=f"Empfehlung: {finding.recommended_fix}", text_color=theme.ACCENT_CYAN, wraplength=790).pack(padx=14, pady=3, anchor="w")
            if finding.source_timestamp or finding.last_success_timestamp:
                ctk.CTkLabel(
                    card,
                    text=f"Quelle: {finding.source} | Fund: {finding.source_timestamp or 'n/a'} | Letzter erfolgreicher Start: {finding.last_success_timestamp or 'n/a'}",
                    text_color=theme.TEXT_MUTED,
                    wraplength=790,
                ).pack(padx=14, pady=3, anchor="w")
            if finding.evidence:
                ctk.CTkLabel(card, text=f"Beleg: {finding.evidence}", text_color=theme.TEXT_MUTED, wraplength=790).pack(padx=14, pady=(3, 12), anchor="w")

    def _page_guardforge(self) -> None:
        frame = self._scroll_panel("GuardForge Alpha")
        frame.grid(row=0, column=0, sticky="nsew")
        protected_paths = self._current_guardforge_paths()
        ctk.CTkLabel(
            frame,
            text="GuardForge Alpha",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=18, pady=(18, 6), anchor="w")
        ctk.CTkLabel(
            frame,
            text="Preview fuer lokale Datei-Events und Risiko-Muster. Keine permanente Ueberwachung, kein Autostart, kein Blockieren, kein Loeschen, kein Netzwerk.",
            text_color=theme.WARNING,
            wraplength=840,
        ).pack(padx=18, pady=(0, 16), anchor="w")
        ctk.CTkLabel(frame, text="Schutzbereiche:", text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=18,
            pady=(4, 6),
            anchor="w",
        )
        for path in protected_paths:
            ctk.CTkLabel(frame, text=f"- {path}", text_color=theme.TEXT_MUTED, wraplength=820).pack(padx=28, pady=2, anchor="w")
        ctk.CTkButton(
            frame,
            text="Mock-Preview auswerten",
            command=self._run_guardforge_preview,
            width=210,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).pack(padx=18, pady=(18, 12), anchor="w")
        if not self.wizard_state.guard_events:
            ctk.CTkLabel(
                frame,
                text="Noch keine Preview ausgefuehrt. Der Button nutzt nur Mock-Daten.",
                text_color=theme.TEXT_MUTED,
            ).pack(padx=18, pady=8, anchor="w")
            return
        ctk.CTkLabel(frame, text="Preview-Events:", text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=18, pady=(10, 4), anchor="w")
        for event in self.wizard_state.guard_events:
            ctk.CTkLabel(
                frame,
                text=f"- {event.event_type}: {event.path} ({event.process_name or 'unknown'})",
                text_color=theme.TEXT,
                wraplength=820,
            ).pack(padx=28, pady=2, anchor="w")
        ctk.CTkLabel(frame, text="Risk-Findings:", text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=18, pady=(14, 4), anchor="w")
        for finding in self.wizard_state.guard_findings:
            color = theme.WARNING if finding.risk_level == "mittel" else theme.SUCCESS
            ctk.CTkLabel(
                frame,
                text=f"- {finding.reason} Risiko: {finding.risk_level}. Empfehlung: {finding.recommendation}",
                text_color=color,
                wraplength=820,
            ).pack(padx=28, pady=3, anchor="w")

    def _page_offline_cache(self) -> None:
        frame = self._scroll_panel("Offline Cache")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        if self.wizard_state.offline_cache is None:
            self._inspect_offline_cache(silent=True)
        summary = self.wizard_state.offline_cache
        ctk.CTkLabel(
            frame,
            text="Offline Cache",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Preview fuer lokale Installer-Dateien. Kein Download, keine Installation, kein Loeschen.",
            text_color=theme.WARNING,
            wraplength=840,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
        cache_root_text = str(CACHE_ROOT)
        ctk.CTkLabel(
            frame,
            text=f"Cache-Ordner: {cache_root_text}",
            text_color=theme.TEXT_MUTED,
            wraplength=860,
        ).grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Cache pruefen",
            command=lambda: self._refresh_offline_cache_page(index_existing=False),
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Index aktualisieren",
            command=lambda: self._refresh_offline_cache_page(index_existing=True),
            width=170,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Ordnerpfad anzeigen",
            command=self._show_offline_cache_path,
            width=170,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("status", "file", "size", "sha256", "note"),
            show="tree headings",
            height=12,
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Paket")
        tree.heading("status", text="Status")
        tree.heading("file", text="Datei")
        tree.heading("size", text="Groesse")
        tree.heading("sha256", text="SHA256")
        tree.heading("note", text="Hinweis")
        tree.column("#0", width=160, minwidth=120, stretch=False)
        tree.column("status", width=90, minwidth=80, stretch=False)
        tree.column("file", width=190, minwidth=140, stretch=False)
        tree.column("size", width=90, minwidth=75, stretch=False)
        tree.column("sha256", width=210, minwidth=120, stretch=False)
        tree.column("note", width=260, minwidth=160, stretch=True)
        if summary:
            for entry in summary.entries:
                tree.insert(
                    "",
                    "end",
                    text=entry.name,
                    values=(
                        entry.status,
                        entry.file_path,
                        self._format_bytes(entry.size_bytes),
                        entry.sha256[:16] + "..." if entry.sha256 else "",
                        entry.note,
                    ),
                    tags=(entry.status,),
                )
        tree.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))

        if summary is None or not summary.entries:
            ctk.CTkLabel(
                frame,
                text="Noch keine Cache-Eintraege. Lege Installer manuell in den Cache-Ordner und nutze danach 'Index aktualisieren'.",
                text_color=theme.TEXT_MUTED,
                wraplength=840,
            ).grid(row=5, column=0, padx=18, pady=(0, 12), sticky="w")
        elif summary.warnings:
            ctk.CTkLabel(
                frame,
                text="Warnungen:\n" + "\n".join(f"- {warning}" for warning in summary.warnings),
                text_color=theme.WARNING,
                justify="left",
                wraplength=840,
            ).grid(row=5, column=0, padx=18, pady=(0, 12), sticky="w")

    def _inspect_offline_cache(self, silent: bool = False) -> CacheSummary | None:
        try:
            summary = inspect_cache(CACHE_ROOT)
        except OfflineCacheError as exc:
            if not silent:
                messagebox.showerror("Offline Cache", str(exc))
            self.logger.warning(f"Offline Cache konnte nicht gelesen werden: {exc}")
            return None
        self.wizard_state.offline_cache = summary
        return summary

    def _refresh_offline_cache_page(self, index_existing: bool) -> None:
        try:
            summary = index_existing_installers(CACHE_ROOT) if index_existing else inspect_cache(CACHE_ROOT)
        except OfflineCacheError as exc:
            messagebox.showerror("Offline Cache", str(exc))
            self.logger.warning(f"Offline Cache fehlgeschlagen: {exc}")
            return
        self.wizard_state.offline_cache = summary
        self._refresh_risk_summary()
        self._refresh_daily_report_summary()
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set(f"Offline Cache: {summary.present_count}/{summary.planned_count} vorhanden")
        self.logger.info(f"Offline Cache geprueft: {summary.present_count}/{summary.planned_count} vorhanden.")
        self._show_page(16)

    def _show_offline_cache_path(self) -> None:
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        messagebox.showinfo("Offline Cache", f"Cache-Ordner:\n{CACHE_ROOT}\n\nIndex:\n{CACHE_INDEX_PATH}")

    def _format_bytes(self, value: int) -> str:
        if value <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB"]
        size = float(value)
        unit = 0
        while size >= 1024 and unit < len(units) - 1:
            size /= 1024
            unit += 1
        return f"{size:.1f} {units[unit]}" if unit else f"{int(size)} {units[unit]}"

    def _page_recoveryforge(self) -> None:
        frame = self._scroll_panel("RecoveryForge Alpha")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        if self.wizard_state.recovery is None:
            self._inspect_recoveryforge(silent=True)
        summary = self.wizard_state.recovery
        ctk.CTkLabel(
            frame,
            text="RecoveryForge Alpha",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Preview fuer lokale Recovery-Ziele. Kein Backup, kein Restore, kein Kopieren, kein Loeschen.",
            text_color=theme.WARNING,
            wraplength=840,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
        ctk.CTkLabel(
            frame,
            text=f"Recovery-Root: {RECOVERY_ROOT}",
            text_color=theme.TEXT_MUTED,
            wraplength=860,
        ).grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Preview aktualisieren",
            command=lambda: self._refresh_recoveryforge_page(),
            width=180,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Recovery-Pfad anzeigen",
            command=self._show_recoveryforge_path,
            width=190,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("status", "kind", "required", "size", "path", "note"),
            show="tree headings",
            height=12,
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Ziel")
        tree.heading("status", text="Status")
        tree.heading("kind", text="Typ")
        tree.heading("required", text="Pflicht")
        tree.heading("size", text="Groesse")
        tree.heading("path", text="Pfad")
        tree.heading("note", text="Hinweis")
        tree.column("#0", width=150, minwidth=120, stretch=False)
        tree.column("status", width=90, minwidth=80, stretch=False)
        tree.column("kind", width=80, minwidth=70, stretch=False)
        tree.column("required", width=70, minwidth=60, stretch=False)
        tree.column("size", width=90, minwidth=75, stretch=False)
        tree.column("path", width=300, minwidth=170, stretch=False)
        tree.column("note", width=250, minwidth=160, stretch=True)
        if summary:
            for target in summary.targets:
                tree.insert(
                    "",
                    "end",
                    text=target.name,
                    values=(
                        target.status,
                        target.kind,
                        "ja" if target.required else "nein",
                        self._format_bytes(target.size_bytes),
                        target.path,
                        target.note,
                    ),
                    tags=(target.status,),
                )
        tree.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))

        if summary and summary.warnings:
            ctk.CTkLabel(
                frame,
                text="Warnungen:\n" + "\n".join(f"- {warning}" for warning in summary.warnings),
                text_color=theme.WARNING,
                justify="left",
                wraplength=840,
            ).grid(row=5, column=0, padx=18, pady=(0, 12), sticky="w")

    def _inspect_recoveryforge(self, silent: bool = False) -> RecoverySummary | None:
        try:
            summary = inspect_recovery_targets(RUNTIME_ROOT)
        except Exception as exc:
            if not silent:
                messagebox.showerror("RecoveryForge", str(exc))
            self.logger.warning(f"RecoveryForge Preview fehlgeschlagen: {exc}")
            return None
        self.wizard_state.recovery = summary
        return summary

    def _refresh_recoveryforge_page(self) -> None:
        summary = self._inspect_recoveryforge(silent=False)
        if summary is None:
            return
        self._refresh_risk_summary()
        self._refresh_daily_report_summary()
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set(f"RecoveryForge: {summary.present_count}/{summary.planned_count} Ziele vorhanden")
        self.logger.info(f"RecoveryForge Preview geprueft: {summary.present_count}/{summary.planned_count} Ziele vorhanden.")
        self._show_page(17)

    def _show_recoveryforge_path(self) -> None:
        messagebox.showinfo("RecoveryForge", f"Recovery-Root:\n{RECOVERY_ROOT}\n\nIn v0.6.0 wird hier nichts automatisch kopiert.")

    def _page_risk_engine(self) -> None:
        frame = self._scroll_panel("Risk Engine")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        if self.wizard_state.risk_summary is None:
            self._refresh_risk_summary()
        summary = self.wizard_state.risk_summary
        ctk.CTkLabel(
            frame,
            text="Risk Engine Preview",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Zentrale Read-only Bewertung aus Diagnose, GuardForge, Offline Cache, RecoveryForge und Reports. Keine Aktionen, keine Auto-Fixes.",
            text_color=theme.WARNING,
            wraplength=860,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Risk neu bewerten",
            command=self._refresh_risk_engine_page,
            width=180,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="ControlDeck",
            command=lambda: self._show_page(0),
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")

        if summary:
            color = self._risk_color(summary.overall_risk)
            ctk.CTkLabel(
                frame,
                text=(
                    f"Gesamtrisiko: {summary.overall_risk} | Score: {summary.score} | "
                    f"Hoch/Mittel/Niedrig: {summary.high_count}/{summary.medium_count}/{summary.low_count}"
                ),
                text_color=color,
                font=ctk.CTkFont(size=15, weight="bold"),
                wraplength=860,
            ).grid(row=3, column=0, padx=18, pady=(0, 12), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("risk", "source", "detail", "recommendation"),
            show="tree headings",
            height=12,
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Finding")
        tree.heading("risk", text="Risiko")
        tree.heading("source", text="Quelle")
        tree.heading("detail", text="Detail")
        tree.heading("recommendation", text="Empfehlung")
        tree.column("#0", width=220, minwidth=150, stretch=False)
        tree.column("risk", width=80, minwidth=70, stretch=False)
        tree.column("source", width=120, minwidth=90, stretch=False)
        tree.column("detail", width=250, minwidth=160, stretch=False)
        tree.column("recommendation", width=330, minwidth=200, stretch=True)
        if summary:
            for finding in summary.findings:
                tree.insert(
                    "",
                    "end",
                    text=finding.title,
                    values=(finding.risk_level, finding.source, finding.detail, finding.recommendation),
                    tags=(self._risk_tag(finding.risk_level),),
                )
        tree.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))
        if summary and not summary.findings:
            ctk.CTkLabel(
                frame,
                text="Keine Risk-Findings aus den vorhandenen lokalen Daten.",
                text_color=theme.SUCCESS,
                wraplength=840,
            ).grid(row=5, column=0, padx=18, pady=(0, 12), sticky="w")

    def _refresh_risk_engine_page(self) -> None:
        summary = self._refresh_risk_summary()
        self._refresh_daily_report_summary()
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set(f"Risk Engine: {summary.overall_risk} (Score {summary.score})")
        self.logger.info(f"Risk Engine read-only bewertet: {summary.overall_risk}, Score {summary.score}.")
        self._show_page(18)

    def _risk_tag(self, risk_level: str) -> str:
        if risk_level == RISK_HIGH:
            return "error"
        if risk_level == RISK_MEDIUM:
            return "warning"
        return "success"

    def _risk_color(self, risk_level: str) -> str:
        if risk_level == RISK_HIGH:
            return theme.ERROR
        if risk_level == RISK_MEDIUM:
            return theme.WARNING
        return theme.SUCCESS

    def _page_daily_report(self) -> None:
        frame = self._scroll_panel("Tagesbericht")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        if self.wizard_state.daily_report is None:
            self._refresh_daily_report_summary()
        summary = self.wizard_state.daily_report
        ctk.CTkLabel(
            frame,
            text="Tagesbericht Preview",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Lokale Tageszusammenfassung aus Session-Reports und Risk Engine. Keine Benachrichtigungen, kein Scheduler, keine Aktionen.",
            text_color=theme.WARNING,
            wraplength=860,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Tagesbericht aktualisieren",
            command=self._refresh_daily_report_page,
            width=210,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Reportpfad anzeigen",
            command=self._show_daily_report_path,
            width=180,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")

        if summary:
            ctk.CTkLabel(
                frame,
                text=(
                    f"Datum: {summary.report_date} | Aktionen: {summary.actions_total} | "
                    f"Fehler: {summary.failures_total} | Hinweise: {summary.alert_count} | "
                    f"Kritisch/Warnung: {summary.critical_count}/{summary.warning_count}"
                ),
                text_color=self._daily_report_color(summary),
                font=ctk.CTkFont(size=15, weight="bold"),
                wraplength=860,
            ).grid(row=3, column=0, padx=18, pady=(0, 12), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("level", "source", "detail", "recommendation"),
            show="tree headings",
            height=12,
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Hinweis")
        tree.heading("level", text="Level")
        tree.heading("source", text="Quelle")
        tree.heading("detail", text="Detail")
        tree.heading("recommendation", text="Empfehlung")
        tree.column("#0", width=220, minwidth=150, stretch=False)
        tree.column("level", width=90, minwidth=70, stretch=False)
        tree.column("source", width=120, minwidth=90, stretch=False)
        tree.column("detail", width=270, minwidth=170, stretch=False)
        tree.column("recommendation", width=330, minwidth=200, stretch=True)
        if summary:
            for alert in summary.alerts:
                tree.insert(
                    "",
                    "end",
                    text=alert.title,
                    values=(alert.level, alert.source, alert.detail, alert.recommendation),
                    tags=(self._daily_alert_tag(alert.level),),
                )
        tree.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))

        if summary:
            text = "Empfehlungen:\n" + "\n".join(f"- {item}" for item in summary.recommendations)
            ctk.CTkLabel(
                frame,
                text=text,
                text_color=theme.TEXT_MUTED if summary.alert_count == 0 else theme.WARNING,
                justify="left",
                wraplength=840,
            ).grid(row=5, column=0, padx=18, pady=(0, 12), sticky="w")

    def _refresh_daily_report_page(self) -> None:
        summary = self._refresh_daily_report_summary()
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set(f"Tagesbericht: {summary.alert_count} Hinweise, {summary.failures_total} Fehler")
        self.logger.info(f"Tagesbericht Preview aktualisiert: {summary.alert_count} Hinweise.")
        self._show_page(19)

    def _show_daily_report_path(self) -> None:
        messagebox.showinfo("Tagesbericht", f"Report-Ordner:\n{RUNTIME_ROOT / 'reports'}\n\nIn v0.8.0 wird kein Tagesbericht automatisch geschrieben.")

    def _daily_alert_tag(self, level: str) -> str:
        if level == ALERT_CRITICAL:
            return "error"
        if level == ALERT_WARNING:
            return "warning"
        return "info"

    def _daily_report_color(self, summary: DailyReportSummary) -> str:
        if summary.critical_count:
            return theme.ERROR
        if summary.warning_count:
            return theme.WARNING
        return theme.SUCCESS

    def _config_filetypes(self) -> list[tuple[str, str]]:
        return [("DEVHub Konfiguration", f"*{CONFIG_EXTENSION}"), ("JSON", "*.json"), ("Alle Dateien", "*.*")]

    def _sync_config_vars(self) -> None:
        config = self.wizard_state.devhub_config
        self.config_dry_run_var.set(config.dry_run_enabled)
        self.config_auto_analysis_var.set(config.auto_analysis_enabled)
        self.config_remember_preset_var.set(config.remember_last_preset)
        self.config_report_mode_var.set(config.default_report_mode)
        for module_id in DEFAULT_ENABLED_MODULES:
            if module_id not in self.config_module_vars:
                self.config_module_vars[module_id] = ctk.BooleanVar(value=module_id in config.enabled_modules)
            self.config_module_vars[module_id].set(module_id in config.enabled_modules)

    def _current_config_from_vars(self) -> DevHubConfig:
        enabled_modules = [
            module_id
            for module_id in DEFAULT_ENABLED_MODULES
            if self.config_module_vars.get(module_id) is None or self.config_module_vars[module_id].get()
        ]
        return DevHubConfig(
            dry_run_enabled=bool(self.config_dry_run_var.get()),
            auto_analysis_enabled=bool(self.config_auto_analysis_var.get()),
            remember_last_preset=bool(self.config_remember_preset_var.get()),
            default_report_mode=self.config_report_mode_var.get(),
            enabled_modules=enabled_modules,
        )

    def _page_configuration(self) -> None:
        frame = self._scroll_panel("Konfiguration")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        self._sync_config_vars()
        config = self.wizard_state.devhub_config
        ctk.CTkLabel(
            frame,
            text="Konfiguration / Testmodus",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Lokale DEVHub-Einstellungen. Import/Export setzt nur Konfiguration und startet keine Aktionen.",
            text_color=theme.WARNING,
            wraplength=860,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
        ctk.CTkLabel(
            frame,
            text=f"Config-Datei: {self.devhub_config_path}",
            text_color=theme.TEXT_MUTED,
            wraplength=860,
        ).grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        controls = ctk.CTkFrame(frame, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        controls.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        controls.grid_columnconfigure(1, weight=1)
        ctk.CTkCheckBox(controls, text="Testmodus / Dry-Run markieren", variable=self.config_dry_run_var).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")
        ctk.CTkCheckBox(controls, text="Auto-Analyse beim Start", variable=self.config_auto_analysis_var).grid(row=1, column=0, padx=14, pady=8, sticky="w")
        ctk.CTkCheckBox(controls, text="Letztes Preset merken", variable=self.config_remember_preset_var).grid(row=2, column=0, padx=14, pady=8, sticky="w")
        ctk.CTkLabel(controls, text="Reportmodus", text_color=theme.TEXT_MUTED).grid(row=3, column=0, padx=14, pady=(8, 14), sticky="w")
        ctk.CTkOptionMenu(
            controls,
            values=["session", "verbose"],
            variable=self.config_report_mode_var,
            fg_color=theme.SECONDARY_BUTTON,
            button_color=theme.PRIMARY_BUTTON,
            button_hover_color=theme.PRIMARY_BUTTON_HOVER,
        ).grid(row=3, column=1, padx=14, pady=(8, 14), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Konfiguration speichern",
            command=self._save_devhub_config,
            width=190,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Konfiguration importieren",
            command=self._import_devhub_config,
            width=210,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Konfiguration exportieren",
            command=self._export_devhub_config,
            width=210,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("enabled", "detail"),
            show="tree headings",
            height=len(DEFAULT_ENABLED_MODULES),
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Modul")
        tree.heading("enabled", text="Aktiv")
        tree.heading("detail", text="Hinweis")
        tree.column("#0", width=190, minwidth=130, stretch=False)
        tree.column("enabled", width=90, minwidth=70, stretch=False)
        tree.column("detail", width=650, minwidth=260, stretch=True)
        for module_id in DEFAULT_ENABLED_MODULES:
            enabled = module_id in config.enabled_modules
            tree.insert(
                "",
                "end",
                text=module_id,
                values=("ja" if enabled else "nein", "Preview-Konfiguration; deaktiviert keine Core-Safety-Gates."),
                tags=("success" if enabled else "info",),
            )
        tree.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 12))

    def _save_devhub_config(self) -> None:
        config = self._current_config_from_vars()
        save_config(self.devhub_config_path, config)
        self.wizard_state.devhub_config = config
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set("Konfiguration gespeichert")
        self.logger.success(f"Konfiguration gespeichert: {self.devhub_config_path}")
        self._show_page(20)

    def _import_devhub_config(self) -> None:
        path_value = filedialog.askopenfilename(
            title="DEVHub Konfiguration importieren",
            filetypes=self._config_filetypes(),
        )
        if not path_value:
            return
        try:
            config = read_config(Path(path_value))
        except DevHubConfigError as exc:
            self.logger.error(f"Konfigurationsimport abgelehnt: {exc}")
            messagebox.showerror("Konfiguration importieren", str(exc))
            return
        save_config(self.devhub_config_path, config)
        self.wizard_state.devhub_config = config
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set("Konfiguration importiert")
        self.logger.info(f"Konfiguration importiert: {path_value}")
        messagebox.showinfo("Konfiguration importieren", "Konfiguration importiert. Keine Aktion wurde gestartet.")
        self._show_page(20)

    def _export_devhub_config(self) -> None:
        path_value = filedialog.asksaveasfilename(
            title="DEVHub Konfiguration exportieren",
            defaultextension=CONFIG_EXTENSION,
            filetypes=self._config_filetypes(),
            initialfile="devhub-config.devhub-config.json",
        )
        if not path_value:
            return
        try:
            path = write_config(self._current_config_from_vars(), Path(path_value))
        except DevHubConfigError as exc:
            self.logger.error(f"Konfigurationsexport abgelehnt: {exc}")
            messagebox.showerror("Konfiguration exportieren", str(exc))
            return
        self.last_status_var.set(f"Konfiguration exportiert: {path}")
        self.logger.success(f"Konfiguration exportiert: {path}")
        messagebox.showinfo("Konfiguration exportieren", f"Konfiguration gespeichert:\n{path}")

    def _page_system_info(self) -> None:
        frame = self._scroll_panel("SystemInfo")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        result = self.wizard_state.system_info
        ctk.CTkLabel(
            frame,
            text="SystemInfo / MSINFO32 Export",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        ctk.CTkLabel(
            frame,
            text="Lokaler TXT-Export fuer spaetere Codex-/Agent-Auswertung. Kein Auto-Start, keine Cloud, keine automatische Analyse.",
            text_color=theme.WARNING,
            wraplength=860,
        ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
        ctk.CTkLabel(
            frame,
            text=f"Export-Ordner: {SYSTEM_INFO_ROOT}",
            text_color=theme.TEXT_MUTED,
            wraplength=860,
        ).grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        ctk.CTkButton(
            actions,
            text="Export vorbereiten",
            command=self._prepare_system_info_export,
            width=170,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="MSINFO32 TXT exportieren",
            command=self._start_system_info_export,
            width=210,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            actions,
            text="Ordnerpfad anzeigen",
            command=self._show_system_info_path,
            width=180,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")

        tree = ttk.Treeview(
            frame,
            columns=("value",),
            show="tree headings",
            height=8,
            style=TREE_STYLE,
            selectmode="browse",
        )
        tree.heading("#0", text="Feld")
        tree.heading("value", text="Wert")
        tree.column("#0", width=180, minwidth=130, stretch=False)
        tree.column("value", width=720, minwidth=260, stretch=True)
        rows = self._system_info_rows(result)
        for label, value, tag in rows:
            tree.insert("", "end", text=label, values=(value,), tags=(tag,))
        tree.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))

    def _system_info_rows(self, result: SystemInfoExportResult | None) -> list[tuple[str, str, str]]:
        if result is None:
            planned = planned_system_info_export(RUNTIME_ROOT, dry_run=self._dry_run_enabled())
            return [
                ("Status", "bereit", "info"),
                ("Geplanter Pfad", planned.export_path, "info"),
                ("Format", "TXT via msinfo32 /report", "info"),
                ("Agent-Auswertung", "vorbereitet, aber nicht automatisch gestartet", "info"),
                ("Testmodus", "aktiv" if self._dry_run_enabled() else "inaktiv", "warning" if self._dry_run_enabled() else "info"),
            ]
        return [
            ("Status", result.status, self._system_info_tag(result)),
            ("Exportpfad", result.export_path, "info"),
            ("Dateigroesse", self._format_bytes(result.size_bytes), "info"),
            ("Dauer", f"{result.duration_seconds} Sekunden", "info"),
            ("Testmodus", "ja" if result.dry_run else "nein", "warning" if result.dry_run else "info"),
            ("Exit-Code", str(result.exit_code) if result.exit_code is not None else "n/a", "info"),
            ("Fehler", result.error or "keiner", "error" if result.error else "success"),
            ("Agent-Auswertung", "vorbereitet, aber nicht automatisch gestartet", "info"),
        ]

    def _prepare_system_info_export(self) -> None:
        self.wizard_state.system_info = planned_system_info_export(RUNTIME_ROOT, dry_run=self._dry_run_enabled())
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self.last_status_var.set("SystemInfo Export vorbereitet")
        self.logger.info("SystemInfo Export vorbereitet.")
        self._show_page(21)

    def _start_system_info_export(self) -> None:
        if self.execution_running:
            return
        self.execution_running = True
        self._refresh_nav_state()
        self.last_status_var.set("SystemInfo Export laeuft..." if not self._dry_run_enabled() else "SystemInfo Dry-Run...")
        self.logger.info("SystemInfo MSINFO32 TXT-Export gestartet." if not self._dry_run_enabled() else "SystemInfo Dry-Run gestartet.")

        def worker() -> None:
            result = export_system_info_txt(RUNTIME_ROOT, dry_run=self._dry_run_enabled())
            self.after(0, lambda: self._finish_system_info_export(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_system_info_export(self, result: SystemInfoExportResult) -> None:
        self.execution_running = False
        self.wizard_state.system_info = result
        self.wizard_state.session_report_json_path = None
        self.wizard_state.session_report_txt_path = None
        self._refresh_nav_state()
        if result.status == SYSTEM_INFO_STATUS_SUCCESS:
            self.last_status_var.set(f"SystemInfo Export fertig: {Path(result.export_path).name}")
            self.logger.success(f"SystemInfo Export fertig: {result.export_path}")
        elif result.dry_run:
            self.last_status_var.set("SystemInfo Dry-Run abgeschlossen")
            self.logger.warning("SystemInfo Export im Testmodus simuliert.")
        else:
            self.last_status_var.set("SystemInfo Export fehlgeschlagen")
            self.logger.error(f"SystemInfo Export fehlgeschlagen: {result.error}")
        self._write_session_report()
        self._show_page(21)

    def _show_system_info_path(self) -> None:
        messagebox.showinfo("SystemInfo", f"SystemInfo-Export-Ordner:\n{SYSTEM_INFO_ROOT}\n\nIn v0.9.2 wird keine automatische Agent-Auswertung gestartet.")

    def _system_info_tag(self, result: SystemInfoExportResult) -> str:
        if result.status == SYSTEM_INFO_STATUS_FAILED:
            return "error"
        if result.status == SYSTEM_INFO_STATUS_SUCCESS:
            return "success"
        return "warning" if result.dry_run else "info"

    def _page_report(self) -> None:
        frame = self._panel()
        frame.grid(row=0, column=0, sticky="nsew")
        if self._has_reportable_session() and not self.wizard_state.session_report_txt_path:
            self._write_session_report()
        report = self.wizard_state.report
        ctk.CTkLabel(
            frame,
            text="Bericht",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=theme.TEXT,
        ).pack(padx=24, pady=(28, 12), anchor="w")
        if report is None:
            ctk.CTkLabel(frame, text="Noch kein Bericht vorhanden.", text_color=theme.WARNING).pack(
                padx=24,
                pady=8,
                anchor="w",
            )
        else:
            status = "abgeschlossen" if not report.failures else f"mit {len(report.failures)} Fehlern abgeschlossen"
            ctk.CTkLabel(
                frame,
                text=f"Setup {status}.",
                font=ctk.CTkFont(size=16),
                text_color=theme.SUCCESS if not report.failures else theme.ERROR,
            ).pack(padx=24, pady=6, anchor="w")
            ctk.CTkLabel(
                frame,
                text=f"JSON: {report.json_path}",
                text_color=theme.TEXT_MUTED,
                wraplength=780,
            ).pack(padx=24, pady=6, anchor="w")
            ctk.CTkLabel(
                frame,
                text=f"TXT: {report.txt_path}",
                text_color=theme.TEXT_MUTED,
                wraplength=780,
            ).pack(padx=24, pady=6, anchor="w")
        if self.wizard_state.tuning_results:
            failures = [result for result in self.wizard_state.tuning_results if result.status == "failed"]
            ctk.CTkLabel(
                frame,
                text=f"Tuning: {len(self.wizard_state.tuning_results)} Aktionen, {len(failures)} Fehler.",
                text_color=theme.SUCCESS if not failures else theme.ERROR,
            ).pack(padx=24, pady=(18, 6), anchor="w")
            if any(result.action.requires_reboot for result in self.wizard_state.tuning_results):
                ctk.CTkLabel(
                    frame,
                    text="Neustart empfohlen: Mindestens eine Repair-Aktion meldet einen Neustart-Hinweis.",
                    text_color=theme.WARNING,
                    wraplength=780,
                ).pack(padx=24, pady=6, anchor="w")
        if self.wizard_state.maintenance_results:
            failures = [result for result in self.wizard_state.maintenance_results if result.status == "failed"]
            ctk.CTkLabel(
                frame,
                text=f"Maintenance: {len(self.wizard_state.maintenance_results)} Aktionen, {len(failures)} Fehler.",
                text_color=theme.SUCCESS if not failures else theme.ERROR,
            ).pack(padx=24, pady=(18, 6), anchor="w")
        if self.wizard_state.imported_profile_name or self.wizard_state.exported_profile_path:
            ctk.CTkLabel(
                frame,
                text="Profilimport/-export",
                text_color=theme.ACCENT_CYAN,
                font=ctk.CTkFont(size=16, weight="bold"),
            ).pack(padx=24, pady=(18, 6), anchor="w")
            if self.wizard_state.imported_profile_name:
                ctk.CTkLabel(
                    frame,
                    text=f"Import: {self.wizard_state.imported_profile_name} ({self.wizard_state.imported_profile_path})",
                    text_color=theme.TEXT_MUTED,
                    wraplength=780,
                ).pack(padx=24, pady=3, anchor="w")
            if self.wizard_state.exported_profile_path:
                ctk.CTkLabel(
                    frame,
                    text=f"Export: {self.wizard_state.exported_profile_path}",
                    text_color=theme.TEXT_MUTED,
                    wraplength=780,
                ).pack(padx=24, pady=3, anchor="w")
            for warning in self.wizard_state.profile_import_warnings:
                ctk.CTkLabel(
                    frame,
                    text=f"Warnung: {warning}",
                    text_color=theme.WARNING,
                    wraplength=780,
                ).pack(padx=24, pady=3, anchor="w")
        if self.wizard_state.session_report_txt_path:
            ctk.CTkLabel(
                frame,
                text=f"Session TXT: {self.wizard_state.session_report_txt_path}",
                text_color=theme.ACCENT_CYAN,
                wraplength=780,
            ).pack(padx=24, pady=(18, 6), anchor="w")
            ctk.CTkLabel(
                frame,
                text=f"Session JSON: {self.wizard_state.session_report_json_path}",
                text_color=theme.TEXT_MUTED,
                wraplength=780,
            ).pack(padx=24, pady=6, anchor="w")

    def _apply_profile_selection(self) -> None:
        selected_profile_id = self.profile_var.get()
        self._apply_builtin_profile(selected_profile_id, persist=True)
        profile = self.wizard_state.selected_profile
        if profile:
            self.last_status_var.set(f"Profil: {profile.name}")
            self.logger.info(f"Profil gewaehlt: {profile.name}")

    def _sync_package_vars(self) -> None:
        for package in self.wizard_state.packages:
            if package.id not in self.package_vars:
                self.package_vars[package.id] = ctk.BooleanVar()
            self.package_vars[package.id].set(package.id in self.wizard_state.selected_package_ids)

    def _apply_package_selection(self) -> None:
        self.wizard_state.selected_package_ids = {
            package_id for package_id, var in self.package_vars.items() if var.get()
        }
        for category in self.package_count_labels:
            self._refresh_package_category_count(category)

    def _sync_tuning_vars(self) -> None:
        for action in self.wizard_state.tuning_actions:
            if action.id not in self.tuning_vars:
                self.tuning_vars[action.id] = ctk.BooleanVar()
            self.tuning_vars[action.id].set(action.id in self.wizard_state.selected_tuning_ids)

    def _apply_tuning_selection(self) -> None:
        self.wizard_state.selected_tuning_ids = {
            action_id for action_id, var in self.tuning_vars.items() if var.get()
        }

    def _sync_uninstall_vars(self) -> None:
        for program in self.wizard_state.installed_programs:
            if program.key not in self.uninstall_vars:
                self.uninstall_vars[program.key] = ctk.BooleanVar(value=program.key in self.wizard_state.selected_uninstall_keys)

    def _apply_uninstall_selection(self) -> None:
        self.wizard_state.selected_uninstall_keys = {
            key for key, var in self.uninstall_vars.items() if var.get()
        }

    def _apply_uninstall_table_selection(self, tree: ttk.Treeview) -> None:
        self.wizard_state.selected_uninstall_keys = {
            self.uninstall_row_keys[row_id]
            for row_id in tree.selection()
            if row_id in self.uninstall_row_keys
        }

    def _toggle_uninstall_tree_checkbox(self, event, tree: ttk.Treeview):
        if tree.identify_column(event.x) != "#1":
            return None
        row_id = tree.identify_row(event.y)
        if row_id:
            self._toggle_uninstall_row(tree, row_id)
        return "break"

    def _toggle_focused_uninstall_tree_checkbox(self, tree: ttk.Treeview):
        row_id = tree.focus()
        if row_id:
            self._toggle_uninstall_row(tree, row_id)
        return "break"

    def _toggle_uninstall_row(self, tree: ttk.Treeview, row_id: str) -> None:
        key = self.uninstall_row_keys.get(row_id)
        if not key:
            return
        if key in self.wizard_state.selected_uninstall_keys:
            self.wizard_state.selected_uninstall_keys.remove(key)
        else:
            self.wizard_state.selected_uninstall_keys.add(key)
        self._refresh_uninstall_tree_row(tree, row_id)

    def _refresh_uninstall_tree_row(self, tree: ttk.Treeview, row_id: str) -> None:
        key = self.uninstall_row_keys.get(row_id)
        program = next((item for item in self.wizard_state.installed_programs if item.key == key), None)
        if program is not None:
            tree.item(row_id, values=self._uninstall_tree_values(program))

    def _sync_update_vars(self) -> None:
        for update in self.wizard_state.available_updates:
            if update.key not in self.update_vars:
                self.update_vars[update.key] = ctk.BooleanVar(value=update.key in self.wizard_state.selected_update_keys)

    def _apply_update_selection(self) -> None:
        self.wizard_state.selected_update_keys = {
            key for key, var in self.update_vars.items() if var.get()
        }

    def _toggle_update_tree_checkbox(self, event, tree: ttk.Treeview):
        if tree.identify_column(event.x) != "#1":
            return None
        row_id = tree.identify_row(event.y)
        if row_id:
            self._toggle_update_row(tree, row_id)
        return "break"

    def _toggle_focused_update_tree_checkbox(self, tree: ttk.Treeview):
        row_id = tree.focus()
        if row_id:
            self._toggle_update_row(tree, row_id)
        return "break"

    def _toggle_update_row(self, tree: ttk.Treeview, row_id: str) -> None:
        key = self.update_row_keys.get(row_id)
        if not key:
            return
        if key in self.wizard_state.selected_update_keys:
            self.wizard_state.selected_update_keys.remove(key)
        else:
            self.wizard_state.selected_update_keys.add(key)
        self._refresh_update_tree_row(tree, row_id)

    def _refresh_update_tree_row(self, tree: ttk.Treeview, row_id: str) -> None:
        key = self.update_row_keys.get(row_id)
        update = next((item for item in self.wizard_state.available_updates if item.key == key), None)
        if update is not None:
            tree.item(row_id, values=self._update_tree_values(update))

    def _select_all_uninstall(self) -> None:
        self.wizard_state.selected_uninstall_keys = {program.key for program in self.wizard_state.installed_programs}
        tree = getattr(self, "uninstall_tree", None)
        if tree is not None:
            self._refresh_uninstall_tree(tree)

    def _clear_uninstall_selection(self) -> None:
        self.wizard_state.selected_uninstall_keys.clear()
        tree = getattr(self, "uninstall_tree", None)
        if tree is not None:
            self._refresh_uninstall_tree(tree)

    def _clear_update_scan(self) -> None:
        self.wizard_state.update_scope = "device"
        self.wizard_state.available_updates.clear()
        self.wizard_state.selected_update_keys.clear()
        self.update_vars.clear()
        self._show_page(11)

    def _select_all_updates(self) -> None:
        self.wizard_state.selected_update_keys = {update.key for update in self.wizard_state.available_updates}
        tree = getattr(self, "update_tree", None)
        if tree is not None:
            self._refresh_update_tree(tree)

    def _clear_update_selection(self) -> None:
        self.wizard_state.selected_update_keys.clear()
        tree = getattr(self, "update_tree", None)
        if tree is not None:
            self._refresh_update_tree(tree)

    def _clear_uninstall_scan(self) -> None:
        self.wizard_state.uninstall_scope = "device"
        self.wizard_state.installed_programs.clear()
        self.wizard_state.selected_uninstall_keys.clear()
        self.uninstall_vars.clear()
        self._show_page(8)

    def _next(self) -> None:
        if self.page_index == 15:
            self._run_guardforge_preview()
            return
        if self.page_index == 16:
            self._show_page(0)
            return
        if self.page_index == 17:
            self._show_page(0)
            return
        if self.page_index == 18:
            self._show_page(0)
            return
        if self.page_index == 19:
            self._show_page(0)
            return
        if self.page_index == 20:
            self._show_page(0)
            return
        if self.page_index == 21:
            self._show_page(0)
            return
        if self.page_index == 14:
            self._show_page(0)
            return
        if self.page_index == 7:
            self.logger.info("App durch Benutzer beendet.")
            self.destroy()
            return
        if self.page_index == 3 and not self.wizard_state.selected_package_ids:
            self.logger.warning("Setup-Start ohne Paketauswahl blockiert.")
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Programm aus.")
            return
        if self.page_index == 5 and not self.wizard_state.selected_tuning_ids:
            self.logger.warning("Tuning-Start ohne Auswahl blockiert.")
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens eine Tuning-Aktion aus.")
            return
        if self.page_index == 8 and not self.wizard_state.selected_uninstall_keys:
            self.logger.warning("Uninstall-Vorschau ohne Auswahl blockiert.")
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Programm aus.")
            return
        if self.page_index == 11 and not self.wizard_state.selected_update_keys:
            self.logger.warning("Update-Vorschau ohne Auswahl blockiert.")
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Update aus.")
            return
        self._show_page(self.page_index + 1)

    def _back(self) -> None:
        if self.page_index > 0:
            self._show_page(self.page_index - 1)

    def _dry_run_enabled(self) -> bool:
        return self.wizard_state.devhub_config.dry_run_enabled

    def _complete_dry_run(self, message: str, target_page: int = 7) -> None:
        self._append_entry(self.logger.warning(message))
        self._write_session_report()
        self.execution_running = False
        self._stop_elapsed_timer()
        self._refresh_nav_state()
        self._show_page(target_page)

    def _start_run(self) -> None:
        if self.execution_running:
            return
        if self.wizard_state.action_plan is None:
            self._append_log("ERROR", "Kein Aktionsplan vorhanden.")
            self.logger.error("Ausfuehrung ohne Aktionsplan blockiert.")
            return
        if not self.wizard_state.action_plan.actions:
            self._append_entry(self.logger.warning("Setup-Ausfuehrung ohne Paketauswahl blockiert."))
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Programm aus.")
            return
        if self._dry_run_enabled():
            self.execution_running = True
            self._refresh_nav_state()
            started_at = datetime.now().isoformat(timespec="seconds")
            simulate_setup_actions(self.wizard_state.action_plan.actions)
            self.wizard_state.report = create_report(self.wizard_state.action_plan, RUNTIME_ROOT / "reports", started_at)
            self._complete_dry_run(f"Testmodus: Setup simuliert ({len(self.wizard_state.action_plan.actions)} Pakete).", 5)
            return
        self.execution_running = True
        self._refresh_nav_state()
        if hasattr(self, "progress_bar"):
            self.progress_bar.start()
        self.executor = WingetExecutor(logger=self.logger)
        started_at = datetime.now().isoformat(timespec="seconds")
        self._append_entry(self.logger.info("Setup-Ausfuehrung gestartet."))
        self._start_elapsed_timer()

        def worker() -> None:
            try:
                assert self.executor is not None
                self._thread_entry(self.logger.info("Installer-Worker gestartet."))
                self.executor.run(self.wizard_state.action_plan.actions, self._thread_log, self._thread_status)
                self.wizard_state.report = create_report(self.wizard_state.action_plan, RUNTIME_ROOT / "reports", started_at)
                self._thread_entry(self.logger.success(f"Bericht gespeichert: {self.wizard_state.report.txt_path}"))
                self._write_session_report()
                self.execution_running = False
                self.after(0, lambda: self._show_page(5))
            except Exception as exc:
                self.execution_running = False
                self._thread_entry(self.logger.error("Unerwarteter Fehler im Setup-Worker", exc))
                self.after(0, self._refresh_nav_state)

        threading.Thread(target=worker, daemon=True).start()

    def _start_tuning_run(self) -> None:
        if self.execution_running:
            return
        actions = self.wizard_state.selected_tuning_actions
        if not actions:
            self._append_entry(self.logger.warning("Tuning-Ausfuehrung ohne Auswahl blockiert."))
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens eine Tuning-Aktion aus.")
            return
        medium_risk_actions = [action for action in actions if action.risk == "mittel"]
        if medium_risk_actions:
            names = "\n".join(f"- {action.name}" for action in medium_risk_actions)
            confirmed = messagebox.askyesno(
                "Mittleres Risiko bestaetigen",
                "Diese Repair-Aktionen koennen Systemzustand oder Netzwerkverhalten veraendern:\n\n"
                f"{names}\n\nTrotzdem starten?",
            )
            if not confirmed:
                self._append_entry(self.logger.warning("Tuning-Ausfuehrung durch Risiko-Bestaetigung abgebrochen."))
                return
        if self._dry_run_enabled():
            self.execution_running = True
            self._refresh_nav_state()
            self.wizard_state.tuning_results = simulate_tuning_actions(actions)
            self._complete_dry_run(f"Testmodus: Tuning simuliert ({len(actions)} Aktionen).", 7)
            return
        self.execution_running = True
        self._refresh_nav_state()
        if hasattr(self, "progress_bar"):
            self.progress_bar.start()
        self.tuning_executor = TuningExecutor(logger=self.logger)
        self._append_entry(self.logger.info(f"Tuning-Ausfuehrung gestartet: {len(actions)} Aktionen."))
        self._start_elapsed_timer()

        def worker() -> None:
            try:
                assert self.tuning_executor is not None
                self._thread_entry(self.logger.info("Tuning-Worker gestartet."))
                self.wizard_state.tuning_results = self.tuning_executor.run(
                    actions,
                    self._thread_log,
                    self._thread_tuning_status,
                )
                self._thread_entry(self.logger.success("Tuning-Ausfuehrung abgeschlossen."))
                self._write_session_report()
                self.execution_running = False
                self.after(0, lambda: self._show_page(7))
            except Exception as exc:
                self.execution_running = False
                self._thread_entry(self.logger.error("Unerwarteter Fehler im Tuning-Worker", exc))
                self.after(0, self._refresh_nav_state)

        threading.Thread(target=worker, daemon=True).start()

    def _get_maintenance(self) -> WingetMaintenance:
        if self.maintenance is None:
            self.maintenance = WingetMaintenance(logger=self.logger)
        return self.maintenance

    def _scan_installed_programs(self) -> None:
        if self.scan_running:
            return
        self.wizard_state.uninstall_scope = "device"
        self._begin_scan(
            "Uninstall-Scan laeuft...",
            "Suchpfad: winget list --accept-source-agreements | Quelle: Geraeteinventar im winget Katalog",
            8,
        )

        def worker() -> None:
            try:
                programs = self._get_maintenance().scan_installed(self.wizard_state.uninstall_scope)
                warning = self._get_maintenance().last_scan_warning
                if warning:
                    self.wizard_state.scan_warnings.append(warning)
                self.wizard_state.installed_programs = programs
                self.wizard_state.selected_uninstall_keys.clear()
                self.uninstall_vars.clear()
                self.after(0, lambda: self._finish_scan(f"Uninstall-Scan abgeschlossen: {len(programs)} Programme gefunden."))
                self.after(0, lambda: self._show_page(8))
            except Exception as exc:
                self.after(0, lambda: self._finish_scan("Uninstall-Scan fehlgeschlagen."))
                self._thread_entry(self.logger.error("Uninstall-Scan fehlgeschlagen", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_updates(self) -> None:
        if self.scan_running:
            return
        self.wizard_state.update_scope = "device"
        self._begin_scan(
            "Update-Scan laeuft...",
            "Suchpfad: winget upgrade --accept-source-agreements | Quelle: Geraeteinventar im winget Katalog",
            11,
        )

        def worker() -> None:
            try:
                updates = self._get_maintenance().scan_updates(self.wizard_state.update_scope)
                warning = self._get_maintenance().last_scan_warning
                if warning:
                    self.wizard_state.scan_warnings.append(warning)
                self.wizard_state.available_updates = updates
                self.wizard_state.selected_update_keys = {update.key for update in updates}
                self.update_vars.clear()
                self.after(0, lambda: self._finish_scan(f"Update-Scan abgeschlossen: {len(updates)} Updates gefunden."))
                self.after(0, lambda: self._show_page(11))
            except Exception as exc:
                self.after(0, lambda: self._finish_scan("Update-Scan fehlgeschlagen."))
                self._thread_entry(self.logger.error("Update-Scan fehlgeschlagen", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _start_uninstall_run(self) -> None:
        if self.execution_running:
            return
        programs = self.wizard_state.selected_uninstall_programs
        if not programs:
            self._append_entry(self.logger.warning("Uninstall ohne Auswahl blockiert."))
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Programm aus.")
            return
        names = "\n".join(f"- {program.name}" for program in programs[:8])
        if len(programs) > 8:
            names += f"\n... plus {len(programs) - 8} weitere"
        confirmed = messagebox.askyesno(
            "Uninstall bestaetigen",
            f"Diese Programme werden deinstalliert (Geraete-Scan, kein user-only Scope):\n\n{names}\n\nWirklich starten?",
        )
        if not confirmed:
            self._append_entry(self.logger.warning("Uninstall durch Benutzer vor Start abgebrochen."))
            return
        if self._dry_run_enabled():
            self.execution_running = True
            self._refresh_nav_state()
            results = simulate_uninstall(programs, self.wizard_state.uninstall_scope)
            self.wizard_state.maintenance_results.extend(results)
            self._complete_dry_run(f"Testmodus: Uninstall simuliert ({len(programs)} Programme).", 7)
            return
        self.execution_running = True
        self._refresh_nav_state()
        if hasattr(self, "progress_bar"):
            self.progress_bar.start()
        self._append_entry(self.logger.info(f"Uninstall-Ausfuehrung gestartet: {len(programs)} Programme."))
        self._start_elapsed_timer()

        def worker() -> None:
            try:
                results = self._get_maintenance().uninstall(
                    programs,
                    self.wizard_state.uninstall_scope,
                    self._thread_log,
                    self._thread_maintenance_status,
                )
                self.wizard_state.maintenance_results.extend(results)
                self._thread_entry(self.logger.success("Uninstall-Ausfuehrung abgeschlossen."))
                self._write_session_report()
                self.execution_running = False
                self.after(0, lambda: self._show_page(7))
            except Exception as exc:
                self.execution_running = False
                self._thread_entry(self.logger.error("Uninstall-Ausfuehrung fehlgeschlagen", exc))
                self.after(0, self._refresh_nav_state)

        threading.Thread(target=worker, daemon=True).start()

    def _start_update_run(self) -> None:
        if self.execution_running:
            return
        updates = self.wizard_state.selected_updates
        if not updates:
            self._append_entry(self.logger.warning("Update-Ausfuehrung ohne Auswahl blockiert."))
            messagebox.showwarning("Keine Auswahl", "Bitte waehle mindestens ein Update aus.")
            return
        if self._dry_run_enabled():
            self.execution_running = True
            self._refresh_nav_state()
            results = simulate_updates(updates, self.wizard_state.update_scope)
            self.wizard_state.maintenance_results.extend(results)
            self._complete_dry_run(f"Testmodus: Updates simuliert ({len(updates)} Updates).", 7)
            return
        self.execution_running = True
        self._refresh_nav_state()
        if hasattr(self, "progress_bar"):
            self.progress_bar.start()
        self._append_entry(self.logger.info(f"Update-Ausfuehrung gestartet: {len(updates)} Updates."))
        self._start_elapsed_timer()

        def worker() -> None:
            try:
                results = self._get_maintenance().upgrade(
                    updates,
                    self.wizard_state.update_scope,
                    self._thread_log,
                    self._thread_maintenance_status,
                )
                self.wizard_state.maintenance_results.extend(results)
                self._thread_entry(self.logger.success("Update-Ausfuehrung abgeschlossen."))
                self._write_session_report()
                self.execution_running = False
                self.after(0, lambda: self._show_page(7))
            except Exception as exc:
                self.execution_running = False
                self._thread_entry(self.logger.error("Update-Ausfuehrung fehlgeschlagen", exc))
                self.after(0, self._refresh_nav_state)

        threading.Thread(target=worker, daemon=True).start()

    def _has_reportable_session(self) -> bool:
        return bool(
            self.wizard_state.report
            or self.wizard_state.tuning_results
            or self.wizard_state.maintenance_results
            or self.wizard_state.scan_warnings
            or self.wizard_state.diagnostic_findings
            or self.wizard_state.guard_findings
            or self.wizard_state.imported_profile_name
            or self.wizard_state.exported_profile_path
            or self.wizard_state.profile_import_warnings
            or self.wizard_state.auto_analysis
            or self.wizard_state.offline_cache
            or self.wizard_state.recovery
            or self.wizard_state.risk_summary
            or self.wizard_state.daily_report
            or self.wizard_state.devhub_config != DevHubConfig()
            or self.wizard_state.system_info
        )

    def _write_session_report(self) -> None:
        self._refresh_daily_report_summary()
        json_path, txt_path = write_session_report(
            RUNTIME_ROOT / "reports",
            setup_report=self.wizard_state.report,
            tuning_results=self.wizard_state.tuning_results,
            maintenance_results=self.wizard_state.maintenance_results,
            scan_warnings=self.wizard_state.scan_warnings,
            diagnostic_findings=self._refresh_diagnostic_findings(),
            guard_findings=self.wizard_state.guard_findings,
            imported_profile_name=self.wizard_state.imported_profile_name,
            imported_profile_path=self.wizard_state.imported_profile_path,
            exported_profile_path=self.wizard_state.exported_profile_path,
            profile_import_warnings=self.wizard_state.profile_import_warnings,
            auto_analysis=self.wizard_state.auto_analysis,
            offline_cache=self.wizard_state.offline_cache,
            recovery=self.wizard_state.recovery,
            risk_summary=self.wizard_state.risk_summary,
            daily_report=self.wizard_state.daily_report,
            devhub_config=self.wizard_state.devhub_config,
            system_info=self.wizard_state.system_info,
        )
        self.wizard_state.session_report_json_path = str(json_path)
        self.wizard_state.session_report_txt_path = str(txt_path)
        entry = self.logger.success(f"Session-Bericht gespeichert: {txt_path}")
        self.after(0, lambda: self._append_entry(entry))

    def _run_guardforge_preview(self) -> None:
        provider = MockFileWatchProvider()
        self.wizard_state.guard_events = provider.collect_events()
        self.wizard_state.guard_findings = score_guard_events(self.wizard_state.guard_events)
        self._refresh_risk_summary()
        self._refresh_daily_report_summary()
        self.last_status_var.set(f"GuardForge Preview: {len(self.wizard_state.guard_findings)} Findings")
        self.logger.info("GuardForge Mock-Preview ausgewertet.")
        self._show_page(15)

    def _cancel_run(self) -> None:
        if self.executor:
            self.executor.cancel()
            self._append_entry(self.logger.warning("Abbruch angefordert. Laufendes Paket wird noch beendet."))

    def _thread_log(self, message: str) -> None:
        self.after(0, lambda: self._append_log("INFO", message))

    def _thread_status(self, action: PlannedAction) -> None:
        level = {
            "success": "SUCCESS",
            "failed": "ERROR",
            "skipped": "WARNING",
        }.get(action.status, "INFO")
        self.after(0, lambda: self._append_log(level, f"Status {action.package.name}: {action.status}"))

    def _thread_tuning_status(self, result: TuningResult) -> None:
        level = {
            "success": "SUCCESS",
            "failed": "ERROR",
        }.get(result.status, "INFO")
        self.after(0, lambda: self._append_log(level, f"Tuning {result.action.name}: {result.status}"))

    def _thread_maintenance_status(self, result: MaintenanceResult) -> None:
        level = {
            "success": "SUCCESS",
            "failed": "ERROR",
        }.get(result.status, "INFO")
        self.after(0, lambda: self._append_log(level, f"{result.operation} {result.name}: {result.status}"))

    def _thread_entry(self, entry: LogEntry) -> None:
        self.after(0, lambda: self._append_entry(entry))

    def _append_entry(self, entry: LogEntry) -> None:
        self._append_log(entry.level, entry.line)

    def _append_log(self, level: str, message: str) -> None:
        self.last_status_var.set(message)
        if hasattr(self, "log_box"):
            text_widget = getattr(self.log_box, "_textbox", self.log_box)
            self.log_box.configure(state="normal")
            if self.console_line_count >= MAX_CONSOLE_LINES:
                text_widget.delete("1.0", f"{CONSOLE_PRUNE_LINES + 1}.0")
                self.console_line_count = max(0, self.console_line_count - CONSOLE_PRUNE_LINES)
            start = text_widget.index("end-1c")
            text_widget.insert("end", message + "\n")
            end = text_widget.index("end-1c")
            text_widget.tag_add(level, start, end)
            self.console_line_count += 1
            self.log_box.configure(state="disabled")
            self.log_box.see("end")

    def _configure_log_tags(self) -> None:
        text_widget = getattr(self.log_box, "_textbox", self.log_box)
        for level, color in theme.LOG_LEVEL_COLORS.items():
            text_widget.tag_config(level, foreground=color)

    def _create_console(self, parent: ctk.CTkFrame) -> ctk.CTkTextbox:
        console = ctk.CTkTextbox(
            parent,
            fg_color="#070a12",
            text_color=theme.INFO,
            border_color=theme.BORDER,
            border_width=1,
            activate_scrollbars=True,
        )
        self.log_box = console
        self.console_line_count = 0
        self._configure_log_tags()
        console.configure(state="disabled")
        return console

    def _clear_console(self) -> None:
        if hasattr(self, "log_box"):
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
            self.console_line_count = 0

    def _start_elapsed_timer(self) -> None:
        self.run_started_at = datetime.now()
        self.elapsed_var.set("00:00")
        self._tick_elapsed_timer()

    def _tick_elapsed_timer(self) -> None:
        if self.run_started_at is None:
            return
        elapsed = int((datetime.now() - self.run_started_at).total_seconds())
        minutes, seconds = divmod(elapsed, 60)
        self.elapsed_var.set(f"{minutes:02d}:{seconds:02d}")
        self.timer_job = self.after(1000, self._tick_elapsed_timer)

    def _stop_elapsed_timer(self) -> None:
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        if hasattr(self, "progress_bar"):
            self.progress_bar.stop()

    def _begin_scan(self, status: str, detail: str, page_id: int) -> None:
        self.scan_running = True
        self.scan_status_var.set(status)
        self.scan_detail_var.set(detail)
        self.scan_elapsed_var.set("00:00")
        self.scan_started_at = datetime.now()
        self._show_page(page_id)
        if hasattr(self, "scan_progress_bar"):
            self.scan_progress_bar.start()
        self._tick_scan_timer()
        self.last_status_var.set(status)
        self.logger.info(detail)

    def _finish_scan(self, status: str) -> None:
        self.scan_running = False
        self.scan_status_var.set(status)
        self.last_status_var.set(status)
        if self.scan_timer_job is not None:
            self.after_cancel(self.scan_timer_job)
            self.scan_timer_job = None
        if hasattr(self, "scan_progress_bar"):
            self.scan_progress_bar.stop()
        self.logger.info(status)
        self._refresh_nav_state()
        self.back_button.configure(state="disabled" if self.page_index == 0 else "normal")
        self.next_button.configure(state="normal")

    def _tick_scan_timer(self) -> None:
        if not self.scan_running or self.scan_started_at is None:
            return
        elapsed = int((datetime.now() - self.scan_started_at).total_seconds())
        minutes, seconds = divmod(elapsed, 60)
        self.scan_elapsed_var.set(f"{minutes:02d}:{seconds:02d}")
        self.scan_timer_job = self.after(1000, self._tick_scan_timer)

    def _set_mode_title(self, tuning_mode: bool) -> None:
        if tuning_mode:
            self.title(f"{APP_DISPLAY_NAME} {APP_VERSION}")
            self.mode_title_var.set(APP_MODULE)
            self.mode_subtitle_var.set("DEVHub Performance")
        else:
            self.title(f"{APP_DISPLAY_NAME} {APP_VERSION}")
            self.mode_title_var.set(APP_MODULE)
            self.mode_subtitle_var.set("DEVHub Setup & Repair")

    def _scan_status_panel(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(parent, fg_color="#070a12", border_color=theme.BORDER, border_width=1, corner_radius=8)
        panel.pack(fill="x", padx=14, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, textvariable=self.scan_status_var, text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
        ctk.CTkLabel(panel, textvariable=self.scan_elapsed_var, text_color=theme.WARNING, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=1, padx=14, pady=(10, 2), sticky="e")
        ctk.CTkLabel(panel, textvariable=self.scan_detail_var, text_color=theme.TEXT_MUTED, wraplength=760, justify="left").grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 8), sticky="w")
        self.scan_progress_bar = ctk.CTkProgressBar(panel, mode="indeterminate", progress_color=theme.ACCENT_CYAN)
        self.scan_progress_bar.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
        self.scan_progress_bar.set(0)
        if self.scan_running:
            self.scan_progress_bar.start()

    def _selection_buttons(self, parent: ctk.CTkFrame, select_command, clear_command) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 10))
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            row,
            text="Alle auswaehlen",
            command=select_command,
            width=140,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        ctk.CTkButton(
            row,
            text="Auswahl leeren",
            command=clear_command,
            width=140,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=2, sticky="e")

    def _program_card(self, parent: ctk.CTkFrame, program) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        card.pack(fill="x", padx=12, pady=6)
        card.grid_columnconfigure(1, weight=1)
        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            variable=self.uninstall_vars[program.key],
            command=self._apply_uninstall_selection,
            fg_color=theme.ACCENT_CYAN,
            hover_color=theme.ACCENT_PURPLE,
            border_color=theme.BORDER_ACTIVE,
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=14, pady=14)
        ctk.CTkLabel(card, text=program.name, font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT).grid(row=0, column=1, sticky="w", padx=4, pady=(12, 0))
        ctk.CTkLabel(card, text=f"{program.package_id or 'no id'} | {program.version or 'no version'} | {program.source or 'unknown source'}", text_color=theme.TEXT_MUTED).grid(row=1, column=1, sticky="w", padx=4, pady=(0, 12))

    def _program_table(self, parent: ctk.CTkFrame) -> None:
        table_frame = tk.Frame(parent, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.BORDER)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._configure_tree_style()

        columns = ("checked", "name", "id", "version", "source")
        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=18,
        )
        tree.heading("checked", text="")
        tree.heading("name", text="Programm")
        tree.heading("id", text="ID")
        tree.heading("version", text="Version")
        tree.heading("source", text="Quelle")
        tree.column("checked", width=44, minwidth=44, stretch=False, anchor="center")
        tree.column("name", width=280, minwidth=180, stretch=True)
        tree.column("id", width=280, minwidth=180, stretch=True)
        tree.column("version", width=130, minwidth=90, stretch=False)
        tree.column("source", width=90, minwidth=70, stretch=False)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.uninstall_row_keys.clear()
        for index, program in enumerate(self.wizard_state.installed_programs):
            row_id = f"program_{index}"
            self.uninstall_row_keys[row_id] = program.key
            tree.insert("", "end", iid=row_id, values=self._uninstall_tree_values(program))
        tree.bind("<Button-1>", lambda event, widget=tree: self._toggle_uninstall_tree_checkbox(event, widget))
        tree.bind("<space>", lambda event, widget=tree: self._toggle_focused_uninstall_tree_checkbox(widget))
        self.uninstall_tree = tree

    def _uninstall_tree_values(self, program) -> tuple[str, str, str, str, str]:
        checked = "[x]" if program.key in self.wizard_state.selected_uninstall_keys else "[ ]"
        return (
            checked,
            program.name,
            program.package_id or "no id",
            program.version or "no version",
            program.source or "unknown",
        )

    def _refresh_uninstall_tree(self, tree: ttk.Treeview) -> None:
        for row_id in self.uninstall_row_keys:
            self._refresh_uninstall_tree_row(tree, row_id)

    def _configure_tree_style(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            TREE_STYLE,
            background=theme.CARD,
            fieldbackground=theme.CARD,
            foreground=theme.TEXT,
            rowheight=25,
            borderwidth=0,
        )
        style.configure(
            TREE_HEADING_STYLE,
            background=theme.PANEL_ALT,
            foreground=theme.ACCENT_CYAN,
            relief="flat",
        )
        style.map(TREE_STYLE, background=[("selected", theme.ACCENT_PURPLE)], foreground=[("selected", theme.TEXT)])

    def _update_card(self, parent: ctk.CTkFrame, update) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=8)
        card.pack(fill="x", padx=12, pady=6)
        card.grid_columnconfigure(1, weight=1)
        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            variable=self.update_vars[update.key],
            command=self._apply_update_selection,
            fg_color=theme.ACCENT_CYAN,
            hover_color=theme.ACCENT_PURPLE,
            border_color=theme.BORDER_ACTIVE,
        )
        checkbox.grid(row=0, column=0, rowspan=2, padx=14, pady=14)
        ctk.CTkLabel(card, text=update.name, font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.TEXT).grid(row=0, column=1, sticky="w", padx=4, pady=(12, 0))
        ctk.CTkLabel(card, text=f"{update.package_id} | {update.current_version} -> {update.available_version} | {update.source}", text_color=theme.TEXT_MUTED).grid(row=1, column=1, sticky="w", padx=4, pady=(0, 12))

    def _update_table(self, parent: ctk.CTkFrame) -> None:
        table_frame = tk.Frame(parent, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.BORDER)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._configure_tree_style()

        columns = ("checked", "name", "id", "current", "available", "source")
        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style=TREE_STYLE,
            height=12,
        )
        tree.heading("checked", text="")
        tree.heading("name", text="Programm")
        tree.heading("id", text="ID")
        tree.heading("current", text="Aktuell")
        tree.heading("available", text="Verfuegbar")
        tree.heading("source", text="Quelle")
        tree.column("checked", width=44, minwidth=44, stretch=False, anchor="center")
        tree.column("name", width=240, minwidth=160, stretch=True)
        tree.column("id", width=230, minwidth=160, stretch=True)
        tree.column("current", width=110, minwidth=80, stretch=False)
        tree.column("available", width=120, minwidth=90, stretch=False)
        tree.column("source", width=90, minwidth=70, stretch=False)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.update_row_keys.clear()
        for index, update in enumerate(self.wizard_state.available_updates):
            row_id = f"update_{index}"
            self.update_row_keys[row_id] = update.key
            tree.insert("", "end", iid=row_id, values=self._update_tree_values(update))
        tree.bind("<Button-1>", lambda event, widget=tree: self._toggle_update_tree_checkbox(event, widget))
        tree.bind("<space>", lambda event, widget=tree: self._toggle_focused_update_tree_checkbox(widget))
        self.update_tree = tree

    def _update_tree_values(self, update) -> tuple[str, str, str, str, str, str]:
        checked = "[x]" if update.key in self.wizard_state.selected_update_keys else "[ ]"
        return (
            checked,
            update.name,
            update.package_id,
            update.current_version,
            update.available_version,
            update.source,
        )

    def _refresh_update_tree(self, tree: ttk.Treeview) -> None:
        for row_id in self.update_row_keys:
            self._refresh_update_tree_row(tree, row_id)

    def _run_panel(self, title: str) -> ctk.CTkFrame:
        frame = self._panel()
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=22, weight="bold"), text_color=theme.TEXT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, textvariable=self.elapsed_var, text_color=theme.ACCENT_CYAN, font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=2, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(frame, mode="indeterminate", progress_color=theme.ACCENT_CYAN)
        self.progress_bar.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.progress_bar.set(0)
        self.log_box = self._create_console(frame)
        self.log_box.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="nsew")
        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            controls,
            text="Console leeren",
            command=self._clear_console,
            width=150,
            fg_color=theme.SECONDARY_BUTTON,
            hover_color=theme.SECONDARY_BUTTON_HOVER,
            border_color=theme.BORDER,
            border_width=1,
        ).grid(row=0, column=1, sticky="e")
        return frame

    def _run_start_button(self, frame: ctk.CTkFrame, text: str, command) -> None:
        ctk.CTkButton(
            frame,
            text=text,
            command=command,
            width=190,
            fg_color=theme.PRIMARY_BUTTON,
            hover_color=theme.PRIMARY_BUTTON_HOVER,
            border_color=theme.ACCENT_CYAN,
            border_width=1,
        ).grid(row=4, column=0, padx=18, pady=(0, 18), sticky="e")

    def _panel(self) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            self.content,
            fg_color=theme.PANEL,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=8,
        )

    def _scroll_panel(self, label_text: str) -> ctk.CTkScrollableFrame:
        return ctk.CTkScrollableFrame(
            self.content,
            label_text=label_text,
            fg_color=theme.PANEL,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=8,
            label_fg_color=theme.PANEL,
            label_text_color=theme.ACCENT_CYAN,
        )

    def _console_strip(self, parent: ctk.CTkFrame, title: str, message: str) -> None:
        strip = ctk.CTkFrame(
            parent,
            fg_color="#070a12",
            border_color=theme.BORDER_ACTIVE,
            border_width=1,
            corner_radius=8,
        )
        strip.pack(fill="x", padx=34, pady=(32, 18), side="bottom")
        ctk.CTkLabel(
            strip,
            text=title,
            text_color=theme.ACCENT_CYAN,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(padx=14, pady=(10, 0), anchor="w")
        ctk.CTkLabel(strip, text=message, text_color=theme.TEXT, font=ctk.CTkFont(size=14)).pack(
            padx=14,
            pady=(0, 10),
            anchor="w",
        )
