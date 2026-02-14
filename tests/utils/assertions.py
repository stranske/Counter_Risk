"""Numeric assertion helpers for fixture-driven tests."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def assert_numeric_outputs_close(
    actual: Any,
    expected: Any,
    *,
    abs_tol: float = 1e-9,
    rel_tol: float = 1e-9,
    atol: float | None = None,
    rtol: float | None = None,
    path: str = "value",
) -> None:
    """Assert nested outputs match using tolerance-aware comparisons for numeric values."""

    # Backward-compatible aliases while standardizing on abs_tol/rel_tol.
    if atol is not None:
        abs_tol = atol
    if rtol is not None:
        rel_tol = rtol

    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise AssertionError(f"{path} expected mapping but got {type(actual).__name__}")

        actual_keys = set(actual)
        expected_keys = set(expected)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            raise AssertionError(f"{path} key mismatch; missing={missing}, extra={extra}")

        for key in sorted(expected):
            assert_numeric_outputs_close(
                actual[key],
                expected[key],
                abs_tol=abs_tol,
                rel_tol=rel_tol,
                path=f"{path}.{key}",
            )
        return

    if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes, bytearray)):
        if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes, bytearray)):
            raise AssertionError(f"{path} expected sequence but got {type(actual).__name__}")
        if len(actual) != len(expected):
            raise AssertionError(f"{path} length mismatch: {len(actual)} != {len(expected)}")

        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            assert_numeric_outputs_close(
                actual_item,
                expected_item,
                abs_tol=abs_tol,
                rel_tol=rel_tol,
                path=f"{path}[{index}]",
            )
        return

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(float(actual), float(expected), abs_tol=abs_tol, rel_tol=rel_tol):
            raise AssertionError(
                f"{path} numeric mismatch: actual={actual}, expected={expected}, "
                f"abs_tol={abs_tol}, rel_tol={rel_tol}"
            )
        return

    if actual != expected:
        raise AssertionError(f"{path} mismatch: actual={actual!r}, expected={expected!r}")
