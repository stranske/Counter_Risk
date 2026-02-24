"""Tests for futures delta computation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, cast

import pytest

from counter_risk.compute.futures_delta import (
    compute_futures_delta,
    normalize_description,
    write_annotated_csv,
)


def _records(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "to_dict"):
        return cast(list[dict[str, Any]], result.to_dict(orient="records"))
    return [dict(row) for row in result]


def _make_rows(*pairs: tuple[str, float]) -> list[dict[str, Any]]:
    return [{"description": desc, "notional": notional} for desc, notional in pairs]


# ---------------------------------------------------------------------------
# normalize_description
# ---------------------------------------------------------------------------


def test_normalize_collapses_whitespace() -> None:
    assert normalize_description("  US  Treasury   Bond  ") == "US TREASURY BOND"


def test_normalize_abbreviated_two_digit_year() -> None:
    assert normalize_description("TY Mar25") == "TY MAR25"


def test_normalize_abbreviated_with_space() -> None:
    assert normalize_description("TY Mar 25") == "TY MAR25"


def test_normalize_full_month_four_digit_year() -> None:
    assert normalize_description("ES March 2025") == "ES MAR25"


def test_normalize_month_with_apostrophe() -> None:
    assert normalize_description("TY Mar '25") == "TY MAR25"


def test_normalize_result_is_uppercase() -> None:
    result = normalize_description("e-mini s&p dec 25")
    assert result == result.upper()


def test_normalize_all_months_recognised() -> None:
    months = [
        ("January", "JAN"),
        ("February", "FEB"),
        ("March", "MAR"),
        ("April", "APR"),
        ("May", "MAY"),
        ("June", "JUN"),
        ("July", "JUL"),
        ("August", "AUG"),
        ("September", "SEP"),
        ("October", "OCT"),
        ("November", "NOV"),
        ("December", "DEC"),
    ]
    for full, abbrev in months:
        result = normalize_description(f"Contract {full} 2025")
        assert abbrev + "25" in result, f"Expected {abbrev}25 in result for {full}"


def test_normalize_no_month_unchanged_aside_from_case_and_whitespace() -> None:
    result = normalize_description("  US  TREASURY  ")
    assert result == "US TREASURY"


# ---------------------------------------------------------------------------
# compute_futures_delta – basic change computation
# ---------------------------------------------------------------------------


def test_basic_change_positive() -> None:
    current = _make_rows(("US 2-Year Note Mar25", 100.0))
    prior = _make_rows(("US 2-Year Note Mar25", 80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert len(rows) == 1
    assert rows[0]["notional"] == pytest.approx(100.0)
    assert rows[0]["prior_notional"] == pytest.approx(80.0)
    assert rows[0]["notional_change"] == pytest.approx(20.0)
    assert rows[0]["sign_flip"] == ""
    assert warnings == []


def test_basic_change_negative() -> None:
    current = _make_rows(("TY Dec25", 50.0))
    prior = _make_rows(("TY Dec25", 75.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["notional_change"] == pytest.approx(-25.0)
    assert warnings == []


# ---------------------------------------------------------------------------
# compute_futures_delta – sign flip
# ---------------------------------------------------------------------------


def test_sign_flip_positive_to_negative() -> None:
    current = _make_rows(("ES Jun25", -50.0))
    prior = _make_rows(("ES Jun25", 50.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == "*"
    assert warnings == []


def test_sign_flip_negative_to_positive() -> None:
    current = _make_rows(("ES Jun25", 50.0))
    prior = _make_rows(("ES Jun25", -50.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == "*"
    assert warnings == []


def test_no_sign_flip_same_positive_sign() -> None:
    current = _make_rows(("ES Jun25", 50.0))
    prior = _make_rows(("ES Jun25", 80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == ""


def test_no_sign_flip_same_negative_sign() -> None:
    current = _make_rows(("ES Jun25", -50.0))
    prior = _make_rows(("ES Jun25", -80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == ""


def test_no_sign_flip_when_prior_zero() -> None:
    """No sign-flip annotation when prior is zero (new position)."""
    current = _make_rows(("ES Jun25", 50.0))
    prior: list[dict[str, Any]] = []
    result, _ = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == ""


def test_no_sign_flip_when_current_zero() -> None:
    """No sign-flip annotation when current is zero (closed position)."""
    current = _make_rows(("ES Jun25", 0.0))
    prior = _make_rows(("ES Jun25", 50.0))
    result, _ = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["sign_flip"] == ""


# ---------------------------------------------------------------------------
# compute_futures_delta – unmatched row warnings
# ---------------------------------------------------------------------------


def test_unmatched_current_row_gets_zero_prior_and_warning() -> None:
    current = _make_rows(("New Contract Dec25", 200.0))
    prior = _make_rows(("Old Contract Dec25", 100.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    # Current row has no prior match.
    assert rows[0]["prior_notional"] == pytest.approx(0.0)
    assert any("Unmatched current" in w for w in warnings)
    # Prior row also unmatched.
    assert any("Unmatched prior" in w for w in warnings)


def test_unmatched_prior_only_produces_warning() -> None:
    current = _make_rows(("Contract A Mar25", 100.0))
    prior = _make_rows(
        ("Contract A Mar25", 80.0),
        ("Contract B Mar25", 50.0),
    )
    _, warnings = compute_futures_delta(current, prior)
    assert any("Unmatched prior" in w and "Contract B" in w for w in warnings)


def test_unmatched_prior_not_in_result_rows() -> None:
    """Prior-only rows should not appear in the output table."""
    current = _make_rows(("Contract A Mar25", 100.0))
    prior = _make_rows(
        ("Contract A Mar25", 80.0),
        ("Contract B Mar25", 50.0),
    )
    result, _ = compute_futures_delta(current, prior)
    rows = _records(result)
    descriptions = [r["description"] for r in rows]
    assert all("Contract B" not in d for d in descriptions)


# ---------------------------------------------------------------------------
# compute_futures_delta – description matching via normalisation
# ---------------------------------------------------------------------------


def test_month_with_space_matches_without_space() -> None:
    """'Mar 25' and 'Mar25' normalise to the same key."""
    current = _make_rows(("TY Mar 25", 100.0))
    prior = _make_rows(("TY Mar25", 80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["prior_notional"] == pytest.approx(80.0)
    assert warnings == []


def test_full_month_name_matches_abbreviated() -> None:
    """'March 2025' and 'Mar25' normalise to the same key."""
    current = _make_rows(("TY March 2025", 100.0))
    prior = _make_rows(("TY Mar25", 80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["prior_notional"] == pytest.approx(80.0)
    assert warnings == []


def test_case_insensitive_matching() -> None:
    current = _make_rows(("ES MAR25", 100.0))
    prior = _make_rows(("ES mar25", 80.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows[0]["prior_notional"] == pytest.approx(80.0)
    assert warnings == []


# ---------------------------------------------------------------------------
# compute_futures_delta – sort order
# ---------------------------------------------------------------------------


def test_output_sorted_by_normalised_description() -> None:
    current = _make_rows(
        ("TY Mar25", 10.0),
        ("ES Mar25", 20.0),
        ("CL Mar25", 30.0),
    )
    prior = _make_rows(
        ("TY Mar25", 5.0),
        ("ES Mar25", 15.0),
        ("CL Mar25", 25.0),
    )
    result, _ = compute_futures_delta(current, prior)
    rows = _records(result)
    norm_descs = [normalize_description(r["description"]) for r in rows]
    assert norm_descs == sorted(norm_descs)


# ---------------------------------------------------------------------------
# compute_futures_delta – edge cases
# ---------------------------------------------------------------------------


def test_empty_current() -> None:
    current: list[dict[str, Any]] = []
    prior = _make_rows(("TY Mar25", 100.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert rows == []
    assert any("Unmatched prior" in w for w in warnings)


def test_empty_prior() -> None:
    current = _make_rows(("TY Mar25", 100.0))
    prior: list[dict[str, Any]] = []
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert len(rows) == 1
    assert rows[0]["prior_notional"] == pytest.approx(0.0)
    assert rows[0]["notional_change"] == pytest.approx(100.0)
    assert any("Unmatched current" in w for w in warnings)


def test_both_empty() -> None:
    result, warnings = compute_futures_delta([], [])
    assert _records(result) == []
    assert warnings == []


def test_multiple_current_rows() -> None:
    current = _make_rows(("A Mar25", 10.0), ("B Mar25", 20.0), ("C Mar25", 30.0))
    prior = _make_rows(("A Mar25", 5.0), ("B Mar25", 15.0), ("C Mar25", 25.0))
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    assert len(rows) == 3
    assert all(r["notional_change"] == pytest.approx(5.0) for r in rows)
    assert warnings == []


# ---------------------------------------------------------------------------
# write_annotated_csv
# ---------------------------------------------------------------------------


def test_write_annotated_csv_creates_file(tmp_path: Path) -> None:
    current = _make_rows(("ES Dec25", 100.0), ("TY Dec25", -50.0))
    prior = _make_rows(("ES Dec25", 120.0), ("TY Dec25", 50.0))
    result, _ = compute_futures_delta(current, prior)
    out_path = tmp_path / "output" / "futures_delta.csv"
    write_annotated_csv(result, out_path)
    assert out_path.exists()


def test_write_annotated_csv_correct_columns(tmp_path: Path) -> None:
    current = _make_rows(("ES Dec25", 100.0))
    prior = _make_rows(("ES Dec25", 80.0))
    result, _ = compute_futures_delta(current, prior)
    out_path = tmp_path / "futures_delta.csv"
    write_annotated_csv(result, out_path)
    with out_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert set(rows[0].keys()) == {
        "description",
        "notional",
        "prior_notional",
        "notional_change",
        "sign_flip",
    }


def test_write_annotated_csv_sign_flip_value(tmp_path: Path) -> None:
    """TY Dec25 flips sign → sign_flip column should be '*'."""
    current = _make_rows(("ES Dec25", 100.0), ("TY Dec25", -50.0))
    prior = _make_rows(("ES Dec25", 120.0), ("TY Dec25", 50.0))
    result, _ = compute_futures_delta(current, prior)
    out_path = tmp_path / "futures_delta.csv"
    write_annotated_csv(result, out_path)
    with out_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    ty_row = next(r for r in rows if "TY" in r["description"])
    assert ty_row["sign_flip"] == "*"


def test_write_annotated_csv_creates_parent_dirs(tmp_path: Path) -> None:
    current = _make_rows(("ES Dec25", 100.0))
    prior = _make_rows(("ES Dec25", 80.0))
    result, _ = compute_futures_delta(current, prior)
    deep_path = tmp_path / "a" / "b" / "c" / "delta.csv"
    write_annotated_csv(result, deep_path)
    assert deep_path.exists()


def test_write_annotated_csv_row_count(tmp_path: Path) -> None:
    current = _make_rows(("A Mar25", 10.0), ("B Mar25", 20.0))
    prior = _make_rows(("A Mar25", 5.0), ("B Mar25", 15.0))
    result, _ = compute_futures_delta(current, prior)
    out_path = tmp_path / "delta.csv"
    write_annotated_csv(result, out_path)
    with out_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Acceptance criteria: sample reference pair
# ---------------------------------------------------------------------------


def test_reference_subset_change_and_sign_flip() -> None:
    """Verify change and sign-flip for a representative synthetic sample."""
    current = _make_rows(
        ("US 2-Year Note (CBT) Mar25", 1_500_000.0),
        ("US 5-Year Note (CBT) Mar25", -250_000.0),
        ("S&P 500 E-Mini (CME) Mar25", 800_000.0),
        ("Euro Dollar (CME) Jun25", 100_000.0),
    )
    prior = _make_rows(
        ("US 2-Year Note (CBT) Mar25", 1_200_000.0),
        ("US 5-Year Note (CBT) Mar25", 200_000.0),
        ("S&P 500 E-Mini (CME) Mar25", 800_000.0),
        # Euro Dollar absent in prior – new position
    )
    result, warnings = compute_futures_delta(current, prior)
    rows = _records(result)
    by_desc = {r["description"]: r for r in rows}

    # 2-Year Note: increased, same sign → no flip
    two_yr = by_desc["US 2-Year Note (CBT) Mar25"]
    assert two_yr["notional_change"] == pytest.approx(300_000.0)
    assert two_yr["sign_flip"] == ""

    # 5-Year Note: sign changed from +200k to -250k → flip
    five_yr = by_desc["US 5-Year Note (CBT) Mar25"]
    assert five_yr["notional_change"] == pytest.approx(-450_000.0)
    assert five_yr["sign_flip"] == "*"

    # S&P: no change → no flip
    sp = by_desc["S&P 500 E-Mini (CME) Mar25"]
    assert sp["notional_change"] == pytest.approx(0.0)
    assert sp["sign_flip"] == ""

    # Euro Dollar: new position → prior 0, no flip annotation
    euro = by_desc["Euro Dollar (CME) Jun25"]
    assert euro["prior_notional"] == pytest.approx(0.0)
    assert euro["sign_flip"] == ""

    # Unmatched prior row surfaced in warnings (none in this case as all prior matched)
    assert not any("Unmatched prior" in w for w in warnings)
    # Unmatched current: Euro Dollar had no prior
    assert any("Euro Dollar" in w for w in warnings)
