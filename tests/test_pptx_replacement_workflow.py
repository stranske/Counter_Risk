from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from counter_risk.writers.pptx_screenshots import replace_screenshot_pictures

_RED_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6n8e0AAAAASUVORK5CYII="
)
_BLUE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAwMBAX0X6XQAAAAASUVORK5CYII="
)
_GREEN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP4DwQACfsD/QX+vJ8AAAAASUVORK5CYII="
)

_TARGET_PICTURE_GEOMETRY = {
    "All Programs": (0, 811705, 9144000, 5817695),
    "Ex Trend": (0, 1304636, 9144000, 5172364),
    "Trend": (0, 2031298, 9144000, 2795403),
}


def _write_png(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _make_workflow_pptx(path: Path, base_image: Path) -> None:
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]

    for title in ("All Programs", "Ex Trend", "Trend"):
        slide = prs.slides.add_slide(blank_layout)
        textbox = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(0.25),
            Inches(8.5),
            Inches(0.6),
        )
        textbox.text_frame.text = title

        left, top, width, height = _TARGET_PICTURE_GEOMETRY[title]
        slide.shapes.add_picture(
            str(base_image),
            left,
            top,
            width=width,
            height=height,
        )

    prs.save(str(path))


def _slide_picture_state(slide: object) -> tuple[int, tuple[tuple[str, tuple[int, int, int, int]], ...]]:
    pictures = [shape for shape in slide.shapes if shape.shape_type == 13]
    details = tuple(
        (
            hashlib.sha256(picture.image.blob).hexdigest(),
            (picture.left, picture.top, picture.width, picture.height),
        )
        for picture in pictures
    )
    return len(pictures), details


def test_replacement_workflow_output_reopens(tmp_path: Path) -> None:
    source = tmp_path / "input.pptx"
    output = tmp_path / "output.pptx"

    base_image = tmp_path / "base.png"
    all_programs_image = tmp_path / "all_programs.png"
    ex_trend_image = tmp_path / "ex_trend.png"
    trend_image = tmp_path / "trend.png"

    _write_png(base_image, _RED_PNG)
    _write_png(all_programs_image, _BLUE_PNG)
    _write_png(ex_trend_image, _GREEN_PNG)
    _write_png(trend_image, _BLUE_PNG)

    _make_workflow_pptx(source, base_image)
    before = Presentation(str(source))
    before_by_title = {
        slide.shapes[0].text_frame.text: _slide_picture_state(slide) for slide in before.slides
    }

    replace_screenshot_pictures(
        source,
        {
            "All Programs": all_programs_image,
            "Ex Trend": ex_trend_image,
            "Trend": trend_image,
        },
        output,
    )

    reopened = Presentation(str(output))
    assert len(reopened.slides) == 3
    after_by_title = {
        slide.shapes[0].text_frame.text: _slide_picture_state(slide) for slide in reopened.slides
    }

    for title in ("All Programs", "Ex Trend", "Trend"):
        before_count, before_details = before_by_title[title]
        after_count, after_details = after_by_title[title]
        assert before_count == after_count
        assert len(before_details) == len(after_details)
        assert any(
            before_hash != after_hash
            for (before_hash, _), (after_hash, _) in zip(before_details, after_details, strict=True)
        )
        assert [geometry for _, geometry in before_details] == [
            geometry for _, geometry in after_details
        ]
