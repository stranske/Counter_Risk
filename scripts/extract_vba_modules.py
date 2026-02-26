#!/usr/bin/env python3
"""Extract VBA module source files from workbook fixtures.

The workbooks embed a readable module mirror in ``xl/vbaProject.bin`` delimited by
``' BEGIN <Module>.bas mirror`` and ``' END <Module>.bas mirror`` markers.
This script exports those modules into ``assets/vba/*.bas``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZipFile

MIRROR_BLOCK_PATTERN = re.compile(
    r"' BEGIN (?P<name>[A-Za-z0-9_]+)\.bas mirror\r?\n(?P<body>.*?)' END (?P=name)\.bas mirror",
    re.DOTALL,
)


DEFAULT_WORKBOOK_PATHS: tuple[Path, ...] = (
    Path("Runner.xlsm"),
    Path("assets/templates/counter_risk_template.xlsm"),
)


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_modules_from_workbook(workbook_path: Path) -> dict[str, str]:
    """Return VBA module sources extracted from one workbook."""
    if not workbook_path.is_file():
        msg = f"Workbook not found: {workbook_path}"
        raise FileNotFoundError(msg)

    with ZipFile(workbook_path) as workbook:
        vba_text = workbook.read("xl/vbaProject.bin").decode("latin1", errors="ignore")

    modules: dict[str, str] = {}
    for match in MIRROR_BLOCK_PATTERN.finditer(vba_text):
        module_name = match.group("name")
        body = _normalize_newlines(match.group("body"))
        anchor = f'Attribute VB_Name = "{module_name}"'
        start = body.find(anchor)
        if start < 0:
            msg = f"Mirror block for {module_name} in {workbook_path} is missing {anchor}."
            raise ValueError(msg)
        modules[module_name] = body[start:].strip() + "\n"

    if not modules:
        msg = f"No VBA mirror blocks were found in {workbook_path}."
        raise ValueError(msg)

    return modules


def extract_modules_from_workbooks(workbook_paths: tuple[Path, ...]) -> dict[str, str]:
    """Extract modules from all workbooks and fail on conflicting module sources."""
    modules: dict[str, str] = {}
    module_sources: dict[str, Path] = {}

    for workbook_path in workbook_paths:
        for module_name, module_source in extract_modules_from_workbook(workbook_path).items():
            if module_name in modules and modules[module_name] != module_source:
                previous_path = module_sources[module_name]
                msg = (
                    f"Conflicting VBA module source for {module_name}: "
                    f"{previous_path} vs {workbook_path}"
                )
                raise ValueError(msg)
            modules[module_name] = module_source
            module_sources[module_name] = workbook_path

    return modules


def write_modules(modules: dict[str, str], output_dir: Path) -> None:
    """Write extracted module text to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for module_name in sorted(modules):
        (output_dir / f"{module_name}.bas").write_text(modules[module_name], encoding="utf-8")


def check_modules(modules: dict[str, str], output_dir: Path) -> tuple[Path, ...]:
    """Return module paths that do not match the extracted inventory."""
    mismatches: list[Path] = []
    expected_module_paths: set[Path] = set()
    for module_name, expected_source in sorted(modules.items()):
        module_path = output_dir / f"{module_name}.bas"
        expected_module_paths.add(module_path)
        actual_source = module_path.read_text(encoding="utf-8") if module_path.exists() else ""
        if actual_source != expected_source:
            mismatches.append(module_path)

    # Keep the committed module set strict: stale .bas files mean the inventory drifted.
    if output_dir.is_dir():
        for module_path in sorted(output_dir.glob("*.bas")):
            if module_path not in expected_module_paths:
                mismatches.append(module_path)
    return tuple(mismatches)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract VBA module sources from workbook fixtures."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("assets/vba"),
        help="Directory where .bas modules are written (default: assets/vba).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify output files already match extracted sources.",
    )
    parser.add_argument(
        "workbook_paths",
        metavar="workbook",
        nargs="*",
        type=Path,
        default=DEFAULT_WORKBOOK_PATHS,
        help="Workbook paths to extract from.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    workbook_paths = tuple(args.workbook_paths)
    modules = extract_modules_from_workbooks(workbook_paths)

    if args.check:
        mismatches = check_modules(modules, args.output_dir)
        if mismatches:
            for path in mismatches:
                print(f"Mismatch: {path}")
            return 1
        print(f"VBA sources are up to date in {args.output_dir}.")
        return 0

    write_modules(modules, args.output_dir)
    print(f"Wrote {len(modules)} VBA module(s) to {args.output_dir}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
