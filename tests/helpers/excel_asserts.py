"""Utilities for deterministic Excel-like assertions in tests."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

_A1_REF_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


@dataclass(frozen=True)
class RangeBounds:
    min_row: int
    min_col: int
    max_row: int
    max_col: int


def _column_to_index(column_label: str) -> int:
    index = 0
    for character in column_label:
        index = (index * 26) + (ord(character) - ord("A") + 1)
    return index


def _parse_a1_reference(reference: str) -> tuple[int, int]:
    match = _A1_REF_PATTERN.match(reference.upper())
    if match is None:
        raise ValueError(f"Invalid A1 reference: {reference}")
    column_label, row_label = match.groups()
    return int(row_label), _column_to_index(column_label)


def parse_a1_range(range_ref: str) -> RangeBounds:
    """Parse an A1 range string into 1-based row/column bounds."""
    pieces = range_ref.replace("$", "").upper().split(":")
    if len(pieces) == 1:
        start = _parse_a1_reference(pieces[0])
        end = start
    elif len(pieces) == 2:
        start = _parse_a1_reference(pieces[0])
        end = _parse_a1_reference(pieces[1])
    else:
        raise ValueError(f"Invalid A1 range: {range_ref}")

    min_row = min(start[0], end[0])
    max_row = max(start[0], end[0])
    min_col = min(start[1], end[1])
    max_col = max(start[1], end[1])
    return RangeBounds(min_row=min_row, min_col=min_col, max_row=max_row, max_col=max_col)


def extract_range_values(
    grid: Sequence[Sequence[Any]], range_ref: str
) -> tuple[tuple[Any, ...], ...]:
    """Extract a rectangular A1 range from a 2D list-like grid."""
    bounds = parse_a1_range(range_ref)
    values: list[tuple[Any, ...]] = []

    for row_number in range(bounds.min_row, bounds.max_row + 1):
        row = grid[row_number - 1]
        row_values = tuple(row[bounds.min_col - 1 : bounds.max_col])
        values.append(row_values)

    return tuple(values)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def float_tolerant_equal(
    left: Any, right: Any, *, abs_tol: float = 1e-9, rel_tol: float = 1e-9
) -> bool:
    """Compare scalars or nested sequences with float tolerance."""
    if _is_sequence(left) and _is_sequence(right):
        if len(left) != len(right):
            return False
        return all(
            float_tolerant_equal(left_item, right_item, abs_tol=abs_tol, rel_tol=rel_tol)
            for left_item, right_item in zip(left, right, strict=True)
        )

    if isinstance(left, float) or isinstance(right, float):
        try:
            return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)
        except (TypeError, ValueError):
            return False

    return bool(left == right)
