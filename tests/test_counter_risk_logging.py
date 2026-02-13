"""Unit tests for counter_risk structured logging."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from counter_risk import logging as cr_logging


def test_resolve_level_handles_known_values() -> None:
    assert cr_logging._resolve_level("info") == logging.INFO
    assert cr_logging._resolve_level(logging.WARNING) == logging.WARNING


def test_resolve_level_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unsupported log level"):
        cr_logging._resolve_level("definitely-not-a-level")


def test_json_formatter_emits_expected_keys() -> None:
    formatter = cr_logging.JsonFormatter()
    record = logging.LogRecord(
        name="counter_risk.tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "counter_risk.tests"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_json_formatter_includes_exception_text() -> None:
    formatter = cr_logging.JsonFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="counter_risk.tests",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    payload = json.loads(formatter.format(record))

    assert "exception" in payload
    assert "RuntimeError" in payload["exception"]


def test_configure_logging_writes_json_file(tmp_path) -> None:
    log_path = tmp_path / "counter-risk.log"
    logger = cr_logging.configure_logging(
        log_level="INFO",
        log_file=log_path,
        console=False,
    )
    logger.info("pipeline started")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message"] == "pipeline started"
    assert payload["level"] == "INFO"
