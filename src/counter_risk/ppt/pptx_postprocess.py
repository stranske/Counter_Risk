from __future__ import annotations

import logging
import posixpath
import re
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote, unquote
from zipfile import BadZipFile, ZipFile

LOGGER = logging.getLogger(__name__)

_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_RELATIONSHIP_QNAME = f"{{{_PACKAGE_REL_NS}}}Relationship"

# Matches one whole <Relationship .../> element (always self-closing per the
# OOXML package-relationships schema) whose Id attribute is one of the given
# ids. Built per-call from the actual removed ids rather than matching on
# TargetMode, so it stays exactly in sync with what _find_external_relationship_ids
# selected.
_RELATIONSHIP_ELEMENT_TEMPLATE = (
    r'<Relationship\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*?\bId="{rid}"(?:[^>"\']|"[^"]*"|\'[^\']*\')*?/>'
)

# Matches one whole element (self-closing or with a body) whose r:id / r:embed
# / r:link attribute is one of the given ids, e.g. <c:externalData r:id="rId2">
# ...</c:externalData>. Real-world OOXML output uses the literal "r:" prefix
# for the officeDocument-relationships namespace, so matching on that prefix
# (rather than resolving namespaces via a full parse) is reliable and lets
# the edit stay a pure substring operation -- see the module docstring below
# for why that matters.
_DANGLING_ELEMENT_TEMPLATE = (
    r'<([\w.:-]+)\b(?:[^>"\']|"[^"]*"|\'[^\']*\')*?'
    r'\br:(?:id|embed|link)="{rid}"'
    r'(?:[^>"\']|"[^"]*"|\'[^\']*\')*?(?:/>|>.*?</\1\s*>)'
)


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
    in_place = source_pptx_path.resolve() == destination.resolve()
    write_destination = destination
    temp_path: Path | None = None
    if in_place:
        with tempfile.NamedTemporaryFile(
            prefix=f"{source_pptx_path.stem}-scrubbed-",
            suffix=source_pptx_path.suffix,
            dir=source_pptx_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
        write_destination = temp_path

    write_destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(source_pptx_path) as source_archive:
            removed_ids_by_part: dict[str, set[str]] = {}
            rewritten_rels: dict[str, bytes] = {}
            for name in source_archive.namelist():
                if not _is_ppt_relationship_part(name):
                    continue
                xml_bytes = source_archive.read(name)
                external_ids = _find_external_relationship_ids(xml_bytes)
                if not external_ids:
                    continue
                rewritten_rels[name] = _strip_relationships_by_id(xml_bytes, external_ids)
                removed_ids_by_part[_owning_part_for_rels(name)] = external_ids

            with ZipFile(write_destination, "w") as output_archive:
                for item in source_archive.infolist():
                    if item.filename in rewritten_rels:
                        output_archive.writestr(item, rewritten_rels[item.filename])
                        continue

                    removed_ids = removed_ids_by_part.get(item.filename)
                    if removed_ids:
                        xml_bytes = source_archive.read(item.filename)
                        output_archive.writestr(
                            item, _strip_dangling_element_refs(xml_bytes, removed_ids)
                        )
                        continue

                    output_archive.writestr(item, source_archive.read(item.filename))
        if temp_path is not None:
            temp_path.replace(destination)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    return destination


def repoint_external_relationship_targets(
    source_pptx_path: Path | str,
    *,
    target_replacements: Mapping[str, Path],
    repointed_pptx_path: Path | str | None = None,
) -> Path:
    """Rewrite external relationship targets to point at a local copy instead.

    *target_replacements* maps a bare filename (e.g. "Historical Counterparty
    Risk Graphs - All Programs 3 Year.xlsx") to the local path that chart's
    external data link should point at instead. Any External relationship
    whose Target ends in one of those filenames gets its Target attribute
    rewritten in place; every other byte in the .rels part -- and the rest of
    the package -- is untouched (same plain-substring-edit approach as
    ``scrub_external_relationships_from_pptx``, for the same reason: chart XML
    survives a substring edit but not an ElementTree parse+reserialize).

    This exists because the chart template bakes in a fixed external link
    (the real production historical workbook path). A pipeline run that
    doesn't write back to that same path needs the chart to point at this
    run's own historical workbook copy instead, so a subsequent shape-level
    link refresh (``Shape.LinkFormat.Update()`` via COM -- confirmed to be the
    call that actually works for this relationship type; ``Presentation.
    UpdateLinks()`` is a silent no-op for it) pulls this run's data rather
    than whatever the original external path currently contains.
    """

    source_pptx_path = Path(source_pptx_path)
    destination = Path(repointed_pptx_path) if repointed_pptx_path is not None else source_pptx_path
    in_place = source_pptx_path.resolve() == destination.resolve()
    write_destination = destination
    temp_path: Path | None = None
    if in_place:
        with tempfile.NamedTemporaryFile(
            prefix=f"{source_pptx_path.stem}-repointed-",
            suffix=source_pptx_path.suffix,
            dir=source_pptx_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
        write_destination = temp_path

    write_destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(source_pptx_path) as source_archive:
            rewritten: dict[str, bytes] = {}
            for name in source_archive.namelist():
                if not _is_ppt_relationship_part(name):
                    continue
                xml_bytes = source_archive.read(name)
                new_bytes = _repoint_relationship_targets(xml_bytes, target_replacements)
                if new_bytes != xml_bytes:
                    rewritten[name] = new_bytes

            with ZipFile(write_destination, "w") as output_archive:
                for item in source_archive.infolist():
                    if item.filename in rewritten:
                        output_archive.writestr(item, rewritten[item.filename])
                    else:
                        output_archive.writestr(item, source_archive.read(item.filename))
        if temp_path is not None:
            temp_path.replace(destination)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    return destination


def _repoint_relationship_targets(
    xml_bytes: bytes, target_replacements: Mapping[str, Path]
) -> bytes:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes

    text = xml_bytes.decode("utf-8")
    for relationship in root.findall(f".//{_RELATIONSHIP_QNAME}"):
        if relationship.attrib.get("TargetMode") != "External":
            continue
        target = relationship.attrib.get("Target", "")
        if not target:
            continue
        filename = unquote(target.replace("\\", "/").rsplit("/", 1)[-1])
        new_local_path = target_replacements.get(filename)
        if new_local_path is None:
            continue
        new_target = _file_uri_for_path(new_local_path)
        text = text.replace(f'Target="{target}"', f'Target="{new_target}"')

    return text.encode("utf-8")


def _file_uri_for_path(path: Path) -> str:
    """Build a Windows-style file:// URI matching Office's own encoding: a
    backslash-separated absolute path (not forward slashes) with spaces and
    other reserved characters percent-encoded, e.g.
    ``file:///C:\\Some%20Dir\\file.xlsx``."""

    absolute = str(Path(path).resolve())
    return "file:///" + quote(absolute, safe="\\:")


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


def _owning_part_for_rels(rels_archive_name: str) -> str:
    """Return the part a .rels file describes, e.g. ppt/charts/_rels/chart1.xml.rels ->
    ppt/charts/chart1.xml."""

    directory, filename = posixpath.split(rels_archive_name)
    owning_directory = posixpath.dirname(directory)  # strip trailing "_rels"
    owning_filename = filename.removesuffix(".rels")
    return posixpath.join(owning_directory, owning_filename)


def _find_external_relationship_ids(xml_bytes: bytes) -> set[str]:
    """Return the Id of every External-targetmode relationship in a .rels part.

    Read-only: .rels parts are a flat list of simple self-closing elements
    with a single namespace, so a full parse here carries none of the
    reserialization risk described on ``_strip_relationships_by_id``.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return set()

    return {
        relationship.attrib["Id"]
        for relationship in root.findall(f".//{_RELATIONSHIP_QNAME}")
        if relationship.attrib.get("TargetMode") == "External" and relationship.attrib.get("Id")
    }


def _strip_relationships_by_id(xml_bytes: bytes, ids: set[str]) -> bytes:
    """Remove the ``<Relationship .../>`` elements matching *ids*, verbatim.

    Edits the raw text rather than parsing-and-reserializing via
    ElementTree: see ``_strip_dangling_element_refs`` for why that distinction
    matters for real OOXML parts. .rels files are simple enough that a full
    round-trip would likely be safe too, but staying byte-identical outside
    the removed elements avoids relying on that.
    """

    text = xml_bytes.decode("utf-8")
    for rel_id in ids:
        pattern = re.compile(_RELATIONSHIP_ELEMENT_TEMPLATE.format(rid=re.escape(rel_id)))
        text = pattern.sub("", text)
    return text.encode("utf-8")


def _strip_dangling_element_refs(xml_bytes: bytes, removed_ids: set[str]) -> bytes:
    """Remove elements referencing *removed_ids* via r:id/r:embed/r:link.

    e.g. a chart's ``<c:externalData r:id="rId2">...</c:externalData>``
    becomes dangling once the relationship it names is scrubbed, and
    PowerPoint refuses to open a file with a dangling relationship reference.

    This edits the raw XML text directly with a targeted regex instead of
    parsing the part with ElementTree and calling ``tostring()`` on it.
    Real chart/slide parts carry markup-compatibility extensions and
    multiple co-declared namespaces; ElementTree's serializer does not
    preserve the original prefix bindings (it reassigns its own ``ns0:``,
    ``ns1:`` ... prefixes), which is enough to make PowerPoint reject the
    result even though the XML remains well-formed. Confirmed by reproducing
    the "PowerPoint could not open the file" error against a real report
    export: an ElementTree round-trip of a 17-chart deck's chart part grew it
    from ~43KB to ~50KB purely from prefix/namespace churn, and every
    resulting Distribution PPTX failed to open. A substring edit leaves
    everything outside the targeted element byte-identical to the source.
    """

    text = xml_bytes.decode("utf-8")
    changed = False
    for rid in removed_ids:
        pattern = re.compile(_DANGLING_ELEMENT_TEMPLATE.format(rid=re.escape(rid)), re.DOTALL)
        new_text, count = pattern.subn("", text)
        if count:
            text = new_text
            changed = True
    if not changed:
        return xml_bytes
    return text.encode("utf-8")
