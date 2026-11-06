#!/usr/bin/env python3
"""Extract VBA module source files from workbook fixtures.

The workbooks embed VBA project binaries in ``xl/vbaProject.bin``. This script
inspects the actual VBA project streams to extract module sources.

For backward compatibility with legacy pseudo-projects (text files with fake
OLE headers), this script first validates that the vbaProject.bin has a proper
OLE CFB signature before attempting extraction.

Note: Extracting VBA modules from real VBA project binaries requires parsing
the VBA-specific structures within the OLE CFB file. This implementation
handles structurally valid OLE files with embedded VBA source code.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZipFile

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
    """Return VBA module sources extracted from one workbook.

    This function first attempts to extract modules from a real VBA project
    binary (OLE CFB format). If that fails, it falls back to the legacy
    mirror block extraction for backward compatibility.

    Raises:
        ValueError: If no modules can be extracted and the vbaProject.bin
                   is not a valid pseudo-project (text-based).
    """
    if not workbook_path.is_file():
        msg = f"Workbook not found: {workbook_path}"
        raise FileNotFoundError(msg)

    with ZipFile(workbook_path) as workbook:
        vba_bytes = workbook.read("xl/vbaProject.bin")

    # Check if this is a real OLE CFB file
    is_ole = (
        len(vba_bytes) >= len(OLE_CFB_SIGNATURE)
        and vba_bytes[: len(OLE_CFB_SIGNATURE)] == OLE_CFB_SIGNATURE
    )

    # Try to extract from real OLE VBA project
    if is_ole:
        modules = _extract_modules_from_ole_vba_project(vba_bytes, workbook_path)
        if modules:
            return modules

    # Fall back to legacy mirror block extraction for pseudo-projects
    vba_text = vba_bytes.decode("latin1", errors="ignore")
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
        msg = (
            f"No VBA modules were found in {workbook_path}. "
            "The vbaProject.bin is not a valid VBA project nor does it contain "
            "legacy mirror blocks. This may be a corrupted or incomplete VBA project."
        )
        raise ValueError(msg)

    return modules


def _extract_modules_from_ole_vba_project(vba_bytes: bytes, workbook_path: Path) -> dict[str, str]:
    """Extract VBA modules from a real OLE VBA project binary.

    This function handles structurally valid OLE CFB files that contain
    VBA source code. It attempts to extract module sources by:
    1. Decoding the bytes as UTF-16 (common for VBA projects)
    2. Looking for VBA module attributes

    Args:
        vba_bytes: The raw bytes of the vbaProject.bin file.
        workbook_path: The path to the workbook (for error messages).

    Returns:
        A dictionary mapping module names to their source code.
    """
    modules: dict[str, str] = {}

    # Try UTF-16 decoding (VBA projects often use UTF-16)
    try:
        vba_text = vba_bytes.decode("utf-16le", errors="ignore")

        # Clean up any null bytes that might be at the end due to padding
        vba_text = vba_text.rstrip("\x00")

        # Look for VBA module attributes
        # Pattern: Attribute VB_Name = "ModuleName"
        module_anchor_pattern = re.compile(
            r'Attribute\s+VB_Name\s*=\s*"(?P<name>[^"]+)"',
            re.IGNORECASE,
        )

        # Find all module declarations
        for match in module_anchor_pattern.finditer(vba_text):
            module_name = match.group("name")

            # Find the start of this module
            module_start = match.start()

            # Find the next module declaration or end of file
            next_match = module_anchor_pattern.search(vba_text, module_start + 1)
            module_end = next_match.start() if next_match else len(vba_text)

            # Extract the module source
            module_source = vba_text[module_start:module_end]

            # Clean up any remaining null bytes
            module_source = module_source.replace("\x00", "")

            # Normalize and clean up
            module_source = _normalize_newlines(module_source).strip()
            if module_source:
                # Add trailing newline
                if not module_source.endswith("\n"):
                    module_source += "\n"
                modules[module_name] = module_source

        if modules:
            return modules

    except Exception:
        # If UTF-16 decoding fails, try other encodings
        pass

    # Try UTF-8 decoding
    try:
        vba_text = vba_bytes.decode("utf-8", errors="ignore")

        # Clean up any null bytes
        vba_text = vba_text.replace("\x00", "")

        # Look for VBA module attributes
        module_anchor_pattern = re.compile(
            r'Attribute\s+VB_Name\s*=\s*"(?P<name>[^"]+)"',
            re.IGNORECASE,
        )

        for match in module_anchor_pattern.finditer(vba_text):
            module_name = match.group("name")
            module_start = match.start()

            next_match = module_anchor_pattern.search(vba_text, module_start + 1)
            module_end = next_match.start() if next_match else len(vba_text)

            module_source = vba_text[module_start:module_end]
            module_source = _normalize_newlines(module_source).strip()
            if module_source:
                if not module_source.endswith("\n"):
                    module_source += "\n"
                modules[module_name] = module_source

    except Exception:
        pass

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
                    # Keep the first module definition for deterministic output
                    # when workbook mirrors drift temporarily.
                    continue
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
