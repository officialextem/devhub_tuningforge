# DEVHub TuningForge

DEVHub TuningForge ist ein sicherer Windows-Setup-, Tuning- und Maintenance-Assistent fuer frische Windows-Installationen. Alle Bereiche folgen dem gleichen Ablauf: Auswahl, Vorschau, expliziter Start, Laufansicht mit Fortschritt/Console und Bericht.

## Start

```powershell
python -m pip install -e ".[dev]"
python -m app.main
```

Falls `python` auf den WindowsApps-Stub zeigt oder nach einem Python-Uninstall nicht mehr startet:

```powershell
& "$env:LOCALAPPDATA\Python\bin\python.exe" -m pip install -e ".[dev]"
& "$env:LOCALAPPDATA\Python\bin\python.exe" -m app.main
```

Wenn `where python` im Projektordner zuerst eine Datei im Projekt selbst zeigt, blockiert eine lokale Stoerdatei den Interpreter. Diese Datei gehoert nicht zum Projekt.

Die App erwartet aktuell einen Admin-Start. Ohne Adminrechte erscheint ein Start-Hinweis mit Neustart-Schaltflaeche.

## Aktuelle Bereiche

- ControlDeck: performante Tabellen-Modulzentrale mit Admin-/winget-Status, aktivem Preset, TuningForge, GuardForge, ErrorDoctor, Reports und lokalen Empfehlungen.
- Auto-Analyse Preview: sichere lokale Read-only-Checks laufen nach dem App-Start im Hintergrund und aktualisieren ControlDeck.
- Offline Installer Cache Preview: lokale Installer-Dateien unter `cache/installers` pruefen und indexieren, ohne Download oder Installation.
- RecoveryForge Alpha: lokale Recovery-Ziele als Preview pruefen, ohne Backup, Restore, Kopieren oder Loeschen.
- Risk Engine Preview: zentrale Read-only-Bewertung aus Diagnose, GuardForge, Offline Cache, RecoveryForge, Scan-Hinweisen und Reports.
- Tagesbericht Preview: lokale Hinweise, Warnungen und Tageszusammenfassung aus Session-Reports, Risk Engine und Auto-Analyse.
- Konfiguration/Testmodus Preview: lokale DEVHub-Konfiguration, Testmodus-Markierung, Auto-Analyse-Schalter, Preset-Merken und Import/Export.
- Dry-Run Executor-Gating: bei aktivem Testmodus werden Setup, Tuning, Updates und Uninstall simuliert und reportet.
- SystemInfoForge Preview: manueller MSINFO32-TXT-Export fuer spaetere Codex-/Agent-Auswertung des lokalen Systems.
- Profilimport/-export: lokale `.devhub-profile.json`-Profile speichern und laden Paket-Auswahl, Tuning-Auswahl und GuardForge-Preview-Schutzbereiche.
- Letztes Preset: die App merkt sich lokal das zuletzt gewaehlte eingebaute Profil oder den zuletzt importierten Profilpfad.
- Setup: Programme per Profil auswaehlen und nach Vorschau mit `winget install` installieren.
- Programme: performante Tabellenansicht mit Checkbox-Spalte, Suche und optionalen Bereichen fuer Gaming, Creator, Medien, Office/Finanzen, Trading/Crypto und Kommunikation.
- Tuning: Repair-First-Aktionen fuer DNS, Temp Cleaner, Systemcache, RAMBoost/Idle-Tasks, winget Quellen, DISM/SFC, Winsock und Datentraegerdiagnose mit Risiko-, Dauer- und Neustart-Hinweisen.
- Uninstall: scannt `winget list` ohne user-only Scope, zeigt Vorschau und verlangt direkt vor dem Start eine zweite Bestaetigung.
- Updates: scannt `winget upgrade` ohne user-only Scope, zeigt eine performante Checkbox-Tabelle, Vorschau und installiert ausgewaehlte Updates.
- Diagnose: ErrorDoctor erkennt bekannte lokale Python-, Tk/Tcl-, Build-, Admin-, winget- und pytest-Probleme und zeigt sichere Empfehlungen.
- GuardForge Alpha: lokale Datei-Event-Preview mit Mock-Daten, Schutzbereichen und Risk-Findings ohne permanente Ueberwachung.

## Sicherheit im MVP

