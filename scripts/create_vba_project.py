#!/usr/bin/env python3
"""Import RunnerLaunch using Windows Excel, save, validate and export its project.

Requires a genuine Excel-saved input workbook, Windows Excel, pywin32 and an
already enabled VBA project automation setting. This tool never changes Office
security settings. It does not manufacture a project from an OLE signature.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.vba_project import project_modules


def create_vba_project(*, bas_path: Path, workbook_path: Path, output_path: Path) -> None:
    """Update a temporary copy through Excel; preserve all unrelated modules."""
    bas_path, workbook_path, output_path = (
        path.resolve() for path in (bas_path, workbook_path, output_path)
    )
    if output_path in {bas_path, workbook_path}:
        raise ValueError("Project output must differ from source and input workbook")
    source = bas_path.read_text(encoding="utf-8").rstrip() + "\n"
    if not source.startswith('Attribute VB_Name = "RunnerLaunch"\n'):
        raise ValueError("Expected a RunnerLaunch standard module export")
    with ZipFile(workbook_path) as workbook:
        before = project_modules(workbook.read("xl/vbaProject.bin"))
    if sys.platform != "win32":
        raise RuntimeError("Windows Excel is required for genuine VBA import/export")
    import win32com.client

    with tempfile.TemporaryDirectory(prefix="counter-risk-vba-") as folder:
        working = Path(folder) / "runner.xlsm"
        shutil.copy2(workbook_path, working)
        excel = win32com.client.DispatchEx("Excel.Application")
        book = None
        try:
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.AutomationSecurity = 3  # Disable macros when opening the input.
            book = excel.Workbooks.Open(str(working), UpdateLinks=0)
            components = book.VBProject.VBComponents
            references = {(ref.GUID, ref.Major, ref.Minor) for ref in book.VBProject.References}
            for component in components:
                if component.Name == "RunnerLaunch":
                    if component.Type != 1:
                        raise ValueError("RunnerLaunch is not a standard module")
                    components.Remove(component)
                    break
            # VBA imports ANSI .bas exports, not UTF-8. Reject lossy conversion.
            imported = Path(folder) / "RunnerLaunch.bas"
            imported.write_bytes(source.replace("\n", "\r\n").encode("mbcs"))
            components.Import(str(imported))
            if {
                (ref.GUID, ref.Major, ref.Minor) for ref in book.VBProject.References
            } != references:
                raise ValueError("VBA import changed project references")
            book.Save()
            book.Close(SaveChanges=False)
            book = None
        finally:
            if book is not None:
                book.Close(SaveChanges=False)
            excel.Quit()
        with ZipFile(working) as workbook:
            data = workbook.read("xl/vbaProject.bin")
        after = project_modules(data)
        if after.get("RunnerLaunch") != source:
            raise ValueError("Excel-saved RunnerLaunch source differs from selected BAS")
        unrelated = {key: value for key, value in before.items() if key != "RunnerLaunch"}
        if {key: value for key, value in after.items() if key != "RunnerLaunch"} != unrelated:
            raise ValueError("Excel changed unrelated module source; output was not replaced")
        with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        try:
            temporary.replace(output_path)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bas-path", type=Path, required=True)
    parser.add_argument("--workbook-path", type=Path, required=True)
    parser.add_argument("--project-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        create_vba_project(
            bas_path=args.bas_path, workbook_path=args.workbook_path, output_path=args.project_path
        )
    except Exception as exc:
        print(f"VBA import/export failed: {exc}", file=sys.stderr)
        return 1
    print(f"Exported Excel-saved project: {args.project_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
