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
    return parser


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

        temp_path.replace(zip_path)
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
