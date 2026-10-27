"""Gate CI budget: pytest distribution and measurement hygiene."""

from __future__ import annotations

import re
import shlex
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


def _job_inputs(workflow_name: str, job_key: str) -> dict:
    workflow = yaml.safe_load((WORKFLOWS / workflow_name).read_text(encoding="utf-8"))
    return dict(workflow["jobs"][job_key]["with"])


def _pytest_args(workflow_name: str, job_key: str) -> str:
    return str(_job_inputs(workflow_name, job_key)["pytest_args"])


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


def _dist_values(args: str) -> list[str]:
    """Every value given to `--dist`, in both `--dist X` and `--dist=X` forms."""
    tokens = shlex.split(args)
    values = []
    for index, token in enumerate(tokens):
        if token == "--dist" and index + 1 < len(tokens):
            values.append(tokens[index + 1])
        elif token.startswith("--dist="):
            values.append(token.split("=", 1)[1])
    return values


def test_dist_option_is_parsed_by_exact_value_not_substring() -> None:
    assert _dist_values("-n auto --dist load") == ["load"]
    assert _dist_values("-n auto --dist=load") == ["load"]
    assert _dist_values("-n auto --dist loadfile") == ["loadfile"]
    assert _dist_values("--dist load --dist loadscope") == ["load", "loadscope"]


def test_gate_pytest_args_do_not_use_loadscope() -> None:
    gate_args = _pytest_args("pr-00-gate.yml", "python-ci")
    ci_args = _pytest_args("ci.yml", "python")

    # Gate and main CI must stay on the same measured winner.
    assert GATE_DIST == MAIN_CI_DIST == "load"
    # Exactly one --dist option, with exactly the measured value (no substring match, no duplicates).
    assert _dist_values(gate_args) == [GATE_DIST]
    assert _dist_values(ci_args) == [MAIN_CI_DIST]
    assert "loadscope" not in gate_args
    assert "loadscope" not in ci_args
    assert "--durations" not in gate_args
    # loadfile lost the same-commit A/B; do not leave it as the chosen dist.
    assert "--dist loadfile" not in gate_args
    assert "--dist loadfile" not in ci_args


def test_pandas_lock_has_cp314_wheels() -> None:
    versions = {
        lock_name: _lock_pandas_version(lock_name)
        for lock_name in ("requirements.lock", "requirements-dev.lock")
    }
    assert all(version >= MIN_PANDAS_LOCK for version in versions.values())
    # Keep the two lock files on the same pandas pin so CI and local sync agree.
    assert len(set(versions.values())) == 1


def test_main_ci_measures_coverage_on_primary_runtime_only() -> None:
    inputs = _job_inputs("ci.yml", "python")

    # Without coverage-python-version the reusable workflow instruments every leg; the 3.13
    # leg then ran 42 min on main (run 40344564212). Coverage belongs on the primary runtime.
    assert inputs.get("coverage") is True
    assert "coverage-python-version" in inputs
    assert str(inputs["coverage-python-version"]) == str(inputs["primary-python-version"])


def test_main_ci_timing_jobs_generate_metrics() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    timing_jobs = {
        name: job["with"]
        for name, job in workflow["jobs"].items()
        if "slow-test-top" in job.get("with", {})
    }
    assert timing_jobs, "main CI must retain primary-runtime timing evidence"
    for name, inputs in timing_jobs.items():
        assert inputs.get("enable-metrics") is True, f"{name} cannot emit its timing artifact"


def test_main_ci_requests_25_slowest_tests_for_every_shard() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    for name, job in workflow["jobs"].items():
        if "reusable-10-ci-python.yml" not in job.get("uses", ""):
            continue
        inputs = job["with"]
        # Checking only jobs that still have slow-test-top misses a removed primary-job
        # setting: the remaining slow shards would keep the metrics test above green.
        assert str(inputs.get("slow-test-top")) == "25", f"{name} must retain 25 timings"


def test_main_ci_reusable_jobs_have_distinct_artifact_prefixes() -> None:
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    prefixes = [
        job.get("with", {}).get("artifact-prefix", "gate-")
        for job in workflow["jobs"].values()
        if "reusable-10-ci-python.yml" in job.get("uses", "")
    ]
    # Coverage-disabled calls still upload test results with overwrite enabled.
    assert len(prefixes) == len(set(prefixes)), "parallel jobs can overwrite CI evidence"
