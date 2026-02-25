"""CLI entrypoint for mapping diff report generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from counter_risk.reports.mapping_diff import generate_mapping_diff_report


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for mapping_diff_report."""

    parser = argparse.ArgumentParser(
        prog="mapping_diff_report",
        description="Generate a deterministic mapping diff report.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/name_registry.yml"),
        help="Path to registry YAML file.",
    )
    parser.add_argument(
        "--normalization-name",
        action="append",
        default=[],
        help="Raw input name observed during normalization. Can be provided multiple times.",
    )
    parser.add_argument(
        "--reconciliation-name",
        action="append",
        default=[],
        help="Raw input name observed during reconciliation. Can be provided multiple times.",
    )
    parser.add_argument(
        "--output-format",
        choices=("text",),
        default="text",
        help="Report output format.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the mapping diff report CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    input_sources = {
        "normalization": list(args.normalization_name),
        "reconciliation": list(args.reconciliation_name),
    }
    try:
        report = generate_mapping_diff_report(
            args.registry,
            input_sources,
            output_format=args.output_format,
        )
    except ValueError as exc:
        error_line = " ".join(str(exc).splitlines())
        print(error_line, file=sys.stderr)
        return 1

    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
