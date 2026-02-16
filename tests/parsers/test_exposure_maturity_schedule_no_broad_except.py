"""Guards against broad exception handling in the exposure maturity parser."""

from __future__ import annotations

from pathlib import Path


def test_exposure_maturity_schedule_parser_has_no_broad_except_exception() -> None:
    parser_path = Path("src/counter_risk/parsers/exposure_maturity_schedule.py")
    text = parser_path.read_text(encoding="utf-8")
    assert "except Exception" not in text
