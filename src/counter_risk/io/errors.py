"""I/O-specific exception types for workbook read/write flows."""

from __future__ import annotations


class DuplicateDescriptionError(ValueError):
    """Raised when duplicate normalized Description keys are detected.

    Attributes
    ----------
    duplicate_key:
        The duplicate normalized description value.
    row_indices:
        Sorted list of zero-based input row indices that share *duplicate_key*.
    """

    def __init__(self, duplicate_key: str, row_indices: list[int]) -> None:
        self.duplicate_key = duplicate_key
        self.row_indices = list(row_indices)
        super().__init__(
            "Duplicate normalized Description key "
            f"{duplicate_key!r} at row indices {self.row_indices}"
        )


__all__ = ["DuplicateDescriptionError"]
