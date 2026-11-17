from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.config import WorkflowConfig
from counter_risk.outputs import (
    HistoricalWalWorkbookOutputGenerator,
    HistoricalWorkbookOutputGenerator,
    OutputContext,
)
from counter_risk.parsers.cprs_ch import ClassNotionalBreakdown
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.manifest_schema import validate_manifest


def _minimal_config(tmp_path: Path) -> WorkflowConfig:
    for filename in (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    ):
        (tmp_path / filename).write_bytes(b"placeholder")

    return WorkflowConfig(
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist_all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist_ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist_llc.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
    )


def _output_context(tmp_path: Path) -> OutputContext:
    return OutputContext(
        config=_minimal_config(tmp_path),
        run_dir=tmp_path / "run",
        as_of_date=date(2026, 1, 31),
        run_date=date(2026, 2, 1),
    )


def test_historical_wal_generator_delegates_to_existing_wal_update_flow(tmp_path: Path) -> None:
    exposure_summary_path = tmp_path / "exposure-summary.xlsx"
    exposure_summary_path.write_bytes(b"placeholder")
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_bytes(b"placeholder")
    calls: list[tuple[str, object, object]] = []

    def _fake_locate() -> Path:
        calls.append(("locate", None, None))
        return workbook_path

    def _fake_calculate(path: Path, px_date: date) -> float:
        calls.append(("calculate_wal", path, px_date))
        return 2.718

    def _fake_append(path: str | Path, *, px_date: date, wal_value: float) -> Path:
        calls.append(("append_wal_row", Path(path), (px_date, wal_value)))
        return Path(path)

    generator = HistoricalWalWorkbookOutputGenerator(
        exposure_summary_path=exposure_summary_path,
        workbook_locator=_fake_locate,
        wal_calculator=_fake_calculate,
        wal_appender=_fake_append,
    )

    generated = generator.generate(context=_output_context(tmp_path))

    assert generator.name == "historical_wal_workbook"
    assert generated == (workbook_path,)
    assert calls == [
        ("locate", None, None),
        ("calculate_wal", exposure_summary_path, date(2026, 1, 31)),
        ("append_wal_row", workbook_path, (date(2026, 1, 31), 2.718)),
    ]


def test_historical_wal_generator_uses_explicit_workbook_path_when_provided(tmp_path: Path) -> None:
    exposure_summary_path = tmp_path / "exposure-summary.xlsx"
    exposure_summary_path.write_bytes(b"placeholder")
    workbook_path = tmp_path / "historical.xlsx"
    workbook_path.write_bytes(b"placeholder")

    locate_calls: list[str] = []

    def _fake_locate() -> Path:
        locate_calls.append("called")
        return tmp_path / "unexpected.xlsx"

    def _fake_calculate(path: Path, px_date: date) -> float:
        del path, px_date
        return 1.23

    def _fake_append(path: str | Path, *, px_date: date, wal_value: float) -> Path:
        del px_date, wal_value
        return Path(path)

    generator = HistoricalWalWorkbookOutputGenerator(
        exposure_summary_path=exposure_summary_path,
        workbook_path=workbook_path,
        workbook_locator=_fake_locate,
        wal_calculator=_fake_calculate,
        wal_appender=_fake_append,
    )

    generated = generator.generate(context=_output_context(tmp_path))

    assert generated == (workbook_path,)
    assert locate_calls == []


