from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast
from zipfile import BadZipFile, ZipFile

LOGGER = logging.getLogger(__name__)

_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_RELATIONSHIP_QNAME = f"{{{_PACKAGE_REL_NS}}}Relationship"


def scrub_external_relationships_from_pptx(
    source_pptx_path: Path | str,
    *,
    scrubbed_pptx_path: Path | str | None = None,
) -> Path:
    """Create a PPTX copy with external relationship targets removed."""

    source_pptx_path = Path(source_pptx_path)
    destination = (
        Path(scrubbed_pptx_path)
        if scrubbed_pptx_path is not None
        else source_pptx_path.with_name(
            f"{source_pptx_path.stem}_scrubbed{source_pptx_path.suffix}"
        )
    )

    destination.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(source_pptx_path) as source_archive, ZipFile(destination, "w") as output_archive:
        for item in source_archive.infolist():
            xml_bytes = source_archive.read(item.filename)
            if not _is_ppt_relationship_part(item.filename):
                output_archive.writestr(item, xml_bytes)
                continue

            output_archive.writestr(item, _remove_external_relationship_targets(xml_bytes))

    return destination


def list_external_relationship_targets(pptx_path: Path | str) -> set[str]:
    """Return external relationship targets under PPT relationship parts."""

    pptx_path = Path(pptx_path)
    if not pptx_path.exists() or not pptx_path.is_file():
        return set()

    try:
        with ZipFile(pptx_path) as archive:
            targets: set[str] = set()
            for rel_path in _iter_ppt_relationship_part_names(archive.namelist()):
                xml_bytes = archive.read(rel_path)
                root = ET.fromstring(xml_bytes)
                for relationship in root.findall(f".//{_RELATIONSHIP_QNAME}"):
                    if relationship.attrib.get("TargetMode") != "External":
                        continue
                    target = relationship.attrib.get("Target", "").strip()
                    if target:
                        targets.add(target)
            return targets
    except (BadZipFile, ET.ParseError, KeyError):
        LOGGER.debug("Skipping external link target scan for non-standard PPTX: %s", pptx_path)
        return set()


def _iter_ppt_relationship_part_names(archive_names: list[str]) -> list[str]:
    return [name for name in archive_names if _is_ppt_relationship_part(name)]


def _is_ppt_relationship_part(archive_name: str) -> bool:
    return (
        archive_name.startswith("ppt/")
        and archive_name.endswith(".rels")
        and "/_rels/" in archive_name
    )


def _remove_external_relationship_targets(xml_bytes: bytes) -> bytes:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes

    changed = False
    for relationship in list(root.findall(f".//{_RELATIONSHIP_QNAME}")):
        if relationship.attrib.get("TargetMode") != "External":
            continue
        root.remove(relationship)
        changed = True

    if not changed:
        return xml_bytes
    return cast(bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True))
