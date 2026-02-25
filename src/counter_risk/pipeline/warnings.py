"""Structured warning records used across pipeline components."""

from __future__ import annotations

WarningRecord = dict[str, object]


def _is_blank_warning_value(value: object) -> bool:
    """Return True for values that should be excluded from structured extras."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


class WarningsCollector:
    """Accumulates structured warnings for manifest and logging integration.

    Pass an instance to computation functions that support a *collector* parameter
    so that warnings are centralised and can be forwarded to :meth:`ManifestBuilder.build`
    via the ``warnings`` argument.

    Warning codes
    -------------
    INVALID_NOTIONAL
        The notional field was found but its value is blank, non-numeric, or NaN.
    MISSING_DESCRIPTION
        The ``Description`` field is absent or blank after stripping.
    MISSING_NOTIONAL
        No notional field was found in the row.
    NO_PRIOR_MONTH_MATCH
        A current-month row has no matching prior-month row.
    """

    INVALID_NOTIONAL: str = "INVALID_NOTIONAL"
    MISSING_DESCRIPTION: str = "MISSING_DESCRIPTION"
    MISSING_NOTIONAL: str = "MISSING_NOTIONAL"
    NO_PRIOR_MONTH_MATCH: str = "NO_PRIOR_MONTH_MATCH"

    def __init__(self) -> None:
        self._entries: list[WarningRecord] = []

    def warn(self, message: str, *, code: str | None = None, **extra: object) -> None:
        """Record a warning with a required ``row_idx`` (defaults to -1)."""
        row_idx_raw = extra.pop("row_idx", -1)
        if isinstance(row_idx_raw, int):
            row_idx = row_idx_raw
        elif isinstance(row_idx_raw, str):
            row_idx = int(row_idx_raw)
        else:
            row_idx = -1
        record: WarningRecord = {"row_idx": row_idx, "message": message}
        if code is not None:
            record["code"] = code
        for key, value in extra.items():
            if not _is_blank_warning_value(value):
                record[key] = value
        self._entries.append(record)

    def add_structured(self, row_idx: int, **extra_fields: object) -> None:
        """Record a structured warning with required ``row_idx`` and filtered extras."""
        record: WarningRecord = {"row_idx": int(row_idx)}
        for key, value in extra_fields.items():
            if not _is_blank_warning_value(value):
                record[key] = value
        self._entries.append(record)

    @property
    def warnings(self) -> list[WarningRecord]:
        """Return a copy of all accumulated structured warnings."""
        return [dict(entry) for entry in self._entries]
