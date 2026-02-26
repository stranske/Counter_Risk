"""Tests for XLSM artifact generation from the base template."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from counter_risk.build import xlsm


def _read_zip_text(path: Path, member: str) -> str:
    with ZipFile(path) as workbook, workbook.open(member) as handle:
        return handle.read().decode("utf-8", errors="ignore")


def test_build_xlsm_artifact_copies_template_and_keeps_required_excel_parts(tmp_path: Path) -> None:
    output_path = tmp_path / "Runner.generated.xlsm"

    built = xlsm.build_xlsm_artifact(
        template_path=Path("assets/templates/counter_risk_template.xlsm"),
        output_path=output_path,
        as_of_date=date(2026, 1, 31),
        run_date=datetime(2026, 2, 26, 12, 0, tzinfo=UTC),
        version="1.2.3",
    )

    assert built == output_path
    assert built.is_file()
    with ZipFile(built) as workbook:
        members = set(workbook.namelist())
    assert "[Content_Types].xml" in members
    assert "xl/workbook.xml" in members
    assert "xl/vbaProject.bin" in members
    assert "docProps/core.xml" in members


def test_build_xlsm_artifact_injects_metadata_into_core_properties(tmp_path: Path) -> None:
    output_path = tmp_path / "Runner.generated.xlsm"

    xlsm.build_xlsm_artifact(
        template_path=Path("assets/templates/counter_risk_template.xlsm"),
        output_path=output_path,
        as_of_date=date(2026, 1, 31),
        run_date=datetime(2026, 2, 26, 12, 34, 56, tzinfo=UTC),
        version="9.9.9",
    )

    core_xml = _read_zip_text(output_path, "docProps/core.xml")
    assert "Counter Risk Runner" in core_xml
    assert "as_of_date=2026-01-31" in core_xml
    assert "version=9.9.9" in core_xml
    assert "2026-02-26T12:34:56Z" in core_xml


def test_build_xlsm_artifact_retains_runnerlaunch_vba_markers(tmp_path: Path) -> None:
    output_path = tmp_path / "Runner.generated.xlsm"

    xlsm.build_xlsm_artifact(
        template_path=Path("assets/templates/counter_risk_template.xlsm"),
        output_path=output_path,
        as_of_date=date(2026, 1, 31),
        run_date=datetime(2026, 2, 26, 12, 0, tzinfo=UTC),
        version="1.2.3",
    )

    with ZipFile(output_path) as workbook, workbook.open("xl/vbaProject.bin") as handle:
        vba_text = handle.read().decode("latin-1", errors="ignore")

    assert 'Attribute VB_Name = "RunnerLaunch"' in vba_text
    assert "Public Sub RunAll_Click()" in vba_text
    assert "Public Sub RunExTrend_Click()" in vba_text
    assert "Public Sub RunTrend_Click()" in vba_text


def test_build_xlsm_artifact_raises_for_missing_template(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Template XLSM was not found"):
        xlsm.build_xlsm_artifact(
            template_path=tmp_path / "missing-template.xlsm",
            output_path=tmp_path / "out.xlsm",
            as_of_date=date(2026, 1, 31),
            run_date=datetime(2026, 2, 26, 12, 0, tzinfo=UTC),
            version="1.2.3",
        )


def test_main_builds_xlsm_artifact_from_cli(tmp_path: Path) -> None:
    output_path = tmp_path / "Runner.generated.xlsm"

    result = xlsm.main(
        [
            "--template-path",
            "assets/templates/counter_risk_template.xlsm",
            "--output-path",
            str(output_path),
            "--as-of-date",
            "2026-01-31",
            "--run-date",
            "2026-02-26T12:00:00+00:00",
            "--version",
            "2.0.0",
        ]
    )

    assert result == 0
    assert output_path.is_file()


def test_build_xlsm_artifact_preserves_vba_project_across_version_updates(tmp_path: Path) -> None:
    output_v1 = tmp_path / "Runner.v1.xlsm"
    output_v2 = tmp_path / "Runner.v2.xlsm"

    xlsm.build_xlsm_artifact(
        template_path=Path("assets/templates/counter_risk_template.xlsm"),
        output_path=output_v1,
        as_of_date=date(2026, 1, 31),
        run_date=datetime(2026, 2, 26, 12, 0, tzinfo=UTC),
        version="1.2.3",
    )
    xlsm.build_xlsm_artifact(
        template_path=Path("assets/templates/counter_risk_template.xlsm"),
        output_path=output_v2,
        as_of_date=date(2026, 1, 31),
        run_date=datetime(2026, 2, 26, 12, 0, tzinfo=UTC),
        version="1.2.4",
    )

    with (
        ZipFile(output_v1) as workbook_v1,
        ZipFile(output_v2) as workbook_v2,
        workbook_v1.open("xl/vbaProject.bin") as vba_v1,
        workbook_v2.open("xl/vbaProject.bin") as vba_v2,
    ):
        assert vba_v1.read() == vba_v2.read()


def test_runner_xlsm_manual_macro_verification_doc_is_present_and_actionable() -> None:
    doc_path = Path("docs/runner_xlsm_macro_manual_verification.md")
    content = doc_path.read_text(encoding="utf-8")

    assert doc_path.is_file()
    assert "Manual Macro/Button Check" in content
    assert "Enable Content" in content
    assert "RunAll_Click" in content
    assert "RunExTrend_Click" in content
    assert "RunTrend_Click" in content
    assert "OpenOutputFolder_Click" in content
    assert "Version Bump Regression Check" in content
    assert "--version 1.2.4" in content
