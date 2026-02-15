"""Centralized retrieval helpers for the internal MOSERS template workbook."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_TEMPLATE_NAME = "mosers_template.xlsx"


def get_mosers_template_path() -> Path:
    """Return the filesystem path to the bundled MOSERS workbook template."""

    template_path = Path(__file__).with_name(_TEMPLATE_NAME)
    if not template_path.exists():
        raise FileNotFoundError(f"MOSERS template workbook not found: {template_path}")
    return template_path


def get_mosers_template_bytes() -> bytes:
    """Return the raw bytes for the bundled MOSERS workbook template."""

    return get_mosers_template_path().read_bytes()


def load_mosers_template_workbook() -> Any:
    """Load the internal MOSERS template workbook into an editable openpyxl workbook."""

    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("openpyxl is required to load MOSERS template workbooks") from exc

    return load_workbook(filename=get_mosers_template_path())
