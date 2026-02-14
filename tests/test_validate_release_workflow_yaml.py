from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_release_workflow_yaml.py"


def _write_workflow(path: Path, *, extra: str = "") -> None:
    path.write_text(
        """
name: Release Bundle Draft

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
      - run: scripts/validate_release_bundle.sh "release/${RELEASE_VERSION}"
      - uses: actions/upload-artifact@v4
        with:
          name: release-${{ env.RELEASE_VERSION }}
          path: release/${{ env.RELEASE_VERSION }}/
"""
        + extra,
        encoding="utf-8",
    )


def test_validate_release_workflow_yaml_passes_for_valid_file(tmp_path: Path) -> None:
    workflow = tmp_path / "release.yml"
    _write_workflow(workflow)

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_validate_release_workflow_yaml_uses_default_path_and_fails_when_missing(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        ["python", str(SCRIPT_PATH)],
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert ".github/workflows/release.yml" in output
    assert "not found" in output.lower()


def test_validate_release_workflow_yaml_uses_default_path_when_present(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "release.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    _write_workflow(workflow)

    result = subprocess.run(
        ["python", str(SCRIPT_PATH)],
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("label", "text", "expected_error"),
    [
        (
            "missing_install",
            """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/}
""",
            'python -m pip install -e ".[dev]"',
        ),
        (
            "missing_pyinstaller",
            """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -e ".[dev]"
      - run: pytest tests/
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/}
""",
            "pyinstaller -y release.spec",
        ),
        (
            "bad_upload_path",
            """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -e ".[dev]"
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: dist/}
""",
            "upload-artifact path must include 'release/'",
        ),
        (
            "missing_upload_step",
            """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -e ".[dev]"
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
""",
            "missing actions/upload-artifact step",
        ),
    ],
)
def test_validate_release_workflow_yaml_fails_for_missing_requirements(
    label: str, text: str, expected_error: str, tmp_path: Path
) -> None:
    workflow = tmp_path / f"{label}.yml"
    workflow.write_text(text, encoding="utf-8")

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert expected_error in output


def test_validate_release_workflow_yaml_rejects_required_version_input(tmp_path: Path) -> None:
    workflow = tmp_path / "required-version.yml"
    workflow.write_text(
        """
name: x
on:
  workflow_dispatch:
    inputs:
      version:
        required: true
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -e ".[dev]"
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "must not set required: true" in output
