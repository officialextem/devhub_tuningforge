from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re


WINGET_EXIT_HINTS = {
    2316632070: "Winget-Installerfehler: App schliessen, Neustart pruefen und danach erneut ausfuehren.",
    1602: "Installation wurde abgebrochen.",
    1603: "Installerfehler: haeufig durch laufende App, fehlende Rechte oder blockierten Installer.",
    3010: "Installation erfolgreich, Neustart erforderlich.",
}


@dataclass(frozen=True)
class DiagnosticFinding:
    problem: str
    severity: str
    evidence: str
    likely_cause: str
    recommended_fix: str
    can_auto_fix: bool = False
    safe_to_auto_fix: bool = False
    status: str = "active"
    source: str = "runtime"
    source_timestamp: str | None = None
    last_success_timestamp: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ErrorDoctor:
    def analyze_texts(self, texts: list[str]) -> list[DiagnosticFinding]:
        findings: list[DiagnosticFinding] = []
        for text in texts:
            findings.extend(self._analyze_text(text))
        return _dedupe_findings(findings)

    def analyze_files(self, paths: list[Path]) -> list[DiagnosticFinding]:
        findings: list[DiagnosticFinding] = []
        for path in paths:
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            source_timestamp = _extract_first_timestamp(text)
            findings.extend(
                _with_source(finding, str(path), source_timestamp, None, "active")
                for finding in self._analyze_text(text)
            )
        return _dedupe_findings(findings)

    def analyze_runtime_logs(self, startup_error_path: Path, app_log_path: Path) -> list[DiagnosticFinding]:
        app_log_text = _read_text(app_log_path)
        last_success = _last_successful_start_timestamp(app_log_text)
        findings = self.analyze_files([startup_error_path, app_log_path])
        updated: list[DiagnosticFinding] = []
        for finding in findings:
            status = finding.status
            if (
                startup_error_path.exists()
                and finding.source == str(startup_error_path)
                and _is_after(last_success, finding.source_timestamp)
            ):
                status = "historical"
            updated.append(
                _with_source(
                    finding,
                    finding.source,
                    finding.source_timestamp,
                    last_success,
                    status,
                )
            )
        return _dedupe_findings(updated)

    def analyze_project_state(self, project_root: Path, is_admin: bool, winget_available: bool) -> list[DiagnosticFinding]:
        findings: list[DiagnosticFinding] = []
        local_python = project_root / "python"
        if local_python.exists():
            findings.append(
                DiagnosticFinding(
                    problem="Lokale Python-Stoerdatei erkannt",
                    severity="warning",
                    evidence=str(local_python),
                    likely_cause="Eine Datei namens python im Projektordner kann die Interpreter-Aufloesung stoeren.",
                    recommended_fix="Datei pruefen und nur nach bewusster Nutzerfreigabe entfernen oder umbenennen.",
                    can_auto_fix=False,
                    safe_to_auto_fix=False,
                    status="active",
                    source="project-state",
                )
            )
        if not is_admin:
            findings.append(
                DiagnosticFinding(
                    problem="Adminrechte fehlen",
                    severity="warning",
                    evidence="App laeuft ohne erhoehte Rechte.",
                    likely_cause="Windows hat die App ohne Administratorrechte gestartet.",
                    recommended_fix="Admin-Start ueber die App-Schaltflaeche oder per Rechtsklick ausfuehren.",
                    can_auto_fix=False,
                    safe_to_auto_fix=False,
                    status="active",
                    source="project-state",
                )
            )
        if not winget_available:
            findings.append(
                DiagnosticFinding(
                    problem="winget nicht erreichbar",
                    severity="error",
                    evidence="shutil.which('winget') liefert keinen Pfad.",
                    likely_cause="App Installer fehlt, ist defekt oder winget ist nicht im PATH.",
                    recommended_fix="App Installer/Microsoft Store pruefen und danach die App neu starten.",
                    can_auto_fix=False,
                    safe_to_auto_fix=False,
                    status="active",
                    source="project-state",
                )
            )
        return _dedupe_findings(findings)

    def _analyze_text(self, text: str) -> list[DiagnosticFinding]:
        normalized = text.casefold()
        findings: list[DiagnosticFinding] = []

        if "can't find a usable init.tcl" in normalized or "init.tcl" in normalized and "tk" in normalized:
            findings.append(
                DiagnosticFinding(
                    problem="Tcl/Tk-Installation defekt",
                    severity="error",
                    evidence=_evidence(text, "init.tcl"),
                    likely_cause="Die Python-Installation enthaelt keine nutzbare Tcl/Tk-Komponente.",
                    recommended_fix="Python reparieren oder neu installieren und Tcl/Tk aktivieren, danach Build/App erneut starten.",
                )
            )
        if "windowsapps" in normalized and ("python" in normalized or "py.exe" in normalized):
            findings.append(
                DiagnosticFinding(
                    problem="WindowsApps Python-Alias erkannt",
                    severity="warning",
                    evidence=_evidence(text, "WindowsApps"),
                    likely_cause="Windows App Execution Alias zeigt auf einen Store-Stub statt auf einen echten Interpreter.",
                    recommended_fix="Echten Python-Pfad verwenden oder App Execution Alias fuer Python deaktivieren.",
                )
            )
        if "winget wurde nicht gefunden" in normalized or "winget" in normalized and "not found" in normalized:
            findings.append(
                DiagnosticFinding(
                    problem="winget nicht erreichbar",
                    severity="error",
                    evidence=_evidence(text, "winget"),
                    likely_cause="App Installer fehlt, ist defekt oder winget ist nicht im PATH.",
                    recommended_fix="App Installer/Microsoft Store pruefen und danach die App neu starten.",
                )
            )
        if "administratorrechte erforderlich" in normalized or "adminrechte fehlen" in normalized or "access is denied" in normalized or "zugriff verweigert" in normalized:
            findings.append(
                DiagnosticFinding(
                    problem="Admin- oder Zugriffsproblem",
                    severity="warning",
                    evidence=_evidence(text, "admin") or _evidence(text, "zugriff"),
                    likely_cause="Die Aktion braucht erhoehte Rechte oder ein Prozess sperrt den Zugriff.",
                    recommended_fix="App als Administrator starten; bei gesperrten Dateien laufende Prozesse schliessen.",
                )
            )
        if "pyinstaller" in normalized and ("error" in normalized or "failed" in normalized or "fehler" in normalized):
            findings.append(
                DiagnosticFinding(
                    problem="PyInstaller-Buildfehler",
                    severity="error",
                    evidence=_evidence(text, "PyInstaller"),
                    likely_cause="Build-Abhaengigkeit, Tcl/Tk-Ressource oder Python-Pfad ist nicht korrekt.",
                    recommended_fix="Build ueber scripts\\build_portable.cmd mit explizitem Python-Pfad erneut starten.",
                )
            )
        if "timeout" in normalized and ("pip" in normalized or "build-isolation" in normalized):
            findings.append(
                DiagnosticFinding(
                    problem="pip Timeout oder Build-Isolation haengt",
                    severity="warning",
                    evidence=_evidence(text, "timeout"),
                    likely_cause="Paketinstallation oder Build-Isolation haengt an Netzwerk, Cache oder Lock.",
                    recommended_fix="Installation spaeter wiederholen; bei Bedarf pip-Cache/Umgebung separat pruefen.",
                )
            )
        if "permissionerror" in normalized and "pytest-tmp" in normalized:
            findings.append(
                DiagnosticFinding(
                    problem="pytest Temp-Ordner gesperrt",
                    severity="warning",
                    evidence=_evidence(text, "pytest-tmp"),
                    likely_cause="Ein alter Testprozess oder Windows-Dateisperre blockiert den pytest-Basetemp-Ordner.",
                    recommended_fix="Tests mit frischem --basetemp starten, z.B. work/pytest-tmp-v010.",
                )
            )
        return findings


