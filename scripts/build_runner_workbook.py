"""Build the Excel Runner workbook artifact.

This script creates ``Runner.xlsm`` with a month selector dropdown on cell ``B3``.
The dropdown values are sourced from a hidden ``ControlData`` sheet so the workbook
can be validated deterministically in tests without relying on Excel automation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from counter_risk.runner_date_control import (
    DateInputControl,
    define_runner_xlsm_date_control_scope,
)

OUTPUT_PATH = Path("Runner.xlsm")
VBA_PROJECT_PATH = Path("assets/vba/vbaProject.bin")


def _month_end_dates(start_year: int, start_month: int, end_year: int, end_month: int) -> list[str]:
    values: list[str] = []
    year = start_year
    month = start_month

    while (year, month) <= (end_year, end_month):
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        month_end = next_month.fromordinal(next_month.toordinal() - 1)
        values.append(month_end.isoformat())

        month += 1
        if month == 13:
            month = 1
            year += 1

    return values


def _inline_str_cell(cell_ref: str, value: str) -> str:
    return f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _runner_sheet_xml(validation_formula: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:D12"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
    <row r="1">
      {_inline_str_cell("A1", "Counter Risk Runner")}
    </row>
    <row r="2">
      {_inline_str_cell("A2", "Select reporting month-end date and choose a run mode.")}
    </row>
    <row r="3">
      {_inline_str_cell("A3", "As-Of Month")}
      <c r="B3"/>
    </row>
    <row r="5">
      {_inline_str_cell("A5", "Run All")}
      {_inline_str_cell("B5", "Run Ex Trend")}
      {_inline_str_cell("C5", "Run Trend")}
      {_inline_str_cell("D5", "Open Output Folder")}
    </row>
  </sheetData>
  <dataValidations count="1">
    <dataValidation type="list" allowBlank="0" showErrorMessage="1" sqref="B3">
      <formula1>{escape(validation_formula)}</formula1>
    </dataValidation>
  </dataValidations>
</worksheet>
"""


def _control_data_sheet_xml(month_values: list[str]) -> str:
    rows = [
        f'<row r="1">{_inline_str_cell("A1", "MonthEnd")}</row>',
    ]
    for index, value in enumerate(month_values, start=2):
        rows.append(f'<row r="{index}">{_inline_str_cell(f"A{index}", value)}</row>')

    rows_xml = "\n    ".join(rows)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:A{len(month_values) + 1}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
    {rows_xml}
  </sheetData>
</worksheet>
"""


def _workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <fileVersion appName="xl"/>
  <workbookPr/>
  <bookViews>
    <workbookView activeTab="0"/>
  </bookViews>
  <sheets>
    <sheet name="Runner" sheetId="1" r:id="rId1"/>
    <sheet name="ControlData" sheetId="2" state="hidden" r:id="rId2"/>
  </sheets>
</workbook>
"""


def _workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>
</Relationships>
"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="1"><xf xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/>
  <Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _core_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcmitype="http://purl.org/dc/dcmitype/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Counter Risk Runner</dc:title>
  <dc:creator>Counter Risk</dc:creator>
  <cp:lastModifiedBy>Counter Risk</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-02-13T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-02-13T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""


def _extended_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
    xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Excel</Application>
</Properties>
"""


def _write_zip_member(zip_file: ZipFile, member_path: str, content: str) -> None:
    zip_info = ZipInfo(member_path)
    zip_info.date_time = (1980, 1, 1, 0, 0, 0)
    zip_info.compress_type = ZIP_DEFLATED
    zip_file.writestr(zip_info, content.encode("utf-8"))


def _write_zip_binary_member(zip_file: ZipFile, member_path: str, content: bytes) -> None:
    zip_info = ZipInfo(member_path)
    zip_info.date_time = (1980, 1, 1, 0, 0, 0)
    zip_info.compress_type = ZIP_DEFLATED
    zip_file.writestr(zip_info, content)


def build_runner_workbook(path: Path = OUTPUT_PATH) -> None:
    scope = define_runner_xlsm_date_control_scope()
    if scope.decision.selected_control is not DateInputControl.MONTH_SELECTOR:
        msg = "Runner workbook builder currently supports month-selector control only."
        raise ValueError(msg)

    month_values = _month_end_dates(2020, 1, 2035, 12)
    vba_project_bin = VBA_PROJECT_PATH.read_bytes()
    data_start_row = 2
    data_end_row = data_start_row + len(month_values) - 1
    validation_formula = f"ControlData!$A${data_start_row}:$A${data_end_row}"

    with ZipFile(path, mode="w") as zip_file:
        _write_zip_member(zip_file, "[Content_Types].xml", _content_types_xml())
        _write_zip_member(zip_file, "_rels/.rels", _root_rels_xml())
        _write_zip_member(zip_file, "docProps/app.xml", _extended_properties_xml())
        _write_zip_member(zip_file, "docProps/core.xml", _core_properties_xml())
        _write_zip_member(zip_file, "xl/workbook.xml", _workbook_xml())
        _write_zip_member(zip_file, "xl/_rels/workbook.xml.rels", _workbook_rels_xml())
        _write_zip_member(zip_file, "xl/styles.xml", _styles_xml())
        _write_zip_binary_member(zip_file, "xl/vbaProject.bin", vba_project_bin)
        _write_zip_member(
            zip_file, "xl/worksheets/sheet1.xml", _runner_sheet_xml(validation_formula)
        )
        _write_zip_member(
            zip_file,
            "xl/worksheets/sheet2.xml",
            _control_data_sheet_xml(month_values),
        )


if __name__ == "__main__":
    build_runner_workbook()
