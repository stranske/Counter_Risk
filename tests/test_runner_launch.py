"""Unit tests for runner launch helpers used to mirror VBA behavior."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from counter_risk.runner_launch import (
    RunnerMode,
    build_command,
    open_output_folder,
    resolve_output_dir,
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
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}"' in command


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
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}"' in command


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
    assert f'--output-dir "C:\\repo\\runs\\{expected_dir_date}"' in command


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
    assert "C:\\repo\\runs\\2025-05-31" in status.message
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
