"""Acceptance-focused tests for raw NISA to MOSERS generation in the pipeline."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import counter_risk.pipeline.run as run_module
from counter_risk.io.excel_range_compare import WorkbookRangeComparison, compare_workbook_ranges
from counter_risk.pipeline.run import run_pipeline


def test_run_pipeline_generates_non_vba_mosers_outputs_matching_reference_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = Path("tests/fixtures")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                f"raw_nisa_all_programs_xlsx: {fixtures / 'NISA Monthly All Programs - Raw.xlsx'}",
                f"raw_nisa_ex_trend_xlsx: {fixtures / 'NISA Monthly Ex Trend - Raw.xlsx'}",
                f"raw_nisa_trend_xlsx: {fixtures / 'NISA Monthly Trend - Raw.xlsx'}",
                f"hist_all_programs_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx'}",
                f"hist_ex_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx'}",
                f"hist_llc_3yr_xlsx: {fixtures / 'Historical Counterparty Risk Graphs - LLC 3 Year.xlsx'}",
                f"monthly_pptx: {fixtures / 'Monthly Counterparty Exposure Report.pptx'}",
                f"output_root: {tmp_path / 'runs'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_module,
        "_run_reconciliation_checks",
        lambda *, run_dir, config, parsed_by_variant, warnings: None,
    )
    monkeypatch.setattr(
        run_module,
        "_compute_metrics",
        lambda parsed_by_variant: ({}, {}),
    )
    monkeypatch.setattr(
        run_module,
        "_compute_and_write_concentration_metrics",
        lambda *, parsed_by_variant, run_dir: [],
    )
    monkeypatch.setattr(
        run_module,
        "_update_historical_outputs",
        lambda *, run_dir, config, parsed_by_variant, as_of_date, warnings: [],
    )
    monkeypatch.setattr(
        run_module,
        "_write_outputs",
        lambda *, run_dir, config, as_of_date, warnings: (
            [],
            run_module.PptProcessingResult(status=run_module.PptProcessingStatus.SUCCESS),
        ),
    )

    run_dir = run_pipeline(config_path)
    references = {
        "all_programs": fixtures
        / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
        "ex_trend": fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
        "trend": fixtures / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
    }

    comparisons_by_variant = {
        "all_programs": (
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "N5:N5"),
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "C30:C30"),
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "C48:C52"),
        ),
        "ex_trend": (
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "C8:C9"),
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "G8:G9"),
            WorkbookRangeComparison("CPRS - CH", "CPRS - CH", "K8:L9"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "C5:C6"),
        ),
        "trend": (
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "C8:C8"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "G8:G8"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "I8:I8"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "K8:L8"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "C25:C26"),
            WorkbookRangeComparison("CPRS - FCM", "CPRS - FCM", "H25:H26"),
        ),
    }

    for variant, comparisons in comparisons_by_variant.items():
        generated_workbook = run_dir / f"{variant}-mosers-input.xlsx"
        assert generated_workbook.exists()

        with zipfile.ZipFile(generated_workbook) as workbook_archive:
            archive_members = {member.casefold() for member in workbook_archive.namelist()}
        assert "xl/vbaproject.bin" not in archive_members

        differences = compare_workbook_ranges(
            references[variant],
            generated_workbook,
            comparisons=comparisons,
            numeric_tolerance=1e-6 if variant == "ex_trend" else 0.0,
        )
        assert differences == []
