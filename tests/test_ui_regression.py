from pathlib import Path


def test_tuningforge_app_does_not_shadow_tk_state_method() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "self.state = WizardState()" not in ui_source
    assert "self.wizard_state = WizardState()" in ui_source


def test_sidebar_routes_are_unique() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "(0, \"ControlDeck\")" in ui_source
    assert "(8, \"Uninstall\")" in ui_source
    assert "(11, \"Updates\")" in ui_source
    assert "(14, \"Diagnose\")" in ui_source
    assert "(15, \"GuardForge\")" in ui_source
    assert "(16, \"Offline Cache\")" in ui_source
    assert "(17, \"RecoveryForge\")" in ui_source
    assert "(18, \"Risk Engine\")" in ui_source
    assert "(19, \"Tagesbericht\")" in ui_source
    assert "(20, \"Konfiguration\")" in ui_source
    assert "(21, \"SystemInfo\")" in ui_source
    assert "def _navigate_to" in ui_source


def test_control_deck_dashboard_is_start_page() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "DEVHub ControlDeck" in ui_source
    assert "def _dashboard_cards" in ui_source
    assert "def _dashboard_snapshot" in ui_source
    assert "def _dashboard_status_table" in ui_source
    assert "def _dashboard_module_table" in ui_source
    assert "def _dashboard_recommendations" in ui_source
    assert "Statusuebersicht" in ui_source
    assert "Modulzentrale" in ui_source
    assert "build_dashboard_snapshot" in ui_source
    assert "shutil.which(\"winget\")" in ui_source
    assert "ErrorDoctor" in ui_source
    assert "GuardForge" in ui_source
    assert "Auto-Analyse" in ui_source
    assert "Offline Cache" in ui_source
    assert "RecoveryForge" in ui_source
    assert "Risk Engine" in ui_source
    assert "Tagesbericht" in ui_source
    assert "Konfiguration" in ui_source
    assert "SystemInfo" in ui_source
    assert "Profil importieren" in ui_source
    assert "Profil exportieren" in ui_source


def test_auto_analysis_startup_worker_is_read_only() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    init_block = ui_source.split("def __init__", 1)[1].split("def _maximize_window", 1)[0]
    auto_block = ui_source.split("def _start_auto_analysis", 1)[1].split("def _restore_saved_preset", 1)[0]

    assert "self.after(250, self._start_auto_analysis)" in init_block
    assert "threading.Thread(target=worker" in auto_block
    assert "build_auto_analysis_snapshot" in auto_block
    assert "CACHE_ROOT.exists()" in auto_block
    assert "Keine Aktionen" not in auto_block
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "_scan_installed_programs",
        "_scan_updates",
        "WingetExecutor",
        "TuningExecutor",
        "WingetMaintenance(",
    ):
        assert forbidden not in auto_block


def test_control_deck_module_actions_only_navigate_or_profile_io() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    welcome_block = ui_source.split("def _page_welcome", 1)[1].split("def _dashboard_cards", 1)[0]
    module_block = ui_source.split("def _dashboard_module_table", 1)[1].split("def _open_dashboard_module", 1)[0]

    assert "_show_page" in welcome_block
    assert "_open_dashboard_module" in module_block
    assert "_import_devhub_profile" in welcome_block
    assert "_export_devhub_profile" in welcome_block
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "_scan_installed_programs",
        "_scan_updates",
    ):
        assert forbidden not in welcome_block
        assert forbidden not in module_block


def test_control_deck_uses_tables_instead_of_nested_module_cards() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    welcome_block = ui_source.split("def _page_welcome", 1)[1].split("def _dashboard_cards", 1)[0]
    module_table = ui_source.split("def _dashboard_module_table", 1)[1].split("def _open_dashboard_module", 1)[0]

    assert "_dashboard_status_table(frame, snapshot)" in welcome_block
    assert "_dashboard_module_table(frame, snapshot)" in welcome_block
    assert "ttk.Treeview" in module_table
    assert "dashboard_module_pages" in module_table
    assert "_dashboard_module(modules" not in welcome_block


