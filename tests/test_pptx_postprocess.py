from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from counter_risk.ppt.pptx_postprocess import (
    list_external_relationship_targets,
    scrub_external_relationships_from_pptx,
)


def _relationship_count(path: Path, rel_part: str) -> int:
    with ZipFile(path) as archive:
        xml_bytes = archive.read(rel_part)
    root = ET.fromstring(xml_bytes)
    return len(
        root.findall(
            ".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
        )
    )


def test_scrub_external_relationships_from_pptx_removes_external_targets_across_ppt_rels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pptx"
    output = tmp_path / "distribution.pptx"

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink\" Target=\"https://example.com\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" Target=\"../media/image1.png\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject\" Target=\"X:\\\\linked\\\\book.xlsx\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/charts/_rels/chart1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/package\" Target=\"file:///X:/linked/chart.xlsx\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr("ppt/media/image1.png", b"png")

    scrubbed = scrub_external_relationships_from_pptx(source, scrubbed_pptx_path=output)

    assert scrubbed == output
    assert list_external_relationship_targets(source) == {
        "https://example.com",
        "X:\\\\linked\\\\book.xlsx",
        "file:///X:/linked/chart.xlsx",
    }
    assert list_external_relationship_targets(output) == set()
    assert _relationship_count(output, "ppt/_rels/presentation.xml.rels") == 0
    assert _relationship_count(output, "ppt/slides/_rels/slide1.xml.rels") == 1
    assert _relationship_count(output, "ppt/charts/_rels/chart1.xml.rels") == 0

    with ZipFile(output) as archive:
        assert archive.read("ppt/media/image1.png") == b"png"
