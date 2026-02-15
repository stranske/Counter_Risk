"""Workflow entrypoint for historical WAL workbook updates."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from counter_risk.calculations.wal import calculate_wal
from counter_risk.writers.historical_update import append_wal_row, locate_ex_llc_3_year_workbook


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for WAL append workflow."""

    parser = argparse.ArgumentParser(prog="counter-risk-historical-update")
    parser.add_argument(
        "--date",
        required=True,
        help="Observation date in YYYY-MM-DD format used for WAL append.",
    )
    parser.add_argument(
        "--exposure-summary-path",
        type=Path,
        required=True,
        help="Path to exposure maturity summary workbook used to compute WAL.",
    )
    return parser


def run(*, px_date: date, exposure_summary_path: Path) -> Path:
    """Calculate WAL and append one historical row to ex LLC workbook."""

    workbook_path = locate_ex_llc_3_year_workbook()
    wal_value = calculate_wal(exposure_summary_path, px_date)
    return append_wal_row(workbook_path, px_date=px_date, wal_value=wal_value)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    px_date = date.fromisoformat(args.date)
    run(px_date=px_date, exposure_summary_path=args.exposure_summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
