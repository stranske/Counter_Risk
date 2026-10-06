"""Persist usable trace context when higher-priority telemetry is malformed."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from counter_risk.pipeline import run as run_module

_LATENCY_KEYS = ("LANGSMITH_TRACE_LATENCY_MS", "LANGSMITH_LATENCY_MS", "TRACE_LATENCY_MS")


@pytest.fixture
def clean_trace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (*_LATENCY_KEYS, "LANGSMITH_ERROR_CATEGORY", "PIPELINE_ERROR_CATEGORY"):
        monkeypatch.delenv(key, raising=False)


def _records(run_dir: Path, output_paths: list[Path] | None = None) -> list[dict]:
    run_dir.mkdir()
    artifact = run_module._write_langsmith_fleet_artifact(
        run_dir=run_dir,
        as_of_date=date(2026, 10, 6),
        output_paths=output_paths or [],
        warnings=[],
        concentration_metrics_records=[],
        risk_proxy_summary={},
        limit_breach_summary={},
    )
    assert artifact == run_dir / "langsmith-fleet.ndjson"
    records = [json.loads(line) for line in artifact.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 5
    return records


@pytest.mark.usefixtures("clean_trace_env")
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (("not-a-number", " 17 ", None), 17),
        ((" ", "", " 23 "), 23),
        (("-1", "7", "99"), 7),
        (("0", "99", None), 0),
        (("bad", "-2", " "), None),
        ((" 31 ", "99", "101"), 31),
        (("1.5", "17", None), 17),
        ((None, None, " 23 "), 23),
    ],
    ids=(
        "invalid-primary",
        "blank-to-tertiary",
        "negative-to-positive",
        "zero-preferred",
        "all-invalid",
        "primary-preferred",
        "fractional-to-secondary",
        "absent-to-tertiary",
    ),
)
def test_fleet_artifact_uses_first_valid_nonnegative_latency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, values: tuple, expected: int | None
) -> None:
    for key, value in zip(_LATENCY_KEYS, values, strict=True):
        if value is not None:
            monkeypatch.setenv(key, value)

    records = _records(tmp_path / "run")

    assert all(record["latency_ms"] == expected for record in records)
    assert all(record["domain"]["shared_metadata"]["latency_ms"] == expected for record in records)


@pytest.mark.usefixtures("clean_trace_env")
def test_fleet_artifact_uses_pipeline_error_after_blank_trace_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LANGSMITH_ERROR_CATEGORY", " \t ")
    monkeypatch.setenv("PIPELINE_ERROR_CATEGORY", "  input-unavailable  ")

    records = _records(tmp_path / "run")

    assert all(record["error_category"] == "input-unavailable" for record in records)
    assert all(
        record["domain"]["shared_metadata"]["error_category"] == "input-unavailable"
        for record in records
    )

    # A blank trace category must also fall through when the pipeline category
    # is unusable; neither whitespace nor an absent value is a real category.
    for index, pipeline_category in enumerate((" \t ", None)):
        if pipeline_category is None:
            monkeypatch.delenv("PIPELINE_ERROR_CATEGORY")
        else:
            monkeypatch.setenv("PIPELINE_ERROR_CATEGORY", pipeline_category)

        records = _records(tmp_path / f"unknown-error-{index}")

        assert all(record["error_category"] == "none" for record in records)
        assert all(
            record["domain"]["shared_metadata"]["error_category"] == "none" for record in records
        )


@pytest.mark.usefixtures("clean_trace_env")
def test_fleet_artifact_omits_external_report_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    outside = tmp_path / "private-input.xlsx"
    outside.write_bytes(b"external-input")
    inside = run_dir / "monthly-report.xlsx"

    records = _records(run_dir, [inside, outside])

    assert all(
        record["domain"]["report_artifacts"] == ["artifact:monthly-report.xlsx"]
        for record in records
    )
    assert all(record["domain"]["report_artifact_count"] == 1 for record in records)
    assert "private-input" not in json.dumps(records)

    records = _records(tmp_path / "external-only-run", [outside])

    assert all(record["domain"]["report_artifacts"] == [] for record in records)
    assert all(record["domain"]["report_artifact_count"] == 0 for record in records)
    assert "private-input" not in json.dumps(records)
    assert outside.read_bytes() == b"external-input"
