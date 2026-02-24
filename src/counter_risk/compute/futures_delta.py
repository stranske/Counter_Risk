"""Futures delta: join prior vs current month detail, compute change, and flag sign flips.

Workflow
--------
1. Parse futures detail rows for the *current* month and the *prior* month via
   :func:`counter_risk.parsers.cprs_fcm.parse_futures_detail`.
2. Pass both tables to :func:`compute_futures_delta`.
3. The function normalises descriptions, joins the two months, computes
   ``notional_change = current - prior``, and marks rows whose sign flipped
   with an asterisk in the ``sign_flip`` column.
4. Optionally persist the annotated table via :func:`write_annotated_csv`.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Description normalisation
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


def normalize_description(description: str) -> str:
    """Normalise a futures description string for cross-month matching.

    Steps applied:

    * Collapse all internal whitespace runs to a single space and strip edges.
    * Standardise contract month + year patterns to the form ``MON{YY}``
      (upper-case three-letter abbreviation + two-digit year), e.g.
      ``"March 2025"`` → ``"MAR25"``, ``"Mar '25"`` → ``"MAR25"``.
    * Upper-case the entire result.

    The normalised string is used only as a join key; output rows retain the
    original description text.
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
# Core computation
# ---------------------------------------------------------------------------


def compute_futures_delta(
    current: Any,
    prior: Any,
) -> tuple[Any, list[str]]:
    """Join current and prior month futures detail, compute change and sign-flip flags.

    Parameters
    ----------
    current:
        Current-month rows.  Must provide ``description`` and ``notional``
        columns/keys.  Accepts a :class:`pandas.DataFrame` or any iterable of
        row mappings.
    prior:
        Prior-month rows in the same format as *current*.

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

        Rows are sorted ascending by normalised description.

    warnings:
        Human-readable strings describing rows that could not be matched.
        Unmatched current-month rows (no prior equivalent) and unmatched
        prior-month rows (dropped from current) are both reported.
    """
    current_rows = _to_row_list(current, arg="current")
    prior_rows = _to_row_list(prior, arg="prior")

    # Build prior lookup: normalised description -> accumulated notional.
    prior_by_key: dict[str, float] = {}
    prior_desc_by_key: dict[str, str] = {}
    for row in prior_rows:
        desc = str(row.get("description", "") or "")
        key = normalize_description(desc)
        notional = _extract_notional(row)
        prior_by_key[key] = prior_by_key.get(key, 0.0) + notional
        if key not in prior_desc_by_key:
            prior_desc_by_key[key] = desc

    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    current_keys: set[str] = set()

    for row in current_rows:
        desc = str(row.get("description", "") or "")
        key = normalize_description(desc)
        current_notional = _extract_notional(row)
        current_keys.add(key)

        if key in prior_by_key:
            prior_notional = prior_by_key[key]
        else:
            prior_notional = 0.0
            warnings.append(f"Unmatched current row (no prior match): {desc!r}")

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
            warnings.append(f"Unmatched prior row (no current match): {original_desc!r}")

    # Sort output by normalised description for stable, alphabetical order.
    records.sort(key=lambda r: normalize_description(str(r.get("description", ""))))

    return _to_output(records=records), warnings


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


def _extract_notional(row: dict[str, Any]) -> float:
    """Extract the notional value from a row, trying common key aliases."""
    for key in ("notional", "Notional", "exposure"):
        val = row.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
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
