# Changelog

## 0.9.2

- SystemInfoForge Preview ergaenzt: MSINFO32-TXT-Export als lokaler Systeminventar-Baustein.
- Neuer Core `core.system_info` mit sicherem Exportpfad unter `reports/systeminfo`, Timeout-Schutz, Status, Dateigroesse, Laufzeit, Exit-Code, Fehler und Dry-Run.
- Neue SystemInfo-Seite mit `Export vorbereiten`, `MSINFO32 TXT exportieren` und `Ordnerpfad anzeigen`.
- ControlDeck zeigt `SystemInfo` als Karte und Modul.
- Session-Reports enthalten `system_info`; TXT-Reports zeigen Exportpfad, Status, Dateigroesse und Agent-Auswertungs-Hinweis.
- Kein Export beim App-Start, keine Auto-Analyse-Integration, keine Cloud und keine automatische Codex-/Agent-Auswertung.

## 0.9.1

- Dry-Run Executor-Gating aktiviert: Setup, Tuning, Uninstall und Updates werden bei aktivem Testmodus simuliert statt ausgefuehrt.
- Neuer Core `core.dry_run` erzeugt kompatible `dry_run`-Resultate fuer Setup-Actions, TuningResults und MaintenanceResults.
- Startpfade pruefen den Testmodus nach Auswahl/Vorschau/Bestaetigung, aber vor `WingetExecutor`, `TuningExecutor` und `WingetMaintenance`-Ausfuehrung.
- Reports markieren simulierte Aktionen mit Status `dry_run` und `Testmodus: nicht ausgefuehrt`.
- Keine winget-Install-/Upgrade-/Uninstall-Kommandos und keine Tuning-Kommandos werden im Testmodus gestartet.

## 0.9.0

- ConfigDeck Preview ergaenzt: lokale DEVHub-Konfiguration unter `config/devhub-config.json`.
- Neuer Core `core.configuration` mit strenger Validierung, Import/Export, Testmodus-Markierung, Auto-Analyse-Schalter, Preset-Merken-Schalter, Reportmodus und aktivierten Modul-IDs.
- ControlDeck zeigt `Konfiguration` als Statuskarte und Modul.
- Neue Konfigurationsseite mit sicheren Buttons `Konfiguration speichern`, `Konfiguration importieren` und `Konfiguration exportieren`.
- Auto-Analyse beim Start und Preset-Wiederherstellung respektieren die lokale Konfiguration.
- Session-Reports koennen Konfigurationsstatus aufnehmen.
- Testmodus ist in v0.9.0 sichtbar und reportbar; die harte Executor-Simulation fuer Setup/Tuning/Uninstall/Updates folgt als eigener sicherer Schnitt.

## 0.8.0

- AlertDeck/Tagesbericht Preview ergaenzt: lokale Hinweise und Tageszusammenfassung aus Session-Reports, Risk Engine und Auto-Analyse.
- Neuer Core `core.alerting` mit AlertItem und DailyReportSummary fuer Aktionen, Fehler, Warnungen, kritische Hinweise und Empfehlungen.
- ControlDeck zeigt `Tagesbericht` als Statuskarte und Modul.
- Neue Tagesbericht-Seite mit performanter `ttk.Treeview`-Tabelle und sicheren Buttons `Tagesbericht aktualisieren` und `Reportpfad anzeigen`.
- Session-Reports koennen Tagesbericht-Snapshots aufnehmen.
- Keine Windows-Notifications, kein Scheduler, kein Hintergrunddienst und keine automatischen Aktionen in v0.8.0.

## 0.7.0

- Risk Engine Preview ergaenzt: zentrale Read-only-Bewertung aus ErrorDoctor, GuardForge, Offline Cache, RecoveryForge, Scan-Hinweisen und letztem Session-Report.
- Neuer Core `core.risk_engine` mit RiskSummary, RiskFinding, Score, Gesamtlevel und Hoch-/Mittel-/Niedrig-Zaehlern.
- ControlDeck zeigt `Risk Engine` als Statuskarte und Modul; neue Risk-Engine-Seite nutzt eine performante `ttk.Treeview`-Tabelle.
- Session-Reports koennen Risk-Engine-Status und Empfehlungen aufnehmen.
- Keine automatischen Aktionen, keine Auto-Fixes, keine Downloads, keine Installationen und keine Systemaenderungen durch die Risk Engine.

