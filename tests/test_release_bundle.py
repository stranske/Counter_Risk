"""Tests for release bundle assembly helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from counter_risk.build import release


def _write_fake_repo(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "fixtures").mkdir(parents=True, exist_ok=True)
    (root / "release.spec").write_text("# fake\n", encoding="utf-8")
    (root / "config" / "fixture_replay.yml").write_text("name: fixture\n", encoding="utf-8")
    (root / "templates" / "Monthly Counterparty Exposure Report.pptx").write_bytes(b"ppt-template")
    (root / "tests" / "fixtures" / "fixture.xlsx").write_bytes(b"xlsx")
    (root / "tests" / "fixtures" / "fixture.pptx").write_bytes(b"fixture-ppt")


def _create_fake_built_executable(root: Path, executable_name: str) -> Path:
    executable_path = root / "dist" / "counter-risk" / executable_name
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_bytes(b"fake-binary")
    return executable_path


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


def test_assemble_release_creates_versioned_bundle_with_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    output_dir = tmp_path / "release"

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)

    def _fake_run_pyinstaller(root: Path, spec_path: Path) -> None:
        assert root == repo_root
        assert spec_path == repo_root / "release.spec"
        _create_fake_built_executable(root, release._executable_filename(for_windows=False))

    monkeypatch.setattr(release, "_run_pyinstaller", _fake_run_pyinstaller)

    bundle_dir = release.assemble_release("9.9.9", output_dir)

    assert bundle_dir == output_dir / "9.9.9"
    assert (bundle_dir / "VERSION").read_text(encoding="utf-8").strip() == "9.9.9"
    assert (bundle_dir / "config" / "fixture_replay.yml").is_file()
    assert list((bundle_dir / "templates").glob("*.pptx"))
    assert list((bundle_dir / "fixtures").glob("*.xlsx"))
    assert (bundle_dir / "bin" / "counter-risk").is_file()
    runner_text = (bundle_dir / "run_counter_risk.cmd").read_text(encoding="utf-8")
    assert "python" not in runner_text.lower()
    assert "%~dp0" in runner_text
    assert "%*" in runner_text
    assert (bundle_dir / "README_HOW_TO_RUN.md").is_file()
    assert "How to run" in (bundle_dir / "README_HOW_TO_RUN.md").read_text(encoding="utf-8")

    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "9.9.9"
    assert manifest["release_name"] == "9.9.9"
    assert manifest["artifacts"]["executable"] == ["bin/counter-risk"]


def test_assemble_release_requires_force_for_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    output_dir = tmp_path / "release"

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)
    monkeypatch.setattr(
        release,
        "_run_pyinstaller",
        lambda root, spec_path: _create_fake_built_executable(
            root, release._executable_filename(for_windows=False)
        ),
    )

    release.assemble_release("1.0.0", output_dir)

    with pytest.raises(ValueError, match="already exists"):
        release.assemble_release("1.0.0", output_dir)


def test_main_accepts_version_and_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    output_dir = tmp_path / "release"

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)
    monkeypatch.setattr(
        release,
        "_run_pyinstaller",
        lambda root, spec_path: _create_fake_built_executable(
            root, release._executable_filename(for_windows=False)
        ),
    )

    result = release.main(["--version", "3.4.5", "--output-dir", str(output_dir)])
    captured = capsys.readouterr()

    assert result == 0
    assert "Release bundle created at:" in captured.out
    assert (output_dir / "3.4.5" / "manifest.json").is_file()


def test_run_release_uses_version_file_when_override_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    output_dir = tmp_path / "release"
    version_file = tmp_path / "VERSION"
    version_file.write_text("8.8.8\n", encoding="utf-8")

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)
    monkeypatch.setattr(
        release,
        "_run_pyinstaller",
        lambda root, spec_path: _create_fake_built_executable(
            root, release._executable_filename(for_windows=False)
        ),
    )

    bundle_dir = release.run_release(version_file=version_file, output_dir=output_dir)

    assert bundle_dir == output_dir / "8.8.8"
    assert (bundle_dir / "VERSION").read_text(encoding="utf-8").strip() == "8.8.8"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "8.8.8"


def test_assemble_release_fails_fast_when_release_spec_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    (repo_root / "release.spec").unlink()
    output_dir = tmp_path / "release"

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)

    with pytest.raises(ValueError, match="Missing required PyInstaller spec file"):
        release.assemble_release("1.2.3", output_dir)


def test_assemble_release_fails_when_pyinstaller_output_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    _write_fake_repo(repo_root)
    output_dir = tmp_path / "release"

    monkeypatch.setattr(release, "repository_root", lambda: repo_root)
    monkeypatch.setattr(release, "_run_pyinstaller", lambda root, spec_path: None)

    with pytest.raises(ValueError, match="expected executable was not found"):
        release.assemble_release("2.3.4", output_dir)


def test_run_pyinstaller_raises_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    spec_path = repo_root / "release.spec"
    spec_path.write_text("# fake\n", encoding="utf-8")

    def _failed_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["pyinstaller", "-y", str(spec_path)],
            returncode=2,
            stdout="build log",
            stderr="error log",
        )

    monkeypatch.setattr(subprocess, "run", _failed_run)

    with pytest.raises(ValueError, match="PyInstaller failed with exit code 2"):
        release._run_pyinstaller(repo_root, spec_path)


def test_validate_version_manifest_consistency_raises_on_mismatch(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"version": "9.9.9"}, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Release metadata mismatch"):
        release._validate_version_manifest_consistency(bundle_dir)
