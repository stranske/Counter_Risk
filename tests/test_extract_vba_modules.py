from __future__ import annotations

from pathlib import Path

from scripts import extract_vba_modules


def test_extract_modules_from_workbook_reads_runnerlaunch() -> None:
    modules = extract_vba_modules.extract_modules_from_workbook(Path("Runner.xlsm"))

    assert "RunnerLaunch" in modules
    assert 'Attribute VB_Name = "RunnerLaunch"' in modules["RunnerLaunch"]


def test_write_and_check_modules_round_trip(tmp_path: Path) -> None:
    workbook_paths = (Path("Runner.xlsm"), Path("assets/templates/counter_risk_template.xlsm"))

    modules = extract_vba_modules.extract_modules_from_workbooks(workbook_paths)
    extract_vba_modules.write_modules(modules, tmp_path)

    expected = Path("assets/vba/RunnerLaunch.bas").read_text(encoding="utf-8")
    actual = (tmp_path / "RunnerLaunch.bas").read_text(encoding="utf-8")

    assert actual == expected
    assert extract_vba_modules.check_modules(modules, tmp_path) == ()


def test_check_mode_flags_outdated_module(tmp_path: Path) -> None:
    output_dir = tmp_path / "vba"
    output_dir.mkdir()
    (output_dir / "RunnerLaunch.bas").write_text(
        'Attribute VB_Name = "RunnerLaunch"\n', encoding="utf-8"
    )

    rc = extract_vba_modules.main(["--check", "--output-dir", str(output_dir), "Runner.xlsm"])

    assert rc == 1


def test_check_mode_passes_for_committed_vba_sources() -> None:
    rc = extract_vba_modules.main(["--check"])
    assert rc == 0
