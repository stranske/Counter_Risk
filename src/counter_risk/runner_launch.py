"""Runner launch helpers mirrored from RunnerLaunch.bas for unit testing.

These helpers keep launch decision logic testable in Python without Excel automation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum

SHELL_ERROR_BASE = 7100


class RunnerMode(str, Enum):
    ALL = "All"
    EX_TREND = "ExTrend"
    TREND = "Trend"


@dataclass(frozen=True)
class LaunchStatus:
    success: bool
    error_code: int
    message: str
    command: str
    exit_code: int


def parse_as_of_month(selected_date: str) -> date:
    parsed_date = date.fromisoformat(selected_date)
    if parsed_date.month == 12:
        next_month_start = date(parsed_date.year + 1, 1, 1)
    else:
        next_month_start = date(parsed_date.year, parsed_date.month + 1, 1)
    return date.fromordinal(next_month_start.toordinal() - 1)


def normalize_path_separators(raw_path: str) -> str:
    normalized_path = raw_path.strip().replace("/", "\\")
    while len(normalized_path) > 3 and normalized_path.endswith("\\"):
        normalized_path = normalized_path[:-1]
    return normalized_path


def resolve_output_dir(repo_root: str, selected_date: str) -> str:
    parsed_date = parse_as_of_month(selected_date)
    return f"{normalize_path_separators(repo_root)}\\runs\\{parsed_date.isoformat()}"


def resolve_config_path(run_mode: RunnerMode) -> str:
    if run_mode is RunnerMode.ALL:
        return "config\\all_programs.yml"
    if run_mode is RunnerMode.EX_TREND:
        return "config\\ex_trend.yml"
    return "config\\trend.yml"


def build_command(run_mode: RunnerMode, selected_date: str, output_dir: str) -> str:
    # Keep date validation behavior aligned with VBA parser semantics.
    parse_as_of_month(selected_date)
    config_path = resolve_config_path(run_mode)
    return f'run --fixture-replay --config "{config_path}" --output-dir "{output_dir}"'


def open_output_folder(
    *,
    repo_root: str,
    selected_date: str,
    directory_exists: Callable[[str], bool],
    open_directory: Callable[[str], int],
) -> LaunchStatus:
    output_dir = resolve_output_dir(repo_root, selected_date)
    if not directory_exists(output_dir):
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE,
            message=f"Directory not found: {output_dir}",
            command=output_dir,
            exit_code=-1,
        )

    try:
        exit_code = int(open_directory(output_dir))
    except Exception as exc:  # pragma: no cover - defensive parity with VBA error flow
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 1,
            message=str(exc),
            command=output_dir,
            exit_code=-1,
        )

    if exit_code != 0:
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + exit_code,
            message=f"Process exited with code {exit_code}",
            command=output_dir,
            exit_code=exit_code,
        )

    return LaunchStatus(
        success=True,
        error_code=0,
        message="Success",
        command=output_dir,
        exit_code=0,
    )
