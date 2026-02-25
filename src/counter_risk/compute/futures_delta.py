"""Futures delta: join prior vs current month detail, compute change, and flag sign flips.

Workflow
--------
1. Parse futures detail rows for the *current* month and the *prior* month via
   :func:`counter_risk.parsers.cprs_fcm.parse_futures_detail`.
2. Pass both tables to :func:`compute_futures_delta`.
3. The function validates each row, normalises descriptions for matching, joins the two
   months, computes ``notional_change = current - prior``, and marks rows whose sign
   flipped with an asterisk in the ``sign_flip`` column.
4. Optionally persist the annotated table via :func:`write_annotated_csv`.

Warnings are reported through a :class:`~counter_risk.pipeline.manifest.WarningsCollector`
passed by the caller, and are also emitted via the module-level Python logger.
"""

from __future__ import annotations

import csv
import logging
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from counter_risk.pipeline.manifest import WarningsCollector

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Description normalisation (used only for cross-month matching, not sorting)
# ---------------------------------------------------------------------------

# Matches contract month abbreviations such as:
#   "Mar25", "MAR 25", "March 2025", "Mar '25", "MARCH2025"
_CONTRACT_MONTH_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s*'?\s*(\d{2,4})\b",
    re.IGNORECASE,
)

_MONTH_SHORT: dict[str, str] = {
    "jan": "JAN",
    "feb": "FEB",
    "mar": "MAR",
    "apr": "APR",
    "may": "MAY",
    "jun": "JUN",
    "jul": "JUL",
    "aug": "AUG",
    "sep": "SEP",
    "oct": "OCT",
    "nov": "NOV",
    "dec": "DEC",
}

_OUTPUT_COLUMNS: tuple[str, ...] = (
    "description",
    "notional",
    "prior_notional",
    "notional_change",
    "sign_flip",
)


def is_blank_description(desc: Any) -> bool:
    """Return True when a description is None, empty, or whitespace-only."""
    if desc is None:
        return True
    return str(desc).strip() == ""


