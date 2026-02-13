from __future__ import annotations

from pathlib import Path

import pytest


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
