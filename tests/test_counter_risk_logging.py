"""Unit tests for counter_risk structured logging."""

from __future__ import annotations

import ast
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from counter_risk import logging as cr_logging
from counter_risk.cli import main


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


def test_configure_logging_writes_json_file(tmp_path: Path) -> None:
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


_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "counter_risk"
_REPO_ROOT = _SRC_ROOT.parents[1]


@pytest.fixture
def restored_root_logger() -> Iterator[None]:
    """Save and restore root logger state around a test that configures logging.

    ``configure_logging`` clears the root handlers by design, so a test that lets the
    CLI configure logging would otherwise leave a handler bound to this test's captured
    stream attached for the remainder of the session.
    """

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        yield
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in saved_handlers:
            root.addHandler(handler)
        root.setLevel(saved_level)


def _modules_calling(function_name: str) -> list[str]:
    """Return every module under ``src/counter_risk`` that CALLS ``function_name``.

    Deliberately an AST walk for a ``Call`` node rather than a substring search. A
    substring search would be satisfied by the import line, by a mention in a comment,
    or by a commented-out call -- none of which installs a log handler at runtime, which
    is the property this is here to protect.
    """

    callers: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name: str | None = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                name = None
            if name == function_name:
                callers.append(str(path.relative_to(_REPO_ROOT)))
                break
    return callers


def test_configure_logging_has_a_production_caller() -> None:
    callers = _modules_calling("configure_logging")
    assert callers, (
        "configure_logging has no production caller under src/counter_risk, so the root "
        "logger has no handler at runtime: every debug/info record in the package emits "
        "nothing and JsonFormatter never formats a production record. The CLI entry "
        "point in src/counter_risk/cli/__init__.py is where the call belongs."
    )


def test_cli_main_configures_logging(restored_root_logger: None) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    assert root.handlers == []

    assert main([]) == 0

    assert root.handlers, "counter-risk main() left the root logger with no handler"


def test_pipeline_info_records_are_emitted_after_cli_configures_logging(
    restored_root_logger: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    capsys.readouterr()  # discard the help text main() prints when given no subcommand

    # The record from src/counter_risk/pipeline/run.py that reports limit checking was
    # silently disabled because config/limits.yml was unreachable.
    logging.getLogger("counter_risk.pipeline.run").info(
        "limit_breaches_skipped missing_limits_config path=%s", "config/limits.yml"
    )

    captured = capsys.readouterr()
    assert captured.err.strip(), "an INFO record produced no output after the CLI ran"
    payload = json.loads(captured.err.strip().splitlines()[-1])
    assert payload["logger"] == "counter_risk.pipeline.run"
    assert payload["level"] == "INFO"
    assert "limit_breaches_skipped" in payload["message"]
