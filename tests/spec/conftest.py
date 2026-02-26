"""Shared fixtures for macro-spec tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from counter_risk.mosers.workbook_generation import (
    generate_mosers_workbook,
    generate_mosers_workbook_ex_trend,
    generate_mosers_workbook_trend,
)
from counter_risk.parsers.nisa import parse_nisa_all_programs
from counter_risk.parsers.nisa_ex_trend import parse_nisa_ex_trend
from counter_risk.parsers.nisa_trend import parse_nisa_trend

ParserFn = Callable[[str | Path], Any]
GeneratorFn = Callable[[str | Path], Any]


@dataclass(frozen=True)
class MacroSpecCase:
    """One macro-equivalent input/output scenario used by spec tests."""

    variant: str
    raw_input_path: Path
    parser: ParserFn
    generator: GeneratorFn


@pytest.fixture(scope="session")
def macro_spec_cases() -> tuple[MacroSpecCase, ...]:
    """Sample fixtures for all reporting variants used in macro parity tests."""

    return (
        MacroSpecCase(
            variant="all_programs",
            raw_input_path=Path("tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
            parser=parse_nisa_all_programs,
            generator=generate_mosers_workbook,
        ),
        MacroSpecCase(
            variant="ex_trend",
            raw_input_path=Path("tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx"),
            parser=parse_nisa_ex_trend,
            generator=generate_mosers_workbook_ex_trend,
        ),
        MacroSpecCase(
            variant="trend",
            raw_input_path=Path("tests/fixtures/NISA Monthly Trend - Raw.xlsx"),
            parser=parse_nisa_trend,
            generator=generate_mosers_workbook_trend,
        ),
    )


@pytest.fixture(scope="session")
def parsed_macro_spec_data(macro_spec_cases: tuple[MacroSpecCase, ...]) -> dict[str, Any]:
    """Pre-parsed sample input payloads keyed by variant for reuse across spec tests."""

    parsed_by_variant: dict[str, Any] = {}
    for case in macro_spec_cases:
        parsed_by_variant[case.variant] = case.parser(case.raw_input_path)
    return parsed_by_variant
