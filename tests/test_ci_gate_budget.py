"""Gate CI budget: pytest distribution and measurement hygiene."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

# Same-commit local A/B on tip (Gate markers, -n 4, ignore integration):
#   --dist load      WALL_SEC=32.87  (kept)
#   --dist loadfile  WALL_SEC=34.75
#   --dist loadscope WALL_SEC=34.91
# Keep the faster strategy on Gate and main CI.
GATE_DIST = "load"
MAIN_CI_DIST = "load"


def _pytest_args(workflow_name: str, job_key: str) -> str:
    workflow = yaml.safe_load((WORKFLOWS / workflow_name).read_text(encoding="utf-8"))
    return str(workflow["jobs"][job_key]["with"]["pytest_args"])


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
