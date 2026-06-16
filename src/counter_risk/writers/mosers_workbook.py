"""Compatibility writer wrapper for MOSERS workbook generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook as _generate_mosers_workbook_in_memory,
)
from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook_ex_trend as _generate_mosers_workbook_ex_trend_in_memory,
)
from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook_trend as _generate_mosers_workbook_trend_in_memory,
)


class _WorkbookLike(Protocol):
    def save(self, filename: str | Path) -> None: ...

    def close(self) -> None: ...

    def __getitem__(self, key: str) -> object: ...


_CPRS_CH_SHEET = "CPRS - CH"
_CPRS_CH_HEADER_DATE_LABEL = "CPRS CH Header Date"
_CPRS_CH_HEADER_DATE_LABEL_CELL = "A3"
_CPRS_CH_HEADER_DATE_VALUE_CELL = "B3"


def _coerce_as_of_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return date.fromisoformat(stripped)
    msg = f"as_of_date must be a date, datetime, or ISO date string; got {type(value)!r}"
    raise TypeError(msg)


def _stamp_as_of_date_on_workbook(workbook: _WorkbookLike, as_of_date: date) -> None:
    worksheet = workbook[_CPRS_CH_SHEET]
    worksheet[_CPRS_CH_HEADER_DATE_LABEL_CELL] = _CPRS_CH_HEADER_DATE_LABEL
    worksheet[_CPRS_CH_HEADER_DATE_VALUE_CELL] = as_of_date


def generate_mosers_workbook(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None = None,
) -> Path:
    """Create a new MOSERS workbook file from raw NISA All Programs input."""

    return _generate_and_save_mosers_workbook(
        raw_nisa_path=raw_nisa_path,
        output_path=output_path,
        as_of_date=as_of_date,
        generator=_generate_mosers_workbook_in_memory,
    )


def generate_mosers_workbook_ex_trend(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None = None,
) -> Path:
    """Create a new MOSERS workbook file from raw NISA Ex Trend input."""

    return _generate_and_save_mosers_workbook(
        raw_nisa_path=raw_nisa_path,
        output_path=output_path,
        as_of_date=as_of_date,
        generator=_generate_mosers_workbook_ex_trend_in_memory,
    )


def generate_mosers_workbook_trend(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None = None,
) -> Path:
    """Create a new MOSERS workbook file from raw NISA Trend input."""

    return _generate_and_save_mosers_workbook(
        raw_nisa_path=raw_nisa_path,
        output_path=output_path,
        as_of_date=as_of_date,
        generator=_generate_mosers_workbook_trend_in_memory,
    )


def _generate_and_save_mosers_workbook(
    *,
    raw_nisa_path: str | Path,
    output_path: str | Path,
    as_of_date: object | None,
    generator: Callable[[str | Path], _WorkbookLike],
) -> Path:
    destination = Path(output_path)
    if destination.suffix.lower() != ".xlsx":
        raise ValueError(f"output_path must point to an .xlsx file: {destination}")

    workbook = generator(raw_nisa_path)
    resolved_as_of_date = _coerce_as_of_date(as_of_date)
    if resolved_as_of_date is not None:
        _stamp_as_of_date_on_workbook(workbook, resolved_as_of_date)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return destination
