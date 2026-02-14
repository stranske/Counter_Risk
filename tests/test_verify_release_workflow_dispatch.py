from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_release_workflow_dispatch.sh"


def _write_valid_workflow(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
name: Release
on:
  workflow_dispatch:
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -e ".[dev]"
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release --version-file VERSION --output-dir release --force
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with:
          path: release/1.2.3/
""",
        encoding="utf-8",
    )


def test_verify_release_workflow_dispatch_reports_missing_workflow_file() -> None:
    result = subprocess.run(
        [str(SCRIPT_PATH), "release.yml", "main"],
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "Workflow file not found" in output
    assert "docs/release.yml.draft" in output
    assert ".github/workflows/release.yml" in output


def test_verify_release_workflow_dispatch_rejects_draft_path() -> None:
    result = subprocess.run(
        [str(SCRIPT_PATH), "docs/release.yml.draft", "main"],
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "cannot be dispatched directly" in output
    assert ".github/workflows/release.yml" in output


def test_verify_release_workflow_dispatch_fails_gh_preflight_or_auth(tmp_path: Path) -> None:
    workflow_path = tmp_path / ".github" / "workflows" / "release.yml"
    _write_valid_workflow(workflow_path)

    result = subprocess.run(
        [str(SCRIPT_PATH), "release.yml", "main"],
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "gh" in output.lower()
    assert "required" in output.lower() or "not found" in output.lower() or "auth" in output.lower()
