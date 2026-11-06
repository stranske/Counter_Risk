"""Build an Excel macro-enabled workbook artifact from the base template."""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

CORE_PROPERTIES_MEMBER = "docProps/core.xml"
CONFIG_SHEET_NAME = "Config"
_CONFIG_DEFINED_NAMES: tuple[tuple[str, str], ...] = (
    ("RunnerConfig_MosersAllPrograms", "Config!$B$4"),
    ("RunnerConfig_MosersExTrend", "Config!$B$5"),
    ("RunnerConfig_MosersTrend", "Config!$B$6"),
    ("RunnerConfig_HistAllPrograms3yr", "Config!$B$7"),
    ("RunnerConfig_HistExLlc3yr", "Config!$B$8"),
    ("RunnerConfig_HistLlc3yr", "Config!$B$9"),
    ("RunnerConfig_MonthlyPptx", "Config!$B$10"),
)
_WORKSHEET_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)
_WORKSHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)


def repository_root() -> Path:
    """Return repository root based on module location."""

    return Path(__file__).resolve().parents[3]


def template_xlsm_path(root: Path | None = None) -> Path:
    """Return default template workbook path."""

    base = repository_root() if root is None else root
    return base / "assets" / "templates" / "counter_risk_template.xlsm"


def default_output_path(root: Path | None = None) -> Path:
    """Return default output location for built workbook."""

    base = repository_root() if root is None else root
    return base / "dist" / "counter_risk_runner.xlsm"


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for XLSM artifact generation."""

    parser = argparse.ArgumentParser(prog="counter-risk-build-xlsm")
    parser.add_argument(
        "--template-path",
        type=Path,
        default=template_xlsm_path(),
        help="Path to source template XLSM.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=default_output_path(),
        help="Destination path for generated XLSM artifact.",
    )
    parser.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        default=date.today(),
        help="Reporting as-of date in ISO format (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--run-date",
        type=datetime.fromisoformat,
        default=datetime.now(UTC),
        help="Pipeline run timestamp in ISO format.",
    )
    parser.add_argument(
        "--version",
        default="dev",
        help="Pipeline version metadata string.",
    )
    parser.add_argument(
        "--inject-config-sheet",
        action="store_true",
        help="Add the Config input sheet and Named Ranges to --template-path in-place.",
    )
    return parser


def _build_config_sheet_xml() -> str:
    """Build the XML for the file-path Config input sheet."""
    labels = [
        (4, "MOSERS All Programs (.xlsx)"),
        (5, "MOSERS Ex-Trend (.xlsx)"),
        (6, "MOSERS Trend (.xlsx)"),
        (7, "Historical All Programs \u2013 3yr (.xlsx)"),
        (8, "Historical Ex-LLC \u2013 3yr (.xlsx)"),
        (9, "Historical LLC \u2013 3yr (.xlsx)"),
        (10, "Monthly Report Template (.pptx)"),
    ]
    header_rows = [
        '    <row r="1"><c r="A1" t="inlineStr"><is><t>'
        "Counter Risk \u2014 File Path Configuration"
        "</t></is></c></row>",
        '    <row r="2"><c r="A2" t="inlineStr"><is><t>'
        "Enter full Windows paths in column B. Leave blank to use config/*.yml defaults."
        "</t></is></c></row>",
    ]
    label_rows = [
        f'    <row r="{row}"><c r="A{row}" t="inlineStr"><is><t>{label}</t></is></c></row>'
        for row, label in labels
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '  <dimension ref="A1:B10"/>',
        '  <sheetViews><sheetView workbookViewId="0"/></sheetViews>',
        '  <sheetFormatPr defaultRowHeight="15"/>',
        "  <cols>",
        '    <col min="1" max="1" width="38" customWidth="1"/>',
        '    <col min="2" max="2" width="80" customWidth="1"/>',
        "  </cols>",
        "  <sheetData>",
        *header_rows,
        *label_rows,
        "  </sheetData>",
        "</worksheet>",
        "",
    ]
    return "\n".join(lines)


def _lowest_free_positive_id(used: set[int]) -> int:
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def inject_config_sheet(xlsm_path: Path) -> None:
    """Structurally add Config inputs, replacing the archive only after validation."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    doc_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    with ZipFile(xlsm_path) as archive:
        infos = archive.infolist()
        if len({i.filename for i in infos}) != len(infos):
            raise ValueError("Unsupported duplicate archive members")
        existing = {i.filename: (i, archive.read(i)) for i in infos}
        archive_comment = archive.comment

    def parse(member: str, expected: str) -> ET.Element:
        data = existing[member][1]
        if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
            raise ValueError("Unsupported XML declarations")
        root = ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        if root.tag != expected:
            raise ValueError(f"Unsupported XML root in {member}: {root.tag}")
        # Prefix-valued compatibility attributes need namespace-aware round-tripping.
        # Do not silently drop their namespace declarations via ElementTree.
        if any("Ignorable" in key or "Requires" in key for el in root.iter() for key in el.attrib):
            raise ValueError(f"Unsupported namespace compatibility attributes in {member}")
        return root

    workbook = parse("xl/workbook.xml", f"{{{ns}}}workbook")
    rels = parse("xl/_rels/workbook.xml.rels", f"{{{rel_ns}}}Relationships")
    types = parse("[Content_Types].xml", f"{{{ct_ns}}}Types")
    sheets_list = workbook.findall(f"{{{ns}}}sheets")
    if len(sheets_list) != 1:
        raise ValueError("Unsupported workbook: expected one sheets element")
    sheets = sheets_list[0]
    if any(el.get("name", "").casefold() == "config" for el in sheets):
        return
    sheet_ids = [el.get("sheetId") for el in sheets]
    rel_ids = [el.get("Id") for el in rels]
    if len(set(sheet_ids)) != len(sheet_ids) or len(set(rel_ids)) != len(rel_ids):
        raise ValueError("Unsupported duplicate sheet/relationship IDs")
    sheet_id = _lowest_free_positive_id({int(value) for value in sheet_ids})
    occupied = {
        int(m.group(1))
        for name in existing
        if (m := re.fullmatch(r"xl/worksheets/sheet(\d+)\.xml", name))
    }
    for el in rels:
        match = re.search(r"(?:^|/)worksheets/sheet(\d+)\.xml$", el.get("Target", ""))
        if match:
            occupied.add(int(match.group(1)))
    for el in types:
        match = re.fullmatch(r"/xl/worksheets/sheet(\d+)\.xml", el.get("PartName", ""))
        if match:
            occupied.add(int(match.group(1)))
    number = _lowest_free_positive_id(occupied)
    target = f"worksheets/sheet{number}.xml"
    rel_number = 1
    while f"rId{rel_number}" in rel_ids:
        rel_number += 1
    rel_id = f"rId{rel_number}"
    ET.SubElement(
        sheets,
        f"{{{ns}}}sheet",
        {
            "name": "Config",
            "sheetId": str(sheet_id),
            f"{{{doc_rel_ns}}}id": rel_id,
        },
    )
    names_list = workbook.findall(f"{{{ns}}}definedNames")
    if len(names_list) > 1:
        raise ValueError("Unsupported multiple definedNames elements")
    if names_list:
        names = names_list[0]
    else:
        names = ET.Element(f"{{{ns}}}definedNames")
        # definedNames follows sheets/externalReferences and precedes calcPr.
        index = list(workbook).index(sheets) + 1
        while index < len(workbook) and workbook[index].tag in {
            f"{{{ns}}}functionGroups",
            f"{{{ns}}}externalReferences",
        }:
            index += 1
        workbook.insert(index, names)
    existing_names = {el.get("name", "").casefold() for el in names}
    for name, ref in _CONFIG_DEFINED_NAMES:
        if name.casefold() not in existing_names:
            ET.SubElement(names, f"{{{ns}}}definedName", {"name": name}).text = ref
    ET.SubElement(
        rels,
        f"{{{rel_ns}}}Relationship",
        {
            "Id": rel_id,
            "Type": _WORKSHEET_REL_TYPE,
            "Target": target,
        },
    )
    ET.SubElement(
        types,
        f"{{{ct_ns}}}Override",
        {
            "PartName": f"/xl/{target}",
            "ContentType": _WORKSHEET_CONTENT_TYPE,
        },
    )
    updated = {
        name: ET.tostring(root, encoding="utf-8", xml_declaration=True)
        for name, root in (
            ("xl/workbook.xml", workbook),
            ("xl/_rels/workbook.xml.rels", rels),
            ("[Content_Types].xml", types),
        )
    }
    with tempfile.NamedTemporaryFile(dir=xlsm_path.parent, delete=False, suffix=".xlsm") as tmp:
        temp_path = Path(tmp.name)
    try:
        with ZipFile(temp_path, "w") as output:
            output.comment = archive_comment
            for filename, (info, data) in existing.items():
                output.writestr(info, updated.get(filename, data))
            output.writestr(f"xl/{target}", _build_config_sheet_xml(), compress_type=ZIP_DEFLATED)
        temp_path.replace(xlsm_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _core_properties_xml(*, as_of_date: date, run_date: datetime, version: str) -> str:
    run_date_utc = run_date.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    as_of = as_of_date.isoformat()
    safe_version = escape(version.strip() or "dev")

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcmitype="http://purl.org/dc/dcmitype/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Counter Risk Runner</dc:title>
  <dc:creator>Counter Risk</dc:creator>
  <cp:keywords>counter-risk;xlsm;runner</cp:keywords>
  <dc:description>Generated workbook: as_of_date={as_of}; version={safe_version}</dc:description>
  <cp:lastModifiedBy>Counter Risk Pipeline</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{run_date_utc}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{run_date_utc}</dcterms:modified>
</cp:coreProperties>
"""


def _replace_zip_member(zip_path: Path, member_name: str, member_bytes: bytes) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsm") as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with ZipFile(zip_path, mode="r") as source, ZipFile(temp_path, mode="w") as target:
            for info in source.infolist():
                if info.filename == member_name:
                    continue
                copied_info = ZipInfo(filename=info.filename, date_time=info.date_time)
                copied_info.compress_type = info.compress_type
                copied_info.external_attr = info.external_attr
                copied_info.internal_attr = info.internal_attr
                copied_info.flag_bits = info.flag_bits
                copied_info.create_system = info.create_system
                target.writestr(copied_info, source.read(info.filename))

            info = ZipInfo(member_name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            target.writestr(info, member_bytes)

        shutil.move(str(temp_path), zip_path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_xlsm_artifact(
    *,
    template_path: Path,
    output_path: Path,
    as_of_date: date,
    run_date: datetime,
    version: str,
) -> Path:
    """Copy template XLSM and inject deterministic run metadata."""

    if not template_path.is_file():
        raise FileNotFoundError(f"Template XLSM was not found: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)

    core_xml = _core_properties_xml(as_of_date=as_of_date, run_date=run_date, version=version)
    _replace_zip_member(output_path, CORE_PROPERTIES_MEMBER, core_xml.encode("utf-8"))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.inject_config_sheet:
        inject_config_sheet(args.template_path)
        print(f"Config sheet injected into: {args.template_path}")
        return 0
    build_xlsm_artifact(
        template_path=args.template_path,
        output_path=args.output_path,
        as_of_date=args.as_of_date,
        run_date=args.run_date,
        version=args.version,
    )
    print(f"Built XLSM artifact: {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