def test_offline_cache_page_is_preview_only_table() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    cache_page = ui_source.split("def _page_offline_cache", 1)[1].split("def _page_report", 1)[0]

    assert "Offline Cache" in cache_page
    assert "ttk.Treeview" in cache_page
    assert "Cache pruefen" in cache_page
    assert "Index aktualisieren" in cache_page
    assert "Ordnerpfad anzeigen" in cache_page
    assert "Kein Download" in cache_page
    assert "keine Installation" in cache_page
    assert "kein Loeschen" in cache_page
    lowered = cache_page.casefold()
    for forbidden in ("download(", "install(", "uninstall(", "delete", "remove", "winget"):
        assert forbidden not in lowered


def test_recoveryforge_page_is_preview_only_table() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    recovery_page = ui_source.split("def _page_recoveryforge", 1)[1].split("def _page_report", 1)[0]

    assert "RecoveryForge Alpha" in recovery_page
    assert "ttk.Treeview" in recovery_page
    assert "Preview aktualisieren" in recovery_page
    assert "Recovery-Pfad anzeigen" in recovery_page
    assert "Kein Backup" in recovery_page
    assert "kein Restore" in recovery_page
    assert "kein Kopieren" in recovery_page
    assert "kein Loeschen" in recovery_page
    lowered = recovery_page.casefold()
    for forbidden in ("copy(", "backup(", "restore(", "delete", "remove", "shutil.copy", "restore-point"):
        assert forbidden not in lowered


def test_risk_engine_page_is_read_only_table() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    risk_page = ui_source.split("def _page_risk_engine", 1)[1].split("def _page_report", 1)[0]

    assert "Risk Engine Preview" in risk_page
    assert "ttk.Treeview" in risk_page
    assert "Risk neu bewerten" in risk_page
    assert "ControlDeck" in risk_page
    assert "Keine Aktionen" in risk_page
    assert "keine Auto-Fixes" in risk_page
    lowered = risk_page.casefold()
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "winget",
        "download",
        "install(",
        "delete",
        "remove",
    ):
        assert forbidden not in lowered


def test_daily_report_page_is_read_only_table() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    daily_page = ui_source.split("def _page_daily_report", 1)[1].split("def _page_report", 1)[0]

    assert "Tagesbericht Preview" in daily_page
    assert "ttk.Treeview" in daily_page
    assert "Tagesbericht aktualisieren" in daily_page
    assert "Reportpfad anzeigen" in daily_page
    assert "Keine Benachrichtigungen" in daily_page
    assert "kein Scheduler" in daily_page
    assert "keine Aktionen" in daily_page
    lowered = daily_page.casefold()
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "winget",
        "download",
        "install(",
        "delete",
        "remove",
        "toast",
        "schedule(",
    ):
        assert forbidden not in lowered


def test_configuration_page_is_local_import_export_only() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    config_page = ui_source.split("def _page_configuration", 1)[1].split("def _page_report", 1)[0]

    assert "Konfiguration / Testmodus" in config_page
    assert "Konfiguration speichern" in config_page
    assert "Konfiguration importieren" in config_page
    assert "Konfiguration exportieren" in config_page
    assert "Testmodus / Dry-Run markieren" in config_page
    assert "Auto-Analyse beim Start" in config_page
    assert "Letztes Preset merken" in config_page
    assert "ttk.Treeview" in config_page
    assert "Keine Aktion wurde gestartet" in config_page
    lowered = config_page.casefold()
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "winget",
        "download",
        "install(",
        "delete",
        "remove",
        "subprocess",
    ):
        assert forbidden not in lowered


