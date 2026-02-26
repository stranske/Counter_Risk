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
MODULE_SOURCE_EXTENSION = ".bas"
ALLOWED_NON_MODULE_FILES = ("vbaProject.bin",)


def _extract_module_names(workbook_path: Path) -> set[str]:
    with ZipFile(workbook_path) as workbook, workbook.open("xl/vbaProject.bin") as handle:
        vba_text = handle.read().decode("latin-1", errors="ignore")
    return set(VBA_MODULE_PATTERN.findall(vba_text))


def test_assets_vba_directory_exists() -> None:
    assert VBA_SOURCE_DIR.is_dir(), "Expected VBA source directory at assets/vba."


def test_vba_inventory_scope_is_explicit() -> None:
    """Define verification scope for VBA inventory parity checks."""

    assert WORKBOOKS_WITH_VBA, "Scope must name at least one workbook with embedded VBA."
    for workbook_path in WORKBOOKS_WITH_VBA:
        assert workbook_path.suffix.lower() == ".xlsm", (
            f"VBA inventory scope only includes macro-enabled workbook sources: {workbook_path}"
        )
    assert MODULE_SOURCE_EXTENSION == ".bas", "VBA module sources must be stored as .bas files."
    for file_name in ALLOWED_NON_MODULE_FILES:
        assert (VBA_SOURCE_DIR / file_name).is_file(), (
            f"Allowed non-module VBA artifact missing from scope: {VBA_SOURCE_DIR / file_name}"
        )


def test_all_embedded_vba_modules_have_bas_sources() -> None:
    discovered_modules: set[str] = set()
    for workbook_path in WORKBOOKS_WITH_VBA:
        assert workbook_path.is_file(), f"Expected workbook fixture to exist: {workbook_path}"
        discovered_modules.update(_extract_module_names(workbook_path))

    assert discovered_modules, "No VBA modules were discovered in workbook fixtures."

    bas_module_names = {path.stem for path in VBA_SOURCE_DIR.glob(f"*{MODULE_SOURCE_EXTENSION}")}
    missing_modules = sorted(discovered_modules - bas_module_names)
    assert not missing_modules, "Missing VBA module source files in assets/vba: " + ", ".join(
        f"{name}{MODULE_SOURCE_EXTENSION}" for name in missing_modules
    )

    wrong_extension_files = sorted(
        str(path.relative_to(VBA_SOURCE_DIR))
        for path in VBA_SOURCE_DIR.iterdir()
        if path.is_file()
        and path.stem in discovered_modules
        and path.suffix.lower() != MODULE_SOURCE_EXTENSION
    )
    assert not wrong_extension_files, (
        f"VBA modules must be committed with {MODULE_SOURCE_EXTENSION} extensions only: "
        + ", ".join(wrong_extension_files)
    )

    unexpected_non_module_files = sorted(
        str(path.relative_to(VBA_SOURCE_DIR))
        for path in VBA_SOURCE_DIR.iterdir()
        if path.is_file()
        and path.stem not in discovered_modules
        and path.name not in ALLOWED_NON_MODULE_FILES
    )
    assert not unexpected_non_module_files, (
        "assets/vba contains files outside module inventory scope: "
        + ", ".join(unexpected_non_module_files)
    )

    for module_name in sorted(discovered_modules):
        module_path = VBA_SOURCE_DIR / f"{module_name}{MODULE_SOURCE_EXTENSION}"
        source = module_path.read_text(encoding="utf-8")
        assert f'Attribute VB_Name = "{module_name}"' in source, (
            f"{module_path} does not declare the expected VB module name {module_name}."
        )
