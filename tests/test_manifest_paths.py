from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.dates import resolve_as_of_date, resolve_run_date
from counter_risk.pipeline.manifest import ManifestBuilder


def _make_config(tmp_path: Path) -> WorkflowConfig:
    return WorkflowConfig(
        as_of_date=date(2026, 2, 13),
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist-all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist-ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist-trend.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
        output_root=tmp_path / "output-root",
    )


def test_manifest_paths_are_relative_and_resolve_to_existing_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    ppt_path = run_dir / "Monthly Counterparty Exposure Report.pptx"
    workbook_path.write_bytes(b"hist")
    ppt_path.write_bytes(b"ppt")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name), Path(ppt_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )
    manifest_path = builder.write(run_dir=run_dir, manifest=manifest)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["run_dir"] == "."
    assert parsed["ppt_status"] in {"success", "skipped", "failed"}
    assert parsed["unmatched_mappings"] == {"count": 0, "by_variant": {}}
    assert parsed["missing_inputs"] == {
        "required": [],
        "missing_required": [],
        "optional_missing": [],
        "is_complete": True,
    }
    assert parsed["reconciliation_results"] == {
        "status": "not_run",
        "fail_policy": "warn",
        "total_gap_count": 0,
        "by_variant": {},
    }

    for artifact_path in parsed["output_paths"]:
        assert not artifact_path.startswith("/")
        assert not re.match(r"^[A-Za-z]:\\", artifact_path)
        assert ".." not in Path(artifact_path).parts
        assert (run_dir / artifact_path).exists()
    summary_path = run_dir / "DATA_QUALITY_SUMMARY.txt"
    assert summary_path.exists()
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Counterparty Risk Data Quality Summary" in summary_text
    assert "Overall status: INFO (GREEN) - Safe to send." in summary_text
    assert "DATA_QUALITY_SUMMARY.txt" in parsed["output_paths"]


def test_manifest_build_rejects_nonexistent_artifact_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    with pytest.raises(ValueError, match="do not exist"):
        builder.build(
            run_dir=run_dir,
            input_hashes={"monthly_pptx": "abc123"},
            output_paths=[Path("missing.xlsx")],
            top_exposures={"all_programs": []},
            top_changes_per_variant={"all_programs": []},
            warnings=[],
        )


def test_manifest_includes_repo_cash_summary_when_provided(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    workbook_path.write_bytes(b"hist")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    repo_cash_summary = {
        "source_type": "csv",
        "source_path": "inputs/repo_cash_2026-02-13.csv",
        "overrides_path": "inputs/cash_overrides_2026-02-13.csv",
        "applied_override_count": 2,
        "override_audit_rows": [
            {
                "counterparty": "ACME",
                "raw_counterparty": "ACME Bank",
                "cash_value": "1000.0",
                "note": "year-end true-up",
            }
        ],
        "counterparty_count": 5,
        "total_cash": 12345.67,
        "required_counterparties": ["ACME", "BARCLAYS"],
        "missing_required_counterparties": [],
        "reconciliation_findings": [],
        "fail_policy": "warn",
        "applied_to_totals": True,
    }
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
        repo_cash_summary=repo_cash_summary,
    )
    manifest_path = builder.write(run_dir=run_dir, manifest=manifest)

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "repo_cash_summary" in parsed
    summary = parsed["repo_cash_summary"]
    assert summary["source_type"] == "csv"
    assert summary["source_path"] == "inputs/repo_cash_2026-02-13.csv"
    assert summary["applied_override_count"] == 2
    assert summary["override_audit_rows"][0]["counterparty"] == "ACME"
    assert summary["counterparty_count"] == 5
    assert summary["total_cash"] == pytest.approx(12345.67)
    assert summary["fail_policy"] == "warn"
    assert summary["applied_to_totals"] is True


def test_manifest_omits_repo_cash_summary_when_not_provided(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    workbook_path.write_bytes(b"hist")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )

    assert "repo_cash_summary" not in manifest


def test_manifest_warnings_are_normalized_to_strings(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    workbook_path.write_bytes(b"hist")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[
            "plain warning",
            {"message": "Reconciliation warning", "sheet": "Total", "row_idx": 4},
            {"code": "MISSING_NOTIONAL", "row_idx": 2},
            None,
            "   ",
        ],
    )

    assert manifest["warnings"] == [
        "plain warning",
        "Reconciliation warning (sheet=Total, row_idx=4)",
        "code=MISSING_NOTIONAL, row_idx=2",
    ]
    assert all(isinstance(entry, str) for entry in manifest["warnings"])


def test_manifest_build_includes_risk_proxy_summary_when_supplied(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    rankings_path = run_dir / "risk_rankings.csv"
    rankings_path.write_text("variant,counterparty,proxy_name,proxy_value,rank\n", encoding="utf-8")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    summary = {
        "outputs": {"risk_rankings": "risk_rankings.csv", "risk_top_movers": None},
        "by_variant": {
            "all_programs": {
                "risk_proxy_notional_annualized_volatility": {
                    "status": "computed",
                    "formula": "Notional * AnnualizedVolatility",
                }
            }
        },
    }
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(rankings_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
        risk_proxy_summary=summary,
    )

    assert manifest["risk_proxy_summary"] == summary


def test_to_relative_artifact_path_normalizes_absolute_path_under_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13_1"
    run_dir.mkdir(parents=True)

    artifact = (run_dir / "outputs" / ".." / "histories" / "all.xlsx").resolve()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"x")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    relative = builder._to_relative_artifact_path(run_dir=run_dir, artifact_path=artifact)

    assert relative == Path("histories/all.xlsx")
    assert relative.as_posix() == "histories/all.xlsx"