## 0.6.0

- RecoveryForge Alpha ergaenzt: lokale Recovery-Ziele werden als Preview ausgewertet.
- Neuer Core `core.recovery` fuer Recovery-Root, Standardziele, Status `present`, `missing`, `invalid` und Warnungen.
- ControlDeck zeigt `RecoveryForge` als Statuskarte und Modul.
- Neue RecoveryForge-Seite mit performanter `ttk.Treeview`-Tabelle und sicheren Buttons `Preview aktualisieren` und `Recovery-Pfad anzeigen`.
- Session-Reports koennen RecoveryForge-Status und Warnungen aufnehmen.
- Keine automatischen Backups, keine Restore-Aktionen, kein Kopieren, kein Loeschen und keine Restore-Points in v0.6.0.

## 0.5.0

- Offline Installer Cache Preview ergaenzt: lokale Struktur `cache/installers` mit Index `installer-cache.json`.
- Neuer Core `core.offline_cache` fuer Cache-Index, SHA256-Hashing, Status `missing`, `present`, `stale` und `invalid`.
- ControlDeck zeigt `Offline Cache` als Modul und Statuskarte.
- Neue Offline-Cache-Seite mit performanter `ttk.Treeview`-Tabelle, `Cache pruefen`, `Index aktualisieren` und `Ordnerpfad anzeigen`.
- Session-Reports koennen Cache-Status und Warnungen aufnehmen; Auto-Analyse zaehlt Cache-Status read-only mit.
- Kein Download, keine Installation, kein Loeschen und keine Datei-Ersetzung in v0.5.0.

## 0.4.2

- ControlDeck-Layout von verschachtelten Card-Frames auf performantere Tabellenbereiche umgestellt.
- Sichtbaren Layer-/Randfehler unter der Modulzentrale behoben, indem innere Modul-Cards nicht mehr in einer aeusseren Card gerendert werden.
- Statusuebersicht und Modulzentrale nutzen jetzt `ttk.Treeview`; Module koennen per Button oder Doppelklick geoeffnet werden.
- UI-Regressionschecks sichern ab, dass keine verschachtelten Modul-Cards mehr im ControlDeck-Renderpfad liegen.

## 0.4.1

- Auto-Analyse Preview beim App-Start ergaenzt: sichere lokale Read-only-Checks laufen im Hintergrund nach UI-Initialisierung.
- Neuer Core `core.auto_analysis` mit Status, Start-/Endzeit, Dauer, Findings, Warnungen, Report-Fehlern und Preset-Status.
- ControlDeck zeigt Auto-Analyse als eigene Karte und Modulbereich.
- Session-Reports koennen Auto-Analyse-Status aufnehmen, erzwingen aber keinen Report nur durch App-Start.
- Safety-Regressions: Auto-Analyse startet keine Setup-, Tuning-, Uninstall-, Update-, Scan- oder GuardForge-Preview-Aktionen.

## 0.4.0

- ControlDeck zur Modulzentrale ausgebaut: Profile, TuningForge, Repair/Tuning, GuardForge, ErrorDoctor und Reports werden als eigene Modulbereiche angezeigt.
- Neuer read-only Dashboard-Core `core.dashboard` fuer Karten, Module, Empfehlungen und Session-Report-Fehlerauswertung.
- ControlDeck zeigt das aktive Preset, Paket-/Tuning-Auswahl, GuardForge-Findings, Diagnose-Status und letzten Session-Report zentral an.
- ControlDeck-Aktionen bleiben Navigation, Profilimport oder Profilexport; Setup, Tuning, Updates, Uninstall, Scans und GuardForge-Preview werden nicht direkt gestartet.
- Dashboard-Tests und UI-Regressionschecks fuer Modulzentrale, Report-Auswertung und Safety-Grenzen ergaenzt.

