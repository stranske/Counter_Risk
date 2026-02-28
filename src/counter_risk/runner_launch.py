"""Runner launch helpers mirrored from RunnerLaunch.bas for unit testing.

These helpers keep launch decision logic testable in Python without Excel automation.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

SHELL_ERROR_BASE = 7100
_OPERATOR_ACTION_PREFIX = "Operator action:"
_DATA_QUALITY_SUMMARY_FILENAME = "DATA_QUALITY_SUMMARY.txt"
_MANIFEST_FILENAME = "manifest.json"
_PPT_OUTPUT_DIRNAME = "distribution_static"


class RunnerMode(StrEnum):
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


def _extract_operator_action(raw_message: str) -> str | None:
    marker_index = raw_message.find(_OPERATOR_ACTION_PREFIX)
    if marker_index < 0:
        return None
    action = raw_message[marker_index:].strip()
    return action or None


def map_runner_error_to_operator_message(raw_message: str) -> str:
    """Translate technical pipeline text into operator-facing guidance."""

    message = raw_message.strip()
    if not message:
        return "Operator action: review run inputs, then rerun the process."

    explicit_operator_action = _extract_operator_action(message)
    if explicit_operator_action is not None:
        return explicit_operator_action

    lowered = message.casefold()
    if "input validation" in lowered or "missing required input" in lowered:
        return (
            "Operator action: verify required input files are present and configured paths are "
            "correct, then rerun."
        )
    if (
        "reconciliation strict mode failed" in lowered
        or "cprs-ch totals mismatch" in lowered
        or "class breakdown sanity check failed" in lowered
    ):
        return (
            "Operator action: reconcile source totals/class breakdown values, apply mapping "
            "updates if needed, and rerun."
        )
    if "unmatched counterparty" in lowered or "unmapped" in lowered:
        return "Operator action: update counterparty mappings for this month and rerun."
    return "Operator action: review the run log details and rerun. Contact support if it repeats."


def format_launch_error_for_runner(status: LaunchStatus) -> str:
    """Build a concise Runner UI error string with operator guidance."""

    if status.success:
        return status.message
    guidance = map_runner_error_to_operator_message(status.message)
    return f"Error {status.error_code}: {guidance}"


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
    # Mirror RunnerLaunch.bas: Format$(parsedDate, "yyyy-mm-dd_hhnnss") on a date-only value.
    # VBA dates carry a midnight time component by default, so the time segment is deterministic.
    return f"{normalize_path_separators(repo_root)}\\runs\\{parsed_date.isoformat()}_000000"


def resolve_data_quality_summary_path(repo_root: str, selected_date: str) -> str:
    return f"{resolve_output_dir(repo_root, selected_date)}\\{_DATA_QUALITY_SUMMARY_FILENAME}"


def resolve_manifest_path(repo_root: str, selected_date: str) -> str:
    return f"{resolve_output_dir(repo_root, selected_date)}\\{_MANIFEST_FILENAME}"


def resolve_ppt_output_dir(repo_root: str, selected_date: str) -> str:
    return f"{resolve_output_dir(repo_root, selected_date)}\\{_PPT_OUTPUT_DIRNAME}"


def resolve_config_path(run_mode: RunnerMode) -> str:
    if run_mode is RunnerMode.ALL:
        return "config\\all_programs.yml"
    if run_mode is RunnerMode.EX_TREND:
        return "config\\ex_trend.yml"
    return "config\\trend.yml"


def resolve_settings_path(temp_root: str | None = None) -> str:
    root = temp_root or os.environ.get("TEMP") or tempfile.gettempdir()
    normalized_root = normalize_path_separators(root)
    return f"{normalized_root}\\counter-risk-runner-settings.json"


def build_runner_settings_payload(
    *,
    input_root: str,
    discovery_mode: str,
    strict_policy: str,
    formatting_profile: str,
    output_root: str,
) -> str:
    payload = {
        "input_root": input_root.strip(),
        "discovery_mode": discovery_mode.strip(),
        "strict_policy": strict_policy.strip(),
        "formatting_profile": formatting_profile.strip(),
        "output_root": output_root.strip(),
    }
    return json.dumps(payload, sort_keys=True)


def write_runner_settings_file(settings_payload: str, settings_path: str) -> None:
    target = Path(settings_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(settings_payload, encoding="utf-8")


def build_command(
    run_mode: RunnerMode, selected_date: str, output_dir: str, settings_path: str | None = None
) -> str:
    # Keep date validation behavior aligned with VBA parser semantics.
    parsed_date = parse_as_of_month(selected_date)
    config_path = resolve_config_path(run_mode)
    selected_settings_path = settings_path or resolve_settings_path()
    return (
        "run "
        f'--config "{config_path}" '
        f'--as-of-date "{parsed_date.isoformat()}" '
        f'--output-dir "{output_dir}" '
        f'--settings "{selected_settings_path}"'
    )


def build_discovery_dry_run_command(
    run_mode: RunnerMode, selected_date: str, settings_path: str | None = None
) -> str:
    parsed_date = parse_as_of_month(selected_date)
    config_path = resolve_config_path(run_mode)
    selected_settings_path = settings_path or resolve_settings_path()
    return (
        "run --dry-run-discovery "
        f'--config "{config_path}" '
        f'--as-of-month "{parsed_date.isoformat()}" '
        f'--settings "{selected_settings_path}"'
    )


def build_discovery_run_command(
    run_mode: RunnerMode, selected_date: str, output_dir: str, settings_path: str | None = None
) -> str:
    parsed_date = parse_as_of_month(selected_date)
    config_path = resolve_config_path(run_mode)
    selected_settings_path = settings_path or resolve_settings_path()
    return (
        "run --discover "
        f'--config "{config_path}" '
        f'--as-of-month "{parsed_date.isoformat()}" '
        f'--output-dir "{output_dir}" '
        f'--settings "{selected_settings_path}"'
    )


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


def open_data_quality_summary(
    *,
    repo_root: str,
    selected_date: str,
    file_exists: Callable[[str], bool],
    open_file: Callable[[str], int],
) -> LaunchStatus:
    summary_path = resolve_data_quality_summary_path(repo_root, selected_date)
    if not file_exists(summary_path):
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 2,
            message=f"Summary not found: {summary_path}",
            command=summary_path,
            exit_code=-1,
        )

    try:
        exit_code = int(open_file(summary_path))
    except Exception as exc:  # pragma: no cover - defensive parity with VBA error flow
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 3,
            message=str(exc),
            command=summary_path,
            exit_code=-1,
        )

    if exit_code != 0:
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + exit_code,
            message=f"Process exited with code {exit_code}",
            command=summary_path,
            exit_code=exit_code,
        )

    return LaunchStatus(
        success=True,
        error_code=0,
        message="Success",
        command=summary_path,
        exit_code=0,
    )


def open_manifest(
    *,
    repo_root: str,
    selected_date: str,
    file_exists: Callable[[str], bool],
    open_file: Callable[[str], int],
) -> LaunchStatus:
    manifest_path = resolve_manifest_path(repo_root, selected_date)
    if not file_exists(manifest_path):
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 4,
            message=f"Manifest not found: {manifest_path}",
            command=manifest_path,
            exit_code=-1,
        )
    try:
        exit_code = int(open_file(manifest_path))
    except Exception as exc:  # pragma: no cover - defensive parity with VBA error flow
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 5,
            message=str(exc),
            command=manifest_path,
            exit_code=-1,
        )
    if exit_code != 0:
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + exit_code,
            message=f"Process exited with code {exit_code}",
            command=manifest_path,
            exit_code=exit_code,
        )
    return LaunchStatus(
        success=True,
        error_code=0,
        message="Success",
        command=manifest_path,
        exit_code=0,
    )


def open_ppt_output_folder(
    *,
    repo_root: str,
    selected_date: str,
    directory_exists: Callable[[str], bool],
    open_directory: Callable[[str], int],
) -> LaunchStatus:
    ppt_dir = resolve_ppt_output_dir(repo_root, selected_date)
    if not directory_exists(ppt_dir):
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 6,
            message=f"PPT output folder not found: {ppt_dir}",
            command=ppt_dir,
            exit_code=-1,
        )
    try:
        exit_code = int(open_directory(ppt_dir))
    except Exception as exc:  # pragma: no cover - defensive parity with VBA error flow
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + 7,
            message=str(exc),
            command=ppt_dir,
            exit_code=-1,
        )
    if exit_code != 0:
        return LaunchStatus(
            success=False,
            error_code=SHELL_ERROR_BASE + exit_code,
            message=f"Process exited with code {exit_code}",
            command=ppt_dir,
            exit_code=exit_code,
        )
    return LaunchStatus(
        success=True,
        error_code=0,
        message="Success",
        command=ppt_dir,
        exit_code=0,
    )


_STATUS_COLOR_LABELS: dict[str, str] = {
    "GREEN": "GREEN - Safe to send",
    "YELLOW": "YELLOW - Review warnings",
    "RED": "RED - Do not send",
}


def read_overall_status_color(summary_path: str | Path) -> str:
    """Read a DATA_QUALITY_SUMMARY.txt and extract the overall status color."""
    path = Path(summary_path)
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        upper_line = line.upper()
        if "(GREEN)" in upper_line:
            return "GREEN"
        if "(RED)" in upper_line:
            return "RED"
        if "(YELLOW)" in upper_line:
            return "YELLOW"
    return ""


def data_quality_status_label(status_color: str) -> str:
    """Map a status color string to a Runner UI display label."""
    return _STATUS_COLOR_LABELS.get(status_color.upper(), "")
