"""Build the Excel Runner workbook artifact.

This script creates ``Runner.xlsm`` with a month selector dropdown on cell ``B3``.
The dropdown values are sourced from a hidden ``ControlData`` sheet so the workbook
can be validated deterministically in tests without relying on Excel automation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
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
OLE_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_SETTINGS_ROWS: tuple[tuple[str, str], ...] = (
    ("Input Root", "inputs"),
    ("Discovery Mode", "discover"),
    ("Strict Policy", "warn"),
    ("Formatting Profile", "default"),
    ("Output Root", "runs"),
)
_SETTINGS_NAMED_RANGES: tuple[tuple[str, str], ...] = (
    ("RunnerSetting_InputRoot", "Settings!$B$2"),
    ("RunnerSetting_DiscoveryMode", "Settings!$B$3"),
    ("RunnerSetting_StrictPolicy", "Settings!$B$4"),
    ("RunnerSetting_FormattingProfile", "Settings!$B$5"),
    ("RunnerSetting_OutputRoot", "Settings!$B$6"),
)
_CONFIG_ROWS: tuple[tuple[int, str], ...] = (
    (4, "MOSERS All Programs (.xlsx)"),
    (5, "MOSERS Ex-Trend (.xlsx)"),
    (6, "MOSERS Trend (.xlsx)"),
    (7, "Historical All Programs - 3yr (.xlsx)"),
    (8, "Historical Ex-LLC - 3yr (.xlsx)"),
    (9, "Historical LLC - 3yr (.xlsx)"),
    (10, "Monthly Report Template (.pptx)"),
)
_CONFIG_NAMED_RANGES: tuple[tuple[str, str], ...] = (
    ("RunnerConfig_MosersAllPrograms", "Config!$B$4"),
    ("RunnerConfig_MosersExTrend", "Config!$B$5"),
    ("RunnerConfig_MosersTrend", "Config!$B$6"),
    ("RunnerConfig_HistAllPrograms3yr", "Config!$B$7"),
    ("RunnerConfig_HistExLlc3yr", "Config!$B$8"),
    ("RunnerConfig_HistLlc3yr", "Config!$B$9"),
    ("RunnerConfig_MonthlyPptx", "Config!$B$10"),
)
_ACTION_CELLS: tuple[tuple[str, str], ...] = (
    ("A5", "Run All"),
    ("B5", "Run Ex Trend"),
    ("C5", "Run Trend"),
    ("D5", "Dry-Run Discovery"),
    ("E5", "Open Output Folder"),
    ("F5", "Open Manifest"),
    ("G5", "Open Summary"),
    ("H5", "Open PPT Folder"),
    ("I5", "Ask about this run"),
)


@dataclass(frozen=True)
class RunnerActionButton:
    cell_ref: str
    caption: str
    macro: str
    control_index: int

    @property
    def shape_id(self) -> int:
        return 1024 + self.control_index

    @property
    def relationship_id(self) -> str:
        return f"rId{self.control_index + 1}"

    @property
    def ctrl_prop_path(self) -> str:
        return f"xl/ctrlProps/ctrlProp{self.control_index}.xml"

    @property
    def macro_formula(self) -> str:
        return f"[0]!{self.macro}"


_RUNNER_ACTION_BUTTONS: tuple[RunnerActionButton, ...] = (
    RunnerActionButton("A5", "Run All", "RunAll_Click", 1),
    RunnerActionButton("B5", "Run Ex Trend", "RunExTrend_Click", 2),
    RunnerActionButton("C5", "Run Trend", "RunTrend_Click", 3),
    RunnerActionButton("E5", "Open Output Folder", "OpenOutputFolder_Click", 4),
    RunnerActionButton("F5", "Open Manifest", "OpenManifest_Click", 5),
    RunnerActionButton("G5", "Open Summary", "OpenSummary_Click", 6),
    RunnerActionButton("H5", "Open PPT Folder", "OpenPPTFolder_Click", 7),
)
_SPREADSHEET_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_CTRL_PROP_CONTENT_TYPE = "application/vnd.ms-excel.controlproperties+xml"
_CTRL_PROP_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/ctrlProp"


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


def _cell_coordinates(cell_ref: str) -> tuple[int, int]:
    column_letters = "".join(char for char in cell_ref if char.isalpha()).upper()
    row_number = int("".join(char for char in cell_ref if char.isdigit()))
    column_index = 0
    for char in column_letters:
        column_index = column_index * 26 + (ord(char) - ord("A") + 1)
    return column_index - 1, row_number - 1


def _runner_sheet_xml(validation_formula: str) -> str:
    action_cells = "\n      ".join(_inline_str_cell(cell_ref, caption) for cell_ref, caption in _ACTION_CELLS)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
           xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
           xmlns:xdr="{_SPREADSHEET_DRAWING_NS}"
           mc:Ignorable="x14">
  <dimension ref="A1:I12"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="9" width="20" customWidth="1"/>
  </cols>
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
    <row r="5" ht="24" customHeight="1">
      {action_cells}
    </row>
    <row r="7">
      {_inline_str_cell("A7", "Status")}
      <c r="B7"/>
    </row>
    <row r="8">
      {_inline_str_cell("A8", "Result")}
      <c r="B8"/>
    </row>
    <row r="9">
      {_inline_str_cell("A9", "Data Quality")}
      <c r="B9"/>
    </row>
  </sheetData>
  <dataValidations count="1">
    <dataValidation type="list" allowBlank="0" showErrorMessage="1" sqref="B3">
      <formula1>{escape(validation_formula)}</formula1>
    </dataValidation>
  </dataValidations>
  <legacyDrawing r:id="rId1"/>
  {_worksheet_controls_xml()}
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


def _settings_sheet_xml() -> str:
    rows = [
        '<row r="1">'
        + _inline_str_cell("A1", "Setting")
        + _inline_str_cell("B1", "Value")
        + "</row>"
    ]
    for index, (label, value) in enumerate(_SETTINGS_ROWS, start=2):
        rows.append(
            '<row r="{row}">{label_cell}{value_cell}</row>'.format(
                row=index,
                label_cell=_inline_str_cell(f"A{index}", label),
                value_cell=_inline_str_cell(f"B{index}", value),
            )
        )
    rows_xml = "\n    ".join(rows)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:B{len(_SETTINGS_ROWS) + 1}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
    {rows_xml}
  </sheetData>
</worksheet>
"""


