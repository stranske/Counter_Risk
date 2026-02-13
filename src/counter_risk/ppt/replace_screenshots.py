"""Screenshot replacement utilities for PPTX artifacts."""

from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

BLIP_QNAME = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
EMBED_QNAME = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
REL_QNAME = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


@dataclass(frozen=True)
class ScreenshotReplacement:
    """Replacement payload for one picture placeholder on a slide."""

    slide_number: int
    image_bytes: bytes
    picture_index: int = 0


@dataclass(frozen=True)
class ReplacementResult:
    """Output metadata for a screenshot replacement operation."""

    output_pptx_path: Path
    replaced_media_parts: list[str]


class PptScreenshotReplacementError(RuntimeError):
    """Raised when PPTX screenshot replacement cannot be completed."""


def list_slide_picture_targets(pptx_path: Path) -> dict[int, list[str]]:
    """Return slide->media mappings for picture shapes in a PPTX."""

    try:
        with ZipFile(pptx_path) as archive:
            return _collect_slide_picture_targets(archive)
    except (BadZipFile, OSError, ET.ParseError) as exc:
        raise PptScreenshotReplacementError(
            f"Unable to parse PPTX picture targets: {pptx_path}"
        ) from exc


def resolve_replacements_to_media_parts(
    *, pptx_path: Path, replacements: list[ScreenshotReplacement]
) -> list[str]:
    """Resolve replacement directives to concrete ``ppt/media/*`` part names."""

    try:
        with ZipFile(pptx_path) as archive:
            targets = _collect_slide_picture_targets(archive)
            return _resolve_media_parts(targets=targets, replacements=replacements)
    except (BadZipFile, OSError, ET.ParseError, ValueError) as exc:
        raise PptScreenshotReplacementError(
            f"Unable to resolve screenshot targets in: {pptx_path}"
        ) from exc


def replace_screenshots_in_pptx(
    *,
    source_pptx_path: Path,
    output_pptx_path: Path,
    replacements: list[ScreenshotReplacement],
) -> ReplacementResult:
    """Replace target screenshot media blobs in ``source_pptx_path`` and write output."""

    if not replacements:
        raise ValueError("At least one screenshot replacement is required")

    try:
        with ZipFile(source_pptx_path) as source_archive:
            slide_targets = _collect_slide_picture_targets(source_archive)
            media_parts = _resolve_media_parts(targets=slide_targets, replacements=replacements)
            payload_by_part: dict[str, bytes] = {
                media_part: replacement.image_bytes
                for media_part, replacement in zip(media_parts, replacements, strict=True)
            }

            for media_part in payload_by_part:
                if media_part not in source_archive.namelist():
                    raise ValueError(
                        f"Replacement target does not exist in archive: {media_part}"
                    )

            output_pptx_path.parent.mkdir(parents=True, exist_ok=True)
            with ZipFile(output_pptx_path, "w") as output_archive:
                for item in source_archive.infolist():
                    payload = payload_by_part.get(item.filename)
                    if payload is None:
                        payload = source_archive.read(item.filename)
                    output_archive.writestr(item, payload)
    except (BadZipFile, OSError, ET.ParseError, ValueError) as exc:
        raise PptScreenshotReplacementError(
            f"Failed to replace PPT screenshots: {source_pptx_path}"
        ) from exc

    return ReplacementResult(
        output_pptx_path=output_pptx_path,
        replaced_media_parts=sorted(payload_by_part.keys()),
    )


def _collect_slide_picture_targets(archive: ZipFile) -> dict[int, list[str]]:
    targets: dict[int, list[str]] = {}

    for name in archive.namelist():
        if not name.startswith("ppt/slides/slide") or not name.endswith(".xml"):
            continue

        suffix = name.removeprefix("ppt/slides/slide").removesuffix(".xml")
        if not suffix.isdigit():
            continue
        slide_number = int(suffix)

        slide_root = ET.fromstring(archive.read(name))
        embeds = [
            blip.attrib.get(EMBED_QNAME)
            for blip in slide_root.findall(f".//{BLIP_QNAME}")
            if blip.attrib.get(EMBED_QNAME)
        ]

        if not embeds:
            targets[slide_number] = []
            continue

        rels_path = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
        if rels_path not in archive.namelist():
            raise ValueError(f"Missing slide relationship part: {rels_path}")
        rels_root = ET.fromstring(archive.read(rels_path))
        rels = {
            rel.attrib["Id"]: rel.attrib.get("Target", "") for rel in rels_root.findall(REL_QNAME)
        }

        slide_dir = posixpath.dirname(name)
        media_parts: list[str] = []
        for embed in embeds:
            target = rels.get(embed)
            if not target:
                raise ValueError(
                    f"Missing relationship target for slide {slide_number} embed id '{embed}'"
                )
            resolved = posixpath.normpath(posixpath.join(slide_dir, target))
            if not resolved.startswith("ppt/media/"):
                raise ValueError(
                    f"Slide {slide_number} embed id '{embed}' points to non-media target: {resolved}"
                )
            media_parts.append(resolved)

        targets[slide_number] = media_parts

    return targets


def _resolve_media_parts(
    *, targets: dict[int, list[str]], replacements: list[ScreenshotReplacement]
) -> list[str]:
    media_parts: list[str] = []

    for replacement in replacements:
        if replacement.slide_number not in targets:
            raise ValueError(f"Slide {replacement.slide_number} not found in presentation")
        slide_targets = targets[replacement.slide_number]
        if replacement.picture_index < 0:
            raise ValueError(
                f"picture_index must be non-negative for slide {replacement.slide_number}"
            )
        if replacement.picture_index >= len(slide_targets):
            raise ValueError(
                f"Slide {replacement.slide_number} has {len(slide_targets)} picture target(s); "
                f"cannot use picture_index={replacement.picture_index}"
            )
        media_parts.append(slide_targets[replacement.picture_index])

    return media_parts
