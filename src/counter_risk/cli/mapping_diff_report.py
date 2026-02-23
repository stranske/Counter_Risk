"""CLI entrypoint for mapping diff report generation."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for mapping_diff_report."""

    return argparse.ArgumentParser(
        prog="mapping_diff_report",
        description="Generate a deterministic mapping diff report.",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the mapping diff report CLI."""

    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
