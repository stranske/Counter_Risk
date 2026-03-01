"""Unit tests for operator formatting profile resolution."""

from __future__ import annotations

from counter_risk.formatting import (
    DEFAULT_FORMATTING_PROFILE,
    normalize_formatting_profile,
    resolve_formatting_policy,
)


def test_normalize_formatting_profile_defaults_unknown_and_empty_values() -> None:
    assert normalize_formatting_profile(None) == DEFAULT_FORMATTING_PROFILE
    assert normalize_formatting_profile("") == DEFAULT_FORMATTING_PROFILE
    assert normalize_formatting_profile("  ") == DEFAULT_FORMATTING_PROFILE
    assert normalize_formatting_profile("not-a-profile") == DEFAULT_FORMATTING_PROFILE


def test_normalize_formatting_profile_accepts_known_profiles() -> None:
    assert normalize_formatting_profile("currency") == "currency"
    assert normalize_formatting_profile("ACCOUNTING") == "accounting"
    assert normalize_formatting_profile(" plain ") == "plain"


def test_resolve_formatting_policy_returns_expected_excel_formats() -> None:
    currency = resolve_formatting_policy("currency")
    assert currency.notional_number_format == "$#,##0.00;[Red]-$#,##0.00"
    assert currency.counterparties_number_format == "0"

    accounting = resolve_formatting_policy("accounting")
    assert accounting.notional_number_format is not None
    assert "#,##0.00" in accounting.notional_number_format
    assert accounting.counterparties_number_format == "0"

    default = resolve_formatting_policy("default")
    assert default.notional_number_format is None
    assert default.counterparties_number_format is None

