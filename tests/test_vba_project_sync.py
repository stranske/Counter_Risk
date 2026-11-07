"""Strict project parsing and Excel export boundary tests."""

import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts import create_vba_project, extract_vba_modules
from scripts import sync_vba_project_runnerlaunch_mirror as sync
from scripts.vba_project import CompoundFile, decompress, project_modules

FIXTURE = Path(__file__).parent / "fixtures/vba/excel_saved.bin"


def test_extract_excel_saved_project(tmp_path):
    expected = 'Attribute VB_Name = "Module1"\nSub say_hello()\n    MsgBox ("Hello from Python!")\nEnd Sub\n'
    path = tmp_path / "excel.xlsm"
    with ZipFile(path, "w") as workbook:
        workbook.writestr("xl/vbaProject.bin", FIXTURE.read_bytes())
    modules = extract_vba_modules.extract_modules_from_workbook(path)
    assert modules["Module1"] == expected
    assert set(modules) == {"Module1", "Sheet1", "Sheet2", "ThisWorkbook", "ThisWorkbook1"}


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(504),
        b'Attribute VB_Name = "RunnerLaunch"',
        FIXTURE.read_bytes()[:-1],
    ],
)
def test_malformed_projects_are_rejected(data):
    with pytest.raises(ValueError):
        project_modules(data)


@pytest.mark.parametrize("data", [b"", b"\x01\x00", b"\x01\x02\xb0\x01\x00\x00"])
def test_malformed_compression_is_rejected(data):
    with pytest.raises(ValueError):
        decompress(data)


def test_sync_passes_selected_absolute_paths_and_preserves_output_on_failure(tmp_path, monkeypatch):
    cwd = tmp_path / "unrelated"
    cwd.mkdir()
    bas = cwd / "custom.bas"
    bas.write_text('Attribute VB_Name = "RunnerLaunch"\nSub ChangedBody()\nEnd Sub\n')
    project = cwd / "selected.bin"
    project.write_bytes(b"preserve output")
    workbook = cwd / "selected.xlsm"
    observed = []

    def failed(command, **kwargs):
        observed.append(command)
        return subprocess.CompletedProcess(command, 1, "stdout diagnostic", "stderr traceback")

    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sync.subprocess, "run", failed)
    with pytest.raises(RuntimeError, match="stdout diagnostic[\\s\\S]*stderr traceback"):
        sync.sync_vba_project(
            bas_path=Path("custom.bas"),
            project_path=Path("selected.bin"),
            workbook_path=Path("selected.xlsm"),
        )
    command = observed[0]
    assert command[command.index("--bas-path") + 1] == str(bas)
    assert command[command.index("--workbook-path") + 1] == str(workbook)
    assert Path(command[command.index("--project-path") + 1]).is_absolute()
    assert project.read_bytes() == b"preserve output"


def test_sync_rejects_valid_but_wrong_module_and_preserves_output(tmp_path, monkeypatch):
    bas = tmp_path / "custom.bas"
    bas.write_text('Attribute VB_Name = "RunnerLaunch"\nSub ChangedBody()\nEnd Sub\n')
    output = tmp_path / "output.bin"
    output.write_bytes(b"original")

    def export(command, **kwargs):
        Path(command[command.index("--project-path") + 1]).write_bytes(FIXTURE.read_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sync.subprocess, "run", export)
    with pytest.raises(ValueError, match="differs"):
        sync.sync_vba_project(
            bas_path=bas, project_path=output, workbook_path=tmp_path / "input.xlsm"
        )
    assert output.read_bytes() == b"original"


def test_excel_export_requires_valid_input_before_starting_excel(tmp_path):
    bas = tmp_path / "RunnerLaunch.bas"
    bas.write_text('Attribute VB_Name = "RunnerLaunch"\n')
    workbook = tmp_path / "invalid.xlsm"
    with ZipFile(workbook, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"fake")
    output = tmp_path / "output.bin"
    output.write_bytes(b"original")
    with pytest.raises(ValueError, match="CFB"):
        create_vba_project.create_vba_project(
            bas_path=bas, workbook_path=workbook, output_path=output
        )
    assert output.read_bytes() == b"original"


def test_fixture_unrelated_streams_are_present():
    assert {"PROJECT", "PROJECTwm", "VBA/dir", "VBA/Module1"} <= CompoundFile(
        FIXTURE.read_bytes()
    ).streams.keys()


def test_extraction_reads_changed_actual_handler_body():
    original = FIXTURE.read_bytes()
    changed = original.replace(b"om Pytho\x08n!", b"om Codin\x08g!")
    assert changed != original
    assert b"Hello from Python!" in changed  # Stale cache must not win over source.
    modules = project_modules(changed)
    assert 'MsgBox ("Hello from Coding!")' in modules["Module1"]
    assert project_modules(original)["Sheet1"] == modules["Sheet1"]
