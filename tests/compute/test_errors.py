"""Tests for compute error-code constants."""

from counter_risk.compute.errors import NO_PRIOR_MONTH_MATCH


def test_no_prior_month_match_constant_value() -> None:
    assert NO_PRIOR_MONTH_MATCH == "NO_PRIOR_MONTH_MATCH"
