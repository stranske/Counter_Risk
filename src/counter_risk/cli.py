"""Command-line interface for Counter Risk maintainers."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import cast

from counter_risk.pipeline import run_fixture_replay
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
    run_parser.set_defaults(handler=_run_command)
    return parser


def _run_command(args: argparse.Namespace) -> int:
    if bool(getattr(args, "fixture_replay", False)):
        run_dir = run_fixture_replay(config_path=args.config, output_dir=args.output_dir)
        print(f"Counter Risk fixture replay completed: {run_dir}")
        return 0

    print("Counter Risk run command is not implemented yet.")
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
