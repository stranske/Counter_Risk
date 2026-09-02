"""Top exposure extraction/sorting tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from counter_risk.chat.session import (
    _extract_top_exposure_rows,
    _format_top_exposures,
    _limit_top_exposure_rows,
    _sort_top_exposure_rows,
)
from counter_risk.chat.utils import cmp_with_tol

_FIXTURE_PATH = Path("tests/fixtures/runs/min_run/manifest.json")


def _load_fixture_manifest() -> dict[str, object]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast(dict[str, object], payload)


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


def test_top_exposure_extraction_ignores_malformed_values_and_uses_numeric_fallbacks() -> None:
    manifest: dict[str, object] = {
        "top_exposures": {
            "all_programs": [
                None,
                {"counterparty": "Bool", "notional": True},
                {"counterparty": "Blank", "notional": "   "},
                {"counterparty": "Invalid", "notional": "not-a-number"},
                {"name": "Fallback", "custom_value": "1,234.50"},
            ],
            "not-a-list": "ignored",
        }
    }

    assert _extract_top_exposure_rows(manifest) == [
        {"variant": "all_programs", "name": "Fallback", "value": 1234.5}
    ]


def test_top_exposure_formatting_is_deterministic_and_filters_negative_values() -> None:
    manifest: dict[str, object] = {
        "top_exposures": {
            "b_variant": [{"name": "Beta", "notional": 10}],
            "a_variant": [
                {"name": "Zulu", "notional": 10},
                {"name": "Alpha", "notional": 10},
                {"name": "Tiny", "notional": 0.0000001},
                {"name": "Negative", "notional": -1},
            ],
        }
    }
    all_negative_manifest: dict[str, object] = {
        "top_exposures": {
            "a_variant": [{"name": "Negative", "notional": -1}],
        }
    }

    assert _format_top_exposures({}) == "No top exposures found in manifest."
    assert _format_top_exposures(all_negative_manifest) == "No top exposures found in manifest."
    assert _format_top_exposures(manifest) == (
        "a_variant: Alpha (10.00); a_variant: Zulu (10.00); "
        "b_variant: Beta (10.00); a_variant: Tiny (0.00)"
    )