def test_historical_workbook_generator_wraps_pipeline_historical_update_flow(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output_context = _output_context(tmp_path)
    warnings: list[str] = []
    copied: list[tuple[Path, Path]] = []
    merged: list[tuple[Path, str, float, int]] = []
    expected_outputs = (
        run_dir / "hist_all.xlsx",
        run_dir / "hist_ex.xlsx",
        run_dir / "hist_llc.xlsx",
    )

    parsed_by_variant: dict[str, dict[str, object]] = {
        "all_programs": {"cprs_ch": [{"Notional": 100.0}]},
        "ex_trend": {"cprs_ch": [{"Notional": 200.0}]},
        "trend": {"cprs_ch": [{"Notional": 300.0}]},
    }

    def _fake_copy(src: str | Path, dst: str | Path, *, follow_symlinks: bool = True) -> str:
        del follow_symlinks
        source = Path(src)
        target = Path(dst)
        copied.append((source, target))
        target.write_bytes(source.read_bytes())
        return str(target)

    def _fake_records(table: Any) -> list[dict[str, object]]:
        return [dict(record) for record in table]

    breakdowns_seen: list[tuple[str, dict[str, float] | None]] = []

    def _fake_merge(
        *,
        workbook_path: Path,
        variant: str,
        as_of_date: date,
        cprs_ch_records: list[dict[str, object]],
        formatting_profile: str | None = None,
        class_breakdown: dict[str, float] | None = None,
        class_breakdown_source: str | None = None,
        coerced_invalid_cells: int = 0,
        warnings: list[str],
    ) -> None:
        del warnings, formatting_profile, class_breakdown_source, coerced_invalid_cells
        notional = cast(float, cprs_ch_records[0]["Notional"])
        merged.append((workbook_path, variant, float(notional), as_of_date.month))
        breakdowns_seen.append((variant, class_breakdown))

    def _fake_breakdown_reader(path: Path) -> dict[str, float] | None:
        del path
        return {"TIPS": 0.1, "Treasury": 0.2, "Equity": 0.3, "Commodity": 0.2, "Currency": 0.2}

    generator = HistoricalWorkbookOutputGenerator(
        parsed_by_variant=parsed_by_variant,
        warnings=warnings,
        workbook_copier=_fake_copy,
        records_extractor=_fake_records,
        workbook_merger=_fake_merge,
        class_breakdown_reader=_fake_breakdown_reader,
    )

    generated = generator.generate(context=output_context)

    assert generator.name == "historical_workbook"
    assert generated == expected_outputs
    assert [target for _, target in copied] == list(expected_outputs)
    assert merged == [
        (expected_outputs[0], "all_programs", 100.0, 1),
        (expected_outputs[1], "ex_trend", 200.0, 1),
        (expected_outputs[2], "trend", 300.0, 1),
    ]
    # The published class breakdown must reach the merger for every variant: Trend's
    # mix comes from an absolute-value row that cannot be derived from the records.
    assert [variant for variant, _ in breakdowns_seen] == ["all_programs", "ex_trend", "trend"]
    assert all(breakdown is not None for _, breakdown in breakdowns_seen)
    assert generator.class_breakdown_sources == dict.fromkeys(parsed_by_variant, "plain")
    assert len(warnings) == 1
    assert "trend uses plain" in warnings[0]


def _generate_class_breakdowns(
    tmp_path: Path, trend_result, *, extra_warnings=(), variant_results=None
):
    context = _output_context(tmp_path)
    context.run_dir.mkdir()
    warnings: list[str] = list(extra_warnings)
    merges: dict[str, dict[str, Any]] = {}

    def reader(path: Path):
        if variant_results is not None and path.name in variant_results:
            result = variant_results[path.name]
            if isinstance(result, Exception):
                raise result
            return result
        if path == context.config.mosers_trend_xlsx:
            return trend_result
        return ClassNotionalBreakdown({"Equity": 1.0}, "plain")

    def merge(**kwargs):
        merges[kwargs["variant"]] = kwargs

    generator = HistoricalWorkbookOutputGenerator(
        parsed_by_variant={
            variant: {"cprs_ch": [{"Notional": 100.0, "Equity": 100.0}]}
            for variant in ("all_programs", "ex_trend", "trend")
        },
        warnings=warnings,
        workbook_merger=merge,
        records_extractor=lambda records: records,
        class_breakdown_reader=reader,
    )
    outputs = generator.generate(context=context)
    builder = ManifestBuilder(
        config=context.config.model_copy(update={"enable_ppt_output": False}),
        as_of_date=context.as_of_date,
        run_date=context.run_date,
    )
    manifest = builder.build(
        run_dir=context.run_dir,
        input_hashes={},
        output_paths=list(outputs),
        top_exposures={},
        top_changes_per_variant={},
        warnings=warnings,
        class_breakdown_sources=generator.class_breakdown_sources,
    )
    path = builder.write(run_dir=context.run_dir, manifest=manifest)
    persisted = json.loads(path.read_text())
    assert validate_manifest(persisted) == (True, None)
    summary = (context.run_dir / "DATA_QUALITY_SUMMARY.txt").read_text()
    return warnings, merges, persisted, summary


def test_trend_class_breakdown_missing_warns_record_derived_fallback(tmp_path: Path) -> None:
    warnings, merges, manifest, summary = _generate_class_breakdowns(tmp_path, None)

    assert len(warnings) == 1, {
        "warnings": warnings,
        "overall_status": manifest["data_quality"]["overall_status"],
        "finding_codes": [row["code"] for row in manifest["data_quality"]["findings"]],
        "trend_source": manifest["class_breakdown_sources"]["trend"],
    }
    assert "trend" in warnings[0]
    assert "record-derived fallback" in warnings[0]
    assert merges["trend"]["class_breakdown"] is None
    assert manifest["class_breakdown_sources"] == {
        "all_programs": "plain",
        "ex_trend": "plain",
        "trend": "record-derived",
    }
    quality = manifest["data_quality"]
    assert quality["overall_status"] == "warn"
    assert [(finding["code"], finding["severity"]) for finding in quality["findings"]] == [
        ("CLASS_BREAKDOWN_FALLBACK", "warn")
    ]
    assert "Overall status: WARN (YELLOW)" in summary


@pytest.mark.parametrize(
    ("result", "source", "status", "codes", "color"),
    [
        (
            ClassNotionalBreakdown({"Equity": 1.0}, "absolute"),
            "absolute",
            "info",
            ["NO_FINDINGS"],
            "GREEN",
        ),
        (
            ClassNotionalBreakdown({"Equity": -1.0}, "plain"),
            "plain",
            "warn",
            ["CLASS_BREAKDOWN_FALLBACK"],
            "YELLOW",
        ),
        ({"Equity": 1.0}, "plain", "warn", ["CLASS_BREAKDOWN_FALLBACK"], "YELLOW"),
        ({}, "record-derived", "warn", ["CLASS_BREAKDOWN_FALLBACK"], "YELLOW"),
        (
            ClassNotionalBreakdown({"Equity": 0.0}, "absolute", 2),
            "absolute",
            "warn",
            ["CLASS_BREAKDOWN_CELL_COERCED"],
            "YELLOW",
        ),
        (
            ClassNotionalBreakdown({"Equity": 0.0}, "plain", 1),
            "plain",
            "warn",
            ["CLASS_BREAKDOWN_FALLBACK", "CLASS_BREAKDOWN_CELL_COERCED"],
            "YELLOW",
        ),
    ],
)
def test_trend_class_breakdown_provenance_controls_quality(
    tmp_path: Path, result, source, status, codes, color
) -> None:
    warnings, merges, manifest, summary = _generate_class_breakdowns(tmp_path, result)

    assert manifest["class_breakdown_sources"]["trend"] == source
    assert manifest["data_quality"]["overall_status"] == status
    assert [row["code"] for row in manifest["data_quality"]["findings"]] == codes
    assert all(row["severity"] == status for row in manifest["data_quality"]["findings"])
    assert f"Overall status: {status.upper()} ({color})" in summary
    expected = result.values if isinstance(result, ClassNotionalBreakdown) else result
    assert merges["trend"]["class_breakdown"] == expected
    if status == "warn":
        assert len(warnings) == len(codes)
    else:
        assert warnings == []


def test_trend_fallback_does_not_hide_failing_quality_checks(tmp_path: Path) -> None:
    _, _, manifest, summary = _generate_class_breakdowns(
        tmp_path, None, extra_warnings=["Source processing failed"]
    )
    assert manifest["data_quality"]["overall_status"] == "fail"
    assert manifest["data_quality"]["counts"]["by_severity"] == {"info": 0, "warn": 1, "fail": 1}
    assert "Overall status: FAIL (RED)" in summary


@pytest.mark.parametrize("filename", ["all.xlsx", "ex.xlsx", "trend.xlsx"])
@pytest.mark.parametrize("result", [None, {}, ValueError("source failed to load")])
def test_each_variant_warns_on_record_derived_fallback(tmp_path: Path, filename, result) -> None:
    warnings, _, manifest, _ = _generate_class_breakdowns(
        tmp_path,
        ClassNotionalBreakdown({"Equity": 1.0}, "absolute"),
        variant_results={filename: result},
    )
    variant = {"all.xlsx": "all_programs", "ex.xlsx": "ex_trend", "trend.xlsx": "trend"}[filename]
    assert len(warnings) == 1
    assert variant in warnings[0]
    assert "record-derived fallback" in warnings[0]
    assert manifest["class_breakdown_sources"][variant] == "record-derived"
    assert manifest["data_quality"]["overall_status"] == "warn"
    assert manifest["data_quality"]["findings"][0]["code"] == "CLASS_BREAKDOWN_FALLBACK"


@pytest.mark.parametrize("filename", ["all.xlsx", "ex.xlsx", "trend.xlsx"])
def test_each_variant_warns_on_coerced_cells(tmp_path: Path, filename) -> None:
    warnings, merges, manifest, _ = _generate_class_breakdowns(
        tmp_path,
        ClassNotionalBreakdown({"Equity": 1.0}, "absolute"),
        variant_results={filename: ClassNotionalBreakdown({"Equity": 0.0}, "absolute", 3)},
    )
    variant = {"all.xlsx": "all_programs", "ex.xlsx": "ex_trend", "trend.xlsx": "trend"}[filename]
    assert len(warnings) == 1
    assert variant in warnings[0]
    assert "3 invalid cell(s)" in warnings[0]
    assert merges[variant]["coerced_invalid_cells"] == 3
    assert manifest["data_quality"]["findings"][0]["code"] == "CLASS_BREAKDOWN_CELL_COERCED"


def test_pipeline_historical_update_reads_provenance_and_records_sources(tmp_path: Path) -> None:
    from openpyxl import Workbook, load_workbook

    from counter_risk.pipeline.run import _update_historical_outputs

    config = _minimal_config(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for filename in ("hist_all.xlsx", "hist_ex.xlsx", "hist_llc.xlsx"):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Class"
        sheet.append(["Date", "TIPS", "Treasury", "Equity", "Commodity", "Currency"])
        sheet.append([date(2025, 12, 31), 0, 0, 1, 0, 0])
        workbook.save(tmp_path / filename)
        workbook.close()
    for filename, label in (
        ("all.xlsx", "Notional Breakdown"),
        ("ex.xlsx", "No published shares"),
        ("trend.xlsx", "Notional Breakdown (Absolute Values)"),
    ):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "CPRS - CH"
        sheet.append(
            [
                None,
                "Counterparty",
                "TIPS",
                "Treasury",
                "Equity",
                "Commodity",
                "Currency",
                "Notional",
            ]
        )
        sheet.append([label, None, 0, 0, "invalid" if filename == "trend.xlsx" else 1, 0, 0])
        workbook.save(tmp_path / filename)
        workbook.close()
    warnings: list[str] = []
    sources: dict[str, str] = {}
    outputs = _update_historical_outputs(
        run_dir=run_dir,
        config=config,
        parsed_by_variant={
            variant: {"cprs_ch": [{"Segment": "totals", "Notional": 100.0, "Equity": 100.0}]}
            for variant in ("all_programs", "ex_trend", "trend")
        },
        as_of_date=date(2026, 1, 31),
        warnings=warnings,
        class_breakdown_sources=sources,
    )
    assert sources == {"all_programs": "plain", "ex_trend": "record-derived", "trend": "absolute"}
    # Generator and merger must not emit duplicate findings for the same issue.
    assert len(warnings) == 2
    assert "CLASS_BREAKDOWN_FALLBACK: ex_trend" in warnings[0]
    assert "CLASS_BREAKDOWN_CELL_COERCED: trend" in warnings[1]
    for path in outputs:
        workbook = load_workbook(path)
        try:
            assert workbook["Class"].max_row == 3
            assert workbook["Class"].cell(3, 4).value == (0 if path.name == "hist_llc.xlsx" else 1)
        finally:
            workbook.close()
