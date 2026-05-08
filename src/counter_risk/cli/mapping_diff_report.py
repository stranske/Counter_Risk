"""CLI entrypoint for mapping diff report generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
        "--normalization-json",
        type=Path,
        action="append",
        default=[],
        help="Path to normalization JSON payload (file can be provided multiple times).",
    )
    parser.add_argument(
        "--reconciliation-json",
        type=Path,
        action="append",
        default=[],
        help="Path to reconciliation JSON payload (file can be provided multiple times).",
    )
    parser.add_argument(
        "--output-format",
        choices=("text",),
        default="text",
        help="Report output format.",
    )
    parser.add_argument(
        "--manifest-json",
        type=Path,
        default=None,
        help="Path to a run manifest JSON file (for monthly run diff extraction).",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Run directory containing manifest.json (for monthly run diff extraction).",
    )
    return parser


def _load_json_payload(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_source_payload(*, names: list[str], payload_paths: list[Path]) -> Any:
    if not payload_paths:
        return names

    payload_items: list[Any] = []
    if names:
        payload_items.extend(names)
    for payload_path in payload_paths:
        payload_items.append(_load_json_payload(payload_path))

    if not payload_items:
        return []
    if len(payload_items) == 1:
        return payload_items[0]
    return payload_items


def _iter_manifest_source_names(payload: Any) -> list[str]:
    names: dict[str, None] = {}
    if not isinstance(payload, dict):
        return []

    reconciliation_results = payload.get("reconciliation_results")
    if not isinstance(reconciliation_results, dict):
        return []
    by_variant = reconciliation_results.get("by_variant")
    if not isinstance(by_variant, dict):
        return []

    for variant_payload in by_variant.values():
        if not isinstance(variant_payload, dict):
            continue
        by_sheet = variant_payload.get("by_sheet")
        if not isinstance(by_sheet, dict):
            continue
        for sheet_payload in by_sheet.values():
            if not isinstance(sheet_payload, dict):
                continue
            source_names = sheet_payload.get("counterparties_in_data")
            if not isinstance(source_names, list):
                continue
            for raw_name in source_names:
                value = str(raw_name)
                if value.strip():
                    names.setdefault(value, None)
    return sorted(names, key=str.casefold)


def main(argv: list[str] | None = None) -> int:
    """Run the mapping diff report CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        manifest_payload: Any | None = None
        if args.manifest_json is not None and args.run_dir is not None:
            print("Use either --manifest-json or --run-dir, not both.", file=sys.stderr)
            return 2
        if args.manifest_json is not None:
            manifest_payload = _load_json_payload(args.manifest_json)
        elif args.run_dir is not None:
            manifest_payload = _load_json_payload(args.run_dir / "manifest.json")

        manifest_names = _iter_manifest_source_names(manifest_payload)
        input_sources = {
            "normalization": _build_source_payload(
                names=[*list(args.normalization_name), *manifest_names],
                payload_paths=list(args.normalization_json),
            ),
            "reconciliation": _build_source_payload(
                names=[*list(args.reconciliation_name), *manifest_names],
                payload_paths=list(args.reconciliation_json),
            ),
        }
    except (OSError, json.JSONDecodeError) as exc:
        error_line = " ".join(str(exc).splitlines())
        print(error_line, file=sys.stderr)
        return 1

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
