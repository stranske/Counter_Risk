from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.utils.xlsx_compare import compare_workbooks


def _create_workbook(path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "base"
    sheet["A1"].number_format = "0.00"
    sheet["A1"].font = openpyxl.styles.Font(
        name="Calibri",
        bold=True,
        size=11,
    )
    sheet["A1"].fill = openpyxl.styles.PatternFill(
        fill_type="solid",
        fgColor="00FF0000",
        bgColor="00FF0000",
    )
    sheet["A1"].alignment = openpyxl.styles.Alignment(
        horizontal="center",
        vertical="center",
    )
    sheet["A1"].border = openpyxl.styles.Border(
        left=openpyxl.styles.Side(style="thin"),
    )

    workbook.save(path)
    workbook.close()


@pytest.mark.parametrize(
    ("property_name", "mutate"),
    [
        ("value", lambda cell, openpyxl: setattr(cell, "value", "changed")),
        ("number_format", lambda cell, openpyxl: setattr(cell, "number_format", "0%")),
        (
            "font",
            lambda cell, openpyxl: setattr(
                cell,
                "font",
                openpyxl.styles.Font(name="Arial"),
            ),
        ),
        (
            "fill",
            lambda cell, openpyxl: setattr(
                cell,
                "fill",
                openpyxl.styles.PatternFill(
                    fill_type="solid",
                    fgColor="0000FF00",
                ),
            ),
        ),
        (
            "alignment",
            lambda cell, openpyxl: setattr(
                cell,
                "alignment",
                openpyxl.styles.Alignment(
                    horizontal="left",
                    vertical="bottom",
                ),
            ),
        ),
        (
            "border",
            lambda cell, openpyxl: setattr(
                cell,
                "border",
                openpyxl.styles.Border(
                    right=openpyxl.styles.Side(style="medium"),
                ),
            ),
        ),
    ],
)
def test_compare_workbooks_reports_sheet_coordinate_property_expected_and_actual(
    tmp_path: Path,
    property_name: str,
    mutate: Callable[[Any, Any], None],
) -> None:
    openpyxl = pytest.importorskip("openpyxl")

    reference = tmp_path / "reference.xlsx"
    generated = tmp_path / "generated.xlsx"
    _create_workbook(reference)
    _create_workbook(generated)

    workbook = openpyxl.load_workbook(generated)
    try:
        cell = workbook["Sheet1"]["A1"]
        mutate(cell, openpyxl)
        workbook.save(generated)
    finally:
        workbook.close()

    with pytest.raises(AssertionError) as exc_info:
        compare_workbooks(
            reference_workbook=reference,
            generated_workbook=generated,
            sheet_names=["Sheet1"],
            ranges_by_sheet={"Sheet1": "A1"},
        )

    message = str(exc_info.value)
    assert "sheet='Sheet1'" in message
    assert "cell='A1'" in message
    assert f"property='{property_name}'" in message
    assert "expected=" in message
    assert "actual=" in message