def _config_sheet_xml() -> str:
    rows = [
        '<row r="1">'
        + _inline_str_cell("A1", "Counter Risk - File Path Configuration")
        + "</row>",
        '<row r="2">'
        + _inline_str_cell(
            "A2", "Enter full Windows paths in column B. Leave blank to use config/*.yml defaults."
        )
        + "</row>",
    ]
    for row_number, label in _CONFIG_ROWS:
        rows.append(f'<row r="{row_number}">{_inline_str_cell(f"A{row_number}", label)}</row>')
    rows_xml = "\n    ".join(rows)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:B10"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="1" width="38" customWidth="1"/>
    <col min="2" max="2" width="80" customWidth="1"/>
  </cols>
  <sheetData>
    {rows_xml}
  </sheetData>
</worksheet>
"""


def _worksheet_control_xml(button: RunnerActionButton) -> str:
    column_index, row_index = _cell_coordinates(button.cell_ref)
    macro_formula = escape(button.macro_formula)
    caption = escape(button.caption)
    relationship_id = button.relationship_id
    shape_id = button.shape_id
    return f"""  <mc:AlternateContent>
    <mc:Choice Requires="x14">
      <control shapeId="{shape_id}" r:id="{relationship_id}" name="{caption} Button">
        <controlPr locked="1" defaultSize="0" print="0" disabled="0" recalcAlways="0" uiObject="0" autoFill="0" autoLine="0" autoPict="0" macro="{macro_formula}" altText="{caption}" cf="pict" r:id="{relationship_id}">
          <anchor moveWithCells="1" sizeWithCells="1" z-order="{button.control_index}">
            <xdr:from>
              <xdr:col>{column_index}</xdr:col>
              <xdr:colOff>0</xdr:colOff>
              <xdr:row>{row_index}</xdr:row>
              <xdr:rowOff>0</xdr:rowOff>
            </xdr:from>
            <xdr:to>
              <xdr:col>{column_index + 1}</xdr:col>
              <xdr:colOff>0</xdr:colOff>
              <xdr:row>{row_index + 1}</xdr:row>
              <xdr:rowOff>0</xdr:rowOff>
            </xdr:to>
          </anchor>
        </controlPr>
      </control>
    </mc:Choice>
    <mc:Fallback/>
  </mc:AlternateContent>"""


def _worksheet_controls_xml() -> str:
    controls = "\n".join(_worksheet_control_xml(button) for button in _RUNNER_ACTION_BUTTONS)
    return f"""<controls>
{controls}
  </controls>"""


def _vml_anchor(button: RunnerActionButton) -> str:
    column_index, row_index = _cell_coordinates(button.cell_ref)
    return f"{column_index}, 2, {row_index}, 2, {column_index + 1}, 2, {row_index + 1}, 2"


def _vml_button_shape(button: RunnerActionButton) -> str:
    column_index, _ = _cell_coordinates(button.cell_ref)
    left_margin_pt = 2 + (column_index * 110)
    caption = escape(button.caption)
    macro_formula = escape(button.macro_formula)
    anchor = _vml_anchor(button)
    return f"""<v:shape id="_x0000_s{button.shape_id}" type="#_x0000_t201" style="position:absolute;margin-left:{left_margin_pt}pt;margin-top:60pt;width:104pt;height:18pt;z-index:{button.control_index};mso-wrap-style:tight" o:button="t" fillcolor="buttonFace [67]" strokecolor="windowText [64]" o:insetmode="auto"><v:fill color2="buttonFace [67]" o:detectmouseclick="t"/><o:lock v:ext="edit" rotation="t"/><v:textbox style="mso-direction-alt:auto" o:singleclick="f"><div style="text-align:center"><font face="Calibri" size="220" color="#000000">{caption}</font></div></v:textbox><x:ClientData ObjectType="Button"><x:Anchor>{anchor}</x:Anchor><x:PrintObject>False</x:PrintObject><x:AutoFill>False</x:AutoFill><x:FmlaMacro>{macro_formula}</x:FmlaMacro><x:TextHAlign>Center</x:TextHAlign><x:TextVAlign>Center</x:TextVAlign></x:ClientData></v:shape>"""


def _vml_drawing_xml() -> str:
    shapes = "".join(_vml_button_shape(button) for button in _RUNNER_ACTION_BUTTONS)
    return f"""<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel"><o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="1"/></o:shapelayout><v:shapetype id="_x0000_t201" coordsize="21600,21600" o:spt="201" path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/><v:path shadowok="f" o:extrusionok="f" strokeok="f" fillok="f" o:connecttype="rect"/><o:lock v:ext="edit" shapetype="t"/></v:shapetype>{shapes}</xml>"""