## 0.3.1

- Letztes Preset wird lokal in `config/app-state.json` gespeichert.
- Beim Start wird das zuletzt gewaehlte eingebaute Profil oder der zuletzt importierte Profilpfad wiederhergestellt.
- Ungueltige, fehlende oder Remote-State-Dateien werden ignoriert; die App faellt sicher auf das Developer-Profil zurueck.
- Profilimport und Profilwahl starten weiterhin keine Aktionen automatisch.

## 0.3.0

- DEVHub-Profilformat `.devhub-profile.json` ergaenzt mit Profilversion, Name, Beschreibung, Paket-Auswahl, Tuning-Auswahl, GuardForge-Schutzbereichen, Erstellzeit und App-Version.
- Sicherer Import/Export-Core ergaenzt: strenges JSON-Schema, keine unbekannten Felder, keine Remote-URLs, keine Script-/Installer-Pfade fuer GuardForge.
- Profilimport akzeptiert nur bekannte lokale Paket- und Tuning-IDs; unbekannte IDs werden ignoriert und als Warnung angezeigt.
- Neue Buttons `Profil importieren` und `Profil exportieren` im ControlDeck- und Profil-Kontext.
- Import setzt nur Auswahl und GuardForge-Preview-Konfiguration. Setup, Tuning, Updates, Uninstall und GuardForge-Aktionen starten weiterhin nie automatisch.
- Session-Reports enthalten importiertes Profil, Importpfad, Exportpfad und Import-Warnungen.
- Bekannte Einschraenkung: Profile bleiben lokale Dateien; kein Cloud-Sync, kein Marketplace und keine Remote-Profile.

## 0.2.0

- GuardForge Alpha ergaenzt: Schutzbereiche, Mock-FileWatchProvider, FileWatchEvents und Risk-Findings.
- GuardForge-Risk-Scoring erkennt viele Loeschungen, viele Aenderungen, Extension-Aenderungen und ausfuehrbare Dateien in sensiblen Bereichen.
- Neue GuardForge-Seite mit Alpha-/Preview-Hinweis; keine permanente Ueberwachung, kein Autostart, kein Blockieren, kein Loeschen und kein Netzwerk.
- Session-Reports enthalten GuardForge-Findings in JSON und TXT.
- App startet maximiert.
- Admin-Neustart bevorzugt im Dev-Modus `pythonw.exe`, um ein sichtbares CMD-Fenster zwischen UAC und Admin-GUI zu vermeiden.

## 0.1.10

- ErrorDoctor Accuracy Polish: Diagnose-Findings enthalten jetzt Status, Quelle, Fund-Zeitstempel und letzten erfolgreichen App-Start.
- Alte `startup-error.log`-Findings werden als historisch markiert, wenn danach ein erfolgreicher Start in `tuningforge.log` steht.
- ControlDeck zaehlt nur aktive Diagnose-Findings als Warnung; historische Findings werden als Info behandelt.
- Diagnose-Seite und Session-Reports trennen aktive und historische Findings.

## 0.1.9

- ErrorDoctor als lokales Diagnosemodul ergaenzt.
- Diagnose-Findings fuer Tcl/Tk, WindowsApps-Python-Alias, lokale Python-Stoerdateien, fehlendes winget, Admin-/Zugriffsprobleme, PyInstaller, pip Timeout und gesperrte pytest-Temp-Ordner.
- Neue Diagnose-Seite im ControlDeck-Kontext ohne Auto-Fixes oder Systemaenderungen.
- Session-Reports enthalten eine `diagnostics`-Sektion und lesbare Diagnose-Hinweise im TXT-Bericht.

## 0.1.8

- Produktnamen zentralisiert: neue UI-, Log-, Report- und Metadaten verwenden konsistent `DEVHub TuningForge`.
- Neue Report-Dateinamen: `tuningforge-*` fuer Setup-Berichte und `devhub-session-*` fuer Session-Berichte.
- Datei-Log fuer neue Runs auf `logs/tuningforge.log` umgestellt.
- Erstes DEVHub-Modulmanifest fuer ControlDeck, TuningForge, GuardForge, ScanForge, RecoveryForge und AgentDeck ergaenzt.
- Zentrales SafetyGate fuer v0.1.x eingefuehrt: High-Risk/blocked bleibt gesperrt, mittlere Risiken brauchen zweite Bestaetigung und duerfen nicht default sein.

