"""Guard runtime imports against being declared only in developer extras."""

from __future__ import annotations

import importlib
import importlib.util
import tomllib
from pathlib import Path

_RUNTIME_IMPORTS = {
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "pydantic": "pydantic",
    "PyYAML": "yaml",
    "python-pptx": "pptx",
    "Pillow": "PIL",
}


def _dependency_name(requirement: str) -> str:
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if separator in requirement:
            requirement = requirement.split(separator, 1)[0]
            break
    return requirement.strip().split("[", 1)[0].lower()


def test_runtime_imports_are_project_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime_dependencies = {
        _dependency_name(requirement) for requirement in project["dependencies"]
    }

    missing_imports = []
    for module_name in _RUNTIME_IMPORTS.values():
        if importlib.util.find_spec(module_name) is None:
            missing_imports.append(module_name)
            continue
        importlib.import_module(module_name)
    missing_declarations = [
        distribution
        for distribution in _RUNTIME_IMPORTS
        if distribution.lower() not in runtime_dependencies
    ]

    assert not missing_imports, "Runtime import modules are unavailable: " + ", ".join(
        missing_imports
    )
    assert (
        not missing_declarations
    ), "Runtime imports must be declared in [project.dependencies], not only extras: " + ", ".join(
        missing_declarations
    )


def test_pywin32_declared_as_windows_only_dependency() -> None:
    """pywin32 must be in [project.dependencies] with a sys_platform=='win32' marker."""
    import tomllib

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    deps: list[str] = project["dependencies"]

    pywin32_entries = [d for d in deps if d.lower().startswith("pywin32")]
    assert pywin32_entries, "pywin32 must be listed in [project.dependencies]"

    entry = pywin32_entries[0].lower()
    assert "sys_platform" in entry and "win32" in entry, (
        f"pywin32 entry must carry a sys_platform == 'win32' marker; got: {pywin32_entries[0]!r}"
    )
