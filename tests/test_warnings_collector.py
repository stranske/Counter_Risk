"""Unit tests for structured warning collection."""

from __future__ import annotations

from counter_risk.pipeline.warnings import WarningsCollector


def test_add_structured_requires_row_idx_and_stores_dict_record() -> None:
    collector = WarningsCollector()

    collector.add_structured(7, code="NO_PRIOR_MATCH", message="Missing prior row")

    assert collector.warnings == [
        {"row_idx": 7, "code": "NO_PRIOR_MATCH", "message": "Missing prior row"}
    ]


def test_add_structured_filters_blank_extra_fields() -> None:
    collector = WarningsCollector()

    collector.add_structured(
        3,
        code="INVALID_NOTIONAL",
        message="invalid notional value",
        missing_none=None,
        missing_empty="",
        missing_whitespace="   ",
        retained_number=42,
        retained_text="ABC",
    )

    assert collector.warnings == [
        {
            "row_idx": 3,
            "code": "INVALID_NOTIONAL",
            "message": "invalid notional value",
            "retained_number": 42,
            "retained_text": "ABC",
        }
    ]


def test_warn_uses_structured_storage_with_default_row_idx() -> None:
    collector = WarningsCollector()

    collector.warn("Unmatched current row", code="NO_PRIOR_MONTH_MATCH")

    assert collector.warnings == [
        {
            "row_idx": -1,
            "code": "NO_PRIOR_MONTH_MATCH",
            "message": "Unmatched current row",
        }
    ]


def test_warn_filters_blank_extras_and_preserves_non_empty_extras() -> None:
    collector = WarningsCollector()

    collector.warn(
        "invalid row",
        code="MISSING_DESCRIPTION",
        row_idx="12",
        description="TY Mar25",
        missing_none=None,
        missing_empty="",
        missing_whitespace="   ",
    )

    assert collector.warnings == [
        {
            "row_idx": 12,
            "code": "MISSING_DESCRIPTION",
            "message": "invalid row",
            "description": "TY Mar25",
        }
    ]
