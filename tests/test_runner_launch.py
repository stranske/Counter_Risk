"""Unit tests for runner launch helpers used to mirror VBA behavior."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from counter_risk.runner_launch import (
    RunnerMode,
    build_command,
    build_discovery_dry_run_command,
    build_discovery_run_command,
    build_runner_settings_payload,
    data_quality_status_label,
    format_launch_error_for_runner,
    map_runner_error_to_operator_message,
    open_data_quality_summary,
    open_manifest,
    open_output_folder,
    open_ppt_output_folder,
    read_overall_status_color,
    resolve_data_quality_summary_path,
    resolve_manifest_path,
    resolve_output_dir,
    resolve_output_root,
    resolve_ppt_output_dir,
    resolve_settings_path,
    write_runner_settings_file,
)


@pytest.fixture
def filesystem_and_explorer_stubs() -> (
    tuple[set[str], list[str], Callable[[str], bool], Callable[[str], int]]
):
    existing_directories: set[str] = set()
    opened_directories: list[str] = []

    def directory_exists(path: str) -> bool:
        return path in existing_directories

    def open_directory(path: str) -> int:
        opened_directories.append(path)
        return 0

    return existing_directories, opened_directories, directory_exists, open_directory


@pytest.mark.parametrize(
    ("selected_date", "expected_dir_date"),
    [
        ("2025-01-31", "2025-01-31"),
        ("2025-02-28", "2025-02-28"),
    ],
)
def test_build_command_all_mode_for_distinct_dates(
    selected_date: str, expected_dir_date: str
) -> None:
    output_dir = resolve_output_dir("C:/repo", selected_date)

    command = build_command(RunnerMode.ALL, selected_date, output_dir)

    assert '--config "config\\all_programs.yml"' in command
    assert f'--as-of-date "{expected_dir_date}"' in command
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}_000000"' in command
    assert '--settings "' in command


@pytest.mark.parametrize(
    ("selected_date", "expected_dir_date"),
    [
        ("2024-11-30", "2024-11-30"),
        ("2024-12-31", "2024-12-31"),
    ],
)
def test_build_command_ex_trend_mode_for_distinct_dates(
    selected_date: str, expected_dir_date: str
) -> None:
    output_dir = resolve_output_dir("C:/repo", selected_date)

    command = build_command(RunnerMode.EX_TREND, selected_date, output_dir)

    assert '--config "config\\ex_trend.yml"' in command
    assert f'--as-of-date "{expected_dir_date}"' in command
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}_000000"' in command
    assert '--settings "' in command


@pytest.mark.parametrize(
    ("selected_date", "expected_dir_date"),
    [
        ("2026-03-31", "2026-03-31"),
        ("2026-04-30", "2026-04-30"),
    ],
)
def test_build_command_trend_mode_for_distinct_dates(
    selected_date: str, expected_dir_date: str
) -> None:
    output_dir = resolve_output_dir("C:/repo", selected_date)

    command = build_command(RunnerMode.TREND, selected_date, output_dir)

    assert '--config "config\\trend.yml"' in command
    assert f'--as-of-date "{expected_dir_date}"' in command
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}_000000"' in command
    assert '--settings "' in command


def test_open_output_folder_returns_missing_directory_error_without_open_call(
    filesystem_and_explorer_stubs: tuple[
        set[str], list[str], Callable[[str], bool], Callable[[str], int]
    ],
) -> None:
    _, opened_directories, directory_exists, open_directory = filesystem_and_explorer_stubs

    status = open_output_folder(
        repo_root="C:/repo",
        selected_date="2025-05-31",
        directory_exists=directory_exists,
        open_directory=open_directory,
    )

    assert status.success is False
    assert "Directory not found" in status.message
    assert "C:\\repo\\runs\\2025-05-31_000000" in status.message
    assert opened_directories == []


def test_open_output_folder_uses_stubbed_explorer_for_existing_directory(
    filesystem_and_explorer_stubs: tuple[
        set[str], list[str], Callable[[str], bool], Callable[[str], int]
    ],
) -> None:
    existing_directories, opened_directories, directory_exists, open_directory = (
        filesystem_and_explorer_stubs
    )
    resolved_path = resolve_output_dir("C:/repo", "2025-06-30")
    existing_directories.add(resolved_path)

    status = open_output_folder(
        repo_root="C:/repo",
        selected_date="2025-06-30",
        directory_exists=directory_exists,
        open_directory=open_directory,
    )

    assert status.success is True
    assert status.message == "Success"
    assert opened_directories == [resolved_path]


def test_open_data_quality_summary_returns_missing_file_error_without_open_call() -> None:
    opened_files: list[str] = []
    summary_path = resolve_data_quality_summary_path("C:/repo", "2025-06-30")

    def open_file(path: str) -> int:
        opened_files.append(path)
        return 0

    status = open_data_quality_summary(
        repo_root="C:/repo",
        selected_date="2025-06-30",
        file_exists=lambda _: False,
        open_file=open_file,
    )

    assert status.success is False
    assert status.error_code == 7102
    assert f"Summary not found: {summary_path}" == status.message
    assert opened_files == []


def test_open_data_quality_summary_opens_existing_file() -> None:
    opened_files: list[str] = []
    summary_path = resolve_data_quality_summary_path("C:/repo", "2025-06-30")

    def open_file(path: str) -> int:
        opened_files.append(path)
        return 0

    status = open_data_quality_summary(
        repo_root="C:/repo",
        selected_date="2025-06-30",
        file_exists=lambda path: path == summary_path,
        open_file=open_file,
    )

    assert status.success is True
    assert status.message == "Success"
    assert opened_files == [summary_path]


def test_open_manifest_returns_missing_file_error_without_open_call() -> None:
    opened_files: list[str] = []
    manifest_path = resolve_manifest_path("C:/repo", "2025-06-30")

    def open_file(path: str) -> int:
        opened_files.append(path)
        return 0

    status = open_manifest(
        repo_root="C:/repo",
        selected_date="2025-06-30",
        file_exists=lambda _: False,
        open_file=open_file,
    )

    assert status.success is False
    assert f"Manifest not found: {manifest_path}" == status.message
    assert status.error_code == 7104
    assert opened_files == []


def test_open_ppt_output_folder_opens_existing_directory() -> None:
    opened_directories: list[str] = []
    ppt_dir = resolve_ppt_output_dir("C:/repo", "2025-06-30")

    def open_directory(path: str) -> int:
        opened_directories.append(path)
        return 0

    status = open_ppt_output_folder(
        repo_root="C:/repo",
        selected_date="2025-06-30",
        directory_exists=lambda path: path == ppt_dir,
        open_directory=open_directory,
    )

    assert status.success is True
    assert status.message == "Success"
    assert opened_directories == [ppt_dir]


def test_resolve_settings_path_uses_temp_root_and_expected_filename() -> None:
    resolved = resolve_settings_path("C:/Temp")
    assert resolved == "C:\\Temp\\counter-risk-runner-settings.json"


def test_resolve_output_root_supports_relative_and_absolute_values() -> None:
    assert resolve_output_root("C:/repo", "runs") == "C:\\repo\\runs"
    assert resolve_output_root("C:/repo", "C:/shared/runs") == "C:\\shared\\runs"
    assert resolve_output_root("C:/repo", "//server/share/runs") == "\\\\server\\share\\runs"


def test_resolve_output_dir_uses_configured_output_root() -> None:
    resolved = resolve_output_dir("C:/repo", "2025-06-30", output_root="C:/shared/runs")
    assert resolved == "C:\\shared\\runs\\2025-06-30_000000"


def test_build_runner_settings_payload_serializes_expected_fields() -> None:
    payload = build_runner_settings_payload(
        input_root="inputs",
        discovery_mode="discover",
        strict_policy="warn",
        formatting_profile="default",
        output_root="runs",
    )
    assert '"input_root": "inputs"' in payload
    assert '"discovery_mode": "discover"' in payload
    assert '"strict_policy": "warn"' in payload
    assert '"formatting_profile": "default"' in payload
    assert '"output_root": "runs"' in payload


def test_write_runner_settings_file_writes_json_payload(tmp_path: Path) -> None:
    target = tmp_path / "counter-risk-runner-settings.json"
    payload = '{"input_root":"inputs"}'
    write_runner_settings_file(payload, str(target))
    assert target.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize(
    ("mode", "expected_config"),
    [
        (RunnerMode.ALL, 'config "config\\all_programs.yml"'),
        (RunnerMode.EX_TREND, 'config "config\\ex_trend.yml"'),
        (RunnerMode.TREND, 'config "config\\trend.yml"'),
    ],
)
def test_build_discovery_dry_run_command_includes_mode_config_and_as_of_date(
    mode: RunnerMode, expected_config: str
) -> None:
    command = build_discovery_dry_run_command(mode, "2025-02-15")

    assert "run --dry-run-discovery" in command
    assert expected_config in command
    assert '--as-of-month "2025-02-28"' in command
    assert '--settings "' in command


@pytest.mark.parametrize(
    ("mode", "expected_config"),
    [
        (RunnerMode.ALL, 'config "config\\all_programs.yml"'),
        (RunnerMode.EX_TREND, 'config "config\\ex_trend.yml"'),
        (RunnerMode.TREND, 'config "config\\trend.yml"'),
    ],
)
def test_build_discovery_run_command_includes_discover_flag_and_output_dir(
    mode: RunnerMode, expected_config: str
) -> None:
    command = build_discovery_run_command(mode, "2025-02-15", "C:\\repo\\runs\\2025-02-28_000000")

    assert "run --discover" in command
    assert expected_config in command
    assert '--as-of-month "2025-02-28"' in command
    assert '--output-dir "C:\\repo\\runs\\2025-02-28_000000"' in command
    assert '--settings "' in command


def test_map_runner_error_to_operator_message_prefers_explicit_operator_action() -> None:
    message = (
        "Pipeline failed during parse stage. "
        "Operator action: update counterparty mappings for this month and rerun. "
        "Unmatched counterparty 'Acme'."
    )

    guidance = map_runner_error_to_operator_message(message)

    assert guidance.startswith("Operator action:")
    assert "counterparty mappings" in guidance


def test_map_runner_error_to_operator_message_maps_missing_input_technical_failure() -> None:
    guidance = map_runner_error_to_operator_message(
        "Pipeline failed during input validation stage: missing required input files."
    )

    assert guidance.startswith("Operator action:")
    assert "required input files" in guidance


def test_map_runner_error_to_operator_message_maps_reconciliation_failure() -> None:
    guidance = map_runner_error_to_operator_message(
        "Reconciliation strict mode failed due to missing/unmapped series; gap_count=3"
    )

    assert guidance.startswith("Operator action:")
    assert "reconcile source totals/class breakdown values" in guidance


def test_format_launch_error_for_runner_includes_error_code_and_guidance() -> None:
    status = open_output_folder(
        repo_root="C:/repo",
        selected_date="2025-05-31",
        directory_exists=lambda _: False,
        open_directory=lambda _: 0,
    )

    rendered = format_launch_error_for_runner(status)

    assert rendered.startswith(f"Error {status.error_code}: Operator action:")
    assert "review the run log details and rerun" in rendered


@pytest.mark.parametrize(
    ("status_text", "expected_color"),
    [
        ("Overall status: INFO (GREEN) - Safe to send.", "GREEN"),
        ("Overall status: WARN (YELLOW) - Review warnings before sending.", "YELLOW"),
        ("Overall status: FAIL (RED) - Do not send until failing checks are resolved.", "RED"),
    ],
)
def test_read_overall_status_color_extracts_color_from_summary(
    tmp_path: Path, status_text: str, expected_color: str
) -> None:
    summary = tmp_path / "DATA_QUALITY_SUMMARY.txt"
    summary.write_text(
        f"Counterparty Risk Data Quality Summary\n\n{status_text}\n",
        encoding="utf-8",
    )

    assert read_overall_status_color(summary) == expected_color


def test_read_overall_status_color_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert read_overall_status_color(tmp_path / "missing.txt") == ""


def test_read_overall_status_color_returns_empty_for_no_status_marker(tmp_path: Path) -> None:
    summary = tmp_path / "DATA_QUALITY_SUMMARY.txt"
    summary.write_text("Some text without a status marker.\n", encoding="utf-8")

    assert read_overall_status_color(summary) == ""


@pytest.mark.parametrize(
    ("color", "expected_label"),
    [
        ("GREEN", "GREEN - Safe to send"),
        ("YELLOW", "YELLOW - Review warnings"),
        ("RED", "RED - Do not send"),
    ],
)
def test_data_quality_status_label_maps_color_to_label(color: str, expected_label: str) -> None:
    assert data_quality_status_label(color) == expected_label


def test_data_quality_status_label_returns_empty_for_unknown_color() -> None:
    assert data_quality_status_label("PURPLE") == ""
    assert data_quality_status_label("") == ""
