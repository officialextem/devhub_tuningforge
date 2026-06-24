import re

from core.app_config import LOG_FILE_NAME
from core.app_logger import get_app_logger


def test_logger_creates_file_and_writes_levels(tmp_path):
    logger = get_app_logger(tmp_path)

    logger.info("Info")
    logger.success("Success")
    logger.warning("Warning")
    logger.error("Error")

    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8").splitlines()

    assert len(content) == 4
    assert re.match(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[INFO\] Info", content[0])
    assert "[SUCCESS] Success" in content[1]
    assert "[WARNING] Warning" in content[2]
    assert "[ERROR] Error" in content[3]


def test_logger_records_exception_text(tmp_path):
    logger = get_app_logger(tmp_path)

    try:
        raise RuntimeError("kaputt")
    except RuntimeError as exc:
        logger.error("Fehler beim Test", exc)

    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")

    assert "[ERROR] Fehler beim Test (RuntimeError: kaputt)" in content
