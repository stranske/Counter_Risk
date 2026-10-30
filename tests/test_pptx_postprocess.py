from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

import pytest

from counter_risk.ppt.pptx_postprocess import (
    list_external_relationship_targets,
    repoint_external_relationship_targets,
    scrub_external_relationships_from_pptx,
)


@pytest.mark.parametrize("in_place", [False, True])
def test_repoint_targets_preserves_unrelated_package_bytes(tmp_path: Path, in_place: bool) -> None:
    source = tmp_path / "source.pptx"
    destination = source if in_place else tmp_path / "nested" / "output.pptx"
    local = tmp_path / "run outputs" / "My Book.xlsx"
    rels = rb"""<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" TargetMode="External" Target="file:///C:/old/My%20Book.xlsx"/>
  <Relationship Id="rId2" TargetMode="External" Target="C:\old\My Book.xlsx"/>
  <Relationship Id="rId3" Target="../media/image.png"/>
  <Relationship Id="rId4" TargetMode="External" Target="https://example.com/other.xlsx"/>
  <Relationship Id="rId5" TargetMode="External"/>
</Relationships>"""
    parts = {
        "ppt/charts/_rels/chart1.xml.rels": rels,
        "ppt/slides/_rels/slide1.xml.rels": b"<malformed",
        "ppt/charts/chart1.xml": b'<chart xmlns:x="urn:preserve"><x:custom/></chart>',
        "ppt/media/image.png": b"image-data",
        "_rels/.rels": b"non-PPT relationships",
    }
    with ZipFile(source, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    original = source.read_bytes()

    assert (
        repoint_external_relationship_targets(
            source, target_replacements={"My Book.xlsx": local}, repointed_pptx_path=destination
        )
        == destination
    )

    expected_uri = "file:///" + quote(str(local.resolve()), safe="\\:")
    expected_rels = rels.replace(b"file:///C:/old/My%20Book.xlsx", expected_uri.encode()).replace(
        b"C:\\old\\My Book.xlsx", expected_uri.encode()
    )
    with ZipFile(destination) as archive:
        assert set(archive.namelist()) == set(parts)
        for name, data in parts.items():
            assert archive.read(name) == (
                expected_rels if name.endswith("chart1.xml.rels") else data
            )
    if not in_place:
        assert source.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == (
        ["source.pptx"] if in_place else ["nested", "source.pptx"]
    )


@pytest.mark.parametrize(
    "operation", [scrub_external_relationships_from_pptx, repoint_external_relationship_targets]
)
def test_in_place_postprocessing_cleans_up_after_bad_archive(
    tmp_path: Path, operation: Callable[..., Path]
) -> None:
    source = tmp_path / "broken.pptx"
    source.write_bytes(b"invalid zip")
    kwargs = (
        {"scrubbed_pptx_path": source}
        if operation is scrub_external_relationships_from_pptx
        else {"target_replacements": {}}
    )
    with pytest.raises(BadZipFile):
        operation(source, **kwargs)

    assert source.read_bytes() == b"invalid zip"
    assert list(tmp_path.iterdir()) == [source]


def test_scrubbing_preserves_malformed_relationship_xml(tmp_path: Path) -> None:
    source = tmp_path / "malformed.pptx"
    with ZipFile(source, "w") as archive:
        archive.writestr("ppt/charts/_rels/chart1.xml.rels", b"<malformed")
    output = scrub_external_relationships_from_pptx(source)
    with ZipFile(output) as archive:
        assert archive.read("ppt/charts/_rels/chart1.xml.rels") == b"<malformed"


@pytest.mark.parametrize("kind", ["missing", "directory", "invalid-zip", "invalid-xml"])
def test_external_target_scan_tolerates_nonstandard_inputs(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "report.pptx"
    if kind == "directory":
        source.mkdir()
    elif kind == "invalid-zip":
        source.write_bytes(b"invalid zip")
    elif kind == "invalid-xml":
        with ZipFile(source, "w") as archive:
            archive.writestr("ppt/charts/_rels/chart1.xml.rels", b"<malformed")
    assert list_external_relationship_targets(source) == set()


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


def test_scrub_external_relationships_removes_dangling_chart_external_data_ref(
    tmp_path: Path,
) -> None:
    """Removing a chart's external relationship must also strip the chart's
    own <c:externalData r:id="..."> reference to it, or the relationship id
    it points to no longer resolves and PowerPoint refuses to open the file
    (reproduced against real report output: every Distribution PPTX failed
    to open via COM with exactly this dangling reference)."""

    source = tmp_path / "source.pptx"
    output = tmp_path / "distribution.pptx"

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/charts/_rels/chart1.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/themeOverride\" Target=\"../theme/themeOverride1.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject\" Target=\"file:///X:/linked/book.xlsx\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr(
            "ppt/charts/chart1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                "<c:chart><c:plotArea/></c:chart>"
                '<c:externalData r:id="rId2"><c:autoUpdate val="0"/></c:externalData>'
                "</c:chartSpace>"
            ),
        )

    scrub_external_relationships_from_pptx(source, scrubbed_pptx_path=output)

    with ZipFile(output) as archive:
        chart_xml = archive.read("ppt/charts/chart1.xml").decode("utf-8")

    assert "externalData" not in chart_xml
    assert "rId2" not in chart_xml
    # The chart's other content, and its still-valid internal relationship,
    # must survive untouched.
    assert "plotArea" in chart_xml
    assert _relationship_count(output, "ppt/charts/_rels/chart1.xml.rels") == 1


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


def test_scrub_external_relationships_from_pptx_supports_in_place_scrub(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pptx"

    with ZipFile(source, "w") as archive:
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink\" Target=\"https://example.com\" TargetMode=\"External\"/>
</Relationships>
""",
        )
        archive.writestr("ppt/presentation.xml", b"<presentation/>")

    scrubbed = scrub_external_relationships_from_pptx(source, scrubbed_pptx_path=source)

    assert scrubbed == source
    assert source.exists()
    assert list_external_relationship_targets(source) == set()
    with ZipFile(source) as archive:
        assert archive.read("ppt/presentation.xml") == b"<presentation/>"


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