def test_system_info_page_is_manual_export_only() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    system_info_page = ui_source.split("def _page_system_info", 1)[1].split("def _page_report", 1)[0]

    assert "SystemInfo / MSINFO32 Export" in system_info_page
    assert "Export vorbereiten" in system_info_page
    assert "MSINFO32 TXT exportieren" in system_info_page
    assert "Ordnerpfad anzeigen" in system_info_page
    assert "ttk.Treeview" in system_info_page
    assert "keine automatische Analyse" in system_info_page
    assert "export_system_info_txt" in system_info_page
    assert "planned_system_info_export" in system_info_page
    lowered = system_info_page.casefold()
    for forbidden in (
        "_start_run",
        "_start_tuning_run",
        "_start_uninstall_run",
        "_start_update_run",
        "_run_guardforge_preview",
        "upload(",
        "openai.",
    ):
        assert forbidden not in lowered


def test_system_info_dry_run_gates_before_msinfo_export() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    start_block = ui_source.split("def _start_system_info_export", 1)[1].split("def _finish_system_info_export", 1)[0]

    assert "dry_run=self._dry_run_enabled()" in start_block
    assert "export_system_info_txt" in start_block
    assert "self._dry_run_enabled()" in start_block


def test_profile_import_export_keeps_manual_preview_required() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    import_block = ui_source.split("def _apply_imported_profile", 1)[1].split("def _import_devhub_profile", 1)[0]

    assert "selected_package_ids" in import_block
    assert "selected_tuning_ids" in import_block
    assert "action_plan = None" in import_block
    assert "_save_last_imported_preset(path)" in import_block
    assert "_start_run" not in import_block
    assert "_start_tuning_run" not in import_block
    assert "_start_uninstall_run" not in import_block
    assert "_start_update_run" not in import_block
    assert "_run_guardforge_preview" not in import_block
    assert "build_action_plan" not in import_block


def test_last_preset_is_persisted_and_restored_from_runtime_config() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert 'RUNTIME_ROOT / "config" / "app-state.json"' in ui_source
    assert "def _restore_saved_preset" in ui_source
    assert "def _save_last_builtin_preset" in ui_source
    assert "def _save_last_imported_preset" in ui_source
    assert "load_app_settings(self.app_settings_path)" in ui_source
    assert "save_app_settings(" in ui_source
    assert "_apply_builtin_profile(selected_profile_id, persist=True)" in ui_source
    assert "_apply_imported_profile(path, imported, show_dialog=True)" in ui_source


def test_app_starts_maximized_with_geometry_fallback() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "def _maximize_window" in ui_source
    assert "def _schedule_maximize_reapply" in ui_source
    assert "self.state(\"zoomed\")" in ui_source
    assert "1500" in ui_source
    assert "except tk.TclError" in ui_source


def test_guardforge_page_is_preview_only() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    guard_page = ui_source.split("def _page_guardforge", 1)[1].split("def _page_report", 1)[0]

    assert "GuardForge Alpha" in guard_page
    assert "Mock-Preview auswerten" in guard_page
    assert "Keine permanente Ueberwachung" in guard_page
    assert "kein Autostart" in guard_page
    assert "kein Blockieren" in guard_page
    assert "kein Loeschen" in guard_page
    assert "kein Netzwerk" in guard_page
    assert "watchdog" not in guard_page.casefold()


def test_diagnostics_page_does_not_auto_fix() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    diagnostics_page = ui_source.split("def _page_diagnostics", 1)[1].split("def _page_report", 1)[0]

    assert "def _page_diagnostics" in ui_source
    assert "Keine bekannten Probleme erkannt" in diagnostics_page
    assert "keine Auto-Fixes" in diagnostics_page
    assert "Historisch" in diagnostics_page
    assert "finding.status" in diagnostics_page
    assert "safe_to_auto_fix" not in diagnostics_page


def test_control_deck_counts_active_diagnostics_separately() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    dashboard_cards = ui_source.split("def _dashboard_cards", 1)[1].split("def _dashboard_card", 1)[0]
    recommendations = ui_source.split("def _dashboard_recommendations", 1)[1].split("def _dashboard_action", 1)[0]

    assert "_dashboard_snapshot().cards" in dashboard_cards
    assert "_dashboard_snapshot().recommendations" in recommendations


