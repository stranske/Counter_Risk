"""Validation for Runner VBA launch module source."""

from __future__ import annotations

from pathlib import Path


def test_runner_vba_module_constructs_arguments_from_date_and_mode() -> None:
    module_source = Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")

    assert "Public Function BuildRunArguments" in module_source
    assert 'Format$(parsedDate, "yyyy-mm-dd")' in module_source
    assert 'QuoteArg("outputs\\" & Format$(parsedDate, "yyyy-mm-dd"))' in module_source

    assert "Case RunnerModeAllPrograms" in module_source
    assert 'ResolveConfigPath = "config\\all_programs.yml"' in module_source

    assert "Case RunnerModeExTrend" in module_source
    assert 'ResolveConfigPath = "config\\ex_trend.yml"' in module_source

    assert "Case RunnerModeTrend" in module_source
    assert 'ResolveConfigPath = "config\\trend.yml"' in module_source
