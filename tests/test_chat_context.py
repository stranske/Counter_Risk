"""Tests for chat run-context loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk.chat.context import (
    RunContextError,
    discover_tables,
    load_manifest,
    load_run_context,
)


def test_load_run_context_returns_non_empty_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    manifest = {
        "as_of_date": "2026-02-13",
        "run_date": "2026-02-14T00:00:00+00:00",
        "warnings": ["PPT links not refreshed; COM refresh skipped"],
        "top_exposures": {"all_programs": [{"counterparty": "A", "notional": 10.0}]},
        "top_changes_per_variant": {
            "all_programs": [{"counterparty": "A", "notional_change": 2.5}]
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "totals.csv").write_text(
        "counterparty,Notional,NotionalChange\nA,10.0,2.5\n",
        encoding="utf-8",
    )

    context = load_run_context(run_dir)

    assert context.warnings
    assert context.deltas["all_programs"][0]["counterparty"] == "A"
    assert "totals.csv" in context.tables
    assert context.summary().strip() != ""


def test_load_manifest_missing_raises_error(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(RunContextError, match="manifest.json is missing"):
        load_manifest(run_dir)


def test_load_manifest_malformed_raises_error(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text("{bad-json", encoding="utf-8")

    with pytest.raises(RunContextError, match="manifest.json is malformed"):
        load_manifest(run_dir)


def test_discover_tables_loads_csv_and_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "totals.csv").write_text("counterparty,Notional\nA,1\n", encoding="utf-8")
    (run_dir / "nested").mkdir()
    parquet_path = run_dir / "nested" / "futures.parquet"
    parquet_path.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "counter_risk.chat.context._load_parquet_table",
        lambda _: [{"counterparty": "B", "notional": 2.0}],
    )

    tables = discover_tables(run_dir)

    assert "totals.csv" in tables
    assert "nested/futures.parquet" in tables
    assert tables["nested/futures.parquet"][0]["counterparty"] == "B"
