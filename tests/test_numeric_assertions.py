from __future__ import annotations

import pytest

from tests.utils.assertions import assert_numeric_outputs_close


def test_assert_numeric_outputs_close_accepts_close_numeric_values() -> None:
    assert_numeric_outputs_close(
        {"a": 1.0, "b": [2.0, {"c": 3.0000001}]},
        {"a": 1.0, "b": [2.0, {"c": 3.0}]},
        atol=1e-6,
        rtol=1e-6,
    )


def test_assert_numeric_outputs_close_raises_for_numeric_mismatch() -> None:
    with pytest.raises(AssertionError, match="numeric mismatch"):
        assert_numeric_outputs_close(
            {"notional": 125.0},
            {"notional": 126.0},
            atol=1e-9,
            rtol=1e-9,
        )


def test_assert_numeric_outputs_close_raises_for_key_mismatch() -> None:
    with pytest.raises(AssertionError, match="key mismatch"):
        assert_numeric_outputs_close(
            {"notional": 125.0},
            {"notional": 125.0, "cash": 50.0},
            atol=1e-9,
            rtol=1e-9,
        )
