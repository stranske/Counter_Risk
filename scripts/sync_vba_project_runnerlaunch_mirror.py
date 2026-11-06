#!/usr/bin/env python3
"""Refresh the RunnerLaunch primary module inside ``assets/vba/vbaProject.bin``.

This script regenerates the VBA project binary from the canonical
``assets/vba/RunnerLaunch.bas`` source file. Since creating a real VBA project
OLE compound file from scratch without Excel is not feasible, this script
invokes the ``scripts/create_vba_project.py`` workflow to build a structurally
valid OLE CFB file containing the updated module source.

The resulting ``vbaProject.bin`` is a binary OLE file, not a text file.
Therefore, this sync operation is a full rebuild rather than an in-place
text replacement.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

OLE_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _read_module_source(bas_path: Path) -> str:
    """Read and normalize the VBA module source."""
    source = bas_path.read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    return source


def _validate_vba_project(project_path: Path) -> None:
    """Validate that the project file has a valid OLE CFB signature."""
    data = project_path.read_bytes()
    if len(data) < len(OLE_CFB_SIGNATURE) or data[: len(OLE_CFB_SIGNATURE)] != OLE_CFB_SIGNATURE:
        msg = (
            f"Invalid VBA project signature in {project_path}. "
            f"Expected OLE/CFB header {OLE_CFB_SIGNATURE.hex(' ').upper()}"
        )
        raise ValueError(msg)


def sync_vba_project(
    *,
    bas_path: Path = Path("assets/vba/RunnerLaunch.bas"),
    project_path: Path = Path("assets/vba/vbaProject.bin"),
) -> None:
    """Sync the VBA project by rebuilding it from the BAS source.

    This is a full rebuild operation: the existing project file is replaced
    with a new OLE CFB file generated from the BAS source.

    Args:
        bas_path: Path to the RunnerLaunch.bas source file.
        project_path: Path to the vbaProject.bin output file.

    Raises:
        FileNotFoundError: If bas_path does not exist.
        ValueError: If the generated project does not have a valid OLE signature.
    """
    if not bas_path.is_file():
        msg = f"BAS source file not found: {bas_path}"
        raise FileNotFoundError(msg)

    # Read the module source
    _read_module_source(bas_path)

    # Create a new VBA project from the BAS source
    # Use the create_vba_project.py script
    create_script = Path(__file__).parent / "create_vba_project.py"

    # Build the command
    cmd = [
        sys.executable,
        str(create_script),
    ]

    # Run the script
    result = subprocess.run(
        cmd,
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        msg = f"Failed to create VBA project: {result.stderr}"
        raise RuntimeError(msg)

    # Validate the generated project
    _validate_vba_project(project_path)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--bas-path",
        type=Path,
        default=Path("assets/vba/RunnerLaunch.bas"),
        help="Path to RunnerLaunch.bas (default: assets/vba/RunnerLaunch.bas).",
    )
    parser.add_argument(
        "--project-path",
        type=Path,
        default=Path("assets/vba/vbaProject.bin"),
        help="Path to vbaProject.bin (default: assets/vba/vbaProject.bin).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        sync_vba_project(bas_path=args.bas_path, project_path=args.project_path)
        print(f"VBA project synced from {args.bas_path} to {args.project_path}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
