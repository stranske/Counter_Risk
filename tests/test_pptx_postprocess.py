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


def test_scrub_external_relationships_from_pptx_returns_new_default_scrubbed_copy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pptx"
    expected_output = tmp_path / "source_scrubbed.pptx"

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink\" Target=\"https://example.com\" TargetMode=\"External\"/>
</Relationships>
""",
        )

    scrubbed = scrub_external_relationships_from_pptx(source)

    assert scrubbed == expected_output
    assert scrubbed.exists()
    assert source.exists()
    assert list_external_relationship_targets(source) == {"https://example.com"}
    assert list_external_relationship_targets(scrubbed) == set()


def test_scrub_external_relationships_from_pptx_accepts_str_paths_and_creates_parent_dirs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input" / "source.pptx"
    destination = tmp_path / "output" / "nested" / "distribution.pptx"
    source.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject\" Target=\"X:\\\\linked\\\\book.xlsx\" TargetMode=\"External\"/>
</Relationships>
""",
        )

    scrubbed = scrub_external_relationships_from_pptx(
        str(source),
        scrubbed_pptx_path=str(destination),
    )

    assert scrubbed == destination
    assert destination.exists()
    assert list_external_relationship_targets(str(source)) == {"X:\\\\linked\\\\book.xlsx"}
    assert list_external_relationship_targets(str(destination)) == set()


def test_scrub_external_relationships_from_pptx_scrubs_external_targets_in_other_ppt_rels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pptx"
    output = tmp_path / "distribution.pptx"

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/notesSlides/_rels/notesSlide1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink\" Target=\"https://example.com/notes\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"../theme/theme1.xml\"/>
</Relationships>
""",
        )

    scrubbed = scrub_external_relationships_from_pptx(source, scrubbed_pptx_path=output)

    assert scrubbed == output
    assert list_external_relationship_targets(source) == {"https://example.com/notes"}
    assert list_external_relationship_targets(output) == set()
    assert _relationship_count(output, "ppt/notesSlides/_rels/notesSlide1.xml.rels") == 0
    assert _relationship_count(output, "ppt/slideLayouts/_rels/slideLayout1.xml.rels") == 1