def test_control_deck_reads_latest_session_report() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    dashboard_source = (Path(__file__).resolve().parent.parent / "core" / "dashboard.py").read_text(encoding="utf-8")

    assert "def _latest_session_payload" in ui_source
    assert "SESSION_REPORT_PREFIX" in ui_source
    assert "def _payload_failures" in ui_source
    assert "latest_payload=latest_payload" in ui_source
    assert "Letzter Report:" in dashboard_source


def test_pyinstaller_paths_split_resources_from_runtime_outputs() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "def _resource_root" in ui_source
    assert "def _runtime_root" in ui_source
    assert 'getattr(sys, "_MEIPASS")' in ui_source
    assert "Path(sys.executable).resolve().parent" in ui_source
    assert "RUNTIME_ROOT / \"reports\"" in ui_source
    assert "RUNTIME_ROOT / \"logs\"" in ui_source


def test_portable_build_script_bundles_config_not_reports() -> None:
    script = (Path(__file__).resolve().parent.parent / "scripts" / "build_portable.ps1").read_text(encoding="utf-8")
    cmd_script = (Path(__file__).resolve().parent.parent / "scripts" / "build_portable.cmd").read_text(encoding="utf-8")

    assert '--add-data "packages;packages"' in script
    assert '--add-data "profiles;profiles"' in script
    assert '--add-data "tuning;tuning"' in script
    assert '--add-data "reports;reports"' not in script
    assert 'Join-Path $OutputDir "reports"' in script
    assert 'Join-Path $OutputDir "logs"' in script
    assert "Resolve-PythonExe" in script
    assert "WindowsApps" in script
    assert "python -m PyInstaller" not in cmd_script
    assert "-m PyInstaller" in cmd_script
    assert "Tkinter/Tcl OK" in cmd_script
    assert "--add-data \"packages;packages\"" in cmd_script
    assert "PYROOT_FILE" in cmd_script
    assert "set /p PYTHON_ROOT" in cmd_script


def test_workers_start_once() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    start_run_block = ui_source.split("def _start_run", 1)[1].split("def _start_tuning_run", 1)[0]
    tuning_block = ui_source.split("def _start_tuning_run", 1)[1].split("def _get_maintenance", 1)[0]

    assert start_run_block.count("threading.Thread(target=worker") == 1
    assert tuning_block.count("threading.Thread(target=worker") == 1


def test_dry_run_gates_execution_before_real_executors() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    start_run_block = ui_source.split("def _start_run", 1)[1].split("def _start_tuning_run", 1)[0]
    tuning_block = ui_source.split("def _start_tuning_run", 1)[1].split("def _get_maintenance", 1)[0]
    uninstall_block = ui_source.split("def _start_uninstall_run", 1)[1].split("def _start_update_run", 1)[0]
    update_block = ui_source.split("def _start_update_run", 1)[1].split("def _has_reportable_session", 1)[0]

    assert "simulate_setup_actions" in start_run_block
    assert start_run_block.index("simulate_setup_actions") < start_run_block.index("WingetExecutor")
    assert "simulate_tuning_actions" in tuning_block
    assert tuning_block.index("simulate_tuning_actions") < tuning_block.index("TuningExecutor")
    assert "simulate_uninstall" in uninstall_block
    assert uninstall_block.index("simulate_uninstall") < uninstall_block.index("self._get_maintenance().uninstall")
    assert "simulate_updates" in update_block
    assert update_block.index("simulate_updates") < update_block.index("self._get_maintenance().upgrade")


def test_run_pages_do_not_auto_start_workers() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    setup_page = ui_source.split("def _page_run", 1)[1].split("def _page_tuning", 1)[0]
    tuning_page = ui_source.split("def _page_tuning_run", 1)[1].split("def _page_report", 1)[0]

    assert "self._start_run()" not in setup_page
    assert "self._start_tuning_run()" not in tuning_page


