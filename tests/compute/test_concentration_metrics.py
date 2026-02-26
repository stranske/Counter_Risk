"""Tests for compute_concentration_metrics and write_concentration_metrics_csv."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from counter_risk.compute.rollups import (
    compute_concentration_metrics,
    write_concentration_metrics_csv,
)

_TOL = 1e-9


def _as_records(table: Any) -> list[dict[str, Any]]:
    if hasattr(table, "to_dict"):
        return table.to_dict(orient="records")
    return [dict(row) for row in table]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SIMPLE_EXPOSURES = [
    {"variant": "all_programs", "segment": "total", "counterparty": "A", "notional": 50.0},
    {"variant": "all_programs", "segment": "total", "counterparty": "B", "notional": 30.0},
    {"variant": "all_programs", "segment": "total", "counterparty": "C", "notional": 20.0},
]

# 10 counterparties for top-N edge testing
_TEN_COUNTERPARTY_EXPOSURES = [
    {"variant": "v1", "segment": "s1", "counterparty": str(i), "notional": float(i + 1)}
    for i in range(10)
]

# Single-entity group (should give top5=top10=hhi=1.0)
_SINGLE_ENTITY_EXPOSURES = [
    {"variant": "only", "segment": "total", "counterparty": "Solo", "notional": 100.0},
]

# Two groups
_TWO_GROUP_EXPOSURES = [
    {"variant": "v1", "segment": "s1", "counterparty": "A", "notional": 80.0},
    {"variant": "v1", "segment": "s1", "counterparty": "B", "notional": 20.0},
    {"variant": "v1", "segment": "s2", "counterparty": "X", "notional": 60.0},
    {"variant": "v1", "segment": "s2", "counterparty": "Y", "notional": 40.0},
]


# ---------------------------------------------------------------------------
# Top 5 share tests
# ---------------------------------------------------------------------------


def test_top5_share_with_three_entities() -> None:
    """All 3 entities fit within top-5 window so share should be 1.0."""
    result = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    assert len(result) == 1
    row = result[0]
    assert row["top5_share"] == pytest.approx(1.0, abs=_TOL)


def test_top5_share_exact_calculation() -> None:
    """Top-5 share with exactly 5 of 10 entities."""
    # notionals: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 → total=55
    # top 5: 10+9+8+7+6 = 40 → share = 40/55
    rows = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    assert len(rows) == 1
    expected = (10 + 9 + 8 + 7 + 6) / 55.0
    assert rows[0]["top5_share"] == pytest.approx(expected, abs=_TOL)


def test_top5_share_fewer_than_five_entities() -> None:
    """When fewer than 5 entities exist top5_share should equal 1.0."""
    data = [
        {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
        for i in range(3)
    ]
    rows = _as_records(compute_concentration_metrics(data))
    assert rows[0]["top5_share"] == pytest.approx(1.0, abs=_TOL)


def test_top5_share_from_known_distribution() -> None:
    """Top-5 share matches manually computed value for a known fixture."""
    # Notionals: 100, 80, 60, 40, 20, 10 → total=310, top5=100+80+60+40+20=300
    data = [
        {"variant": "v", "segment": "s", "counterparty": "P1", "notional": 100.0},
        {"variant": "v", "segment": "s", "counterparty": "P2", "notional": 80.0},
        {"variant": "v", "segment": "s", "counterparty": "P3", "notional": 60.0},
        {"variant": "v", "segment": "s", "counterparty": "P4", "notional": 40.0},
        {"variant": "v", "segment": "s", "counterparty": "P5", "notional": 20.0},
        {"variant": "v", "segment": "s", "counterparty": "P6", "notional": 10.0},
    ]
    rows = _as_records(compute_concentration_metrics(data))
    assert rows[0]["top5_share"] == pytest.approx(300.0 / 310.0, abs=_TOL)


# ---------------------------------------------------------------------------
# Top 10 share tests
# ---------------------------------------------------------------------------


def test_top10_share_with_fewer_than_ten_entities() -> None:
    """When fewer than 10 entities exist top10_share equals 1.0."""
    rows = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    assert rows[0]["top10_share"] == pytest.approx(1.0, abs=_TOL)


def test_top10_share_exact_ten_entities() -> None:
    """With exactly 10 entities top10_share equals 1.0."""
    rows = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    assert rows[0]["top10_share"] == pytest.approx(1.0, abs=_TOL)


def test_top10_share_more_than_ten_entities() -> None:
    """Top-10 share computed correctly when group has >10 entities."""
    # 12 entities with notionals 1..12, total=78
    # top10: 12+11+10+9+8+7+6+5+4+3=75
    data = [
        {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
        for i in range(12)
    ]
    rows = _as_records(compute_concentration_metrics(data))
    expected = (12 + 11 + 10 + 9 + 8 + 7 + 6 + 5 + 4 + 3) / 78.0
    assert rows[0]["top10_share"] == pytest.approx(expected, abs=_TOL)


# ---------------------------------------------------------------------------
# HHI tests
# ---------------------------------------------------------------------------


def test_hhi_perfectly_concentrated() -> None:
    """Single entity: HHI must equal 1.0."""
    rows = _as_records(compute_concentration_metrics(_SINGLE_ENTITY_EXPOSURES))
    assert rows[0]["hhi"] == pytest.approx(1.0, abs=_TOL)


def test_hhi_equally_distributed() -> None:
    """N equal-weight entities: HHI = 1/N."""
    n = 5
    data = [
        {"variant": "v", "segment": "s", "counterparty": str(i), "notional": 1.0} for i in range(n)
    ]
    rows = _as_records(compute_concentration_metrics(data))
    assert rows[0]["hhi"] == pytest.approx(1.0 / n, abs=_TOL)


def test_hhi_known_distribution() -> None:
    """HHI computed correctly for manually verifiable fixture."""
    # shares: 50%, 30%, 20% → HHI = 0.25 + 0.09 + 0.04 = 0.38
    rows = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    expected = 0.5**2 + 0.3**2 + 0.2**2
    assert rows[0]["hhi"] == pytest.approx(expected, abs=_TOL)


def test_hhi_bounds() -> None:
    """HHI must always be in [1/N, 1.0]."""
    rows = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    hhi = rows[0]["hhi"]
    n = 10
    assert hhi >= 1.0 / n - _TOL
    assert hhi <= 1.0 + _TOL


# ---------------------------------------------------------------------------
# Grouping tests
# ---------------------------------------------------------------------------


def test_groups_are_partitioned_correctly() -> None:
    """Each (variant, segment) pair produces exactly one output row."""
    rows = _as_records(compute_concentration_metrics(_TWO_GROUP_EXPOSURES))
    keys = {(r["variant"], r["segment"]) for r in rows}
    assert keys == {("v1", "s1"), ("v1", "s2")}


def test_group_metrics_are_independent() -> None:
    """Metrics for one group do not bleed into another."""
    rows = _as_records(compute_concentration_metrics(_TWO_GROUP_EXPOSURES))
    by_key = {(r["variant"], r["segment"]): r for r in rows}

    # s1: A=80, B=20 → total=100, top5=1.0, hhi=0.68
    s1 = by_key[("v1", "s1")]
    assert s1["top5_share"] == pytest.approx(1.0, abs=_TOL)
    assert s1["hhi"] == pytest.approx(0.8**2 + 0.2**2, abs=_TOL)

    # s2: X=60, Y=40 → total=100, top5=1.0, hhi=0.52
    s2 = by_key[("v1", "s2")]
    assert s2["top5_share"] == pytest.approx(1.0, abs=_TOL)
    assert s2["hhi"] == pytest.approx(0.6**2 + 0.4**2, abs=_TOL)


def test_custom_group_by_columns() -> None:
    """group_by parameter is respected for non-default column names."""
    data = [
        {"category": "X", "region": "east", "counterparty": "A", "notional": 70.0},
        {"category": "X", "region": "east", "counterparty": "B", "notional": 30.0},
        {"category": "X", "region": "west", "counterparty": "C", "notional": 100.0},
    ]
    rows = _as_records(compute_concentration_metrics(data, group_by=["category", "region"]))
    assert len(rows) == 2
    keys = {(r["category"], r["region"]) for r in rows}
    assert keys == {("X", "east"), ("X", "west")}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_input() -> None:
    """Empty input returns an empty result with correct structure."""
    result = _as_records(compute_concentration_metrics([]))
    assert result == []


def test_zero_total_notional() -> None:
    """Groups where all notionals are zero produce 0.0 for all metrics."""
    data = [
        {"variant": "v", "segment": "s", "counterparty": "A", "notional": 0.0},
        {"variant": "v", "segment": "s", "counterparty": "B", "notional": 0.0},
    ]
    rows = _as_records(compute_concentration_metrics(data))
    assert rows[0]["top5_share"] == pytest.approx(0.0, abs=_TOL)
    assert rows[0]["top10_share"] == pytest.approx(0.0, abs=_TOL)
    assert rows[0]["hhi"] == pytest.approx(0.0, abs=_TOL)


def test_missing_group_by_column_raises() -> None:
    """ValueError raised when a required group_by column is absent."""
    data = [{"variant": "v", "counterparty": "A", "notional": 1.0}]
    with pytest.raises(ValueError, match="segment"):
        compute_concentration_metrics(data)


def test_missing_notional_column_raises() -> None:
    """ValueError raised when the notional column cannot be found."""
    data = [{"variant": "v", "segment": "s", "counterparty": "A"}]
    with pytest.raises((ValueError, KeyError)):
        compute_concentration_metrics(data)


def test_single_entity_group() -> None:
    """Single entity → top5=top10=hhi=1.0 regardless of notional value."""
    rows = _as_records(compute_concentration_metrics(_SINGLE_ENTITY_EXPOSURES))
    assert rows[0]["top5_share"] == pytest.approx(1.0, abs=_TOL)
    assert rows[0]["top10_share"] == pytest.approx(1.0, abs=_TOL)
    assert rows[0]["hhi"] == pytest.approx(1.0, abs=_TOL)


def test_fewer_than_five_entities_top5_equals_1() -> None:
    """Groups with 1–4 entities: top5_share must be 1.0."""
    for count in range(1, 5):
        data = [
            {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
            for i in range(count)
        ]
        rows = _as_records(compute_concentration_metrics(data))
        assert rows[0]["top5_share"] == pytest.approx(1.0, abs=_TOL), f"count={count}"


def test_fewer_than_ten_entities_top10_equals_1() -> None:
    """Groups with 1–9 entities: top10_share must be 1.0."""
    for count in range(1, 10):
        data = [
            {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
            for i in range(count)
        ]
        rows = _as_records(compute_concentration_metrics(data))
        assert rows[0]["top10_share"] == pytest.approx(1.0, abs=_TOL), f"count={count}"


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


def test_determinism_top5_share() -> None:
    """Identical inputs produce identical top5_share across multiple calls."""
    first = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    second = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    assert first[0]["top5_share"] == second[0]["top5_share"]


def test_determinism_top10_share() -> None:
    """Identical inputs produce identical top10_share across multiple calls."""
    first = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    second = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    assert first[0]["top10_share"] == second[0]["top10_share"]


def test_determinism_hhi() -> None:
    """Identical inputs produce identical HHI across multiple calls."""
    first = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    second = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    assert first[0]["hhi"] == second[0]["hhi"]


def test_determinism_repeated_runs_multi_group() -> None:
    """All metrics are identical across repeated calls for multi-group input."""
    first = _as_records(compute_concentration_metrics(_TWO_GROUP_EXPOSURES))
    second = _as_records(compute_concentration_metrics(_TWO_GROUP_EXPOSURES))
    assert first == second


def test_determinism_reversed_input_order() -> None:
    """Metrics are the same regardless of input row order within a group."""
    forward = _as_records(compute_concentration_metrics(_SIMPLE_EXPOSURES))
    backward = _as_records(compute_concentration_metrics(list(reversed(_SIMPLE_EXPOSURES))))
    # Same group, same results
    assert forward[0]["top5_share"] == pytest.approx(backward[0]["top5_share"], abs=_TOL)
    assert forward[0]["top10_share"] == pytest.approx(backward[0]["top10_share"], abs=_TOL)
    assert forward[0]["hhi"] == pytest.approx(backward[0]["hhi"], abs=_TOL)


# ---------------------------------------------------------------------------
# Total-exposure denominator consistency tests
# ---------------------------------------------------------------------------


def test_top5_share_denominator_is_total_exposure_not_partial_sum() -> None:
    """Top-5 share divides by total group exposure, not just the top-5 partial sum."""
    # notionals: 1, 2, ..., 10 → total=55, top-5 sum=40
    # If denominator were top-5 only (40), top5_share would equal 1.0
    # If denominator is total (55), top5_share = 40/55 < 1.0
    rows = _as_records(compute_concentration_metrics(_TEN_COUNTERPARTY_EXPOSURES))
    top5_share = rows[0]["top5_share"]
    expected_using_total = (10 + 9 + 8 + 7 + 6) / 55.0
    # Verify it equals the total-denominator result (not 1.0)
    assert top5_share == pytest.approx(expected_using_total, abs=_TOL)
    assert top5_share < 1.0 - _TOL


def test_top10_share_denominator_is_total_exposure_not_partial_sum() -> None:
    """Top-10 share divides by total group exposure, not just the top-10 partial sum."""
    # 12 entities with notionals 1..12, total=78, top-10 sum=75
    # If denominator were top-10 only (75), top10_share would equal 1.0
    # If denominator is total (78), top10_share = 75/78 < 1.0
    data = [
        {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
        for i in range(12)
    ]
    rows = _as_records(compute_concentration_metrics(data))
    top10_share = rows[0]["top10_share"]
    expected_using_total = (12 + 11 + 10 + 9 + 8 + 7 + 6 + 5 + 4 + 3) / 78.0
    # Verify it equals the total-denominator result (not 1.0)
    assert top10_share == pytest.approx(expected_using_total, abs=_TOL)
    assert top10_share < 1.0 - _TOL


def test_top5_and_top10_share_same_denominator() -> None:
    """Top-5 and Top-10 shares use the same denominator (total group exposure)."""
    # 12 entities, notionals 1..12, total=78
    # top-5 sum = 12+11+10+9+8 = 50, top-10 sum = 12+..+3 = 75
    # Both divided by 78
    data = [
        {"variant": "v", "segment": "s", "counterparty": str(i), "notional": float(i + 1)}
        for i in range(12)
    ]
    rows = _as_records(compute_concentration_metrics(data))
    top5_share = rows[0]["top5_share"]
    top10_share = rows[0]["top10_share"]
    total = sum(range(1, 13))  # 78
    top5_sum = sum(range(8, 13))  # 8+9+10+11+12 = 50
    top10_sum = sum(range(3, 13))  # 3+4+...+12 = 75
    assert top5_share == pytest.approx(top5_sum / total, abs=_TOL)
    assert top10_share == pytest.approx(top10_sum / total, abs=_TOL)


# ---------------------------------------------------------------------------
# write_concentration_metrics_csv tests
# ---------------------------------------------------------------------------


def test_write_concentration_metrics_csv_creates_file(tmp_path: Path) -> None:
    """CSV file is created at the specified path."""
    out = tmp_path / "metrics.csv"
    result = compute_concentration_metrics(_SIMPLE_EXPOSURES)
    write_concentration_metrics_csv(result, out)
    assert out.exists()


def test_write_concentration_metrics_csv_has_expected_columns(tmp_path: Path) -> None:
    """CSV file contains the expected column headers."""
    out = tmp_path / "metrics.csv"
    result = compute_concentration_metrics(_SIMPLE_EXPOSURES)
    write_concentration_metrics_csv(result, out)
    with out.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
    assert "variant" in headers
    assert "segment" in headers
    assert "top5_share" in headers
    assert "top10_share" in headers
    assert "hhi" in headers


def test_write_concentration_metrics_csv_values_match(tmp_path: Path) -> None:
    """Values written to CSV match the computed metrics."""
    out = tmp_path / "metrics.csv"
    result = compute_concentration_metrics(_SIMPLE_EXPOSURES)
    expected_records = _as_records(result)
    write_concentration_metrics_csv(result, out)

    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == len(expected_records)
    assert float(rows[0]["top5_share"]) == pytest.approx(
        expected_records[0]["top5_share"], abs=_TOL
    )
    assert float(rows[0]["hhi"]) == pytest.approx(expected_records[0]["hhi"], abs=_TOL)


def test_write_concentration_metrics_csv_empty_input(tmp_path: Path) -> None:
    """Writing empty metrics produces an empty file without error."""
    out = tmp_path / "empty.csv"
    result = compute_concentration_metrics([])
    write_concentration_metrics_csv(result, out)
    assert out.exists()
    assert out.stat().st_size == 0


def test_write_concentration_metrics_csv_creates_parent_dirs(tmp_path: Path) -> None:
    """Parent directories are created automatically if absent."""
    out = tmp_path / "subdir" / "nested" / "metrics.csv"
    result = compute_concentration_metrics(_SIMPLE_EXPOSURES)
    write_concentration_metrics_csv(result, out)
    assert out.exists()


def test_write_concentration_metrics_csv_multi_group(tmp_path: Path) -> None:
    """Multi-group output writes one CSV row per (variant, segment) group."""
    out = tmp_path / "multi.csv"
    result = compute_concentration_metrics(_TWO_GROUP_EXPOSURES)
    write_concentration_metrics_csv(result, out)
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    keys = {(r["variant"], r["segment"]) for r in rows}
    assert keys == {("v1", "s1"), ("v1", "s2")}
