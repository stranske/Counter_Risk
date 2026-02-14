"""Deterministic tests for the embedded VBA project in Runner.xlsm."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

RUNNER_WORKBOOK_PATH = Path("Runner.xlsm")
VBA_PROJECT_BIN_PATH = "xl/vbaProject.bin"
VBA_PROJECT_CHECKSUM_FIXTURE_PATH = Path("tests/fixtures/vba/vbaProject.bin.sha256")


def _extract_vba_project_bin_bytes(workbook_path: Path = RUNNER_WORKBOOK_PATH) -> bytes:
    """Return raw bytes for the embedded VBA project from a macro-enabled workbook."""
    with ZipFile(workbook_path) as zip_file, zip_file.open(VBA_PROJECT_BIN_PATH) as handle:
        return handle.read()


def _compute_sha256(payload: bytes) -> str:
    """Return lowercase SHA-256 for payload bytes."""
    return hashlib.sha256(payload).hexdigest()


def _load_expected_vba_project_checksum(
    fixture_path: Path = VBA_PROJECT_CHECKSUM_FIXTURE_PATH,
) -> str:
    """Load expected checksum from `<checksum>  xl/vbaProject.bin` fixture content."""
    fixture_content = fixture_path.read_text(encoding="utf-8").strip()
    checksum, _, artifact_path = fixture_content.partition("  ")
    assert artifact_path == VBA_PROJECT_BIN_PATH, (
        f"Expected fixture artifact path '{VBA_PROJECT_BIN_PATH}', got '{artifact_path}' in "
        f"{fixture_path}"
    )
    return checksum


def test_extract_vba_project_bin_bytes_returns_binary_payload() -> None:
    vba_project = _extract_vba_project_bin_bytes()

    assert isinstance(vba_project, bytes)
    assert len(vba_project) > 0


def test_runner_vba_project_bin_checksum_matches_fixture() -> None:
    expected_checksum = _load_expected_vba_project_checksum()
    actual_checksum = _compute_sha256(_extract_vba_project_bin_bytes())

    assert actual_checksum == expected_checksum, (
        "Embedded VBA project checksum mismatch for "
        f"{RUNNER_WORKBOOK_PATH}:{VBA_PROJECT_BIN_PATH}. "
        f"Expected {expected_checksum}, got {actual_checksum}."
    )
