from __future__ import annotations

import hashlib
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest

_SYNTHETIC_MANIFEST = Path("tests/fixtures/SYNTHETIC_FIXTURES.sha256")
_PRODUCTION_ARTIFACT_NAME = re.compile(
    r"(?:MOSERS Counterparty Risk Summary|Historical Counterparty Risk Graphs|"
    r"NISA Drop-In Template|Monthly Counterparty Exposure Report|"
    r"Counterparty Risk Report Procedures)",
    re.IGNORECASE,
)
_PRODUCTION_NARRATIVE_TEXT = re.compile(
    rb"Data sources:|Prospective (?:credit|equity|fixed income)|Correlation estimates|"
    rb"Risk includes the",
    re.IGNORECASE,
)
_PRODUCTION_VALUE_TEXT = re.compile(
    rb"613563453\.14|2437132088\.31|4647960361\.939|124181574\.6156|"
    rb"10837843\.75|7811999634\.2546|13704178\.2738|2422820068\.71|"
    rb"4578574679\.329|124131536\.3156|7739089737\.494599|224224528\.0238|"
    rb"153080581\.45"
)


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


def test_synthetic_fixture_hashes_match_reviewed_manifest() -> None:
    for line in _SYNTHETIC_MANIFEST.read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split("  ", maxsplit=1)
        fixture_path = Path(relative_path)
        assert fixture_path.is_file(), f"Missing synthetic fixture: {fixture_path}"
        actual_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        assert (
            actual_hash == expected_hash
        ), f"Synthetic fixture changed without manifest review: {fixture_path}"


def test_production_named_office_artifacts_are_not_tracked_as_docs() -> None:
    roots = (Path("docs"), Path(".github"))
    offenders = sorted(
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".docx", ".pptx", ".xlsx", ".xlsm"}
        and _PRODUCTION_ARTIFACT_NAME.search(path.name)
    )
    assert offenders == []


def test_reconstructed_workbooks_have_no_hidden_office_payloads() -> None:
    fixture_paths = [
        Path(line.split("  ", maxsplit=1)[1])
        for line in _SYNTHETIC_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.endswith(".xlsx")
    ]
    forbidden_part_names = ("externalLinks", "connections", "comments", "drawings", "media")
    for fixture_path in fixture_paths:
        with ZipFile(fixture_path) as archive:
            hidden_parts = [
                name
                for name in archive.namelist()
                if any(token.casefold() in name.casefold() for token in forbidden_part_names)
            ]
            searchable_xml = b"".join(
                archive.read(name)
                for name in archive.namelist()
                if name.endswith((".xml", ".rels"))
            )
        assert hidden_parts == [], f"Hidden Office payloads remain in {fixture_path}"
        assert not _PRODUCTION_NARRATIVE_TEXT.search(
            searchable_xml
        ), f"Production-derived narrative remains in {fixture_path}"
        assert not _PRODUCTION_VALUE_TEXT.search(
            searchable_xml
        ), f"Known production-derived value remains in {fixture_path}"


def test_reconstructed_presentation_contains_only_synthetic_embedded_images() -> None:
    fixture_path = Path("tests/fixtures/Monthly Counterparty Exposure Report.pptx")
    with ZipFile(fixture_path) as archive:
        media_parts = sorted(name for name in archive.namelist() if name.startswith("ppt/media/"))
        media_hashes = {hashlib.sha256(archive.read(name)).hexdigest() for name in media_parts}
        searchable_xml = b"".join(
            archive.read(name) for name in archive.namelist() if name.endswith((".xml", ".rels"))
        )

    assert len(media_parts) == 6
    assert len(media_hashes) == 1
    assert b'TargetMode="External"' not in searchable_xml
    assert not _PRODUCTION_NARRATIVE_TEXT.search(searchable_xml)
    assert not _PRODUCTION_VALUE_TEXT.search(searchable_xml)


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
        # The real NISA workbook's tab is "Exposure Maturity Schedule" and lays out
        # product blocks (label, then Reverse Repo / Repo / Total Return Swaps /
        # Total columns) with maturity dates beside each block -- not the flat
        # Counterparty/Product Type/Bucket table an earlier revision assumed.
        assert "Exposure Maturity Schedule" in workbook.sheetnames
        worksheet = workbook["Exposure Maturity Schedule"]
        text_cells = {
            str(worksheet.cell(row=row, column=column).value).strip()
            for row in range(1, min(worksheet.max_row, 20) + 1)
            for column in range(1, min(worksheet.max_column, 10) + 1)
            if worksheet.cell(row=row, column=column).value is not None
        }
        assert "Px Date" in text_cells
        # WAL tracks the TIPS block, so the fixture must carry one.
        assert any(
            cell.upper().startswith("NISA ") and "TIPS" in cell.upper() for cell in text_cells
        )
        assert "Total" in text_cells
    finally:
        workbook.close()
