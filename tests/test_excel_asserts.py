from tests.helpers.excel_asserts import (
    RangeBounds,
    extract_range_values,
    float_tolerant_equal,
    parse_a1_range,
)


def test_parse_a1_range_rectangular_bounds() -> None:
    assert parse_a1_range("B2:D4") == RangeBounds(min_row=2, min_col=2, max_row=4, max_col=4)


def test_parse_a1_range_normalizes_reverse_coordinates() -> None:
    assert parse_a1_range("D4:B2") == RangeBounds(min_row=2, min_col=2, max_row=4, max_col=4)


def test_extract_range_values_returns_expected_rectangle() -> None:
    grid = [
        ["A1", "B1", "C1", "D1"],
        ["A2", "B2", "C2", "D2"],
        ["A3", "B3", "C3", "D3"],
    ]
    assert extract_range_values(grid, "B1:C3") == (
        ("B1", "C1"),
        ("B2", "C2"),
        ("B3", "C3"),
    )


def test_float_tolerant_equal_for_nested_sequence() -> None:
    left = ((1.0, 2.0000000001), (3.0, 4.0))
    right = ((1.0, 2.0), (3.0, 4.0))
    assert float_tolerant_equal(left, right, abs_tol=1e-9, rel_tol=1e-9)


def test_float_tolerant_equal_is_deterministic() -> None:
    left = ((100.0, 200.0),)
    right = ((100.0, 200.0000001),)
    first = float_tolerant_equal(left, right, abs_tol=1e-6, rel_tol=1e-6)
    second = float_tolerant_equal(left, right, abs_tol=1e-6, rel_tol=1e-6)
    assert first is second


def test_float_tolerant_equal_detects_real_difference() -> None:
    assert not float_tolerant_equal((1.0, 2.0), (1.0, 2.1), abs_tol=1e-9, rel_tol=1e-9)
