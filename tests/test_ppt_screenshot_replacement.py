"""Tests for zip-based PPT screenshot replacement."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from counter_risk.ppt.replace_screenshots import (
    ScreenshotReplacement,
    replace_screenshots_in_pptx,
    resolve_replacements_to_media_parts,
)


def _read_media_parts(pptx_path: Path) -> dict[str, bytes]:
    with ZipFile(pptx_path) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("ppt/media/") and not name.endswith("/")
        }


def test_replace_screenshots_writes_modified_ppt_and_changes_target_media_parts(
    tmp_path: Path,
) -> None:
    source = Path("tests/fixtures/Monthly Counterparty Exposure Report.pptx")
    output = tmp_path / "run" / source.name

    replacements = [
        ScreenshotReplacement(slide_number=1, picture_index=0, image_bytes=b"slide-1-replacement"),
        ScreenshotReplacement(slide_number=2, picture_index=0, image_bytes=b"slide-2-replacement"),
    ]

    expected_targets = resolve_replacements_to_media_parts(
        pptx_path=source,
        replacements=replacements,
    )

    result = replace_screenshots_in_pptx(
        source_pptx_path=source,
        output_pptx_path=output,
        replacements=replacements,
    )

    assert output.exists()
    assert output.read_bytes() != source.read_bytes()

    input_media = _read_media_parts(source)
    output_media = _read_media_parts(output)

    changed_media_parts = sorted(
        name
        for name, bytes_payload in output_media.items()
        if input_media.get(name) != bytes_payload
    )
    assert changed_media_parts == sorted(expected_targets)
    assert changed_media_parts == result.replaced_media_parts
