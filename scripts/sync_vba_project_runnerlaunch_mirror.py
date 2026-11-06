#!/usr/bin/env python3
"""Refresh the RunnerLaunch primary module and mirror inside ``assets/vba/vbaProject.bin``.

Both the executable module text and the trailing ``' BEGIN/END RunnerLaunch.bas mirror``
block are overwritten from ``assets/vba/RunnerLaunch.bas``. The leading bytes before the
first ``Attribute VB_Name = "RunnerLaunch"`` line are preserved.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _read_module_source(bas_path: Path) -> str:
    source = bas_path.read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    return source


def sync_vba_project(
    *,
    bas_path: Path = Path("assets/vba/RunnerLaunch.bas"),
    project_path: Path = Path("assets/vba/vbaProject.bin"),
) -> None:
    module_source = _read_module_source(bas_path)

    data = project_path.read_bytes()
    text = data.decode("latin-1", errors="strict")

    module_anchor = 'Attribute VB_Name = "RunnerLaunch"\n'
    primary_start = text.find(module_anchor)
    if primary_start < 0:
        msg = f"RunnerLaunch module anchor not found in {project_path}"
        raise ValueError(msg)

    marker_begin = "' BEGIN RunnerLaunch.bas mirror\n"
    marker_end = "' END RunnerLaunch.bas mirror\n"

    i_begin = text.find(marker_begin)
    i_end = text.find(marker_end)
    if i_begin < 0 or i_end < 0 or i_end <= i_begin:
        msg = f"Mirror markers not found in {project_path}"
        raise ValueError(msg)

    suffix = text[i_end + len(marker_end) :]
    if suffix:
        msg = f"Unexpected content after mirror end in {project_path}"
        raise ValueError(msg)

    prefix = text[:primary_start]
    rebuilt = prefix + module_source + "\n'\n" + marker_begin + module_source + marker_end
    project_path.write_bytes(rebuilt.encode("latin-1", errors="strict"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
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
    sync_vba_project(bas_path=args.bas_path, project_path=args.project_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