- Keine Registry-Tweaks
- Kein CPU-Boost-/Windows-11-Power-Tuning in v0.1.x
- Keine Remote-Funktionen
- Keine Installation ohne Vorschau und Bestaetigung
- Keine automatische Aktion beim Oeffnen einer Laufseite
- ControlDeck startet keine systemveraendernden Aktionen direkt; Modulbuttons navigieren nur zu den passenden Seiten
- Auto-Analyse liest nur lokale Statusdaten, Logs, Presets und Reports; sie startet keine Setup-, Tuning-, Update-, Uninstall-, Scan- oder GuardForge-Aktionen
- Offline Cache prueft nur lokale Dateien im Cache-Ordner; kein Download, keine Installation, kein Loeschen, keine Datei-Ersetzung
- RecoveryForge prueft nur lokale Zielpfade; kein Backup, kein Restore, kein Kopieren, kein Loeschen, keine Restore-Points
- Risk Engine bewertet nur vorhandene lokale Zustandsdaten; keine Auto-Fixes, keine Downloads, keine Installationen und keine Systemaenderungen
- Tagesbericht liest nur lokale Session-Reports; keine Windows-Notifications, kein Scheduler, kein Hintergrunddienst und keine automatischen Aktionen
- Konfiguration setzt nur lokale Einstellungen; Import startet keine Aktionen und akzeptiert keine unbekannten Felder, keine Remote-URLs und keine unbekannten Modul-IDs
- Testmodus blockiert echte Setup-, Tuning-, Update- und Uninstall-Ausfuehrung und erzeugt stattdessen `dry_run`-Reports
- SystemInfo exportiert nur nach Nutzerklick lokal unter `reports/systeminfo`; kein Auto-Start, keine Cloud, keine automatische Agent-Auswertung
- Kein Profilimport startet Setup, Tuning, Updates, Uninstall oder GuardForge-Aktionen automatisch
- Profilimporte akzeptieren nur bekannte lokale Paket- und Tuning-IDs; unbekannte IDs werden als Warnung protokolliert
- Profile duerfen keine Remote-URLs, keine Script-/Installer-Pfade fuer GuardForge und keine unbekannten JSON-Felder enthalten
- Die letzte Preset-Auswahl wird nur lokal unter `config/app-state.json` gespeichert; ungueltige oder Remote-Pfade werden ignoriert
- Navigation bleibt frei, wird aber waehrend aktiver Scans/Laeufe gesperrt
- Uninstall und Updates nutzen einen Geraete-Scan ohne `--scope user`; jede Aenderung braucht Vorschau und expliziten Start
- Tuning-Aktionen mit mittlerem Risiko sind nicht vorausgewaehlt und brauchen vor dem Start eine zweite Bestaetigung

## Logs und Reports

- Live-Console: farbige Level fuer INFO, SUCCESS, WARNING und ERROR.
- Datei-Log: `logs/tuningforge.log` als plain text ohne ANSI-Farben.
- Einzelner Setup-Bericht: `tuningforge-*.json/.txt` in `reports/`.
- Session-Bericht: `devhub-session-*.json/.txt` in `reports/` mit Setup, Tuning, Uninstall, Updates, Fehlern, Exit-Codes und Scan-Hinweisen.
- Fehlerdiagnose: bekannte Exit-Codes bekommen Hinweise; fehlgeschlagene Aktionen enthalten Ausgabe-Auszuege im Session-Bericht.
- ErrorDoctor-Findings erscheinen im Session-Bericht unter `Diagnose`.
- GuardForge-Preview-Findings erscheinen im Session-Bericht unter `GuardForge`.
- Profilimport/-export erscheint im Session-Bericht mit Importpfad, Exportpfad und Import-Warnungen.
- Risk-Engine-Ergebnisse erscheinen im Session-Bericht unter `Risk Engine`.
- Tagesbericht-Snapshots erscheinen im Session-Bericht unter `Tagesbericht Preview`.
- Konfigurationsstatus erscheint im Session-Bericht unter `Konfiguration`.
- SystemInfo-/MSINFO32-Exporte erscheinen im Session-Bericht unter `SystemInfo / MSINFO32`.

## DEVHub Modulbasis

