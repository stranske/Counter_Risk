from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest


def _assert_office_zip_container(path: Path) -> None:
    assert path.exists(), f"Missing required fixture: {path}"
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
    except BadZipFile as exc:  # pragma: no cover - depends on local file damage
        pytest.fail(f"Fixture is not a readable Office ZIP container at {path}: {exc}")

    assert "[Content_Types].xml" in names, f"Fixture missing [Content_Types].xml: {path}"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "NISA Monthly All Programs - Raw.xlsx",
        "NISA Monthly Ex Trend - Raw.xlsx",
        "NISA Monthly Trend - Raw.xlsx",
    ],
)
def test_raw_nisa_fixture_exists_and_opens(fixture_name: str) -> None:
    fixture_path = Path("tests/fixtures") / fixture_name
    _assert_office_zip_container(fixture_path)


def test_mosers_reference_fixture_exists_and_opens() -> None:
    fixture_path = Path("tests/fixtures/mosers_reference.xlsx")
    _assert_office_zip_container(fixture_path)


def test_fixture_workbooks_and_presentations_open() -> None:
    pptx = pytest.importorskip("pptx")
    openpyxl = pytest.importorskip("openpyxl")

    fixtures_root = Path("tests/fixtures")
    already_validated_fixture_names = {
        "NISA Monthly All Programs - Raw.xlsx",
        "NISA Monthly Ex Trend - Raw.xlsx",
        "NISA Monthly Trend - Raw.xlsx",
        "mosers_reference.xlsx",
    }
    fixture_paths = sorted(
        path
        for path in fixtures_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".pptx", ".xlsx"}
        and path.name not in already_validated_fixture_names
    )
    assert fixture_paths, f"No .pptx/.xlsx fixtures found under {fixtures_root}."
    assert (
        len(fixture_paths) >= 10
    ), "Expected representative fixture inventory under tests/fixtures."

    workbook_fixtures = [path for path in fixture_paths if path.suffix.lower() == ".xlsx"]
    presentation_fixtures = [path for path in fixture_paths if path.suffix.lower() == ".pptx"]
    assert workbook_fixtures, "Expected at least one .xlsx fixture."
    assert presentation_fixtures, "Expected at least one .pptx fixture."

    sampled_fixture_paths = [
        min(workbook_fixtures, key=lambda path: path.stat().st_size),
        min(presentation_fixtures, key=lambda path: path.stat().st_size),
    ]

    for fixture_path in sampled_fixture_paths:
        if fixture_path.suffix.lower() == ".pptx":
            pptx.Presentation(str(fixture_path))
            continue

        workbook = openpyxl.load_workbook(
            filename=fixture_path,
            read_only=True,
            data_only=True,
        )
        workbook.close()


def test_wal_exposure_summary_fixture_exists_and_has_expected_headers() -> None:
    openpyxl = pytest.importorskip("openpyxl")

    fixture_path = Path("tests/fixtures/nisa/NISA_Monthly_Exposure_Summary_sanitized.xlsx")
    assert fixture_path.exists(), f"Missing required WAL fixture: {fixture_path}"

    workbook = openpyxl.load_workbook(
        filename=fixture_path,
        read_only=True,
        data_only=True,
    )
    try:
        assert "Exposure Maturity Summary" in workbook.sheetnames
        worksheet = workbook["Exposure Maturity Summary"]
        headers = [worksheet.cell(row=1, column=column).value for column in range(1, 7)]
        assert headers == [
            "Counterparty",
            "Product Type",
            "Current Exposure",
            "Years to Maturity",
            "Maturity Date",
            "Bucket",
        ]
    finally:
        workbook.close()
