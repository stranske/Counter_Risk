"""Numeric assertion helpers for fixture-driven tests."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


def assert_numeric_outputs_close(
    actual: Any,
    expected: Any,
    *,
    atol: float,
    rtol: float,
    path: str = "value",
) -> None:
    """Assert numeric outputs match with explicit absolute/relative tolerances."""

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
                atol=atol,
                rtol=rtol,
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
                atol=atol,
                rtol=rtol,
                path=f"{path}[{index}]",
            )
        return

    if isinstance(expected, Real) and isinstance(actual, Real):
        if not math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=rtol):
            raise AssertionError(
                f"{path} numeric mismatch: actual={actual}, expected={expected}, "
                f"atol={atol}, rtol={rtol}"
            )
        return

    if actual != expected:
        raise AssertionError(f"{path} mismatch: actual={actual!r}, expected={expected!r}")