- TuningForge fuehrt jetzt zentrale Produkt- und Dateinamen aus `core.app_config`.
- `core.modules` beschreibt die DEVHub-Bausteine ControlDeck, TuningForge, GuardForge, ScanForge, RecoveryForge und AgentDeck als erste Plug-and-play-Manifeste.
- `core.dashboard` erzeugt in v0.4.0 read-only Karten, Modulstatus und Empfehlungen fuer ControlDeck.
- `core.auto_analysis` erzeugt in v0.4.1 read-only Startanalyse-Snapshots fuer ControlDeck und Session-Reports.
- `core.offline_cache` erzeugt in v0.5.0 den lokalen Installer-Cache-Index und prueft Dateien read-only.
- `core.recovery` erzeugt in v0.6.0 RecoveryForge-Preview-Ziele und prueft sie read-only.
- `core.risk_engine` erzeugt in v0.7.0 eine zentrale Read-only-Risikobewertung aus vorhandenen Modul- und Reportdaten.
- `core.alerting` erzeugt in v0.8.0 lokale Alert- und Tagesbericht-Snapshots aus vorhandenen Reports und Risk-Daten.
- `core.configuration` erzeugt in v0.9.0 lokale DEVHub-Konfigurationen mit strenger Validierung und Import/Export.
- `core.system_info` erzeugt in v0.9.2 lokale MSINFO32-TXT-Exports fuer spaetere Agent-Auswertung.
- `core.safety` kapselt die v0.1.x-Sicherheitsregeln: niedrige Risiken sind erlaubt, mittlere Risiken brauchen zweite Bestaetigung, High-Risk/blocked bleibt gesperrt.
- `core.profile_io` bildet in v0.3.0 den ersten lokalen Plug-and-play-Konfigurationsbaustein fuer exportierbare DEVHub-Profile.
- Die Manifest- und Safety-Struktur ist vorbereitet, fuehrt aber noch keine neuen Hintergrund-, Remote- oder Ueberwachungsaktionen aus.

## ControlDeck Modulzentrale

- Zeigt eine kompakte Statusuebersicht fuer Admin, winget, Preset, Inventar, Updates, Diagnose, GuardForge, Auto-Analyse, Offline Cache, RecoveryForge, Risk Engine, Tagesbericht, Konfiguration, SystemInfo und Reports.
- Zeigt eine performante Modultabelle fuer Auto-Analyse, Profile, TuningForge, Repair/Tuning, GuardForge, Offline Cache, RecoveryForge, Risk Engine, Tagesbericht, Konfiguration, SystemInfo, ErrorDoctor und Reports.
- Vermeidet verschachtelte Card-Frames im ControlDeck, damit kein doppelter Layer/Rand sichtbar wird und die Startseite schneller rendert.
- Liest den neuesten Session-Report und hebt Fehler, Warnungen und offene Diagnose-/GuardForge-Hinweise hervor.
- Nutzt das gespeicherte letzte Preset aus `config/app-state.json`.
- Bleibt read-only: keine Installation, kein Tuning, kein Uninstall, kein Update, kein Scan und keine GuardForge-Preview startet direkt aus dem Dashboard.

## Auto-Analyse Preview

- Startet nach UI-Initialisierung im Hintergrund.
- Prueft Adminstatus, winget-Erreichbarkeit, gespeichertes Preset, letzte Session-Reports, ErrorDoctor-Findings und vorhandene GuardForge-Preview-Findings.
- Zeigt Status `bereit`, `laeuft`, `abgeschlossen` oder `fehlgeschlagen` im ControlDeck.
- Schreibt keinen eigenen Report nur durch App-Start; vorhandene Session-Reports koennen den letzten Auto-Analyse-Status aufnehmen.
- Bleibt strikt read-only und fuehrt keine Reparatur-, Installations-, Update-, Uninstall-, Cleanup-, Watchdog- oder Netzwerkaktionen aus.

## Offline Installer Cache Preview

- Nutzt `cache/installers` als lokalen Cache-Ordner.
- Nutzt `cache/installers/installer-cache.json` als Index mit Paket-ID, Name, Quelle, Dateipfad, Groesse, SHA256, Status und Zeitstempel.
- Statuswerte: `missing`, `present`, `stale`, `invalid`.
- `Cache pruefen` liest den bestehenden Index und prueft lokale Dateien read-only.
- `Index aktualisieren` indexiert vorhandene lokale Installer-Dateien im Cache-Ordner.
- `Ordnerpfad anzeigen` zeigt nur den lokalen Pfad an.
- Kein Download, keine Installation, kein Loeschen und keine Datei-Ersetzung in v0.5.0.

