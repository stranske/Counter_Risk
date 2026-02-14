"""Validation for Runner VBA launch module source."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


def _module_source() -> str:
    return Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")


def test_runner_vba_module_constructs_arguments_from_date_and_mode() -> None:
    module_source = _module_source()

    assert "Public Function BuildRunArguments" in module_source
    assert "BuildCommandArguments(ModeToString(mode), parsedDate, outputDir)" in module_source

    assert "Public Function ResolveOutputDir" in module_source
    assert 'ResolveOutputDir = NormalizePathSeparators(repoRoot) & "\\runs\\"' in module_source
    assert 'Format$(parsedDate, "yyyy-mm-dd")' in module_source
    assert '" --as-of-month " & QuoteArg(Format$(parsedDate, "yyyy-mm-dd"))' in module_source

    assert "Case RunnerModeAllPrograms" in module_source
    assert 'ResolveConfigPath = "config\\all_programs.yml"' in module_source
    assert "Case RunnerModeExTrend" in module_source
    assert 'ResolveConfigPath = "config\\ex_trend.yml"' in module_source
    assert "Case RunnerModeTrend" in module_source
    assert 'ResolveConfigPath = "config\\trend.yml"' in module_source


def test_runner_vba_module_defines_structured_launch_status_and_execution() -> None:
    module_source = _module_source()

    assert "Public Type LaunchStatus" in module_source
    assert "Success As Boolean" in module_source
    assert "ErrorCode As Long" in module_source
    assert "Message As String" in module_source
    assert "Command As String" in module_source
    assert "ExitCode As Long" in module_source

    assert "Public Function BuildCommand" in module_source
    assert "On Error GoTo BuildCommandError" in module_source
    assert 'Set shellObject = CreateObject("WScript.Shell")' in module_source
    assert "shellObject.Run(shellCommand, 0, True)" in module_source
    assert 'WriteStatus "Error"' in module_source


def test_runner_vba_module_uses_single_shared_builder_for_all_run_modes() -> None:
    module_source = _module_source()

    assert "Public Sub RunAll_Click()" in module_source
    assert 'RunModeClick "All"' in module_source
    assert "Public Sub RunExTrend_Click()" in module_source
    assert 'RunModeClick "ExTrend"' in module_source
    assert "Public Sub RunTrend_Click()" in module_source
    assert 'RunModeClick "Trend"' in module_source

    assert "Private Sub RunModeClick" in module_source
    assert "command = BuildCommand(runMode, selectedDate, outputDir)" in module_source


def test_runner_vba_module_updates_status_before_launch_and_writes_error_result() -> None:
    module_source = _module_source()

    assert 'WriteStatus "Running..."' in module_source
    assert 'WriteStatus "Success"' in module_source
    assert 'WriteStatus "Error"' in module_source
    assert 'WriteResult "Error " & CStr(Err.Number) & ": " & Err.Description' in module_source


def test_runner_vba_open_output_folder_checks_directory_and_reports_missing_path() -> None:
    module_source = _module_source()

    assert "Public Sub OpenOutputFolder_Click()" in module_source
    assert "resolvedPath = ResolveOutputDir(ResolveRepoRoot(), selectedDate)" in module_source
    assert 'If Dir$(resolvedPath, vbDirectory) = "" Then' in module_source
    assert 'Set fileSystem = CreateObject("Scripting.FileSystemObject")' in module_source
    assert "fileSystem.FolderExists(resolvedPath)" in module_source
    assert 'MsgBox "Directory not found" & resolvedPath' in module_source
    assert 'MsgBox "Directory not found: " & resolvedPath' not in module_source
    assert 'MsgBox "Directory not found - " & resolvedPath' not in module_source
    assert "status = OpenDirectory(resolvedPath)" in module_source


def test_runner_vba_module_has_stub_friendly_shell_and_filesystem_boundaries() -> None:
    module_source = _module_source()

    assert "Private Function ExecuteShellCommand" in module_source
    assert 'CreateObject("WScript.Shell")' in module_source
    assert "Private Function OpenDirectory" in module_source
    assert "Private Function DirectoryExists" in module_source
    assert "Dir$(directoryPath, vbDirectory)" in module_source


def test_runner_vba_module_defines_public_entrypoints() -> None:
    module_source = Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")

    assert "Public Sub RunAll_Click()" in module_source
    assert "Public Sub RunExTrend_Click()" in module_source
    assert "Public Sub RunTrend_Click()" in module_source
    assert "Public Sub OpenOutputFolder_Click()" in module_source


def test_runner_vba_run_all_reads_selected_date_and_calls_shared_builder() -> None:
    module_source = _module_source()

    assert "Public Sub RunAll_Click()" in module_source
    assert 'RunModeClick "All"' in module_source


def test_runner_vba_run_ex_trend_reads_selected_date_and_calls_shared_builder() -> None:
    module_source = _module_source()

    assert "Public Sub RunExTrend_Click()" in module_source
    assert 'RunModeClick "ExTrend"' in module_source


def test_runner_vba_run_trend_reads_selected_date_and_calls_shared_builder() -> None:
    module_source = _module_source()

    assert "Public Sub RunTrend_Click()" in module_source
    assert 'RunModeClick "Trend"' in module_source


def test_runner_workbook_embeds_runnerlaunch_entrypoints_in_vba_project() -> None:
    with ZipFile("Runner.xlsm") as zip_file, zip_file.open("xl/vbaProject.bin") as handle:
        vba_project = handle.read().decode("latin-1", errors="ignore")

    assert 'Attribute VB_Name = "RunnerLaunch"' in vba_project
    assert "Public Sub RunAll_Click()" in vba_project
    assert "Public Sub RunExTrend_Click()" in vba_project
    assert "Public Sub RunTrend_Click()" in vba_project
    assert "Public Sub OpenOutputFolder_Click()" in vba_project
