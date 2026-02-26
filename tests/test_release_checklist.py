"""Validation tests for release checklist documentation."""

from __future__ import annotations

from pathlib import Path


def test_release_checklist_exists_with_required_commands_and_bundle_contents() -> None:
    checklist_path = Path(__file__).resolve().parents[1] / "docs" / "RELEASE_CHECKLIST.md"
    assert checklist_path.is_file()

    contents = checklist_path.read_text(encoding="utf-8")

    assert "pyinstaller -y release.spec" in contents
    assert "python -m counter_risk.build.release" in contents
    assert "gh workflow run release.yml" in contents

    assert "run_counter_risk.cmd" in contents
    assert "templates/" in contents
    assert "config/fixture_replay.yml" in contents
    assert "VERSION" in contents
    assert "manifest.json" in contents
    assert "bin/counter-risk" in contents
    assert "runner_xlsm_macro_manual_verification.md" in contents
    assert "Manual Macro/Button Check" in contents
    assert "Version Bump Regression Check" in contents
    assert "--version 1.2.4" in contents
