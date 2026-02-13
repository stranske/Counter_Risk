"""PowerPoint artifact helpers."""

from counter_risk.ppt.replace_screenshots import (
    PptScreenshotReplacementError,
    ReplacementResult,
    ScreenshotReplacement,
    list_slide_picture_targets,
    replace_screenshots_in_pptx,
    resolve_replacements_to_media_parts,
)

__all__ = [
    "PptScreenshotReplacementError",
    "ReplacementResult",
    "ScreenshotReplacement",
    "list_slide_picture_targets",
    "replace_screenshots_in_pptx",
    "resolve_replacements_to_media_parts",
]