def test_to_relative_artifact_path_normalizes_relative_path_to_posix(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13_1"
    run_dir.mkdir(parents=True)

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    relative = builder._to_relative_artifact_path(
        run_dir=run_dir,
        artifact_path=Path("subdir/./reports/../deck.pptx"),
    )

    assert relative == Path("subdir/deck.pptx")
    assert relative.as_posix() == "subdir/deck.pptx"


def test_to_relative_artifact_path_rejects_parent_traversal_segments(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13_1"
    run_dir.mkdir(parents=True)

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    with pytest.raises(ValueError, match=r"cannot contain '\.\.' segments"):
        builder._to_relative_artifact_path(run_dir=run_dir, artifact_path=Path("../outside.xlsx"))


def test_to_relative_artifact_path_rejects_absolute_path_outside_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13_1"
    run_dir.mkdir(parents=True)
    outside = (tmp_path / "outside.xlsx").resolve()
    outside.write_bytes(b"outside")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    with pytest.raises(ValueError, match="must be within run_dir"):
        builder._to_relative_artifact_path(run_dir=run_dir, artifact_path=outside)


def test_data_quality_summary_derives_counts_when_counts_missing(tmp_path: Path) -> None:
    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    summary_text = builder._build_data_quality_summary(
        {
            "as_of_date": "2026-02-13",
            "run_date": "2026-02-14",
            "data_quality": {
                "overall_status": "warn",
                "findings": [
                    {
                        "category": "input",
                        "severity": "fail",
                        "code": "MISSING_REQUIRED_INPUTS",
                        "message": "Missing required input workbook.",
                    },
                    {
                        "category": "ppt",
                        "severity": "warn",
                        "code": "PPT_GENERATION_SKIPPED",
                        "message": "PPT generation was skipped for this run.",
                    },
                ],
                "recommended_actions": [
                    {
                        "category": "input",
                        "severity": "fail",
                        "action": "Restore required input files before rerunning.",
                    }
                ],
            },
        }
    )

    assert "Overall status: WARN (YELLOW) - Review warnings before sending." in summary_text
    assert "Finding counts:" in summary_text
    assert "- Total findings: 2" in summary_text
    assert "- warn: 1" in summary_text
    assert "- fail: 1" in summary_text
    assert "- input: total=1 (info=0, warn=0, fail=1)" in summary_text
    assert (
        "- [FAIL] input / MISSING_REQUIRED_INPUTS: Missing required input workbook." in summary_text
    )
    assert "- [FAIL] input: Restore required input files before rerunning." in summary_text


def test_manifest_records_date_resolution_block_when_resolutions_supplied(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    workbook_path.write_bytes(b"hist")

    config = _make_config(tmp_path).model_copy(update={"as_of_date": None})
    as_of_resolution = resolve_as_of_date(config, {"CPRS CH Header Date": "02/13/2026"})
    run_resolution = resolve_run_date(config.model_copy(update={"run_date": date(2026, 2, 14)}))

    builder = ManifestBuilder(
        config=config,
        as_of_date=as_of_resolution.value,
        run_date=run_resolution.value,
        as_of_date_resolution=as_of_resolution,
        run_date_resolution=run_resolution,
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={"monthly_pptx": "abc123"},
        output_paths=[Path(workbook_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )
    manifest_path = builder.write(run_dir=run_dir, manifest=manifest)
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert parsed["as_of_date"] == "2026-02-13"
    assert parsed["run_date"] == "2026-02-14"
    assert parsed["date_resolution"]["as_of_date"] == {
        "value": "2026-02-13",
        "source": "cprs_header_mapping",
        "details": {
            "header_label": "CPRS CH Header Date",
            "raw_value": "02/13/2026",
        },
    }
    assert parsed["date_resolution"]["run_date"] == {
        "value": "2026-02-14",
        "source": "config",
        "details": {"config_field": "run_date"},
    }


def test_manifest_date_resolution_falls_back_when_resolutions_omitted(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "2026-02-13"
    run_dir.mkdir(parents=True)
    workbook_path = run_dir / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx"
    workbook_path.write_bytes(b"hist")

    builder = ManifestBuilder(
        config=_make_config(tmp_path),
        as_of_date=date(2026, 2, 13),
        run_date=date(2026, 2, 14),
    )
    manifest = builder.build(
        run_dir=run_dir,
        input_hashes={},
        output_paths=[Path(workbook_path.name)],
        top_exposures={"all_programs": []},
        top_changes_per_variant={"all_programs": []},
        warnings=[],
    )

    assert manifest["date_resolution"] == {
        "as_of_date": {"value": "2026-02-13", "source": "unspecified", "details": {}},
        "run_date": {"value": "2026-02-14", "source": "unspecified", "details": {}},
    }
