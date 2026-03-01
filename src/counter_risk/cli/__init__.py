"""Command-line interface for Counter Risk maintainers and operators."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, cast

from counter_risk.config import WorkflowConfig, load_config
from counter_risk.io.discover import discover_workflow_inputs, resolve_discovery_selections
from counter_risk.pipeline import run_fixture_replay, run_pipeline_with_config
from counter_risk.runtime_paths import resolve_runtime_path

_SETTINGS_DISCOVERY_MODE_KEY = "discovery_mode"
_SETTINGS_INPUT_ROOT_KEY = "input_root"
_SETTINGS_OUTPUT_ROOT_KEY = "output_root"
_SETTINGS_STRICT_POLICY_KEY = "strict_policy"
_SETTINGS_FORMATTING_PROFILE_KEY = "formatting_profile"
_KNOWN_RUNNER_SETTINGS = {
    _SETTINGS_DISCOVERY_MODE_KEY,
    _SETTINGS_INPUT_ROOT_KEY,
    _SETTINGS_OUTPUT_ROOT_KEY,
    _SETTINGS_STRICT_POLICY_KEY,
    _SETTINGS_FORMATTING_PROFILE_KEY,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""

    parser = argparse.ArgumentParser(prog="counter-risk")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the Counter Risk pipeline")
    run_parser.add_argument(
        "--fixture-replay",
        action="store_true",
        help="Run fixture replay mode to validate release bundle outputs.",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        default=resolve_runtime_path(Path("config/fixture_replay.yml")),
        help="Path to workflow YAML config used by --fixture-replay mode.",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory override for workflow-mode or --fixture-replay runs.",
    )
    run_parser.add_argument(
        "--as-of-date",
        "--as-of-month",
        dest="as_of_date",
        type=str,
        default=None,
        help="As-of reporting date in YYYY-MM-DD format.",
    )
    run_parser.add_argument(
        "--dry-run-discovery",
        action="store_true",
        help="List discovered workflow input candidates without executing the workflow.",
    )
    run_parser.add_argument(
        "--discover",
        action="store_true",
        help="Use input discovery to locate files, prompt for selection when multiple "
        "matches are found, and execute the workflow with discovered inputs.",
    )
    run_parser.add_argument(
        "--export-pdf",
        dest="export_pdf",
        action="store_true",
        default=None,
        help="Enable PDF export in workflow-mode runs.",
    )
    run_parser.add_argument(
        "--no-export-pdf",
        dest="export_pdf",
        action="store_false",
        default=None,
        help="Disable PDF export in workflow-mode runs.",
    )
    run_parser.add_argument(
        "--strict-policy",
        choices=("warn", "strict"),
        default=None,
        help="Override reconciliation.fail_policy for this run.",
    )
    run_parser.add_argument(
        "--formatting-profile",
        type=str,
        default=None,
        help="Reserved runtime formatting profile selector (stored for follow-on workflows).",
    )
    run_parser.add_argument(
        "--settings",
        type=Path,
        default=None,
        help="Path to runner settings JSON written by Runner.xlsm.",
    )
    run_parser.set_defaults(handler=_run_command)
    return parser


def _run_command(args: argparse.Namespace) -> int:
    try:
        runner_settings = _load_runner_settings(getattr(args, "settings", None))
    except ValueError as exc:
        print(f"Runner settings error: {exc}")
        return 2

    args.runner_settings = runner_settings

    if bool(getattr(args, "dry_run_discovery", False)):
        config = _load_config_with_runner_settings(args.config, runner_settings)
        as_of_date = _resolve_discovery_as_of_date(
            config=config,
            as_of_date=getattr(args, "as_of_date", None),
        )
        if as_of_date is None:
            print(
                "Discovery dry-run requires an as-of date. "
                "Set config.as_of_date or pass --as-of-date YYYY-MM-DD."
            )
            return 2

        print(_format_discovery_dry_run(config=config, as_of_date=as_of_date))
        return 0

    if bool(getattr(args, "discover", False)) or _runner_settings_enable_discovery(runner_settings):
        return _run_with_discovery(args)

    if bool(getattr(args, "fixture_replay", False)):
        run_dir = run_fixture_replay(config_path=args.config, output_dir=args.output_dir)
        print(f"Counter Risk fixture replay completed: {run_dir}")
        return 0

    return _run_workflow_mode(args)


def _run_with_discovery(args: argparse.Namespace) -> int:
    """Run the workflow using auto-discovered inputs with interactive selection."""

    runner_settings = _runner_settings(args)
    config = _load_config_with_runner_settings(args.config, runner_settings)
    as_of_date = _resolve_discovery_as_of_date(
        config=config,
        as_of_date=getattr(args, "as_of_date", None),
    )
    if as_of_date is None:
        print(
            "Discovery mode requires an as-of date. "
            "Set config.as_of_date or pass --as-of-date YYYY-MM-DD."
        )
        return 2

    result = discover_workflow_inputs(config, as_of_date=as_of_date)

    # Show summary before prompting
    print(f"Discovering inputs for as-of date {as_of_date.isoformat()}...")
    has_gaps = False
    for input_name in sorted(result.matches_by_input):
        matches = result.matches_by_input[input_name]
        count = len(matches)
        if count == 0:
            print(f"  {input_name}: no matches found")
            has_gaps = True
        elif count == 1:
            print(f"  {input_name}: {matches[0].path}")
        else:
            print(f"  {input_name}: {count} matches (selection required)")

    # Resolve selections (auto-pick singles, prompt for multiples)
    selected = resolve_discovery_selections(result)

    if has_gaps:
        missing = [name for name, matches in result.matches_by_input.items() if not matches]
        print(f"\nWarning: no files discovered for: {', '.join(missing)}")
        print("Proceeding with config defaults for those inputs.")

    # Build an updated config with discovered paths overriding defaults
    overrides: dict[str, object] = {"as_of_date": as_of_date}
    strict_policy = _effective_strict_policy(args, runner_settings)
    if strict_policy:
        overrides["reconciliation"] = config.reconciliation.model_copy(
            update={"fail_policy": strict_policy}
        )
    export_pdf = getattr(args, "export_pdf", None)
    if export_pdf is not None:
        overrides["export_pdf"] = bool(export_pdf)
    for input_name, path in selected.items():
        if hasattr(config, input_name):
            overrides[input_name] = path
    updated_config = config.model_copy(update=overrides)
    formatting_profile = _effective_formatting_profile(args, runner_settings)

    config_dir = args.config.resolve().parent
    output_dir: Path | None = getattr(args, "output_dir", None)
    run_dir = run_pipeline_with_config(
        updated_config,
        config_dir=config_dir,
        output_dir=output_dir,
        formatting_profile=formatting_profile,
    )
    if formatting_profile:
        print(
            "Note: formatting profile applied to supported output formatters; "
            f"selected profile: {formatting_profile}"
        )

    print(f"\nCounter Risk discovery run completed: {run_dir}")
    return 0


def _resolve_discovery_as_of_date(*, config: WorkflowConfig, as_of_date: str | None) -> date | None:
    if as_of_date:
        return date.fromisoformat(as_of_date.strip())
    return config.as_of_date


def _run_workflow_mode(args: argparse.Namespace) -> int:
    """Run the full workflow pipeline using the provided config."""

    try:
        runner_settings = _runner_settings(args)
        config = _load_config_with_runner_settings(args.config, runner_settings)
        overrides: dict[str, object] = {}
        as_of_date_raw = cast(str | None, getattr(args, "as_of_date", None))
        if as_of_date_raw:
            overrides["as_of_date"] = date.fromisoformat(as_of_date_raw.strip())
        strict_policy = _effective_strict_policy(args, runner_settings)
        if strict_policy:
            overrides["reconciliation"] = config.reconciliation.model_copy(
                update={"fail_policy": strict_policy}
            )
        export_pdf = getattr(args, "export_pdf", None)
        if export_pdf is not None:
            overrides["export_pdf"] = bool(export_pdf)
        runtime_config = config.model_copy(update=overrides) if overrides else config
        formatting_profile = _effective_formatting_profile(args, runner_settings)
        run_dir = run_pipeline_with_config(
            runtime_config,
            config_dir=args.config.resolve().parent,
            output_dir=getattr(args, "output_dir", None),
            formatting_profile=formatting_profile,
        )
        if formatting_profile:
            print(
                "Note: formatting profile applied to supported output formatters; "
                f"selected profile: {formatting_profile}"
            )
        print(f"Counter Risk run completed: {run_dir}")
        return 0
    except Exception as exc:
        print(f"Counter Risk run failed: {exc}")
        return 1


def _format_discovery_dry_run(*, config: WorkflowConfig, as_of_date: date) -> str:
    result = discover_workflow_inputs(config, as_of_date=as_of_date)
    lines = [f"Discovery dry-run for as-of date {as_of_date.isoformat()}"]
    for input_name in sorted(result.matches_by_input):
        matches = result.matches_by_input[input_name]
        lines.append(f"- {input_name}: {len(matches)} match(es)")
        for match in matches:
            lines.append(f"  {match.path}")
    return "\n".join(lines)


def _load_runner_settings(settings_path: Path | None) -> dict[str, str]:
    if settings_path is None:
        return {}

    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read settings file '{settings_path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"settings file '{settings_path}' is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"settings file '{settings_path}' must contain a JSON object.")

    normalized: dict[str, str] = {}
    for key in _KNOWN_RUNNER_SETTINGS:
        value = raw.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                normalized[key] = stripped
    return normalized


def _runner_settings(args: argparse.Namespace) -> dict[str, str]:
    return cast(dict[str, str], getattr(args, "runner_settings", {}))


def _effective_strict_policy(args: argparse.Namespace, settings: dict[str, str]) -> str | None:
    strict_policy = cast(str | None, getattr(args, "strict_policy", None))
    if strict_policy:
        return strict_policy
    configured = settings.get(_SETTINGS_STRICT_POLICY_KEY)
    if configured in {"warn", "strict"}:
        return configured
    return None


def _effective_formatting_profile(args: argparse.Namespace, settings: dict[str, str]) -> str | None:
    formatting_profile = cast(str | None, getattr(args, "formatting_profile", None))
    if formatting_profile:
        return formatting_profile
    return settings.get(_SETTINGS_FORMATTING_PROFILE_KEY)


def _runner_settings_enable_discovery(settings: dict[str, str]) -> bool:
    return settings.get(_SETTINGS_DISCOVERY_MODE_KEY, "").strip().casefold() == "discover"


def _load_config_with_runner_settings(
    config_path: Path, settings: dict[str, str]
) -> WorkflowConfig:
    config = load_config(config_path)
    overrides: dict[str, Any] = {}

    output_root = settings.get(_SETTINGS_OUTPUT_ROOT_KEY)
    if output_root:
        overrides["output_root"] = Path(output_root)

    input_root = settings.get(_SETTINGS_INPUT_ROOT_KEY)
    if input_root:
        input_root_path = Path(input_root)
        configured_roots = dict(config.input_discovery.directory_roots)
        if configured_roots:
            overrides["input_discovery"] = config.input_discovery.model_copy(
                update={"directory_roots": dict.fromkeys(sorted(configured_roots), input_root_path)}
            )
        else:
            overrides["input_discovery"] = config.input_discovery.model_copy(
                update={
                    "directory_roots": {
                        "monthly_inputs": input_root_path,
                        "historical_inputs": input_root_path,
                        "template_inputs": input_root_path,
                    }
                }
            )

    if not overrides:
        return config
    return config.model_copy(update=overrides)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    command_handler = cast(Callable[[argparse.Namespace], int], handler)
    return command_handler(args)