def normalize_description(description: str) -> str:
    """Normalise a futures description string for cross-month matching.

    Steps applied:

    * Collapse all internal whitespace runs to a single space and strip edges.
    * Standardise contract month + year patterns to the form ``MON{YY}``
      (upper-case three-letter abbreviation + two-digit year), e.g.
      ``"March 2025"`` → ``"MAR25"``, ``"Mar '25"`` → ``"MAR25"``.
    * Upper-case the entire result.

    The normalised string is used only as a join key; output rows retain the
    original description text and output ordering uses the raw description.
    """
    text = re.sub(r"\s+", " ", description).strip()

    def _replace_month(match: re.Match[str]) -> str:
        abbrev = match.group(1)[:3].lower()
        month = _MONTH_SHORT.get(abbrev, abbrev.upper())
        year = match.group(2)
        if len(year) == 4:
            year = year[2:]
        return f"{month}{year}"

    text = _CONTRACT_MONTH_RE.sub(_replace_month, text)
    return text.upper()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidNotionalError(ValueError):
    """Raised in strict mode when a notional value is missing or invalid.

    The message includes at minimum the row identifier (``Description`` or row index)
    so the caller can pinpoint the problematic input row.
    """


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_futures_delta(
    current: Any,
    prior: Any,
    *,
    collector: WarningsCollector | None = None,
) -> Any:
    """Join current and prior month futures detail, compute change and sign-flip flags.

    Warnings (unmatched rows, invalid notional, missing fields) are emitted via the
    module-level logger **and** pushed to *collector* when one is supplied.  The
    function does **not** return a warnings list; callers should inspect
    ``collector.warnings`` after the call.

    Parameters
    ----------
    current:
        Current-month rows.  Must provide ``Description`` (or ``description``) and
        ``Notional`` (or ``notional`` / ``exposure``) columns/keys.  Accepts a
        :class:`pandas.DataFrame` or any iterable of row mappings.
    prior:
        Prior-month rows in the same format as *current*.
    collector:
        Optional :class:`~counter_risk.pipeline.manifest.WarningsCollector` that
        receives structured warnings with reason codes such as
        ``NO_PRIOR_MONTH_MATCH``.

    Returns
    -------
    result:
        Annotated table (a :class:`pandas.DataFrame` when pandas is available,
        otherwise a list of dicts) with columns:

        * ``description`` – original description from the current-month row.
        * ``notional`` – current-month notional.
        * ``prior_notional`` – matched prior-month notional (``0.0`` when no
          prior row matched).
        * ``notional_change`` – ``notional - prior_notional``.
        * ``sign_flip`` – ``"*"`` when the sign changed between months
          (both values non-zero and of opposite sign), ``""`` otherwise.

        Rows are sorted ascending by the raw ``description`` text (exact input
        string, no normalisation applied to the sort key).  Ties (duplicate
        descriptions) preserve the original input order (stable sort).
    """
    current_rows = _to_row_list(current, arg="current")
    prior_rows = _to_row_list(prior, arg="prior")

    # Build prior lookup: normalised description -> accumulated notional.
    prior_by_key: dict[str, float] = {}
    prior_desc_by_key: dict[str, str] = {}
    for row in prior_rows:
        desc = str(row.get("description", row.get("Description", "")) or "")
        key = normalize_description(desc)
        notional = _extract_notional(row, row_id=desc or "<prior row>", collector=collector)
        prior_by_key[key] = prior_by_key.get(key, 0.0) + notional
        if key not in prior_desc_by_key:
            prior_desc_by_key[key] = desc

    records: list[dict[str, Any]] = []
    current_keys: set[str] = set()

    for row_idx, row in enumerate(current_rows):
        # Per-row required-field validation; skip invalid rows.
        if not _validate_row(row, row_idx=row_idx, collector=collector):
            continue

        desc = str(row.get("description", row.get("Description", "")) or "")
        key = normalize_description(desc)
        current_notional = _extract_notional(row, row_id=desc, collector=collector)
        current_keys.add(key)

        if key in prior_by_key:
            prior_notional = prior_by_key[key]
        else:
            prior_notional = 0.0
            msg = f"Unmatched current row (no prior match): {desc!r}"
            _LOG.warning(msg)
            if collector is not None:
                collector.warn(msg, code="NO_PRIOR_MONTH_MATCH", row_idx=row_idx)

        change = current_notional - prior_notional

        # Sign flip: both sides non-zero and opposite sign.
        if prior_notional != 0.0 and current_notional != 0.0:
            sign_flip = "*" if (current_notional > 0) != (prior_notional > 0) else ""
        else:
            sign_flip = ""

        records.append(
            {
                "description": desc,
                "notional": current_notional,
                "prior_notional": prior_notional,
                "notional_change": change,
                "sign_flip": sign_flip,
            }
        )

    # Report prior rows that have no match in current.
    for key, _prior_notional in prior_by_key.items():
        if key not in current_keys:
            original_desc = prior_desc_by_key.get(key, key)
            msg = f"Unmatched prior row (no current match): {original_desc!r}"
            _LOG.warning(msg)
            if collector is not None:
                collector.warn(msg, code="NO_PRIOR_MONTH_MATCH")

    # Sort output by raw description text for stable, deterministic order.
    # Python's sort is stable: duplicate descriptions preserve input order.
    records.sort(key=lambda r: str(r.get("description", "")))

    return _to_output(records=records)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def write_annotated_csv(result: Any, path: Path | str) -> None:
    """Write the annotated futures delta table to a CSV file.

    Parameters
    ----------
    result:
        Return value of :func:`compute_futures_delta` (DataFrame or list of
        dicts).
    path:
        Destination file path.  Parent directories are created automatically.
    """
    rows = _to_row_list(result, arg="result")
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(_OUTPUT_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_row_list(table: Any, *, arg: str) -> list[dict[str, Any]]:
    """Convert a DataFrame or iterable-of-mappings to a plain list of dicts."""
    if hasattr(table, "to_dict") and hasattr(table, "columns"):
        return list(table.to_dict(orient="records"))
    if isinstance(table, (str, bytes)):
        raise TypeError(
            f"{arg} must be a DataFrame or iterable of row mappings, not {type(table)!r}"
        )
    try:
        rows = list(table)
    except TypeError as exc:
        raise TypeError(
            f"{arg} must be a DataFrame or iterable of row mappings, not {type(table)!r}"
        ) from exc
    result: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not hasattr(row, "get"):
            raise TypeError(f"{arg} row at index {i} must be a mapping, got {type(row)!r}")
        result.append(dict(row))
    return result


def _validate_row(
    row: dict[str, Any],
    *,
    row_idx: int,
    collector: WarningsCollector | None = None,
) -> bool:
    """Validate required fields on a single row.

    A row is valid when:

    * ``description`` (or ``Description``) is present and non-empty after
      stripping whitespace.
    * At least one notional key (``notional``, ``Notional``, ``exposure``) is
      present in the mapping.

    Invalid rows emit a structured warning via the logger and *collector*, and
    are excluded from matching and output.  The warning includes the 0-based
    *row_idx* and all available non-empty field values.

    Returns ``True`` when the row is valid.
    """
    desc_raw = row.get("description", row.get("Description"))
    if desc_raw is None or str(desc_raw).strip() == "":
        non_empty = {k: v for k, v in row.items() if v is not None and str(v).strip() != ""}
        msg = (
            f"Row {row_idx}: missing/blank Description; " f"available non-empty fields: {non_empty}"
        )
        _LOG.warning(msg)
        if collector is not None:
            collector.warn(msg, code="MISSING_DESCRIPTION", row_idx=row_idx)
        return False

    notional_present = any(k in row for k in ("notional", "Notional", "exposure"))
    if not notional_present:
        desc = str(desc_raw).strip()
        msg = f"Row {row_idx}: Notional field missing for {desc!r}"
        _LOG.warning(msg)
        if collector is not None:
            collector.warn(msg, code="MISSING_NOTIONAL", row_idx=row_idx)
        return False

    return True


def _extract_notional(
    row: dict[str, Any],
    *,
    row_id: str = "",
    strict: bool = False,
    collector: WarningsCollector | None = None,
) -> float:
    """Extract the notional value from a row, trying common key aliases.

    Parameters
    ----------
    row:
        Row mapping to extract from.
    row_id:
        Human-readable identifier (e.g. ``Description`` text or row index) used
        in warning and exception messages.
    strict:
        When ``True``, raise :class:`InvalidNotionalError` instead of returning
        ``0.0`` for missing/invalid values.
    collector:
        Optional warnings collector that receives a structured warning entry
        when the notional is missing, blank, non-numeric, or NaN.

    Returns
    -------
    float
        The extracted notional, or ``0.0`` when missing/invalid (non-strict mode).

    Raises
    ------
    InvalidNotionalError
        In strict mode only, when the notional value is missing or invalid.
    """
    notional_keys = ("notional", "Notional", "exposure")

    # Try each key alias in order.
    for key in notional_keys:
        val = row.get(key)
        if val is None:
            continue
        # Treat blank strings as missing.
        if isinstance(val, str) and val.strip() == "":
            msg = f"Blank notional for row {row_id!r} (key={key!r})"
            _LOG.warning(msg)
            if collector is not None:
                collector.warn(msg, code="INVALID_NOTIONAL")
            if strict:
                raise InvalidNotionalError(msg)
            return 0.0
        try:
            result = float(val)
        except (TypeError, ValueError):
            msg = f"Non-numeric notional {val!r} for row {row_id!r} (key={key!r})"
            _LOG.warning(msg)
            if collector is not None:
                collector.warn(msg, code="INVALID_NOTIONAL")
            if strict:
                raise InvalidNotionalError(msg) from None
            return 0.0
        # Treat NaN as invalid.
        if math.isnan(result):
            msg = f"NaN notional for row {row_id!r} (key={key!r})"
            _LOG.warning(msg)
            if collector is not None:
                collector.warn(msg, code="INVALID_NOTIONAL")
            if strict:
                raise InvalidNotionalError(msg)
            return 0.0
        return result

    # No notional key found at all.
    msg = f"Missing notional field for row {row_id!r}"
    _LOG.warning(msg)
    if collector is not None:
        collector.warn(msg, code="MISSING_NOTIONAL")
    if strict:
        raise InvalidNotionalError(msg)
    return 0.0


def _to_output(*, records: list[dict[str, Any]]) -> Any:
    """Return the records as a DataFrame when pandas is available."""
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return [{col: row.get(col, "") for col in _OUTPUT_COLUMNS} for row in records]

    frame = pd.DataFrame(records) if records else pd.DataFrame(columns=list(_OUTPUT_COLUMNS))
    for col in _OUTPUT_COLUMNS:
        if col not in frame.columns:
            frame[col] = "" if col == "sign_flip" else 0.0
    return frame.loc[:, list(_OUTPUT_COLUMNS)]
