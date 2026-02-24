"""PowerPoint output validation helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_RELATIONSHIP_QNAME = f"{{{_PACKAGE_REL_NS}}}Relationship"


@dataclass(frozen=True)
class PptStandaloneValidationResult:
    """Validation result for standalone distribution PPT outputs."""

    is_valid: bool
    external_relationship_count: int
    relationship_parts_scanned: tuple[str, ...]
    external_relationship_parts: tuple[str, ...]


def validate_distribution_ppt_standalone(pptx_path: Path) -> PptStandaloneValidationResult:
    """Validate that a distribution PPT contains no external link relationships."""

    if not pptx_path.exists() or not pptx_path.is_file():
        raise FileNotFoundError(f"Distribution PPT not found for validation: {pptx_path}")

    try:
        with ZipFile(pptx_path) as archive:
            relationship_parts = tuple(
                name for name in archive.namelist() if _is_link_relationship_part(name)
            )
            external_relationship_parts: list[str] = []
            external_relationship_count = 0
            for rel_path in relationship_parts:
                root = ET.fromstring(archive.read(rel_path))
                external_links_in_part = sum(
                    1
                    for relationship in root.findall(f".//{_RELATIONSHIP_QNAME}")
                    if relationship.attrib.get("TargetMode") == "External"
                )
                if external_links_in_part > 0:
                    external_relationship_parts.append(rel_path)
                    external_relationship_count += external_links_in_part
    except (BadZipFile, ET.ParseError, KeyError) as exc:
        raise RuntimeError(
            f"Failed to validate distribution PPT for external relationships: {pptx_path}"
        ) from exc

    return PptStandaloneValidationResult(
        is_valid=external_relationship_count == 0,
        external_relationship_count=external_relationship_count,
        relationship_parts_scanned=relationship_parts,
        external_relationship_parts=tuple(external_relationship_parts),
    )


def _is_link_relationship_part(archive_name: str) -> bool:
    return archive_name.endswith(".rels") and (
        archive_name.startswith("ppt/slides/_rels/")
        or archive_name.startswith("ppt/charts/_rels/")
        or archive_name == "ppt/_rels/presentation.xml.rels"
    )