## RecoveryForge Alpha

- Nutzt `recovery/` als geplanten lokalen Recovery-Root.
- Prueft wichtige lokale Ziele wie App-State, Profile, Paketkatalog, Tuning-Aktionen, Reports, Logs und Offline-Cache-Index.
- Statuswerte: `present`, `missing`, `invalid`.
- `Preview aktualisieren` liest nur lokale Pfade und aktualisiert die Tabelle.
- `Recovery-Pfad anzeigen` zeigt nur den geplanten lokalen Recovery-Root.
- Kein Backup, kein Restore, kein Kopieren, kein Loeschen und keine Restore-Points in v0.6.0.

## Risk Engine Preview

- Buendelt vorhandene lokale Hinweise aus ErrorDoctor, GuardForge, Offline Cache, RecoveryForge, Scan-Hinweisen und dem letzten Session-Report.
- Erzeugt ein Gesamtlevel `niedrig`, `mittel` oder `hoch` plus Score und Finding-Zaehler.
- `Risk neu bewerten` liest nur aktuellen Session-State und lokale Reportdaten.
- Die Seite nutzt eine `ttk.Treeview`-Tabelle fuer Finding, Risiko, Quelle, Detail und Empfehlung.
- Keine Aktionen, keine Auto-Fixes, keine Downloads, keine Installationen und keine Systemaenderungen in v0.7.0.

## Tagesbericht Preview

- Liest lokale `devhub-session-*.json`-Reports fuer den aktuellen Tag.
- Buendelt Aktionen, Fehler, Warnungen, Risk-Engine-Hinweise und Auto-Analyse-Fehler.
- Erzeugt lokale Alert-Level `info`, `warning` und `critical`.
- `Tagesbericht aktualisieren` berechnet nur den lokalen Snapshot neu.
- `Reportpfad anzeigen` zeigt nur den lokalen Report-Ordner.
- Keine Windows-Notifications, kein Scheduler, kein Hintergrunddienst und keine automatischen Aktionen in v0.8.0.

## Konfiguration / Testmodus Preview

- Nutzt `config/devhub-config.json` als lokale DEVHub-Konfiguration.
- Felder: `dry_run_enabled`, `auto_analysis_enabled`, `remember_last_preset`, `default_report_mode`, `enabled_modules`, `app_version`.
- `Konfiguration speichern` schreibt nur lokale Einstellungen.
- `Konfiguration importieren` validiert streng und startet keine Aktionen.
- `Konfiguration exportieren` schreibt `.devhub-config.json`.
- `auto_analysis_enabled=false` verhindert die automatische Startanalyse.
- `remember_last_preset=false` verhindert Speichern und Wiederherstellen des letzten Presets.
- `dry_run_enabled=true` simuliert Setup, Tuning, Uninstall und Updates, ohne `winget`- oder Tuning-Kommandos zu starten.
- Simulierte Ergebnisse erhalten Status `dry_run` und erscheinen in Setup-/Session-Reports.

## SystemInfoForge Preview

- Nutzt `reports/systeminfo/` als lokalen Exportordner.
- Erzeugt TXT-Reports ueber `msinfo32 /report <pfad>`.
- `Export vorbereiten` zeigt nur den geplanten Zielpfad.
- `MSINFO32 TXT exportieren` startet den Export nur nach Nutzerklick.
- Testmodus erzeugt nur `dry_run`-Metadaten und startet kein `msinfo32`.
- Session-Reports enthalten Status, Exportpfad, Dateigroesse, Dauer, Exit-Code und Fehler.
- Keine automatische Codex-/Agent-Auswertung, keine Cloud und kein Export beim App-Start in v0.9.2.

## Profilimport/-export

- Export schreibt lokale Dateien mit der Endung `.devhub-profile.json`.
- Das Profil enthaelt nur Konfiguration: Name, Beschreibung, Paket-IDs, Tuning-IDs, GuardForge-Preview-Pfade, Erstellzeit und App-Version.
- Import setzt bekannte Paket- und Tuning-Auswahl sowie GuardForge-Preview-Pfade.
- Unbekannte Paket- oder Tuning-IDs werden ignoriert und als Warnung in UI und Session-Report gefuehrt.
- Nach jedem Import bleiben Vorschau und expliziter Start erforderlich.
- Der zuletzt importierte Profilpfad wird beim naechsten Start wieder geladen, wenn die Datei noch existiert und valide ist.
- Eingebaute Profilwahlen werden ebenfalls als letztes Preset gespeichert.
- Kein Cloud-Sync, keine Remote-Profile, kein Marketplace und keine Script-Ausfuehrung in v0.3.0.

