"""Top exposure extraction/sorting tests."""

from __future__ import annotations

import json
from pathlib import Path

from counter_risk.chat.session import (
    _extract_top_exposure_rows,
    _limit_top_exposure_rows,
    _sort_top_exposure_rows,
)
from counter_risk.chat.utils import cmp_with_tol

_FIXTURE_PATH = Path("tests/fixtures/runs/min_run/manifest.json")


def _load_fixture_manifest() -> dict[str, object]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_top_exposure_rows_sorted_in_non_increasing_order() -> None:
    manifest = _load_fixture_manifest()
    rows = _extract_top_exposure_rows(manifest)

    sorted_rows = _sort_top_exposure_rows(rows)
    values = [float(row["value"]) for row in sorted_rows]

    for left, right in zip(values, values[1:], strict=False):
        assert cmp_with_tol(left, right) >= 0


def test_top_exposure_rows_multi_row_output_length_at_least_three() -> None:
    manifest = _load_fixture_manifest()
    rows = _extract_top_exposure_rows(manifest)

    sorted_rows = _sort_top_exposure_rows(rows)
    top_rows = _limit_top_exposure_rows(sorted_rows, top_n=5, min_value=0.0)

    assert len(top_rows) >= 3


def test_top_exposure_sorting_uses_tolerance_for_nearly_equal_values() -> None:
    manifest = _load_fixture_manifest()
    rows = _extract_top_exposure_rows(manifest)

    sorted_rows = _sort_top_exposure_rows(rows)
    top_two_names = [str(row["name"]) for row in sorted_rows[:2]]

    assert top_two_names == ["Alpha", "Beta"]
