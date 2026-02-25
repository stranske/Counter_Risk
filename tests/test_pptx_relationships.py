from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import counter_risk.pipeline.run as run_module
from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.ppt_naming import resolve_ppt_output_names

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_QNAME = f"{{{_REL_NS}}}Relationship"
_FORBIDDEN_EXTERNAL_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
    "http://schemas.microsoft.com/office/2006/relationships/oleObject",
}


def _write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _write_pptx_with_external_relationships(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com" TargetMode="External"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2006/relationships/oleObject" Target="X:\\linked\\book.xlsx" TargetMode="External"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/charts/_rels/chart1.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="file:///X:/linked/chart.xlsx" TargetMode="External"/>
</Relationships>
""",
        )
        archive.writestr("ppt/media/image1.png", b"png")


def _iter_relationship_attributes(pptx_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with ZipFile(pptx_path) as archive:
        for name in sorted(archive.namelist()):
            if not (name.startswith("ppt/") and name.endswith(".rels") and "/_rels/" in name):
                continue
            root = ET.fromstring(archive.read(name))
            for relationship in root.findall(f".//{_REL_QNAME}"):
                rows.append(
                    {
                        "part": name,
                        "id": relationship.attrib.get("Id", ""),
                        "type": relationship.attrib.get("Type", ""),
                        "target_mode": relationship.attrib.get("TargetMode", ""),
                    }
                )
    return rows


def _build_config(tmp_path: Path, monthly_pptx: Path) -> WorkflowConfig:
    inputs_dir = tmp_path / "inputs"
    files = {
        "all_programs": inputs_dir / "all_programs.xlsx",
        "ex_trend": inputs_dir / "ex_trend.xlsx",
        "trend": inputs_dir / "trend.xlsx",
        "hist_all": inputs_dir / "hist_all.xlsx",
        "hist_ex": inputs_dir / "hist_ex.xlsx",
        "hist_llc": inputs_dir / "hist_llc.xlsx",
    }
    for file_path in files.values():
        _write_placeholder(file_path)

    return WorkflowConfig(
        mosers_all_programs_xlsx=files["all_programs"],
        mosers_ex_trend_xlsx=files["ex_trend"],
        mosers_trend_xlsx=files["trend"],
        hist_all_programs_3yr_xlsx=files["hist_all"],
        hist_ex_llc_3yr_xlsx=files["hist_ex"],
        hist_llc_3yr_xlsx=files["hist_llc"],
        monthly_pptx=monthly_pptx,
        output_root=tmp_path / "ignored-output-root",
        enable_screenshot_replacement=False,
    )


def test_distribution_pptx_contains_no_external_relationships(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    source_pptx = tmp_path / "source.pptx"
    _write_pptx_with_external_relationships(source_pptx)

    config = _build_config(tmp_path, source_pptx)
    as_of_date = date(2026, 2, 13)
    run_module._write_outputs(
        run_dir=run_dir,
        config=config,
        as_of_date=as_of_date,
        warnings=[],
    )

    output_names = resolve_ppt_output_names(as_of_date)
    master = run_dir / output_names.master_filename
    distribution = run_dir / output_names.distribution_filename

    master_rows = _iter_relationship_attributes(master)
    distribution_rows = _iter_relationship_attributes(distribution)

    assert any(row["target_mode"] == "External" for row in master_rows)
    assert all(row["target_mode"] != "External" for row in distribution_rows)
    assert not any(
        row["target_mode"] == "External" and row["type"] in _FORBIDDEN_EXTERNAL_TYPES
        for row in distribution_rows
    )
