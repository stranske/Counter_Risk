from __future__ import annotations

import re
from pathlib import Path


def _load_runnerlaunch_source() -> str:
    source_path = Path("assets/vba/RunnerLaunch.bas")
    return source_path.read_text(encoding="utf-8")


def _extract_buildcommand_body(source: str) -> str:
    match = re.search(
        r"Public\s+Function\s+BuildCommand\s*\(.*?\)\s*As\s+String(.*?)End\s+Function",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, "BuildCommand function body was not found in RunnerLaunch.bas."
    return match.group(1)


def test_buildcommand_signature_has_exactly_three_parameters() -> None:
    source = _load_runnerlaunch_source()
    normalized_source = re.sub(
        r"Function\s+BuildCommand",
        "Sub BuildCommand",
        source,
        flags=re.IGNORECASE,
    )
    signature_pattern = re.compile(
        r"Sub\s+BuildCommand\s*\([^,]+,[^,]+,[^,]+\)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert (
        signature_pattern.search(normalized_source) is not None
    ), "BuildCommand signature must contain exactly three parameters."


def test_buildcommand_contains_date_parsing_call() -> None:
    source = _load_runnerlaunch_source()
    body = _extract_buildcommand_body(source)
    date_pattern = re.compile(r"(CDate|DateValue|DateSerial)\s*\(", flags=re.IGNORECASE)
    assert (
        date_pattern.search(body) is not None
    ), "BuildCommand body must contain CDate, DateValue, or DateSerial date parsing."
