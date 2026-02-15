from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_release_workflow_yaml.py"

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("yaml") is None,
    reason="PyYAML required for release workflow validator tests",
)


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
        with:
          python-version: "3.11"
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release --version-file VERSION --output-dir release --force
      - run: scripts/validate_release_bundle.sh "release/${RELEASE_VERSION}"
      - uses: actions/upload-artifact@v4
        with:
          name: release-${{ env.RELEASE_VERSION }}
          path: release/${{ env.RELEASE_VERSION }}/
          retention-days: 7
""" + extra,
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
            "pip install -r requirements.txt",
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
        with: {python-version: "3.11"}
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/, retention-days: 14}
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
        with: {python-version: "3.11"}
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: dist/, retention-days: 14}
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
        with: {python-version: "3.11"}
      - run: python -m pip install -r requirements.txt
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
        with:
          python-version: "3.11"
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/, retention-days: 14}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "must not set required: true" in output


def test_validate_release_workflow_yaml_rejects_old_action_versions(tmp_path: Path) -> None:
    workflow = tmp_path / "old-actions.yml"
    workflow.write_text(
        """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v3
        with: {python-version: "3.11"}
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v2
        with: {path: release/1.2.3/, retention-days: 14}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "actions/checkout must be v3 or later" in output
    assert "actions/setup-python must be v4 or later" in output
    assert "actions/upload-artifact must be v3 or later" in output


def test_validate_release_workflow_yaml_rejects_python_below_floor(tmp_path: Path) -> None:
    workflow = tmp_path / "python-floor.yml"
    workflow.write_text(
        """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.7"}
      - run: python -m pip install -r requirements.txt
      - run: pytest tests/
      - run: pyinstaller -y release.spec
      - run: python -m counter_risk.build.release
      - run: scripts/validate_release_bundle.sh release/1.2.3
      - uses: actions/upload-artifact@v4
        with: {path: release/1.2.3/, retention-days: 14}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python", str(SCRIPT_PATH), str(workflow)], text=True, capture_output=True, check=False
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "python-version must be 3.8 or later" in output


def test_validate_release_workflow_yaml_requires_upload_retention_days(tmp_path: Path) -> None:
    workflow = tmp_path / "retention.yml"
    workflow.write_text(
        """
name: x
on: {workflow_dispatch: null}
jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: python -m pip install -r requirements.txt
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
    assert "must set retention-days" in output
