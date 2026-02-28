"""Unit tests for the Tkinter runner orchestration helpers."""

from __future__ import annotations

import json
from pathlib import Path

from counter_risk.gui.runner import GuiRunState, execute_gui_run


def test_execute_gui_run_builds_run_args_and_writes_settings(tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        return 0

    state = GuiRunState(
        as_of_date="2025-12-31",
        run_mode="ex_trend",
        discovery_mode="manual",
        strict_policy="strict",
        formatting_profile="accounting",
        input_root="shared-inputs",
        output_root=str(tmp_path / "runs"),
    )
    result = execute_gui_run(state=state, runner=fake_runner, temp_dir=tmp_path)

    assert result.exit_code == 0
    assert result.output_dir == Path(tmp_path / "runs" / "2025-12-31_000000")
    assert result.settings_path == tmp_path / "counter-risk-runner-settings.json"
    assert result.settings_path.is_file()
    settings_payload = json.loads(result.settings_path.read_text(encoding="utf-8"))
    assert settings_payload["strict_policy"] == "strict"
    assert settings_payload["formatting_profile"] == "accounting"
    assert settings_payload["input_root"] == "shared-inputs"
    assert settings_payload["output_root"] == str(tmp_path / "runs")

    assert captured["argv"] == list(result.cli_args)
    assert captured["argv"][0] == "run"
    assert captured["argv"][2] == "config/ex_trend.yml"
    assert "--as-of-date" in captured["argv"]
    assert "--output-dir" in captured["argv"]
    assert "--settings" in captured["argv"]
    assert "--strict-policy" in captured["argv"]


def test_execute_gui_run_supports_discovery_and_dry_run(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_runner(argv: list[str]) -> int:
        captured.append(argv)
        return 0

    discover_state = GuiRunState(
        as_of_date="2025-11-15",
        run_mode="all",
        discovery_mode="discover",
        output_root=str(tmp_path / "runs"),
    )
    discover_result = execute_gui_run(state=discover_state, runner=fake_runner, temp_dir=tmp_path)

    assert discover_result.exit_code == 0
    assert "--discover" in discover_result.cli_args
    assert "--as-of-month" in discover_result.cli_args
    assert "--dry-run-discovery" not in discover_result.cli_args

    dry_run_result = execute_gui_run(
        state=discover_state,
        runner=fake_runner,
        dry_run_discovery=True,
        temp_dir=tmp_path,
    )
    assert dry_run_result.exit_code == 0
    assert "--dry-run-discovery" in dry_run_result.cli_args
    assert "--discover" not in dry_run_result.cli_args
    assert dry_run_result.output_dir is None


def test_execute_gui_run_validates_dates_before_runner_call(tmp_path: Path) -> None:
    calls = 0

    def fake_runner(_argv: list[str]) -> int:
        nonlocal calls
        calls += 1
        return 0

    bad_state = GuiRunState(as_of_date="not-a-date")

    try:
        execute_gui_run(state=bad_state, runner=fake_runner, temp_dir=tmp_path)
    except ValueError:
        pass
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected ValueError for invalid date input.")

    assert calls == 0
