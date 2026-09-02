"""Properties of the downloadable, fixture-only demo artifact."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

import counter_risk.demo_artifact as demo_artifact


def _assert_no_absolute_paths(value: object) -> None:
    if isinstance(value, str):
        assert not Path(value).is_absolute()
    elif isinstance(value, list):
        for item in value:
            _assert_no_absolute_paths(item)
    elif isinstance(value, dict):
        for item in value.values():
            _assert_no_absolute_paths(item)


def test_build_demo_artifact_is_self_contained_fixture_only_and_offline(tmp_path: Path) -> None:
    """A public download must be portable and disclose its synthetic, no-egress boundary."""

    config_path = Path("config/fixture_replay.yml")
    run_dir = demo_artifact.build_demo_artifact(
        config_path=config_path,
        output_dir=tmp_path / "artifact",
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_zone"] == "synthetic-fixtures-only"
    assert manifest["chat_offline_mode"] == "1"
    assert manifest["data_quality_summary"] == "DATA_QUALITY_SUMMARY.txt"
    assert os.environ["COUNTER_RISK_CHAT_OFFLINE_MODE"] == "1"
    _assert_no_absolute_paths(manifest)

    expected_outputs = {
        "mosers_all_programs_xlsx",
        "mosers_ex_trend_xlsx",
        "mosers_trend_xlsx",
        "hist_all_programs_3yr_xlsx",
        "hist_ex_llc_3yr_xlsx",
        "hist_llc_3yr_xlsx",
        "monthly_pptx",
    }
    assert set(manifest["outputs"]) == expected_outputs
    for output_path in manifest["outputs"].values():
        assert (run_dir / output_path).is_file()

    summary = (run_dir / "DATA_QUALITY_SUMMARY.txt").read_text(encoding="utf-8")
    assert "bundled tests/fixtures only" in summary
    assert "COUNTER_RISK_CHAT_OFFLINE_MODE=1" in summary
    assert "Config: config/fixture_replay.yml" in summary
    assert str(config_path.resolve()) not in summary


def test_build_demo_artifact_rejects_non_fixture_input_before_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The upload boundary must reject proprietary inputs before any artifact is generated."""

    raw_config = yaml.safe_load(Path("config/fixture_replay.yml").read_text(encoding="utf-8"))
    assert isinstance(raw_config, dict)
    raw_config["cash_source_path"] = str(tmp_path / "proprietary_cash_source.csv")
    config_path = tmp_path / "unsafe_demo.yml"
    config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")

    def fail_if_replay_starts(**_kwargs: object) -> Path:
        pytest.fail("fixture replay started before validating source containment")

    monkeypatch.setattr(demo_artifact, "run_fixture_replay", fail_if_replay_starts)

    with pytest.raises(ValueError, match="cash_source_path.*tests/fixtures"):
        demo_artifact.build_demo_artifact(
            config_path=config_path,
            output_dir=tmp_path / "artifact",
        )


def test_normalize_manifest_paths_preserves_structure_without_host_paths(tmp_path: Path) -> None:
    """Nested metadata must not expose checkout, run-directory, or unrelated host paths."""

    run_dir = tmp_path / "artifact"
    run_dir.mkdir()
    run_output = run_dir / "generated" / "report.xlsx"
    fixture_source = Path("tests/fixtures/daily_holdings_sample_1.pdf").resolve()
    repo_config = Path("config/fixture_replay.yml").resolve()
    outside_source = tmp_path.parent / "private-inputs" / "positions.csv"
    manifest = {
        "run_output": str(run_output),
        "sources": [
            str(fixture_source),
            str(repo_config),
            str(outside_source),
            "already/relative.csv",
        ],
        "metadata": {"count": 7, "optional": None},
    }

    normalized = demo_artifact._normalize_manifest_paths(manifest, run_dir=run_dir)

    assert normalized == {
        "run_output": "generated/report.xlsx",
        "sources": [
            "tests/fixtures/daily_holdings_sample_1.pdf",
            "config/fixture_replay.yml",
            "positions.csv",
            "already/relative.csv",
        ],
        "metadata": {"count": 7, "optional": None},
    }
