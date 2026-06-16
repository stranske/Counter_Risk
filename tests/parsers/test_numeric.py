"""Tests for consolidated coerce_accounting_float helper."""

from __future__ import annotations

import pytest

from counter_risk.parsers._xlsx_reader import coerce_accounting_float


def test_coerce_accounting_float_basics() -> None:
    assert coerce_accounting_float(None) == 0.0
    assert coerce_accounting_float(123) == 123.0
    assert coerce_accounting_float(123.45) == 123.45
    assert coerce_accounting_float("") == 0.0
    assert coerce_accounting_float("-") == 0.0
    assert coerce_accounting_float("--") == 0.0
    assert coerce_accounting_float("N/A") == 0.0
    assert coerce_accounting_float("n/a") == 0.0


def test_coerce_accounting_float_percentages() -> None:
    # Under the default strip_percent=True contract:
    # "% is stripped but not rescaled by /100"
    assert coerce_accounting_float("5.5%") == 5.5
    assert coerce_accounting_float("5.5%", strip_percent=True) == 5.5
    # If strip_percent=False, it should raise ValueError
    with pytest.raises(ValueError, match="Unable to parse numeric cell value"):
        coerce_accounting_float("5.5%", strip_percent=False)


def test_coerce_accounting_float_parentheses_negatives() -> None:
    assert coerce_accounting_float("(123.45)") == -123.45
    assert coerce_accounting_float("($1,234.56)") == -1234.56


def test_coerce_accounting_float_currency_and_separators() -> None:
    assert coerce_accounting_float("$1,234.56") == 1234.56
    assert coerce_accounting_float("-$1,234.56") == -1234.56


def test_coerce_accounting_float_non_finite_rejection() -> None:
    with pytest.raises(ValueError, match="Non-finite numeric value"):
        coerce_accounting_float(float("nan"))
    with pytest.raises(ValueError, match="Non-finite"):
        coerce_accounting_float(float("inf"))
    with pytest.raises(ValueError, match="Non-finite"):
        coerce_accounting_float(float("-inf"))
    with pytest.raises(ValueError, match="Non-finite"):
        coerce_accounting_float("nan")
    with pytest.raises(ValueError, match="Non-finite"):
        coerce_accounting_float("inf")


def test_coerce_accounting_float_us_locale_assumption() -> None:
    # European decimals "1.234,56" should either raise ValueError or parse incorrectly
    # (since the commas are stripped and dot is treated as decimal, it might yield 1234.56)
    # We document that US locale is assumed: commas are stripped, dots are decimals.
    # In "1.234,56", commas are stripped -> "1.23456" -> 1.23456 (incorrect, not 1234.56)
    assert coerce_accounting_float("1.234,56") == pytest.approx(1.23456)
