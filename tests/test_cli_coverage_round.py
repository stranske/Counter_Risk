"""Focused CLI behavior coverage for coverage-autopilot issue #1214."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pytest

from counter_risk import cli
from counter_risk.config import WorkflowConfig


def test_discovery_reports_gaps_and_applies_explicit_run_overrides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery must retain defaults for gaps while forwarding explicit operator overrides."""

    config_path = tmp_path / "workflow.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "mosers_all_programs_xlsx: all.xlsx",
                "mosers_ex_trend_xlsx: ex.xlsx",
                "mosers_trend_xlsx: trend.xlsx",
                "hist_all_programs_3yr_xlsx: hist-all.xlsx",
                "hist_ex_llc_3yr_xlsx: hist-ex.xlsx",
                "hist_llc_3yr_xlsx: hist-trend.xlsx",
                "monthly_pptx: report.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = cli.load_config(config_path)

    class Match:
        def __init__(self, path: Path) -> None:
            self.path = path

    class DiscoveryResult:
        matches_by_input = {
            "missing_input": [],
            "one_match": [Match(tmp_path / "single.xlsx")],
            "many_matches": [Match(tmp_path / "first.xlsx"), Match(tmp_path / "second.xlsx")],
        }

    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "_load_config_with_runner_settings", lambda *_: config)
    monkeypatch.setattr(
        cli, "discover_workflow_inputs", lambda *_args, **_kwargs: DiscoveryResult()
    )
    monkeypatch.setattr(
        cli,
        "resolve_discovery_selections",
        lambda _result: {"mosers_all_programs_xlsx": tmp_path / "selected.xlsx"},
    )

    def fake_run_pipeline_with_config(runtime_config: WorkflowConfig, **kwargs: object) -> Path:
        captured["config"] = runtime_config
        captured["kwargs"] = kwargs
        return tmp_path / "output"

    monkeypatch.setattr(cli, "run_pipeline_with_config", fake_run_pipeline_with_config)
    args = argparse.Namespace(
        config=config_path,
        as_of_date=None,
        strict_policy="strict",
        export_pdf=True,
        formatting_profile="accounting",
        output_dir=tmp_path / "output",
        report_date_override="confirmed-source-date",
        runner_settings={},
    )

    assert cli._run_with_discovery(args) == 0

    runtime_config = captured["config"]
    assert isinstance(runtime_config, WorkflowConfig)
    assert runtime_config.mosers_all_programs_xlsx == tmp_path / "selected.xlsx"
    assert runtime_config.reconciliation.fail_policy == "strict"
    assert runtime_config.export_pdf is True
    assert captured["kwargs"] == {
        "config_dir": tmp_path,
        "output_dir": tmp_path / "output",
        "formatting_profile": "accounting",
        "report_date_override": "confirmed-source-date",
    }
    output = capsys.readouterr().out
    assert "missing_input: no matches found" in output
    assert "many_matches: 2 matches (selection required)" in output
    assert "Proceeding with config defaults" in output
    assert "selected profile: accounting" in output


def test_gui_non_headless_launches_with_a_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The interactive GUI path must launch rather than silently returning."""

    captured: dict[str, object] = {}

    def fake_launch_gui(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("counter_risk.gui.runner.launch_gui", fake_launch_gui)

    args = argparse.Namespace(
        as_of_date="2025-12-31",
        mode="trend",
        discovery_mode="discover",
        strict_policy="strict",
        formatting_profile="plain",
        input_root="inputs",
        output_root="runs",
        config=Path("workflow.yml"),
        headless=False,
    )

    assert cli._gui_command(args) == 0
    state = captured["initial_state"]
    assert state.run_mode == "trend"
    assert state.discovery_mode == "discover"
    assert captured["runner"]([]) == 0


def test_runner_settings_helpers_reject_non_object_and_prefer_cli_values(tmp_path: Path) -> None:
    """Settings files are a narrow override channel; explicit CLI values win."""

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        cli._load_runner_settings(settings_path)

    args = argparse.Namespace(strict_policy="warn", formatting_profile="currency")
    settings = {"strict_policy": "strict", "formatting_profile": "accounting"}
    assert cli._effective_strict_policy(args, settings) == "warn"
    assert cli._effective_formatting_profile(args, settings) == "currency"
    config = WorkflowConfig(
        as_of_date="2025-12-31",
        hist_all_programs_3yr_xlsx=tmp_path / "hist-all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist-ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist-trend.xlsx",
        monthly_pptx=tmp_path / "report.pptx",
    )
    assert cli._resolve_discovery_as_of_date(config=config, as_of_date="2026-01-31") == date(
        2026, 1, 31
    )
