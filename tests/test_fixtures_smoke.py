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
    already_validated_fixture_names = {
        "NISA Monthly All Programs - Raw.xlsx",
        "NISA Monthly Ex Trend - Raw.xlsx",
        "NISA Monthly Trend - Raw.xlsx",
        "mosers_reference.xlsx",
    }
    fixture_paths = sorted(
        path
        for path in fixtures_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".pptx", ".xlsx"}
        and path.name not in already_validated_fixture_names
    )
    assert fixture_paths, f"No .pptx/.xlsx fixtures found under {fixtures_root}."
    assert len(fixture_paths) >= 10, "Expected representative fixture inventory under tests/fixtures."

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
