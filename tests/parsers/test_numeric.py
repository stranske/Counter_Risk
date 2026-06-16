"""Tests for consolidated coerce_accounting_float helper."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from counter_risk.parsers._xlsx_reader import cell_value, coerce_accounting_float


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
    with pytest.raises(ValueError, match="Unsupported mixed-separator numeric format"):
        coerce_accounting_float("1.234,56")


def test_cell_value_concatenates_rich_inline_strings() -> None:
    cell = ET.fromstring(
        """
        <c xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" t="inlineStr">
          <is><r><t>Alpha</t></r><r><t> Beta</t></r></is>
        </c>
        """
    )

    assert cell_value(cell, []) == "Alpha Beta"


def test_cell_value_rejects_negative_shared_string_indexes() -> None:
    cell = ET.fromstring(
        """
        <c xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" t="s">
          <v>-1</v>
        </c>
        """
    )

    assert cell_value(cell, ["should-not-wrap"]) is None
