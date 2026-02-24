from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from counter_risk.pipeline.ppt_validation import validate_distribution_ppt_standalone


def _write_distribution_ppt(path: Path, rels_xml: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", rels_xml)


def test_distribution_standalone_validation_succeeds_without_external_relationships(
    tmp_path: Path,
) -> None:
    distribution_ppt = tmp_path / "distribution.pptx"
    _write_distribution_ppt(
        distribution_ppt,
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>
""",
    )

    result = validate_distribution_ppt_standalone(distribution_ppt)

    assert result.is_valid is True
    assert result.external_relationship_count == 0
    assert result.external_relationship_parts == ()
    assert result.relationship_parts_scanned == ("ppt/slides/_rels/slide1.xml.rels",)


def test_distribution_standalone_validation_fails_with_external_relationships(
    tmp_path: Path,
) -> None:
    distribution_ppt = tmp_path / "distribution.pptx"
    _write_distribution_ppt(
        distribution_ppt,
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="X:\\linked\\book.xlsx" TargetMode="External"/>
</Relationships>
""",
    )

    result = validate_distribution_ppt_standalone(distribution_ppt)

    assert result.is_valid is False
    assert result.external_relationship_count == 1
    assert result.external_relationship_parts == ("ppt/slides/_rels/slide1.xml.rels",)
