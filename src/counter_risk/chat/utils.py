"""Numeric helpers for tolerance-aware chat computations."""

from __future__ import annotations

import math

DEFAULT_REL_TOL = 1e-9
DEFAULT_ABS_TOL = 1e-6


def is_close(
    left: float,
    right: float,
    *,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
) -> bool:
    """Return True when two numbers are equal within configured tolerance."""

    return math.isclose(left, right, rel_tol=rel_tol, abs_tol=abs_tol)


def cmp_with_tol(
    left: float,
    right: float,
    *,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
) -> int:
    """Three-way comparison with tolerance."""

    if is_close(left, right, rel_tol=rel_tol, abs_tol=abs_tol):
        return 0
    return -1 if left < right else 1
