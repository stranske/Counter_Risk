from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "fixture_name",
    [
        "NISA Monthly All Programs - Raw.xlsx",
        "NISA Monthly Ex Trend - Raw.xlsx",
        "NISA Monthly Trend - Raw.xlsx",
    ],
)
def test_raw_nisa_fixture_exists_and_opens(fixture_name: str) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    fixture_path = Path("tests/fixtures") / fixture_name
    assert fixture_path.exists(), f"Missing required fixture: {fixture_path}"

    workbook = openpyxl.load_workbook(
        filename=fixture_path,
        read_only=True,
        data_only=True,
    )
    try:
        assert workbook.sheetnames, "Raw NISA fixture workbook has no worksheets."
    finally:
        workbook.close()


def test_mosers_reference_fixture_exists_and_opens() -> None:
    openpyxl = pytest.importorskip("openpyxl")

    fixture_path = Path("tests/fixtures/mosers_reference.xlsx")
    assert fixture_path.exists(), f"Missing required fixture: {fixture_path}"

    try:
        workbook = openpyxl.load_workbook(
            filename=fixture_path,
            read_only=True,
            data_only=False,
        )
    except Exception as exc:  # pragma: no cover - depends on local file damage
        pytest.fail(f"Unable to load fixture workbook at {fixture_path}: {exc}")
    else:
        workbook.close()


def test_fixture_workbooks_and_presentations_open() -> None:
    pptx = pytest.importorskip("pptx")
    openpyxl = pytest.importorskip("openpyxl")

    fixtures_root = Path("tests/fixtures")
    fixture_paths = sorted(
        path
        for path in fixtures_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".pptx", ".xlsx"}
    )
    assert fixture_paths, f"No .pptx/.xlsx fixtures found under {fixtures_root}."

    for fixture_path in fixture_paths:
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
