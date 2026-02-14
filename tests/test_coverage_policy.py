"""Coverage policy regression tests for keepalive acceptance criteria."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_coverage_fail_under_is_env_driven() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    fail_under = pyproject["tool"]["coverage"]["report"]["fail_under"]
    assert fail_under == "${COVERAGE_FAIL_UNDER-0}"
