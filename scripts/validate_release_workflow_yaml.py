#!/usr/bin/env python3
"""Static validation checks for release workflow YAML."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REQUIRED_RUN_SNIPPETS = (
    'python -m pip install -e ".[dev]"',
    "pytest tests/",
    "pyinstaller -y release.spec",
    "python -m counter_risk.build.release",
    "scripts/validate_release_bundle.sh",
)
DEFAULT_WORKFLOW_PATH = Path(".github/workflows/release.yml")


class ValidationError(Exception):
    """Raised when the workflow does not meet required criteria."""


def _load_yaml(path: Path) -> dict:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValidationError(f"{path} did not parse as a mapping")
    return parsed


def _workflow_on(parsed: dict) -> dict:
    on_node = parsed.get("on", parsed.get(True, {}))
    if on_node is None:
        return {}
    if not isinstance(on_node, dict):
        raise ValidationError("workflow 'on' stanza must be a mapping")
    return on_node


def _steps(parsed: dict) -> list[dict]:
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        raise ValidationError("missing jobs mapping")

    release_job = jobs.get("release")
    if not isinstance(release_job, dict):
        raise ValidationError("missing jobs.release mapping")

    steps = release_job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise ValidationError("jobs.release.steps must be a list of mappings")
    return steps


def validate_release_workflow(path: Path) -> list[str]:
    parsed = _load_yaml(path)
    workflow_on = _workflow_on(parsed)

    errors: list[str] = []
    if "workflow_dispatch" not in workflow_on:
        errors.append("missing 'on.workflow_dispatch' trigger")

    dispatch_inputs = (workflow_on.get("workflow_dispatch") or {}).get("inputs") or {}
    version_input = dispatch_inputs.get("version")
    if isinstance(version_input, dict) and version_input.get("required") is True:
        errors.append("workflow_dispatch.inputs.version must not set required: true")

    try:
        steps = _steps(parsed)
    except ValidationError as exc:
        return [str(exc)]

    uses_steps = [str(step.get("uses", "")) for step in steps]
    run_steps = [str(step.get("run", "")) for step in steps if "run" in step]

    if "actions/checkout@v4" not in uses_steps:
        errors.append("missing actions/checkout@v4 step")
    if "actions/setup-python@v5" not in uses_steps:
        errors.append("missing actions/setup-python@v5 step")

    for snippet in REQUIRED_RUN_SNIPPETS:
        if not any(snippet in run for run in run_steps):
            errors.append(f"missing run step containing: {snippet}")

    upload_steps = [
        step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact")
    ]
    if not upload_steps:
        errors.append("missing actions/upload-artifact step")
    else:
        upload_path = str(upload_steps[0].get("with", {}).get("path", ""))
        if "release/" not in upload_path:
            errors.append("upload-artifact path must include 'release/'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_path", type=Path, nargs="?", default=DEFAULT_WORKFLOW_PATH)
    args = parser.parse_args()

    if not args.workflow_path.is_file():
        print(f"[ERROR] Workflow file not found: {args.workflow_path}")
        return 1

    errors = validate_release_workflow(args.workflow_path)
    if errors:
        print(f"[ERROR] Workflow validation failed for {args.workflow_path}:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"[INFO] Workflow validation checks passed for {args.workflow_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
