from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from traceback import format_exception_only

from core.app_config import LOG_FILE_NAME


LEVEL_INFO = "INFO"
LEVEL_SUCCESS = "SUCCESS"
LEVEL_WARNING = "WARNING"
LEVEL_ERROR = "ERROR"
LOG_LEVELS = {LEVEL_INFO, LEVEL_SUCCESS, LEVEL_WARNING, LEVEL_ERROR}


@dataclass(frozen=True)
class LogEntry:
    level: str
    message: str
    timestamp: str

    @property
    def line(self) -> str:
        return f"[{self.timestamp}] [{self.level}] {self.message}"


class AppLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_path = log_dir / LOG_FILE_NAME
        self._lock = Lock()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def info(self, message: str) -> LogEntry:
        return self._write(LEVEL_INFO, message)

    def success(self, message: str) -> LogEntry:
        return self._write(LEVEL_SUCCESS, message)

    def warning(self, message: str) -> LogEntry:
        return self._write(LEVEL_WARNING, message)

    def error(self, message: str, exc: BaseException | None = None) -> LogEntry:
        if exc is not None:
            exc_text = "".join(format_exception_only(type(exc), exc)).strip()
            message = f"{message} ({exc_text})"
        return self._write(LEVEL_ERROR, message)

    def _write(self, level: str, message: str) -> LogEntry:
        if level not in LOG_LEVELS:
            raise ValueError(f"Unknown log level: {level}")
        entry = LogEntry(
            level=level,
            message=message,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(entry.line + "\n")
        return entry


def get_app_logger(log_dir: Path) -> AppLogger:
    return AppLogger(log_dir)