def diagnostic_hint(exit_code: int | None, output: list[str] | None = None) -> str | None:
    if exit_code is None:
        return None
    if exit_code in WINGET_EXIT_HINTS:
        return WINGET_EXIT_HINTS[exit_code]
    joined_output = "\n".join(output or []).casefold()
    if "reboot" in joined_output or "neustart" in joined_output:
        return "Neustart-Hinweis erkannt. System neu starten und Aktion erneut pruefen."
    if "access" in joined_output or "zugriff" in joined_output or "denied" in joined_output:
        return "Zugriffsproblem erkannt. App als Administrator starten und laufende Programme schliessen."
    return f"Unbekannter Exit-Code {exit_code}. Details im Ausgabe-Auszug pruefen."


def output_excerpt(output: list[str] | None, limit: int = 1200) -> str:
    lines = [line.strip() for line in output or [] if line.strip()]
    if not lines:
        return ""
    text = "\n".join(lines[-20:])
    if len(text) <= limit:
        return text
    return text[-limit:]


def _dedupe_findings(findings: list[DiagnosticFinding]) -> list[DiagnosticFinding]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[DiagnosticFinding] = []
    for finding in findings:
        key = (finding.problem, finding.evidence, finding.source)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _evidence(text: str, needle: str, limit: int = 220) -> str:
    lowered = text.casefold()
    index = lowered.find(needle.casefold())
    if index < 0:
        return output_excerpt(text.splitlines(), limit=limit)
    start = max(0, index - 80)
    end = min(len(text), index + len(needle) + 120)
    return " ".join(text[start:end].split())[:limit]


def _with_source(
    finding: DiagnosticFinding,
    source: str,
    source_timestamp: str | None,
    last_success_timestamp: str | None,
    status: str,
) -> DiagnosticFinding:
    return DiagnosticFinding(
        problem=finding.problem,
        severity=finding.severity,
        evidence=finding.evidence,
        likely_cause=finding.likely_cause,
        recommended_fix=finding.recommended_fix,
        can_auto_fix=finding.can_auto_fix,
        safe_to_auto_fix=finding.safe_to_auto_fix,
        status=status,
        source=source,
        source_timestamp=source_timestamp,
        last_success_timestamp=last_success_timestamp,
    )


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_first_timestamp(text: str) -> str | None:
    match = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", text)
    return match.group(1) if match else None


def _last_successful_start_timestamp(text: str) -> str | None:
    last: str | None = None
    for line in text.splitlines():
        if "DEVHub TuningForge" in line and "gestartet" in line:
            timestamp = _extract_first_timestamp(line)
            if timestamp:
                last = timestamp
    return last


def _is_after(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    try:
        return datetime.strptime(left, "%Y-%m-%d %H:%M:%S") > datetime.strptime(right, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
