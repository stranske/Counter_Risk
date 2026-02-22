from __future__ import annotations

from datetime import date

from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names


def test_resolve_ppt_output_names_uses_expected_master_and_distribution_patterns() -> None:
    names = resolve_ppt_output_names(date(2026, 1, 31))

    assert (
        names.master_filename == "Monthly Counterparty Exposure Report (Master) - 2026-01-31.pptx"
    )
    assert names.distribution_filename == "Monthly Counterparty Exposure Report - 2026-01-31.pptx"


def test_resolve_ppt_output_names_is_deterministic_for_same_date() -> None:
    as_of_date = date(2025, 12, 31)

    first = resolve_ppt_output_names(as_of_date)
    second = resolve_ppt_output_names(as_of_date)

    assert first == second
