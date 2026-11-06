#!/usr/bin/env python3
"""Extract declared CFB/MS-OVBA module streams; legacy recovery is explicitly separate."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from zipfile import ZipFile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# OLE CFB signature
OLE_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Pattern for mirror blocks in legacy pseudo-projects (kept for backward compatibility)
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
    """Extract only declared, decompressed module streams from an executable project."""
    from scripts.vba_project import project_modules

    with ZipFile(workbook_path) as workbook:
        return project_modules(workbook.read("xl/vbaProject.bin"))


def extract_legacy_mirrors(vba_bytes: bytes) -> dict[str, str]:
    """Recover historical text mirrors; never use this as project validation."""
    modules = {}
    for match in MIRROR_BLOCK_PATTERN.finditer(vba_bytes.decode("latin1")):
        name = match.group("name")
        source = _normalize_newlines(match.group("body"))
        anchor = f'Attribute VB_Name = "{name}"'
        start = source.find(anchor)
        if start < 0:
            raise ValueError(f"Missing legacy module attribute: {name}")
        modules[name] = source[start:].strip() + "\n"
    return modules


def extract_modules_from_workbooks(workbook_paths: tuple[Path, ...]) -> dict[str, str]:
    """Extract modules from all workbooks.

    When the same module appears in multiple workbooks with different text, keep
    the first-seen source to preserve deterministic output from the ordered
    ``workbook_paths`` input.
    """
    modules: dict[str, str] = {}

    for workbook_path in workbook_paths:
        for module_name, module_source in extract_modules_from_workbook(workbook_path).items():
            if module_name in modules:
                if modules[module_name] != module_source:
                    raise ValueError(f"Conflicting actual module: {module_name} in {workbook_path}")
            else:
                modules[module_name] = module_source

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
