"""Screenshot replacement helpers for PowerPoint reports."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape
from pptx.slide import Slide


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _slide_title(slide: Slide) -> str:
    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            continue
        text_frame = getattr(shape, "text_frame", None)
        if text_frame is None:
            continue
        text = str(getattr(text_frame, "text", "")).strip()
        if text:
            return text
    return ""


def _picture_shapes(slide: Slide) -> list[BaseShape]:
    return [shape for shape in slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE]


def _resolve_image_path(value: Path | str) -> Path:
    image_path = Path(value)
    if not image_path.exists() or not image_path.is_file():
        raise ValueError(f"replacement image does not exist: {image_path}")
    return image_path


def replace_screenshot_pictures(
    pptx_in: Path | str,
    images_by_section: Mapping[str, Path | str],
    pptx_out: Path | str,
) -> None:
    """Replace existing screenshot pictures by matching section titles.

    Matching is based on section-title text plus existing picture shapes in the
    matched slide. Existing picture shapes are replaced in-place by preserving
    their count, location, and size.
    """

    source = Path(pptx_in)
    destination = Path(pptx_out)
    if not source.exists() or not source.is_file():
        raise ValueError(f"input pptx does not exist: {source}")

    normalized_targets: dict[str, Path] = {}
    for section, image in images_by_section.items():
        normalized_targets[_normalize_key(section)] = _resolve_image_path(image)

    if not normalized_targets:
        raise ValueError("images_by_section must contain at least one section mapping")

    presentation = Presentation(str(source))
    matched_sections: set[str] = set()

    for slide in presentation.slides:
        title_key = _normalize_key(_slide_title(slide))
        if not title_key:
            continue

        matched_target: str | None = None
        for section_key in normalized_targets:
            if section_key == title_key or section_key in title_key:
                matched_target = section_key
                break

        if matched_target is None:
            continue

        pictures = _picture_shapes(slide)
        if not pictures:
            raise ValueError(
                "matched slide has no picture shapes for section " f"'{matched_target}'"
            )

        replacement = normalized_targets[matched_target]
        for picture in list(pictures):
            left, top, width, height = picture.left, picture.top, picture.width, picture.height
            slide.shapes.add_picture(str(replacement), left, top, width=width, height=height)
            picture._element.getparent().remove(picture._element)

        if len(_picture_shapes(slide)) != len(pictures):
            raise ValueError(
                "picture replacement changed shape count for section " f"'{matched_target}'"
            )

        matched_sections.add(matched_target)

    missing = sorted(set(normalized_targets) - matched_sections)
    if missing:
        raise ValueError("no matching slide title found for sections: " + ", ".join(missing))

    destination.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(destination))
