"""Targeted manifest PPT-entry tests for acceptance selectors."""

from __future__ import annotations

from pathlib import Path

from counter_risk.pipeline.manifest_schema import validate_manifest_ppt_outputs


def test_manifest_ppt_disabled_has_no_entries_and_validation_passes() -> None:
    manifest = {
        "as_of_date": "2025-12-31",
        "run_date": "2026-01-02",
    }

    is_valid, error = validate_manifest_ppt_outputs(manifest, ppt_enabled=False)

    assert is_valid is True
    assert error is None
    assert "ppt_outputs" not in manifest


def test_manifest_ppt_enabled_contains_both_outputs_with_existing_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    master = run_dir / "Monthly Counterparty Exposure Report (Master) - 2025-12-31.pptx"
    distribution = run_dir / "Monthly Counterparty Exposure Report - 2025-12-31.pptx"
    master.write_bytes(b"master")
    distribution.write_bytes(b"distribution")

    manifest = {
        "as_of_date": "2025-12-31",
        "run_date": "2026-01-02",
        "ppt_outputs": {
            "master": {"path": str(master.resolve())},
            "distribution": {"path": str(distribution.resolve())},
        },
    }

    is_valid, error = validate_manifest_ppt_outputs(manifest, ppt_enabled=True)

    assert is_valid is True
    assert error is None
    assert Path(manifest["ppt_outputs"]["master"]["path"]).exists()
    assert Path(manifest["ppt_outputs"]["distribution"]["path"]).exists()
