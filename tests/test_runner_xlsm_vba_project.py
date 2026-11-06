"""Deterministic tests for the embedded VBA project in Runner.xlsm.

These tests intentionally avoid checksum fixtures and instead validate the
presence/absence of specific VBA source markers that define the required
Runner behavior.
"""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

RUNNER_WORKBOOK_PATH = Path("Runner.xlsm")
VBA_PROJECT_BIN_PATH = "xl/vbaProject.bin"
_OLE_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

WINDOWS_RUN_FOLDER_FORMAT_LITERAL = "yyyy-mm-dd"
WINDOWS_RUN_FOLDER_FORMAT_REGEX = re.compile(
    r"BuildRunFolderName\(\s*baseName\s*,\s*suffixIndex\s*\)",
    flags=re.IGNORECASE,
)


def _extract_embedded_vba_text(workbook_path: Path = RUNNER_WORKBOOK_PATH) -> str:
    with ZipFile(workbook_path) as zip_file, zip_file.open(VBA_PROJECT_BIN_PATH) as handle:
        raw = handle.read()
    # Real OLE projects store module source as UTF-16LE. Legacy pseudo-projects
    # stored the same markers as latin-1 text.
    if raw.startswith(_OLE_CFB_SIGNATURE):
        return raw.decode("utf-16le", errors="ignore")
    return raw.decode("latin-1", errors="ignore")


def _load_runnerlaunch_bas_source() -> str:
    return Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")


def test_runnerlaunch_bas_contains_required_behavior_markers() -> None:
    source = _load_runnerlaunch_bas_source()

    assert "Public Function BuildCommand" in source
    assert "Public Function ExecuteRunnerCommand" in source
    assert "Public Function ResolveOutputDir" in source

    assert "ResolveRepoRoot()" in source
    assert "RUN_FOLDER_FORMAT" in source
    assert f'RUN_FOLDER_FORMAT As String = "{WINDOWS_RUN_FOLDER_FORMAT_LITERAL}"' in source
    assert "Public Function ResolveExistingOutputDir" in source

    assert "PRE_LAUNCH_STATUS" in source
    assert "POST_LAUNCH_STATUS" in source
    assert "COMPLETE_STATUS" in source

    assert 'ResolveOutputDir("."' not in source
    assert WINDOWS_RUN_FOLDER_FORMAT_REGEX.search(source) is not None


def test_runner_workbook_embeds_required_runnerlaunch_markers() -> None:
    vba_text = _extract_embedded_vba_text()

    assert 'Attribute VB_Name = "RunnerLaunch"' in vba_text
    assert "Public Function BuildCommand" in vba_text
    assert "Public Function ExecuteRunnerCommand" in vba_text
    assert "Public Function ResolveOutputDir" in vba_text

    assert "ResolveRepoRoot()" in vba_text
    assert f'RUN_FOLDER_FORMAT As String = "{WINDOWS_RUN_FOLDER_FORMAT_LITERAL}"' in vba_text
    assert "Public Function ResolveExistingOutputDir" in vba_text
    assert WINDOWS_RUN_FOLDER_FORMAT_REGEX.search(vba_text) is not None

    assert 'PRE_LAUNCH_STATUS As String = "Launching..."' in vba_text
    assert 'POST_LAUNCH_STATUS As String = "Finished"' in vba_text
    assert 'COMPLETE_STATUS As String = "Complete"' in vba_text

    assert 'ResolveOutputDir("."' not in vba_text
