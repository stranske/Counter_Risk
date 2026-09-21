"""Pipeline-level LangSmith fleet data_quality_status mapper tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from counter_risk.pipeline import run as run_module


def _write_fleet(
    tmp_path: Path,
    *,
    warnings: list[object],
    limit_breach_summary: dict[str, object],
) -> list[dict[str, object]]:
    run_dir = tmp_path / "2025-12-31"
    run_dir.mkdir()
    artifact_path = run_module._write_langsmith_fleet_artifact(
        run_dir=run_dir,
        as_of_date=date(2025, 12, 31),
        output_paths=[],
        warnings=warnings,
        concentration_metrics_records=[],
        risk_proxy_summary={},
        limit_breach_summary=limit_breach_summary,
    )
    return [
        json.loads(line)
        for line in artifact_path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_fleet_data_quality_status_reflects_fail_limit_breaches(tmp_path: Path) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=[],
        limit_breach_summary={
            "has_breaches": True,
            "breach_count": 1,
            "max_severity": "fail",
            "warning_breach_count": 0,
            "fail_breach_count": 1,
        },
    )
    assert records
    assert all(record["domain"]["data_quality_status"] == "fail" for record in records)
    data_quality_record = next(record for record in records if record["operation"] == "data-quality")
    assert data_quality_record["domain"]["stage_status"] == "fail"


def test_fleet_data_quality_status_fail_when_max_severity_omitted_with_fail_breaches(
    tmp_path: Path,
) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=[],
        limit_breach_summary={
            "has_breaches": True,
            "breach_count": 2,
            "warning_breach_count": 0,
            "fail_breach_count": 2,
        },
    )
    assert all(record["domain"]["data_quality_status"] == "fail" for record in records)


def test_fleet_data_quality_status_warning_for_warning_limit_breaches(tmp_path: Path) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=[],
        limit_breach_summary={
            "has_breaches": True,
            "breach_count": 1,
            "max_severity": "warning",
            "warning_breach_count": 1,
            "fail_breach_count": 0,
        },
    )
    assert all(record["domain"]["data_quality_status"] == "warning" for record in records)


def test_fleet_data_quality_status_warning_for_warn_severity_warnings(tmp_path: Path) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=["Portfolio concentration exceeds policy threshold"],
        limit_breach_summary={
            "has_breaches": False,
            "breach_count": 0,
            "warning_breach_count": 0,
            "fail_breach_count": 0,
        },
    )
    assert all(record["domain"]["data_quality_status"] == "warning" for record in records)


def test_fleet_data_quality_status_success_for_info_only_warnings(tmp_path: Path) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=["Applied repo cash values to all_programs totals"],
        limit_breach_summary={
            "has_breaches": False,
            "breach_count": 0,
            "warning_breach_count": 0,
            "fail_breach_count": 0,
        },
    )
    assert all(record["domain"]["data_quality_status"] == "success" for record in records)


def test_fleet_data_quality_status_success_when_no_findings(tmp_path: Path) -> None:
    records = _write_fleet(
        tmp_path,
        warnings=[],
        limit_breach_summary={
            "has_breaches": False,
            "breach_count": 0,
            "warning_breach_count": 0,
            "fail_breach_count": 0,
        },
    )
    assert all(record["domain"]["data_quality_status"] == "success" for record in records)