## GuardForge Alpha

- Bereitet lokale Schutzbereiche wie Documents, Desktop, Downloads und den DEVHub-Projektordner vor.
- Nutzt in v0.2.0 nur Mock-/Preview-Events.
- Erkennt Muster wie viele Loeschungen, viele Aenderungen, Extension-Aenderungen und ausfuehrbare Dateien in sensiblen Bereichen.
- Fuehrt keine permanente Ueberwachung, keinen Autostart, kein Blockieren, kein Loeschen, keine Quarantaene und keine Netzwerkuebertragung aus.
- Die App startet maximiert; im Dev-Modus nutzt der Admin-Neustart bevorzugt `pythonw.exe`, damit kein zusaetzliches CMD-Fenster sichtbar wird.

## ErrorDoctor

- Erkennt bekannte lokale Fehlerbilder wie defektes Tcl/Tk, WindowsApps-Python-Aliase, lokale `python`-Stoerdateien, fehlendes `winget`, fehlende Adminrechte, PyInstaller-/pip-Probleme und gesperrte pytest-Temp-Ordner.
- Markiert alte Startup-Fehler als historisch, wenn danach ein erfolgreicher Start in `logs/tuningforge.log` liegt.
- Liest nur lokale Statusdaten, Logs und Scan-Hinweise.
- Fuehrt keine Auto-Fixes aus und aendert keine Dateien.
- Empfohlener Testlauf bei gesperrtem Standard-Temp:

```powershell
python -m pytest --basetemp=work/pytest-tmp-v092
```

## Paketkatalog

- Neue Katalogbereiche sind optional sichtbar und werden nicht automatisch in bestehende Profile aufgenommen.
- Empfehlungstags wie Gaming, Creator, Office oder ExTeM dienen nur als Orientierung.
- PDFgear/PDF24 wurden noch nicht aufgenommen, weil `winget search` in der aktuellen Codex-Umgebung nicht zugreifbar war. Vor Aufnahme lokal eindeutig per Winget-ID pruefen.

## Tests

```powershell
python -m pytest
```

## Portable Build

Empfohlen aus CMD:

```cmd
scripts\build_portable.cmd
```

Bei mehreren Python-Versionen kann ein expliziter Interpreter uebergeben werden:

```cmd
scripts\build_portable.cmd C:\Pfad\zu\python.exe
```

Alternativ aus PowerShell mit explizitem Python-Pfad:

```powershell
.\scripts\build_portable.ps1 -PythonExe "C:\Pfad\zu\python.exe"
```

- Kataloge und Profile werden in die EXE gebuendelt.
- `reports\` und `logs\` werden neben der EXE angelegt und dort beschrieben.
- Der Build liegt unter `dist\DEVHub TuningForge\`.
- Der Build prueft vorab `tkinter.Tk()`. Wenn Python meldet `Can't find a usable init.tcl`, ist die lokale Python-Tcl/Tk-Installation defekt oder unvollstaendig. Dann Python reparieren/neu installieren und dabei Tcl/Tk aktivieren, danach den Build erneut starten.

## Roadmap

- v0.2.0: GuardForge Alpha / Datei-Event-Preview
- v0.3.0: Profilimport/-export
- v0.4.0: DEVHub Dashboard Integration
- v0.4.1: Auto-Analyse Preview
- v0.5.0: Offline Installer Cache
- v0.6.0: Recovery Builder Alpha
- v0.7.0: Risk Engine Preview
- v0.8.0: Alarmierung / Tagesberichte Preview
- v0.9.0: Konfiguration / Testmodus
- v0.9.1: Dry-Run Executor-Gating fuer Setup, Tuning, Updates und Uninstall
- v0.9.2: MSINFO32 SystemInfo Export Preview
- v0.9.3: Agent-Auswertung Preview fuer SystemInfo
- v1.0.0: Stabiler modularer MVP
