"""Validate README testing section requirements for keepalive task tracking."""

from __future__ import annotations

import re
from pathlib import Path


def _testing_section_lines(readme: str) -> list[str]:
    match = re.search(r"^## Testing\s*$\n(.*?)(?=^##\s|\Z)", readme, re.MULTILINE | re.DOTALL)
    assert match is not None, "README.md must contain a '## Testing' section"
    body = match.group(1)
    return [line.strip() for line in body.splitlines() if line.strip()]


def test_testing_section_contains_single_autopilot_sentence() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    lines = _testing_section_lines(readme)

    assert len(lines) == 1, "Testing section must contain exactly one sentence"
    sentence = lines[0]

    assert "autopilot smoke tests" in sentence.lower()
    assert sentence.endswith("."), "Testing sentence must end with a period"

    words = [word for word in re.findall(r"[A-Za-z0-9']+", sentence)]
    assert 10 <= len(words) <= 20, "Testing sentence must be between 10 and 20 words"