def test_tuning_page_shows_repair_metadata_and_medium_risk_confirmation() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    tuning_page = ui_source.split("def _page_tuning", 1)[1].split("def _page_tuning_run", 1)[0]
    tuning_start = ui_source.split("def _start_tuning_run", 1)[1].split("def _get_maintenance", 1)[0]

    assert "TUNING_CATEGORY_ORDER" in ui_source
    assert "action.impact" in tuning_page
    assert "action.duration_hint" in tuning_page
    assert "action.requires_reboot" in tuning_page
    assert "Mittleres Risiko bestaetigen" in tuning_start
    assert "messagebox.askyesno" in tuning_start


def test_navigation_guard_covers_scans_and_runs() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    busy_block = ui_source.split("def _is_busy_page", 1)[1].split("def _navigate_to", 1)[0]

    assert "self.scan_running" in busy_block
    assert "self.execution_running" in busy_block


def test_uninstall_requires_second_confirmation() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    uninstall_block = ui_source.split("def _start_uninstall_run", 1)[1].split("def _start_update_run", 1)[0]

    assert "messagebox.askyesno" in uninstall_block
    assert "Uninstall bestaetigen" in uninstall_block


def test_admin_restart_uses_two_step_handoff() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    restart_block = ui_source.split("def _restart_as_admin", 1)[1].split("def _show_page", 1)[0]

    assert "def _show_admin_restart_confirmation" in ui_source
    assert "Admin-Fenster oeffnen" in ui_source
    assert "def _show_admin_handoff" in ui_source
    assert "Dieses Fenster schliessen" in ui_source
    assert "Admin-Neustart an Windows uebergeben" in restart_block
    assert "messagebox.showinfo" not in restart_block


def test_main_logs_startup_errors() -> None:
    main_source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(encoding="utf-8")

    assert "def _write_startup_error" in main_source
    assert "startup-error.log" in main_source
    assert "from app.ui import TuningForgeApp" in main_source
    assert "except Exception as exc" in main_source


def test_program_page_has_treeview_table_and_search() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "package_search_text" in ui_source
    assert "textvariable=self.package_search" not in ui_source
    assert "def _package_table" in ui_source
    assert "def _toggle_package_tree_checkbox" in ui_source
    assert "text=\"Alle sichtbaren auswaehlen\"" in ui_source
    assert "text=\"Sichtbare leeren\"" in ui_source
    assert "PACKAGE_CATEGORY_ORDER" in ui_source


def test_package_table_actions_do_not_rebuild_page() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")
    select_block = ui_source.split("def _select_visible_packages", 1)[1].split("def _clear_visible_packages", 1)[0]
    clear_block = ui_source.split("def _clear_visible_packages", 1)[1].split("def _refresh_package_tree", 1)[0]

    assert "self._show_page(2)" not in select_block
    assert "self._show_page(2)" not in clear_block
    assert "_refresh_package_tree" in select_block
    assert "_refresh_package_tree" in clear_block


def test_console_output_is_pruned_for_performance() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "MAX_CONSOLE_LINES" in ui_source
    assert "CONSOLE_PRUNE_LINES" in ui_source
    assert "text_widget.delete(\"1.0\"" in ui_source


def test_uninstall_page_uses_treeview_table_for_large_scans() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "ttk.Treeview" in ui_source
    assert "def _program_table" in ui_source
    assert "def _toggle_uninstall_tree_checkbox" in ui_source
    assert "\"checked\"" in ui_source
    assert "self._show_page(8)" not in ui_source.split("def _select_all_uninstall", 1)[1].split("def _clear_update_scan", 1)[0]


def test_updates_page_uses_treeview_table_with_checkbox_column() -> None:
    ui_source = (Path(__file__).resolve().parent.parent / "app" / "ui.py").read_text(encoding="utf-8")

    assert "def _update_table" in ui_source
    assert "def _toggle_update_tree_checkbox" in ui_source
    assert "def _update_tree_values" in ui_source
    assert "self._show_page(11)" not in ui_source.split("def _select_all_updates", 1)[1].split("def _clear_uninstall_scan", 1)[0]
