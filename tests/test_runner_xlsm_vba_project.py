"""Deterministic tests for the embedded VBA project in Runner.xlsm."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

RUNNER_WORKBOOK_PATH = Path("Runner.xlsm")
VBA_PROJECT_BIN_PATH = "xl/vbaProject.bin"


def _extract_vba_project_bin_bytes(workbook_path: Path = RUNNER_WORKBOOK_PATH) -> bytes:
    """Return raw bytes for the embedded VBA project from a macro-enabled workbook."""
    with ZipFile(workbook_path) as zip_file, zip_file.open(VBA_PROJECT_BIN_PATH) as handle:
        return handle.read()


def test_extract_vba_project_bin_bytes_returns_binary_payload() -> None:
    vba_project = _extract_vba_project_bin_bytes()

    assert isinstance(vba_project, bytes)
    assert len(vba_project) > 0
