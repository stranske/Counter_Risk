"""Workbook archive comparison helpers for deterministic regression checks."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from xml.etree import ElementTree
from zipfile import ZipFile

CORE_PROPERTIES_PART = "docProps/core.xml"

_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DCTERMS_NS = "http://purl.org/dc/terms/"

_CORE_TAGS_TO_IGNORE = {
    f"{{{_DCTERMS_NS}}}created",
    f"{{{_DCTERMS_NS}}}modified",
    f"{{{_CORE_NS}}}lastModifiedBy",
}


def compare_workbooks(reference_workbook: Path | str, generated_workbook: Path | str) -> list[str]:
    """Return archive-level differences between two workbook files.

    The comparison intentionally ignores volatile core-properties metadata fields:
    ``dcterms:modified`` and ``cp:lastModifiedBy``.
    """

    reference_path = Path(reference_workbook)
    generated_path = Path(generated_workbook)

    differences: list[str] = []
    with ZipFile(reference_path) as reference_zip, ZipFile(generated_path) as generated_zip:
        reference_members = set(reference_zip.namelist())
        generated_members = set(generated_zip.namelist())

        for member in sorted(reference_members - generated_members):
            differences.append(f"Missing member in generated workbook: {member}")
        for member in sorted(generated_members - reference_members):
            differences.append(f"Extra member in generated workbook: {member}")

        shared_members = sorted(reference_members & generated_members)
        for member in shared_members:
            reference_bytes = reference_zip.read(member)
            generated_bytes = generated_zip.read(member)

            if member == CORE_PROPERTIES_PART:
                differences.extend(
                    _compare_core_properties(reference_bytes, generated_bytes),
                )
                continue

            if reference_bytes != generated_bytes:
                differences.append(f"Member differs: {member}")

    return differences


def assert_workbooks_equal(reference_workbook: Path | str, generated_workbook: Path | str) -> None:
    """Assert two workbook archives are equivalent under comparison rules."""
    differences = compare_workbooks(reference_workbook, generated_workbook)
    if differences:
        raise AssertionError("\n".join(differences))


def _normalize_core_properties(raw_xml: bytes) -> bytes:
    """Remove volatile fields from core-properties XML before comparison."""
    root = ElementTree.fromstring(raw_xml)  # noqa: S314
    for child in list(root):
        if child.tag in _CORE_TAGS_TO_IGNORE:
            root.remove(child)
    return cast(bytes, ElementTree.tostring(root, encoding="utf-8"))


def _compare_core_properties(reference_xml: bytes, generated_xml: bytes) -> list[str]:
    """Compare core properties while excluding volatile metadata fields."""
    normalized_reference = _normalize_core_properties(reference_xml)
    normalized_generated = _normalize_core_properties(generated_xml)
    if normalized_reference == normalized_generated:
        return []

    reference_props = _extract_core_properties(normalized_reference)
    generated_props = _extract_core_properties(normalized_generated)
    keys = sorted(set(reference_props) | set(generated_props))

    differences: list[str] = []
    for key in keys:
        if reference_props.get(key) != generated_props.get(key):
            differences.append(
                "Core property differs: "
                f"{key} (reference={reference_props.get(key)!r}, generated={generated_props.get(key)!r})"
            )
    return differences


def _extract_core_properties(raw_xml: bytes) -> dict[str, str]:
    """Return core-properties text values keyed by namespace-local tag name."""
    root = ElementTree.fromstring(raw_xml)  # noqa: S314
    properties: dict[str, str] = {}
    for child in root:
        local_name = child.tag.rsplit("}", 1)[-1]
        properties[local_name] = (child.text or "").strip()
    return properties
