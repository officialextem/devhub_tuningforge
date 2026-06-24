from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


EVENT_CREATED = "created"
EVENT_MODIFIED = "modified"
EVENT_DELETED = "deleted"
EVENT_RENAMED = "renamed"
SENSITIVE_EXECUTABLE_EXTENSIONS = {".exe", ".msi", ".ps1", ".bat", ".cmd"}


@dataclass(frozen=True)
class GuardProfile:
    id: str
    name: str
    protected_paths: list[str]
    enabled: bool = True
    alpha_preview_only: bool = True


@dataclass(frozen=True)
class FileWatchEvent:
    event_type: str
    path: str
    timestamp: str
    old_path: str | None = None
    process_name: str | None = None


@dataclass(frozen=True)
class GuardRiskFinding:
    risk_level: str
    reason: str
    affected_paths: list[str]
    recommendation: str
    event_count: int

    def to_dict(self) -> dict:
        return asdict(self)


class FileWatchProvider:
    def collect_events(self) -> list[FileWatchEvent]:
        raise NotImplementedError


@dataclass
class MockFileWatchProvider(FileWatchProvider):
    events: list[FileWatchEvent] = field(default_factory=list)

    def collect_events(self) -> list[FileWatchEvent]:
        return list(self.events or sample_guard_events())


def default_guard_profile(project_root: Path) -> GuardProfile:
    home = Path.home()
    return GuardProfile(
        id="default-local",
        name="Lokale Standardbereiche",
        protected_paths=[
            str(home / "Documents"),
            str(home / "Desktop"),
            str(home / "Downloads"),
            str(project_root),
        ],
    )


def sample_guard_events() -> list[FileWatchEvent]:
    return [
        FileWatchEvent(EVENT_MODIFIED, r"%USERPROFILE%\Documents\Projekt\Notizen.md", "2026-06-18T02:15:00", process_name="Code.exe"),
        FileWatchEvent(EVENT_RENAMED, r"%USERPROFILE%\Documents\Rechnung.pdf.locked", "2026-06-18T02:15:03", old_path=r"%USERPROFILE%\Documents\Rechnung.pdf", process_name="unknown.exe"),
        FileWatchEvent(EVENT_CREATED, r"%USERPROFILE%\Downloads\setup-helper.exe", "2026-06-18T02:15:07", process_name="browser.exe"),
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\Archiv\old-01.txt", "2026-06-18T02:15:08", process_name="unknown.exe"),
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\Archiv\old-02.txt", "2026-06-18T02:15:09", process_name="unknown.exe"),
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\Archiv\old-03.txt", "2026-06-18T02:15:10", process_name="unknown.exe"),
    ]


def score_guard_events(events: list[FileWatchEvent]) -> list[GuardRiskFinding]:
    findings: list[GuardRiskFinding] = []
    deleted = [event for event in events if event.event_type == EVENT_DELETED]
    if len(deleted) >= 3:
        findings.append(
            GuardRiskFinding(
                risk_level="mittel",
                reason="Viele Loeschungen in kurzer Zeit erkannt.",
                affected_paths=[event.path for event in deleted],
                recommendation="Aenderungen pruefen, bevor echte GuardForge-Ueberwachung aktiviert wird.",
                event_count=len(deleted),
            )
        )

    if len(events) >= 6:
        findings.append(
            GuardRiskFinding(
                risk_level="niedrig",
                reason="Viele Dateiaenderungen in kurzer Zeit erkannt.",
                affected_paths=[event.path for event in events[:6]],
                recommendation="Quelle der Aenderungen im Event-Log pruefen.",
                event_count=len(events),
            )
        )

    renamed_suspicious = [
        event
        for event in events
        if event.event_type == EVENT_RENAMED and event.old_path and Path(event.old_path).suffix.lower() != Path(event.path).suffix.lower()
    ]
    if renamed_suspicious:
        findings.append(
            GuardRiskFinding(
                risk_level="mittel",
                reason="Verdaechtige Extension-Aenderung erkannt.",
                affected_paths=[event.path for event in renamed_suspicious],
                recommendation="Dateien nicht oeffnen, bis Herkunft und Prozess geklaert sind.",
                event_count=len(renamed_suspicious),
            )
        )

    executable_events = [
        event for event in events if _is_sensitive_path(event.path) and Path(event.path).suffix.lower() in SENSITIVE_EXECUTABLE_EXTENSIONS
    ]
    if executable_events:
        findings.append(
            GuardRiskFinding(
                risk_level="mittel",
                reason="Ausfuehrbare Datei in sensiblem Bereich erkannt.",
                affected_paths=[event.path for event in executable_events],
                recommendation="Signatur, Quelle und Zweck pruefen; keine automatische Ausfuehrung.",
                event_count=len(executable_events),
            )
        )

    if not findings and events:
        findings.append(
            GuardRiskFinding(
                risk_level="niedrig",
                reason="Normale Einzelereignisse ohne auffaellige Muster.",
                affected_paths=[event.path for event in events],
                recommendation="Keine Aktion erforderlich; Preview dient nur zur Transparenz.",
                event_count=len(events),
            )
        )
    return findings


def _is_sensitive_path(path: str) -> bool:
    normalized = path.lower().replace("/", "\\")
    return any(part in normalized for part in ("\\documents\\", "\\desktop\\", "\\downloads\\", "%userprofile%\\documents", "%userprofile%\\desktop", "%userprofile%\\downloads"))
