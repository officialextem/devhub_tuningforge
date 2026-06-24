import hashlib
import json
from pathlib import Path

import pytest

from core.offline_cache import (
    CACHE_INDEX_NAME,
    CACHE_STATUS_INVALID,
    CACHE_STATUS_MISSING,
    CACHE_STATUS_PRESENT,
    CACHE_STATUS_STALE,
    CacheEntry,
    OfflineCacheError,
    index_existing_installers,
    inspect_cache,
    load_cache_index,
    write_cache_index,
)


def test_empty_cache_is_valid_preview(tmp_path: Path) -> None:
    summary = inspect_cache(tmp_path / "cache" / "installers")

    assert summary.planned_count == 0
    assert summary.present_count == 0
    assert summary.warnings == []


def test_existing_installer_is_indexed_with_sha256(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache" / "installers"
    cache_root.mkdir(parents=True)
    installer = cache_root / "git.exe"
    installer.write_bytes(b"installer-bytes")

    summary = index_existing_installers(cache_root)

    assert summary.present_count == 1
    assert summary.entries[0].status == CACHE_STATUS_PRESENT
    assert summary.entries[0].file_path == "git.exe"
    assert summary.entries[0].sha256 == hashlib.sha256(b"installer-bytes").hexdigest()
    assert (cache_root / CACHE_INDEX_NAME).exists()


def test_missing_file_is_marked_missing(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache" / "installers"
    entry = CacheEntry("git", "Git", "manual", "git.exe")

    summary = inspect_cache(cache_root, [entry])

    assert summary.entries[0].status == CACHE_STATUS_MISSING
    assert summary.entries[0].note == "Datei fehlt."


def test_stale_hash_is_detected(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache" / "installers"
    cache_root.mkdir(parents=True)
    (cache_root / "git.exe").write_bytes(b"new")
    entry = CacheEntry("git", "Git", "manual", "git.exe", sha256=hashlib.sha256(b"old").hexdigest())

    summary = inspect_cache(cache_root, [entry])

    assert summary.entries[0].status == CACHE_STATUS_STALE
    assert summary.warnings


def test_path_outside_cache_is_rejected_as_invalid(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache" / "installers"
    entry = CacheEntry("bad", "Bad", "manual", "../outside.exe")

    summary = inspect_cache(cache_root, [entry])

    assert summary.entries[0].status == CACHE_STATUS_INVALID
    assert "ausserhalb" in summary.entries[0].note


def test_cache_index_roundtrip_and_invalid_schema(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache" / "installers"
    entry = CacheEntry("git", "Git", "manual", "git.exe")

    write_cache_index(cache_root, [entry])
    loaded = load_cache_index(cache_root)

    assert loaded == [entry]
    (cache_root / CACHE_INDEX_NAME).write_text(json.dumps({"entries": "bad"}), encoding="utf-8")
    with pytest.raises(OfflineCacheError):
        load_cache_index(cache_root)
