from pathlib import Path

from core.guardforge import (
    EVENT_CREATED,
    EVENT_DELETED,
    EVENT_MODIFIED,
    EVENT_RENAMED,
    FileWatchEvent,
    MockFileWatchProvider,
    default_guard_profile,
    score_guard_events,
)


def test_default_guard_profile_contains_expected_paths(tmp_path: Path) -> None:
    profile = default_guard_profile(tmp_path)

    assert profile.alpha_preview_only is True
    assert str(tmp_path) in profile.protected_paths
    assert any(path.endswith("Documents") for path in profile.protected_paths)
    assert any(path.endswith("Desktop") for path in profile.protected_paths)
    assert any(path.endswith("Downloads") for path in profile.protected_paths)


def test_mock_file_watch_provider_returns_reproducible_events() -> None:
    provider = MockFileWatchProvider()

    first = provider.collect_events()
    second = provider.collect_events()

    assert first == second
    assert len(first) >= 3


def test_guardforge_scores_mass_deletion_extension_change_and_executable() -> None:
    events = [
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\a.txt", "2026-06-18T02:00:01"),
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\b.txt", "2026-06-18T02:00:02"),
        FileWatchEvent(EVENT_DELETED, r"%USERPROFILE%\Documents\c.txt", "2026-06-18T02:00:03"),
        FileWatchEvent(EVENT_RENAMED, r"%USERPROFILE%\Documents\invoice.pdf.locked", "2026-06-18T02:00:04", old_path=r"%USERPROFILE%\Documents\invoice.pdf"),
        FileWatchEvent(EVENT_CREATED, r"%USERPROFILE%\Downloads\helper.exe", "2026-06-18T02:00:05"),
    ]

    findings = score_guard_events(events)
    reasons = {finding.reason for finding in findings}

    assert "Viele Loeschungen in kurzer Zeit erkannt." in reasons
    assert "Verdaechtige Extension-Aenderung erkannt." in reasons
    assert "Ausfuehrbare Datei in sensiblem Bereich erkannt." in reasons


def test_guardforge_scores_normal_single_change_as_low_risk() -> None:
    events = [FileWatchEvent(EVENT_MODIFIED, r"%USERPROFILE%\Documents\note.md", "2026-06-18T02:00:01")]

    findings = score_guard_events(events)

    assert len(findings) == 1
    assert findings[0].risk_level == "niedrig"
