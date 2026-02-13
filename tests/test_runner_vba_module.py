"""Validation for Runner VBA launch module source."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


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


def test_runner_vba_module_defines_public_entrypoints() -> None:
    module_source = Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")

    assert "Public Sub RunAll_Click()" in module_source
    assert "Public Sub RunExTrend_Click()" in module_source
    assert "Public Sub RunTrend_Click()" in module_source
    assert "Public Sub OpenOutputFolder_Click()" in module_source


def test_runner_workbook_embeds_runnerlaunch_entrypoints_in_vba_project() -> None:
    with ZipFile("Runner.xlsm") as zip_file:
        with zip_file.open("xl/vbaProject.bin") as handle:
            vba_project = handle.read().decode("latin-1", errors="ignore")

    assert "Attribute VB_Name = \"RunnerLaunch\"" in vba_project
    assert "Public Sub RunAll_Click()" in vba_project
    assert "Public Sub RunExTrend_Click()" in vba_project
    assert "Public Sub RunTrend_Click()" in vba_project
    assert "Public Sub OpenOutputFolder_Click()" in vba_project