## 0.1.7

- Schnellfixe erweitert: Benutzer-Temp-Cleaner, Windows-Komponentencache-Bereinigung und RAMBoost/Idle-Tasks.
- Temp- und Systemcache-Cleanups bleiben mittleres Risiko, nicht default, und brauchen die bestehende zweite Bestaetigung.

## 0.1.6

- Repair-First Fixing Pack ergaenzt: winget Quellen, DISM/SFC, Winsock, DNS und Datentraegerdiagnose.
- Tuning-Aktionen um optionale Felder `requires_reboot`, `duration_hint` und `impact` erweitert.
- Strenges Sicherheitsmodell: mittlere Risiken sind nicht default und brauchen vor dem Start eine zweite Bestaetigung.
- Tuning-UI zeigt Wirkung, Dauer, Risiko und Neustart-Hinweis; Reports enthalten die neuen Felder.

## 0.1.5

- `scripts/build_portable.cmd` Batch-Quoting korrigiert, damit `python -c` in CMD nicht falsch zerlegt wird.

## 0.1.4

- Portable-Build robuster gemacht: `build_portable.ps1` sucht echte Python-Interpreter und ignoriert WindowsApps-Aliase.
- Optionaler Parameter `-PythonExe` fuer explizite Python-Pfade ergaenzt.
- `scripts/build_portable.cmd` hinzugefuegt, damit der Build eigenstaendig direkt aus CMD gestartet werden kann.

## 0.1.3

- Admin-Gate auf zweistufigen Ablauf umgestellt: erst bestaetigen, danach wird das Admin-Fenster angefordert.
- Nach erfolgreicher UAC-Uebergabe zeigt das alte Fenster eine Rueckfallseite mit Button `Dieses Fenster schliessen`.
- Info-Dialog nach Admin-Uebergabe entfernt, damit der Ablauf klar im Hauptfenster bleibt.

## 0.1.2

- Admin-Neustart robuster gemacht: Das aktuelle Fenster bleibt offen, falls UAC/Admin-Start nicht sichtbar wird.
- Statusmeldung und Info-Dialog nach erfolgreicher UAC-Uebergabe ergaenzt.
- Regressionstest ergaenzt, damit `_restart_as_admin` die App nicht mehr direkt schliesst.
- Lokale 0-Byte-Stoerdatei `python` aus dem Projekt entfernt, damit der echte Python-Interpreter wieder gefunden werden kann.
- Bekannte Einschraenkung: Auf diesem System zeigen `python.exe` und `py.exe` aktuell auf WindowsApps-Aliase; fuer Tests ist der echte Interpreter unter `C:\Users\info\AppData\Local\Python\bin\python.exe` nutzbar.

## 0.1.1

- Portable-Build vorbereitet: Ressourcen werden aus dem PyInstaller-Bundle gelesen, Logs und Reports neben der EXE geschrieben.
- Build-Script fuer `DEVHub TuningForge` ergaenzt und Runtime-Ordner `logs/` und `reports/` nach dem Build angelegt.
- Tk/Tcl-Build-Preflight dokumentiert, damit eine kaputte lokale Python/Tkinter-Installation keine defekte EXE erzeugt.
- Bekannte Einschraenkung: Der lokale Python-Interpreter muss `tkinter.Tk()` erfolgreich starten koennen, bevor PyInstaller eine gueltige GUI-EXE bauen kann.

## 0.1.0

- Initialer MVP fuer DEVHub SetupForge.
- Deutsche CustomTkinter-Wizard-Oberflaeche.
- Profilbasierte Programmauswahl.
- Sichere Vorschau vor Installation.
- `winget`-Executor mit Live-Log und Status je Paket.
- JSON- und TXT-Berichte pro Lauf.
