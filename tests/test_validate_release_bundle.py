from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_release_bundle.sh"


def _write_release_artifacts(
    bundle_dir: Path, *, include_unix_binary: bool = True, include_windows_binary: bool = True
) -> None:
    (bundle_dir / "config").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "templates").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "bin").mkdir(parents=True, exist_ok=True)

    (bundle_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (bundle_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (bundle_dir / "config" / "fixture_replay.yml").write_text("name: fixture\n", encoding="utf-8")
    (bundle_dir / "run_counter_risk.cmd").write_text("@echo off\n", encoding="utf-8")
    (bundle_dir / "README_HOW_TO_RUN.md").write_text("# How to run\n", encoding="utf-8")

    if include_unix_binary:
        (bundle_dir / "bin" / "counter-risk").write_text("binary\n", encoding="utf-8")
    if include_windows_binary:
        (bundle_dir / "bin" / "counter-risk.exe").write_text("binary\n", encoding="utf-8")


def _make_test_env(
    tmp_path: Path,
    *,
    uname_output: str = "Linux",
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = tmp_path / "test-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    gh_path = bin_dir / "gh"
    gh_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    gh_path.chmod(0o755)

    uname_path = bin_dir / "uname"
    uname_path.write_text(f"#!/usr/bin/env bash\necho '{uname_output}'\n", encoding="utf-8")
    uname_path.chmod(0o755)

    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)
    return env


@pytest.fixture
def complete_bundle_dir(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "release" / "1.2.3"
    _write_release_artifacts(bundle_dir)
    return bundle_dir


@pytest.fixture
def missing_one_artifact_bundle_dir(tmp_path: Path) -> tuple[Path, str]:
    bundle_dir = tmp_path / "release" / "1.2.3"
    _write_release_artifacts(bundle_dir)
    missing_artifact = "manifest.json"
    (bundle_dir / missing_artifact).unlink()
    return bundle_dir, missing_artifact


def test_validate_bundle_success(complete_bundle_dir: Path, tmp_path: Path) -> None:
    env = _make_test_env(tmp_path)

    result = subprocess.run(
        [str(SCRIPT_PATH), str(complete_bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr


def test_validate_bundle_missing_artifact(
    missing_one_artifact_bundle_dir: tuple[Path, str], tmp_path: Path
) -> None:
    bundle_dir, missing_artifact = missing_one_artifact_bundle_dir
    env = _make_test_env(tmp_path)

    result = subprocess.run(
        [str(SCRIPT_PATH), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    combined_output = f"{result.stdout}\n{result.stderr}".lower()

    assert result.returncode != 0
    assert (
        missing_artifact in combined_output
        or f"/{missing_artifact}" in combined_output
        or "missing" in combined_output
    )


@pytest.mark.parametrize(
    ("extra_env", "expect_success"),
    [
        ({"OS": "Windows_NT"}, True),
        ({"MSYSTEM": "MINGW64"}, True),
        ({"CYGWIN": "nodosfilewarning"}, True),
        ({"MINGW": "1"}, True),
        ({"OSTYPE": "msys"}, True),
        ({"WSL_DISTRO_NAME": "Ubuntu"}, False),
    ],
)
def test_windows_detection_env_signals(
    extra_env: dict[str, str], expect_success: bool, tmp_path: Path
) -> None:
    bundle_dir = tmp_path / "release" / "1.2.3"
    _write_release_artifacts(bundle_dir, include_unix_binary=False, include_windows_binary=True)
    env = _make_test_env(tmp_path, uname_output="Linux", extra_env=extra_env)

    result = subprocess.run(
        [str(SCRIPT_PATH), str(bundle_dir)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    if expect_success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        combined_output = f"{result.stdout}\n{result.stderr}"
        assert "counter-risk" in combined_output
