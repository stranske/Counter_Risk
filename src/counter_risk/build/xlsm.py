"""Build an Excel macro-enabled workbook artifact from the base template."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

CORE_PROPERTIES_MEMBER = "docProps/core.xml"
CONFIG_SHEET_NAME = "Config"
_CONFIG_SHEET_RID = "rId5"
_CONFIG_SHEET_TARGET = "worksheets/sheet3.xml"


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


def _defined_names_xml() -> str:
    """Build the <definedNames> XML block for Config sheet Named Ranges."""
    ranges = [
        ("RunnerConfig_MosersAllPrograms", "Config!$B$4"),
        ("RunnerConfig_MosersExTrend", "Config!$B$5"),
        ("RunnerConfig_MosersTrend", "Config!$B$6"),
        ("RunnerConfig_HistAllPrograms3yr", "Config!$B$7"),
        ("RunnerConfig_HistExLlc3yr", "Config!$B$8"),
        ("RunnerConfig_HistLlc3yr", "Config!$B$9"),
        ("RunnerConfig_MonthlyPptx", "Config!$B$10"),
    ]
    inner = "\n".join(f'    <definedName name="{name}">{ref}</definedName>' for name, ref in ranges)
    return f"  <definedNames>\n{inner}\n  </definedNames>"


def inject_config_sheet(xlsm_path: Path) -> None:
    """Add a Config input sheet to an XLSM file if not already present.

    Injects a visible 'Config' worksheet with labeled rows and Named Ranges
    for the seven input file paths. The VBA macro reads these Named Ranges
    to override config/*.yml file paths at runtime.

    Safe to call multiple times — exits immediately if Config sheet already
    exists.
    """
    with ZipFile(xlsm_path, mode="r") as zf:
        workbook_bytes = zf.read("xl/workbook.xml")
        if b'name="Config"' in workbook_bytes:
            return
        all_infos = zf.infolist()
        existing = {info.filename: (info, zf.read(info.filename)) for info in all_infos}

    workbook_xml = workbook_bytes.decode("utf-8")
    rels_xml = existing["xl/_rels/workbook.xml.rels"][1].decode("utf-8")
    ct_xml = existing["[Content_Types].xml"][1].decode("utf-8")

    # Add sheet entry to workbook.xml
    sheet_tag = f'    <sheet name="Config" sheetId="3" r:id="{_CONFIG_SHEET_RID}"/>\n  '
    workbook_xml = workbook_xml.replace("  </sheets>", sheet_tag + "</sheets>")

    # Add definedNames section to workbook.xml
    workbook_xml = workbook_xml.replace("</workbook>", _defined_names_xml() + "\n</workbook>")

    # Add relationship to workbook.xml.rels
    ws_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    rel_tag = (
        f'  <Relationship Id="{_CONFIG_SHEET_RID}" Type="{ws_type}"'
        f' Target="{_CONFIG_SHEET_TARGET}"/>\n'
    )
    rels_xml = rels_xml.replace("</Relationships>", rel_tag + "</Relationships>")

    # Add content type to [Content_Types].xml
    ws_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
    ct_tag = f'  <Override PartName="/xl/{_CONFIG_SHEET_TARGET}" ContentType="{ws_ct}"/>\n'
    ct_xml = ct_xml.replace("</Types>", ct_tag + "</Types>")

    updated = {
        "xl/workbook.xml": workbook_xml.encode("utf-8"),
        "xl/_rels/workbook.xml.rels": rels_xml.encode("utf-8"),
        "[Content_Types].xml": ct_xml.encode("utf-8"),
    }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsm") as tmp:
        temp_path = Path(tmp.name)

    try:
        with ZipFile(temp_path, mode="w") as out_zf:
            for filename, (info, data) in existing.items():
                out_info = ZipInfo(filename=info.filename, date_time=info.date_time)
                out_info.compress_type = info.compress_type
                out_info.external_attr = info.external_attr
                out_info.internal_attr = info.internal_attr
                out_info.flag_bits = info.flag_bits
                out_info.create_system = info.create_system
                out_zf.writestr(out_info, updated.get(filename, data))
            sheet_info = ZipInfo(_CONFIG_SHEET_TARGET.replace("worksheets/", "xl/worksheets/"))
            sheet_info.date_time = (1980, 1, 1, 0, 0, 0)
            sheet_info.compress_type = ZIP_DEFLATED
            out_zf.writestr(sheet_info, _build_config_sheet_xml().encode("utf-8"))
        shutil.move(str(temp_path), xlsm_path)
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
