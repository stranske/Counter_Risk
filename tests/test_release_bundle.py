"""Tests for release bundle assembly helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from counter_risk.build import release


def test_read_version_prefers_override(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.0.1\n", encoding="utf-8")

    resolved = release.read_version(" 1.2.3 ", version_file)

    assert resolved == "1.2.3"


def test_read_version_uses_file(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4\n", encoding="utf-8")

    resolved = release.read_version(None, version_file)

    assert resolved == "2.3.4"


def test_read_version_raises_for_missing_source(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"

    with pytest.raises(ValueError, match="Unable to read VERSION file"):
        release.read_version(None, version_file)


def test_assemble_release_creates_versioned_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"

    bundle_dir = release.assemble_release("9.9.9", output_dir)

    assert bundle_dir == output_dir / "counter-risk-9.9.9"
    assert (bundle_dir / "VERSION").read_text(encoding="utf-8").strip() == "9.9.9"
    assert (bundle_dir / "config").is_dir()
    assert (bundle_dir / "templates").is_dir()
    assert list((bundle_dir / "templates").glob("*.pptx"))
    assert (bundle_dir / "pipeline" / "counter_risk_cli.py").is_file()
    assert (bundle_dir / "pipeline" / "src" / "counter_risk" / "cli.py").is_file()
    assert (bundle_dir / "run_counter_risk.cmd").is_file()
    assert (bundle_dir / "README_HOW_TO_RUN.md").is_file()
    assert "How to run" in (bundle_dir / "README_HOW_TO_RUN.md").read_text(encoding="utf-8")
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "9.9.9"
    assert manifest["release_name"] == "counter-risk-9.9.9"


def test_assemble_release_requires_force_for_existing_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    release.assemble_release("1.0.0", output_dir)

    with pytest.raises(ValueError, match="already exists"):
        release.assemble_release("1.0.0", output_dir)


def test_main_accepts_version_and_output_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "dist"

    result = release.main(["--version", "3.4.5", "--output-dir", str(output_dir)])
    captured = capsys.readouterr()

    assert result == 0
    assert "Release bundle created at:" in captured.out
    assert (output_dir / "counter-risk-3.4.5" / "manifest.json").is_file()


def test_bundled_entrypoint_runs_from_copied_folder(tmp_path: Path) -> None:
    output_dir = tmp_path / "release-output"
    bundle_dir = release.assemble_release("4.5.6", output_dir)
    copied_bundle = tmp_path / "shared-drive" / bundle_dir.name
    shutil.copytree(bundle_dir, copied_bundle)

    process = subprocess.run(
        [sys.executable, "pipeline/counter_risk_cli.py", "run"],
        cwd=copied_bundle,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "not implemented yet" in process.stdout.lower()
