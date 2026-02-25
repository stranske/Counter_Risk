"""Command-line interface for Counter Risk maintainers."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import cast

from counter_risk.config import WorkflowConfig, load_config
from counter_risk.io.discover import discover_workflow_inputs, resolve_discovery_selections
from counter_risk.pipeline import run_fixture_replay, run_pipeline_with_config
from counter_risk.runtime_paths import resolve_runtime_path


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""

    parser = argparse.ArgumentParser(prog="counter-risk")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the Counter Risk pipeline (stub)")
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
        help="Output directory override for --fixture-replay mode.",
    )
    run_parser.add_argument(
        "--as-of-month",
        type=str,
        default=None,
        help="As-of reporting date in YYYY-MM-DD format for discovery preview.",
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
    run_parser.set_defaults(handler=_run_command)
    return parser


def _run_command(args: argparse.Namespace) -> int:
    if bool(getattr(args, "dry_run_discovery", False)):
        config = load_config(args.config)
        as_of_date = _resolve_discovery_as_of_date(
            config=config,
            as_of_month=getattr(args, "as_of_month", None),
        )
        if as_of_date is None:
            print(
                "Discovery dry-run requires an as-of date. "
                "Set config.as_of_date or pass --as-of-month YYYY-MM-DD."
            )
            return 2

        print(_format_discovery_dry_run(config=config, as_of_date=as_of_date))
        return 0

    if bool(getattr(args, "discover", False)):
        return _run_with_discovery(args)

    if bool(getattr(args, "fixture_replay", False)):
        run_dir = run_fixture_replay(config_path=args.config, output_dir=args.output_dir)
        print(f"Counter Risk fixture replay completed: {run_dir}")
        return 0

    print("Counter Risk run command is not implemented yet.")
    return 0


def _run_with_discovery(args: argparse.Namespace) -> int:
    """Run the workflow using auto-discovered inputs with interactive selection."""

    config = load_config(args.config)
    as_of_date = _resolve_discovery_as_of_date(
        config=config,
        as_of_month=getattr(args, "as_of_month", None),
    )
    if as_of_date is None:
        print(
            "Discovery mode requires an as-of date. "
            "Set config.as_of_date or pass --as-of-month YYYY-MM-DD."
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
    for input_name, path in selected.items():
        if hasattr(config, input_name):
            overrides[input_name] = path
    updated_config = config.model_copy(update=overrides)

    config_dir = args.config.resolve().parent
    output_dir: Path | None = getattr(args, "output_dir", None)
    run_dir = run_pipeline_with_config(
        updated_config,
        config_dir=config_dir,
        output_dir=output_dir,
    )
    print(f"\nCounter Risk discovery run completed: {run_dir}")
    return 0


def _resolve_discovery_as_of_date(
    *, config: WorkflowConfig, as_of_month: str | None
) -> date | None:
    if as_of_month:
        return date.fromisoformat(as_of_month.strip())
    return config.as_of_date


def _format_discovery_dry_run(*, config: WorkflowConfig, as_of_date: date) -> str:
    result = discover_workflow_inputs(config, as_of_date=as_of_date)
    lines = [f"Discovery dry-run for as-of date {as_of_date.isoformat()}"]
    for input_name in sorted(result.matches_by_input):
        matches = result.matches_by_input[input_name]
        lines.append(f"- {input_name}: {len(matches)} match(es)")
        for match in matches:
            lines.append(f"  {match.path}")
    return "\n".join(lines)


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
