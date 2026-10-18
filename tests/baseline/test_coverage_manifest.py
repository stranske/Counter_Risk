"""Coverage manifest -- which flat metric keys are exercised; emit a report.

Uses the generic ``baseline_kit.CoverageManifest``. The app supplies the input
space (every flat metric key the surface produces across all scenarios) and the
touched set (metric keys referenced by at least one directional check).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from baseline_kit import CoverageManifest, evaluate_direction, load_catalog

from . import adapter
from .conftest import CATALOG_PATH, REPO_ROOT

REPORT_PATH = REPO_ROOT / "docs" / "reports" / "baseline-coverage.md"

# Segment top-share directionals added for issue #1163; each priority key must
# stay uniquely covered by its named check so deletion exposes a gap.
_SEGMENT_SHARE_DIRECTIONALS = (
    "treasury_dispersed_lowers_top5",
    "treasury_dispersed_lowers_top10",
    "equity_dispersed_lowers_top5",
    "equity_dispersed_lowers_top10",
)


def _all_metric_keys(catalog) -> set[str]:
    base_rows = catalog["base"]["exposures"]
    keys: set[str] = set()
    for scenario in catalog["scenarios"]:
        keys.update(adapter.run_scenario(scenario, base_rows).keys())
    return keys


def _build_manifest() -> CoverageManifest:
    catalog = load_catalog(CATALOG_PATH)
    touched = {d["metric"] for d in catalog.get("directionals", [])}
    return CoverageManifest(
        all_keys=_all_metric_keys(catalog),
        touched_keys=touched,
        priority_params=list(catalog.get("priority_metrics", [])),
        title="Counter_Risk baseline coverage manifest",
    )


def test_directional_metrics_exist():
    m = _build_manifest()
    assert not m.unknown_catalog_keys, (
        "Directional checks reference metric keys the adapter never produces: "
        f"{sorted(m.unknown_catalog_keys)}"
    )


def test_priority_metrics_covered():
    m = _build_manifest()
    assert not m.priority_gaps, "Priority metrics with no directional check: " + ", ".join(
        m.priority_gaps
    )


def test_emit_coverage_report(tmp_path: Path):
    m = _build_manifest()
    report_path = (
        REPORT_PATH
        if os.environ.get("BASELINE_REFRESH_REPORT") == "1"
        else tmp_path / "baseline-coverage.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(m.to_markdown())
    assert report_path.exists()
    # Declared catalog coverage is nine of nine flat keys; the kit's
    # "Observed read at runtime" count is not production wiring evidence.
    assert "Input parameters: **9**" in report_path.read_text()
    assert "Exercised by a scenario: **9**" in report_path.read_text()


@pytest.mark.parametrize("directional_id", _SEGMENT_SHARE_DIRECTIONALS)
def test_removing_segment_share_directional_exposes_priority_gap(directional_id: str) -> None:
    """Deleting each required segment-share directional must open a priority gap."""
    catalog = load_catalog(CATALOG_PATH)
    directionals = catalog["directionals"]
    removed = next(d for d in directionals if d["id"] == directional_id)
    touched = {d["metric"] for d in directionals if d["id"] != directional_id}
    manifest = CoverageManifest(
        all_keys=_all_metric_keys(catalog),
        touched_keys=touched,
        priority_params=list(catalog.get("priority_metrics", [])),
        title="Counter_Risk baseline coverage manifest",
    )
    assert removed["metric"] in manifest.priority_gaps, (
        f"Removing {directional_id} should gap priority key {removed['metric']}; "
        f"gaps={manifest.priority_gaps}"
    )


@pytest.mark.parametrize("directional_id", _SEGMENT_SHARE_DIRECTIONALS)
def test_constant_one_mutation_fails_segment_share_directional(directional_id: str) -> None:
    """Freezing the variant segment share at 1.0 must fail the decrease check."""
    catalog = load_catalog(CATALOG_PATH)
    scenarios = {s["id"]: s for s in catalog["scenarios"]}
    scen = next(d for d in catalog["directionals"] if d["id"] == directional_id)
    base_rows = catalog["base"]["exposures"]
    control = adapter.run_scenario(scenarios[scen["control"]], base_rows)[scen["metric"]]
    holds = evaluate_direction(scen["direction"], 1.0, control)
    assert scen.get("enforce") is True
    assert not holds, (
        f"{directional_id}: constant-1.0 variant must fail {scen['direction']} "
        f"vs control={control}"
    )
