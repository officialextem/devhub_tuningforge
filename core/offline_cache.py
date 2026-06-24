from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


CACHE_INDEX_NAME = "installer-cache.json"
CACHE_STATUS_MISSING = "missing"
CACHE_STATUS_PRESENT = "present"
CACHE_STATUS_STALE = "stale"
CACHE_STATUS_INVALID = "invalid"


class OfflineCacheError(ValueError):
    pass


@dataclass(frozen=True)
class CacheEntry:
    package_id: str
    name: str
    source: str
    file_path: str
    size_bytes: int = 0
    sha256: str = ""
    status: str = CACHE_STATUS_MISSING
    checked_at: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CacheSummary:
    root: str
    index_path: str
    entries: list[CacheEntry]
    warnings: list[str]
    checked_at: str

    @property
    def present_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == CACHE_STATUS_PRESENT)

    @property
    def planned_count(self) -> int:
        return len(self.entries)

    @property
    def invalid_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == CACHE_STATUS_INVALID)

    @property
    def missing_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == CACHE_STATUS_MISSING)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "index_path": self.index_path,
            "entries": [entry.to_dict() for entry in self.entries],
            "warnings": self.warnings,
            "checked_at": self.checked_at,
            "present_count": self.present_count,
            "planned_count": self.planned_count,
            "invalid_count": self.invalid_count,
            "missing_count": self.missing_count,
        }


def cache_paths(runtime_root: Path) -> tuple[Path, Path]:
    cache_root = runtime_root / "cache" / "installers"
    return cache_root, cache_root / CACHE_INDEX_NAME


def load_cache_index(cache_root: Path) -> list[CacheEntry]:
    index_path = cache_root / CACHE_INDEX_NAME
    if not index_path.exists():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfflineCacheError(f"Cache-Index konnte nicht gelesen werden: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise OfflineCacheError("Cache-Index muss ein Objekt mit entries-Liste sein.")
    return [_entry_from_payload(item) for item in payload["entries"]]


def write_cache_index(cache_root: Path, entries: list[CacheEntry]) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    index_path = cache_root / CACHE_INDEX_NAME
    payload = {
        "schema_version": "1",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [entry.to_dict() for entry in entries],
    }
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def inspect_cache(cache_root: Path, entries: list[CacheEntry] | None = None) -> CacheSummary:
    cache_root.mkdir(parents=True, exist_ok=True)
    index_path = cache_root / CACHE_INDEX_NAME
    source_entries = entries if entries is not None else load_cache_index(cache_root)
    checked_at = datetime.now().isoformat(timespec="seconds")
    checked_entries = [_inspect_entry(cache_root, entry, checked_at) for entry in source_entries]
    warnings = _cache_warnings(checked_entries)
    return CacheSummary(
        root=str(cache_root),
        index_path=str(index_path),
        entries=checked_entries,
        warnings=warnings,
        checked_at=checked_at,
    )


def index_existing_installers(cache_root: Path) -> CacheSummary:
    cache_root.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().isoformat(timespec="seconds")
    entries: list[CacheEntry] = []
    for path in sorted(cache_root.iterdir()):
        if not path.is_file() or path.name == CACHE_INDEX_NAME:
            continue
        entry = CacheEntry(
            package_id=path.stem,
            name=path.stem,
            source="manual-cache",
            file_path=path.name,
            checked_at=checked_at,
        )
        entries.append(_inspect_entry(cache_root, entry, checked_at))
    write_cache_index(cache_root, entries)
    return CacheSummary(
        root=str(cache_root),
        index_path=str(cache_root / CACHE_INDEX_NAME),
        entries=entries,
        warnings=_cache_warnings(entries),
        checked_at=checked_at,
    )


def _entry_from_payload(payload: object) -> CacheEntry:
    if not isinstance(payload, dict):
        raise OfflineCacheError("Cache-Eintrag muss ein Objekt sein.")
    try:
        return CacheEntry(
            package_id=_required_string(payload, "package_id"),
            name=_required_string(payload, "name"),
            source=_required_string(payload, "source"),
            file_path=_required_string(payload, "file_path"),
            size_bytes=int(payload.get("size_bytes", 0)),
            sha256=str(payload.get("sha256", "")),
            status=str(payload.get("status", CACHE_STATUS_MISSING)),
            checked_at=payload.get("checked_at"),
            note=str(payload.get("note", "")),
        )
    except (TypeError, ValueError) as exc:
        raise OfflineCacheError(f"Cache-Eintrag ungueltig: {exc}") from exc


def _required_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise OfflineCacheError(f"{key} muss ein nicht-leerer Textwert sein.")
    if "://" in value:
        raise OfflineCacheError(f"{key} darf keine Remote-URL enthalten.")
    return value


def _inspect_entry(cache_root: Path, entry: CacheEntry, checked_at: str) -> CacheEntry:
    try:
        path = _safe_cache_file(cache_root, entry.file_path)
    except OfflineCacheError as exc:
        return CacheEntry(
            **{**entry.to_dict(), "status": CACHE_STATUS_INVALID, "checked_at": checked_at, "note": str(exc)}
        )
    if not path.exists():
        return CacheEntry(
            **{**entry.to_dict(), "size_bytes": 0, "sha256": "", "status": CACHE_STATUS_MISSING, "checked_at": checked_at, "note": "Datei fehlt."}
        )
    if not path.is_file():
        return CacheEntry(
            **{**entry.to_dict(), "size_bytes": 0, "sha256": "", "status": CACHE_STATUS_INVALID, "checked_at": checked_at, "note": "Pfad ist keine Datei."}
        )
    size = path.stat().st_size
    sha256 = _sha256(path)
    status = CACHE_STATUS_PRESENT
    note = "Datei lokal vorhanden."
    if entry.sha256 and entry.sha256 != sha256:
        status = CACHE_STATUS_STALE
        note = "Hash weicht vom Index ab."
    return CacheEntry(
        **{
            **entry.to_dict(),
            "size_bytes": size,
            "sha256": sha256,
            "status": status,
            "checked_at": checked_at,
            "note": note,
        }
    )


def _safe_cache_file(cache_root: Path, file_path: str) -> Path:
    candidate = (cache_root / file_path).resolve()
    root = cache_root.resolve()
    if not str(candidate).casefold().startswith(str(root).casefold()):
        raise OfflineCacheError("Pfad liegt ausserhalb des Cache-Ordners.")
    if "://" in file_path:
        raise OfflineCacheError("Remote-URLs sind im Offline Cache nicht erlaubt.")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_warnings(entries: list[CacheEntry]) -> list[str]:
    warnings: list[str] = []
    for entry in entries:
        if entry.status in {CACHE_STATUS_INVALID, CACHE_STATUS_STALE}:
            warnings.append(f"{entry.name}: {entry.note}")
    return warnings
