"""Inventory checks for committed VBA module source files."""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

VBA_SOURCE_DIR = Path("assets/vba")
WORKBOOKS_WITH_VBA = (
    Path("Runner.xlsm"),
    Path("assets/templates/counter_risk_template.xlsm"),
)
VBA_MODULE_PATTERN = re.compile(r'Attribute VB_Name\s*=\s*"([^"]+)"')


def _extract_module_names(workbook_path: Path) -> set[str]:
    with ZipFile(workbook_path) as workbook, workbook.open("xl/vbaProject.bin") as handle:
        vba_text = handle.read().decode("latin-1", errors="ignore")
    return set(VBA_MODULE_PATTERN.findall(vba_text))


def test_assets_vba_directory_exists() -> None:
    assert VBA_SOURCE_DIR.is_dir(), "Expected VBA source directory at assets/vba."


def test_all_embedded_vba_modules_have_bas_sources() -> None:
    discovered_modules: set[str] = set()
    for workbook_path in WORKBOOKS_WITH_VBA:
        assert workbook_path.is_file(), f"Expected workbook fixture to exist: {workbook_path}"
        discovered_modules.update(_extract_module_names(workbook_path))

    assert discovered_modules, "No VBA modules were discovered in workbook fixtures."

    bas_module_names = {path.stem for path in VBA_SOURCE_DIR.glob("*.bas")}
    missing_modules = sorted(discovered_modules - bas_module_names)
    assert not missing_modules, "Missing VBA module source files in assets/vba: " + ", ".join(
        f"{name}.bas" for name in missing_modules
    )

    wrong_extension_files = sorted(
        str(path.relative_to(VBA_SOURCE_DIR))
        for path in VBA_SOURCE_DIR.iterdir()
        if path.is_file() and path.stem in discovered_modules and path.suffix.lower() != ".bas"
    )
    assert (
        not wrong_extension_files
    ), "VBA modules must be committed with .bas extensions only: " + ", ".join(
        wrong_extension_files
    )

    for module_name in sorted(discovered_modules):
        module_path = VBA_SOURCE_DIR / f"{module_name}.bas"
        source = module_path.read_text(encoding="utf-8")
        assert (
            f'Attribute VB_Name = "{module_name}"' in source
        ), f"{module_path} does not declare the expected VB module name {module_name}."
