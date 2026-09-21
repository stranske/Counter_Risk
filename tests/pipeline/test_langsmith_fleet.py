"""Pipeline-level LangSmith fleet artifact tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from counter_risk.pipeline import run as run_module


def test_fleet_data_quality_status_reflects_fail_limit_breaches(tmp_path: Path) -> None:
    run_dir = tmp_path / "2025-12-31"
    run_dir.mkdir()

    artifact_path = run_module._write_langsmith_fleet_artifact(
        run_dir=run_dir,
        as_of_date=date(2025, 12, 31),
        output_paths=[],
        warnings=[],
        concentration_metrics_records=[],
        risk_proxy_summary={},
        limit_breach_summary={
            "has_breaches": True,
            "breach_count": 1,
            "max_severity": "fail",
            "warning_breach_count": 0,
            "fail_breach_count": 1,
        },
    )

    records = [
        json.loads(line) for line in artifact_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert records
    assert all(record["domain"]["data_quality_status"] == "fail" for record in records)
    data_quality_record = next(record for record in records if record["operation"] == "data-quality")
    assert data_quality_record["domain"]["stage_status"] == "fail"
