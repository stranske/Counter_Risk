"""Tests for release bundle validation script and workflow draft docs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]


def _create_valid_bundle(bundle_dir: Path, *, executable_name: str) -> None:
    (bundle_dir / "config").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "templates").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "bin").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (bundle_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (bundle_dir / "config" / "fixture_replay.yml").write_text("name: fixture\n", encoding="utf-8")
    (bundle_dir / "run_counter_risk.cmd").write_text("@echo off\n", encoding="utf-8")
    (bundle_dir / "README_HOW_TO_RUN.md").write_text("# How to run\n", encoding="utf-8")
    (bundle_dir / "bin" / executable_name).write_text("binary\n", encoding="utf-8")


def _env_with_stub_gh(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = tmp_path / "test-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh_path = bin_dir / "gh"
    gh_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    gh_path.chmod(0o755)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


def test_validate_release_bundle_script_exists_and_passes_for_valid_bundle(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "validate_release_bundle.sh"
    assert script.is_file()

    executable_name = (
        "counter-risk.exe"
        if subprocess.run(["uname", "-s"], text=True, capture_output=True, check=False)
        .stdout.strip()
        .startswith(("CYGWIN", "MINGW", "MSYS"))
        else "counter-risk"
    )
    bundle_dir = tmp_path / "release" / "1.2.3"
    _create_valid_bundle(bundle_dir, executable_name=executable_name)

    result = subprocess.run(
        [str(script), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
        env=_env_with_stub_gh(tmp_path),
    )

    assert result.returncode == 0, result.stderr


def test_validate_release_bundle_script_fails_when_manifest_missing(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "validate_release_bundle.sh"
    assert script.is_file()

    executable_name = (
        "counter-risk.exe"
        if subprocess.run(["uname", "-s"], text=True, capture_output=True, check=False)
        .stdout.strip()
        .startswith(("CYGWIN", "MINGW", "MSYS"))
        else "counter-risk"
    )
    bundle_dir = tmp_path / "release" / "1.2.3"
    _create_valid_bundle(bundle_dir, executable_name=executable_name)
    (bundle_dir / "manifest.json").unlink()

    result = subprocess.run(
        [str(script), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
        env=_env_with_stub_gh(tmp_path),
    )

    assert result.returncode != 0
    assert "manifest" in result.stderr


def test_release_workflow_draft_contains_required_steps() -> None:
    workflow_path = REPO_ROOT / "docs" / "release.yml.draft"
    assert workflow_path.is_file()

    contents = workflow_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(contents)
    workflow_on = parsed.get("on", parsed.get(True, {}))
    assert workflow_on["workflow_dispatch"] is None

    steps = parsed["jobs"]["release"]["steps"]
    uses_steps = [str(step.get("uses", "")) for step in steps]
    run_steps = [str(step.get("run", "")) for step in steps if "run" in step]

    assert "actions/checkout@v4" in uses_steps
    assert "actions/setup-python@v5" in uses_steps

    assert any("pip install -r requirements.txt" in run for run in run_steps)
    assert any("pytest tests/" in run for run in run_steps)
    assert any("pyinstaller -y release.spec" in run for run in run_steps)
    assert any("python -m counter_risk.build.release" in run for run in run_steps)
    assert any("scripts/validate_release_bundle.sh" in run for run in run_steps)

    upload_steps = [
        step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact")
    ]
    assert upload_steps
    upload_with = upload_steps[0].get("with", {})
    upload_path = str(upload_with.get("path", ""))
    assert "release/" in upload_path
    assert "retention-days" in upload_with


def test_release_workflow_draft_dispatch_inputs_do_not_require_version() -> None:
    workflow_path = REPO_ROOT / "docs" / "release.yml.draft"
    assert workflow_path.is_file()

    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    workflow_on = parsed.get("on", parsed.get(True, {}))
    dispatch_inputs = (workflow_on or {}).get("workflow_dispatch") or {}
    version_input = (dispatch_inputs.get("inputs") or {}).get("version")
    if version_input is None:
        return

    assert version_input.get("required") is not True


def test_release_workflow_setup_doc_exists_with_promotion_steps() -> None:
    setup_path = REPO_ROOT / "docs" / "RELEASE_WORKFLOW_SETUP.md"
    assert setup_path.is_file()

    contents = setup_path.read_text(encoding="utf-8")

    assert "requirements.txt" in contents
    assert (
        "python -m counter_risk.build.release --version-file VERSION --output-dir release --force"
        in contents
    )
    assert "docs/release.yml.draft" in contents
    assert ".github/workflows/release.yml" in contents
    assert "workflow_dispatch" in contents