def _form_control_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<x14:formControlPr xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" objectType="Button" textHAlign="center" textVAlign="center" lockText="1"/>
"""


def _runner_sheet_rels_xml() -> str:
    ctrl_prop_rels = "\n".join(
        f'  <Relationship Id="{button.relationship_id}" Type="{_CTRL_PROP_REL_TYPE}" Target="../ctrlProps/ctrlProp{button.control_index}.xml"/>'
        for button in _RUNNER_ACTION_BUTTONS
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" Target="../drawings/vmlDrawing1.vml"/>
{ctrl_prop_rels}
</Relationships>
"""


def _workbook_xml() -> str:
    defined_names = "\n    ".join(
        f'<definedName name="{name}">{reference}</definedName>'
        for name, reference in (*_SETTINGS_NAMED_RANGES, *_CONFIG_NAMED_RANGES)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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
    <sheet name="Settings" sheetId="3" r:id="rId3"/>
    <sheet name="Config" sheetId="4" r:id="rId6"/>
  </sheets>
  <definedNames>
    {defined_names}
  </definedNames>
</workbook>
"""


def _workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId5" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>
  <Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>
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
    ctrl_prop_overrides = "\n  ".join(
        f'<Override PartName="/xl/ctrlProps/ctrlProp{button.control_index}.xml" ContentType="{_CTRL_PROP_CONTENT_TYPE}"/>'
        for button in _RUNNER_ACTION_BUTTONS
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/>
  <Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  {ctrl_prop_overrides}
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


def _load_vba_project_bin(path: Path | None = None) -> bytes:
    if path is None:
        path = VBA_PROJECT_PATH

    if not path.is_file():
        msg = f"Missing VBA project binary: {path}"
        raise FileNotFoundError(msg)

    content = path.read_bytes()
    if (
        len(content) < len(OLE_CFB_SIGNATURE)
        or content[: len(OLE_CFB_SIGNATURE)] != OLE_CFB_SIGNATURE
    ):
        msg = (
            "Invalid VBA project binary signature for "
            f"{path}; expected OLE/CFB header {OLE_CFB_SIGNATURE.hex(' ').upper()}"
        )
        raise ValueError(msg)

    return content


def build_runner_workbook(path: Path = OUTPUT_PATH) -> None:
    scope = define_runner_xlsm_date_control_scope()
    if scope.decision.selected_control is not DateInputControl.MONTH_SELECTOR:
        msg = "Runner workbook builder currently supports month-selector control only."
        raise ValueError(msg)

    month_values = _month_end_dates(2020, 1, 2035, 12)
    vba_project_bin = _load_vba_project_bin()
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
        _write_zip_member(zip_file, "xl/worksheets/_rels/sheet1.xml.rels", _runner_sheet_rels_xml())
        _write_zip_member(zip_file, "xl/drawings/vmlDrawing1.vml", _vml_drawing_xml())
        for button in _RUNNER_ACTION_BUTTONS:
            _write_zip_member(zip_file, button.ctrl_prop_path, _form_control_properties_xml())
        _write_zip_member(
            zip_file,
            "xl/worksheets/sheet2.xml",
            _control_data_sheet_xml(month_values),
        )
        _write_zip_member(
            zip_file,
            "xl/worksheets/sheet3.xml",
            _settings_sheet_xml(),
        )
        _write_zip_member(
            zip_file,
            "xl/worksheets/sheet4.xml",
            _config_sheet_xml(),
        )


def main() -> int:
    try:
        build_runner_workbook()
    except Exception as exc:  # pragma: no cover - exercised via unit tests
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
