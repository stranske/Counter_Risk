"""Gate CI budget: pytest distribution and measurement hygiene."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Same-commit local A/B on tip (Gate markers, -n 4, ignore integration):
#   --dist load      WALL_SEC=32.87  (kept)
#   --dist loadfile  WALL_SEC=34.75
#   --dist loadscope WALL_SEC=34.91
# Keep the faster strategy on Gate and main CI.
GATE_DIST = "load"
MAIN_CI_DIST = "load"

# pandas 2.3.0 has no cp314 wheels; Gate 3.14 spent ~4m building from source.
# 2.3.3+ ships manylinux cp314 wheels (Install dropped 245s → 4s on run 40260367717).
MIN_PANDAS_LOCK = (2, 3, 3)


def _pytest_args(workflow_name: str, job_key: str) -> str:
    workflow = yaml.safe_load((WORKFLOWS / workflow_name).read_text(encoding="utf-8"))
    return str(workflow["jobs"][job_key]["with"]["pytest_args"])


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split("."):
        digits = re.match(r"([0-9]+)", piece)
        if digits is None:
            break
        parts.append(int(digits.group(1)))
    return tuple(parts)


def _lock_pandas_version(lock_name: str) -> tuple[int, ...]:
    text = (REPO_ROOT / lock_name).read_text(encoding="utf-8")
    match = re.search(r"^pandas==([0-9][^\s#]+)", text, flags=re.MULTILINE)
    assert match is not None, f"pandas pin missing from {lock_name}"
    return _version_tuple(match.group(1))


def test_gate_pytest_args_do_not_use_loadscope() -> None:
    gate_args = _pytest_args("pr-00-gate.yml", "python-ci")
    ci_args = _pytest_args("ci.yml", "python")

    assert f"--dist {GATE_DIST}" in gate_args
    assert f"--dist {MAIN_CI_DIST}" in ci_args
    assert "loadscope" not in gate_args
    assert "loadscope" not in ci_args
    assert "--durations" not in gate_args
    # loadfile lost the same-commit A/B; do not leave it as the chosen dist.
    assert "--dist loadfile" not in gate_args
    assert "--dist loadfile" not in ci_args


def test_pandas_lock_has_cp314_wheels() -> None:
    for lock_name in ("requirements.lock", "requirements-dev.lock"):
        assert _lock_pandas_version(lock_name) >= MIN_PANDAS_LOCK
