"""Evidence provenance contract for manifest top exposure facts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig
from counter_risk.observability.langsmith_fleet import FleetRunContext, build_fleet_records
from counter_risk.pipeline import run as run_module
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.pipeline.manifest_schema import validate_manifest


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key(child, key) for child in value)
    return False


class _FakeDataFrame:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = [dict(record) for record in records]

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        if orient != "records":
            raise ValueError("Only records orient is supported")
        return [dict(record) for record in self._records]


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


def test_top_exposures_carry_source_evidence_that_validates_in_manifest(
    tmp_path: Path,
) -> None:
    """Top exposure facts point back to a manifest input hash source."""

    top_exposures, top_changes = run_module._compute_metrics(
        {
            "all_programs": {
                "totals": _FakeDataFrame(
                    [
                        {
                            "counterparty": "Alpha Bank",
                            "Notional": 100.0,
                            "NotionalChange": 3.0,
                        }
                    ]
                ),
                "totals_evidence": {
                    "Alpha Bank": {
                        "counterparty": "Alpha Bank",
                        "sheet": "CPRS - FCM",
                        "row": 42,
                        "method": "nisa_parser",
                    }
                },
            }
        }
    )
    entry = top_exposures["all_programs"][0]
    evidence = entry["evidence"]

    assert evidence["source_id"] == "mosers_all_programs_xlsx"
    assert evidence["sheet"] == "CPRS - FCM"
    assert evidence["row"] == 42
    assert evidence["method"] == "nisa_parser"

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
        input_hashes={"mosers_all_programs_xlsx": "sha256"},
        output_paths=[Path(workbook_path.name)],
        top_exposures=top_exposures,
        top_changes_per_variant=top_changes,
        warnings=[],
    )

    assert evidence["source_id"] in manifest["input_hashes"]
    is_valid, reason = validate_manifest(manifest)
    assert is_valid, reason
    assert reason is None


def test_langsmith_fleet_records_do_not_export_evidence_fields() -> None:
    """Local evidence provenance stays out of dashboard-safe LangSmith records."""

    records = build_fleet_records(
        context=FleetRunContext(
            run_id="run-123",
            as_of_date="2026-02-13",
            scenario="fixture",
        ),
        data_quality_status="info",
        risk_proxy_status="success",
        concentration_metric_count=1,
        limit_breach_count=0,
        report_artifacts=["manifest.json"],
    )

    assert not _contains_key(records, "source_id")
    assert not _contains_key(records, "evidence")
