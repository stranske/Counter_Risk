"""Hand-checkable Treasury/Equity dispersion fixtures (issue #1163).

Verifies the segment-only dispersion scenarios cross both concentration cutoffs
(>10 positive names ⇒ top5/top10 < 1.0), match independently calculated expected
shares, and leave the other segments' metrics identical to the base control.
"""

from __future__ import annotations

import pytest
from baseline_kit import load_catalog

from . import adapter
from .conftest import CATALOG_PATH

_TOL = 1e-12
_CATALOG = load_catalog(CATALOG_PATH)
_BASE_ROWS = _CATALOG["base"]["exposures"]
_SCENARIOS = {s["id"]: s for s in _CATALOG["scenarios"]}

# Independently calculated from the catalog patch DSL (see catalog.yaml comments).
# Treasury: [120, 50, 30] + 11×55 → N=14, sum=805; top5=340/805, top10=615/805.
_TREASURY_EXPECTED = {
    "n_positive": 14,
    "top5_share": 340.0 / 805.0,
    "top10_share": 615.0 / 805.0,
}
# Equity: [70, 30] + 11×40 → N=13, sum=540; top5=230/540, top10=430/540.
_EQUITY_EXPECTED = {
    "n_positive": 13,
    "top5_share": 230.0 / 540.0,
    "top10_share": 430.0 / 540.0,
}

_CONTROL_SEGMENTS = {
    "treasury_dispersed": ("total", "equity"),
    "equity_dispersed": ("total", "treasury"),
}


def _positive_count(scenario_id: str, segment: str) -> int:
    rows = adapter.apply_patch(_BASE_ROWS, _SCENARIOS[scenario_id].get("patch"))
    return sum(1 for row in rows if row.get("segment") == segment and float(row["notional"]) > 0.0)


def _metrics(scenario_id: str) -> dict[str, float]:
    return adapter.run_scenario(_SCENARIOS[scenario_id], _BASE_ROWS)


@pytest.mark.parametrize(
    ("scenario_id", "segment", "expected"),
    [
        ("treasury_dispersed", "treasury", _TREASURY_EXPECTED),
        ("equity_dispersed", "equity", _EQUITY_EXPECTED),
    ],
)
def test_dispersion_crosses_cutoffs_with_hand_checkable_shares(
    scenario_id: str, segment: str, expected: dict
) -> None:
    """>10 positive names; top5/top10 < control 1.0 and match hand-calc shares."""
    n_pos = _positive_count(scenario_id, segment)
    assert n_pos == expected["n_positive"]
    assert n_pos > 10

    metrics = _metrics(scenario_id)
    control = _metrics("base")
    top5_key = f"all_programs.{segment}.top5_share"
    top10_key = f"all_programs.{segment}.top10_share"

    assert control[top5_key] == pytest.approx(1.0, abs=_TOL)
    assert control[top10_key] == pytest.approx(1.0, abs=_TOL)

    assert metrics[top5_key] == pytest.approx(expected["top5_share"], abs=_TOL)
    assert metrics[top10_key] == pytest.approx(expected["top10_share"], abs=_TOL)
    assert metrics[top5_key] < 1.0 - _TOL
    assert metrics[top10_key] < 1.0 - _TOL
    assert metrics[top5_key] < control[top5_key]
    assert metrics[top10_key] < control[top10_key]


@pytest.mark.parametrize("scenario_id", ["treasury_dispersed", "equity_dispersed"])
def test_dispersion_leaves_control_segments_unaffected(scenario_id: str) -> None:
    """Segment-only patches must not move total or the other product segment."""
    metrics = _metrics(scenario_id)
    control = _metrics("base")
    for segment in _CONTROL_SEGMENTS[scenario_id]:
        for metric in adapter.METRIC_NAMES:
            key = f"all_programs.{segment}.{metric}"
            assert metrics[key] == pytest.approx(control[key], abs=_TOL), key
