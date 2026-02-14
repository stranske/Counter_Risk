"""Tests for release bundle validation script and workflow draft docs."""

from __future__ import annotations

import subprocess
from pathlib import Path


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


def test_validate_release_bundle_script_exists_and_passes_for_valid_bundle(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "validate_release_bundle.sh"
    assert script.is_file()

    executable_name = "counter-risk.exe" if subprocess.run(
        ["uname", "-s"], text=True, capture_output=True, check=False
    ).stdout.strip().startswith(("CYGWIN", "MINGW", "MSYS")) else "counter-risk"
    bundle_dir = tmp_path / "release" / "1.2.3"
    _create_valid_bundle(bundle_dir, executable_name=executable_name)

    result = subprocess.run(
        [str(script), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_validate_release_bundle_script_fails_when_manifest_missing(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "validate_release_bundle.sh"
    assert script.is_file()

    executable_name = "counter-risk.exe" if subprocess.run(
        ["uname", "-s"], text=True, capture_output=True, check=False
    ).stdout.strip().startswith(("CYGWIN", "MINGW", "MSYS")) else "counter-risk"
    bundle_dir = tmp_path / "release" / "1.2.3"
    _create_valid_bundle(bundle_dir, executable_name=executable_name)
    (bundle_dir / "manifest.json").unlink()

    result = subprocess.run(
        [str(script), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "manifest" in result.stderr


def test_release_workflow_draft_contains_required_steps() -> None:
    workflow_path = REPO_ROOT / "docs" / "release.yml.draft"
    assert workflow_path.is_file()

    contents = workflow_path.read_text(encoding="utf-8")

    assert "workflow_dispatch" in contents
    assert "actions/checkout@v4" in contents
    assert "actions/setup-python@v5" in contents
    assert "python -m pip install -e \".[dev]\"" in contents
    assert "python -m pip install pyinstaller" in contents
    assert "pytest tests/" in contents
    assert "pyinstaller -y release.spec" in contents
    assert "python -m counter_risk.build.release" in contents
    assert "scripts/validate_release_bundle.sh" in contents
    assert "actions/upload-artifact@v4" in contents


def test_release_workflow_setup_doc_exists_with_promotion_steps() -> None:
    setup_path = REPO_ROOT / "docs" / "RELEASE_WORKFLOW_SETUP.md"
    assert setup_path.is_file()

    contents = setup_path.read_text(encoding="utf-8")

    assert "pyproject.toml" in contents
    assert "python -m counter_risk.build.release --version-file VERSION --output-dir release --force" in contents
    assert "docs/release.yml.draft" in contents
    assert ".github/workflows/release.yml" in contents
    assert "workflow_dispatch" in contents
