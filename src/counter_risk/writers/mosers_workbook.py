"""Compatibility writer wrapper for MOSERS workbook generation."""

from __future__ import annotations

from collections.abc import Callable
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

    _ = as_of_date
    workbook = generator(raw_nisa_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return destination
