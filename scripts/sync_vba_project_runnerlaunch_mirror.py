#!/usr/bin/env python3
"""Refresh actual RunnerLaunch via Excel import/export, never a source mirror."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.vba_project import project_modules


def sync_vba_project(
    *,
    bas_path: Path = Path("assets/vba/RunnerLaunch.bas"),
    project_path: Path = Path("assets/vba/vbaProject.bin"),
    workbook_path: Path = Path("Runner.xlsm"),
) -> None:
    """Resolve caller-selected paths once; validate output before replacing it."""
    bas_path, project_path, workbook_path = (
        path.resolve() for path in (bas_path, project_path, workbook_path)
    )
    if project_path in {bas_path, workbook_path}:
        raise ValueError("Project output must differ from source and input workbook")
    expected = bas_path.read_text(encoding="utf-8").rstrip() + "\n"
    with tempfile.TemporaryDirectory(dir=project_path.parent) as folder:
        generated = Path(folder) / "vbaProject.bin"
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("create_vba_project.py")),
                "--bas-path",
                str(bas_path),
                "--project-path",
                str(generated),
                "--workbook-path",
                str(workbook_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(
                f"Excel project export failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        modules = project_modules(generated.read_bytes())
        if modules.get("RunnerLaunch") != expected:
            raise ValueError("Exported actual RunnerLaunch differs from selected source")
        generated.replace(project_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bas-path", type=Path, default=Path("assets/vba/RunnerLaunch.bas"))
    parser.add_argument("--project-path", type=Path, default=Path("assets/vba/vbaProject.bin"))
    parser.add_argument("--workbook-path", type=Path, default=Path("Runner.xlsm"))
    args = parser.parse_args(argv)
    try:
        sync_vba_project(**vars(args))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Synced actual RunnerLaunch to {args.project_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
