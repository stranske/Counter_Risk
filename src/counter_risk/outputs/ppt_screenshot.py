"""Output generator for monthly PPT screenshot replacement."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig
from counter_risk.outputs.base import OutputContext, OutputGenerator
from counter_risk.pipeline.ppt_naming import PptOutputNames, resolve_ppt_output_names

ScreenshotReplacer = Callable[[Path, Path, dict[str, Path]], None]
_ScreenshotInputMappingResolver = Callable[[WorkflowConfig], dict[str, Path]]
_ScreenshotReplacerResolver = Callable[[str], ScreenshotReplacer]
_MasterLinkTargetValidator = Callable[..., None]
_PptOutputNamesResolver = Callable[[date], PptOutputNames]
_PptCopier = Callable[[str | Path, str | Path], str]


def _copy_ppt(source: str | Path, destination: str | Path) -> str:
    return shutil.copy2(str(source), str(destination))


def export_ppt_slides_as_png_via_com(*, source_pptx: Path, slide_images_dir: Path) -> list[Path]:
    """Export one PNG image per slide via PowerPoint COM automation."""
    from counter_risk.integrations.powerpoint_com import initialize_powerpoint_application

    app: Any | None = None
    presentation: Any | None = None
    slide_images: list[Path] = []
    try:
        app = initialize_powerpoint_application()
        with suppress(Exception):
            app.Visible = 0
        presentation = app.Presentations.Open(str(source_pptx), False, True, False)

        slide_images_dir.mkdir(parents=True, exist_ok=True)
        slide_count = int(presentation.Slides.Count)
        for slide_idx in range(1, slide_count + 1):
            image_path = slide_images_dir / f"slide_{slide_idx:04d}.png"
            try:
                presentation.Slides[slide_idx].Export(str(image_path), "PNG")
            except Exception as exc:
                raise RuntimeError(
                    "PowerPoint slide PNG export failed "
                    f"for slide {slide_idx} to '{image_path}': {exc}"
                ) from exc
            slide_images.append(image_path)
    finally:
        if presentation is not None:
            with suppress(Exception):
                presentation.Close()
        if app is not None:
            with suppress(Exception):
                app.Quit()
    return slide_images


@dataclass(frozen=True)
class PptScreenshotOutputGenerator(OutputGenerator):
    """Generate the Master PPT output with optional screenshot replacement."""

    warnings: list[str]
    screenshot_input_mapping_resolver: _ScreenshotInputMappingResolver
    screenshot_replacer_resolver: _ScreenshotReplacerResolver
    master_link_target_validator: _MasterLinkTargetValidator
    name: str = "ppt_screenshot"
    ppt_output_names_resolver: _PptOutputNamesResolver = resolve_ppt_output_names
    ppt_copier: _PptCopier = _copy_ppt

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        config = context.config
        if not config.ppt_output_enabled:
            return ()

        source_ppt = config.monthly_pptx
        output_names = self.ppt_output_names_resolver(context.as_of_date)
        target_master_ppt = context.run_dir / output_names.master_filename
        target_master_ppt.parent.mkdir(parents=True, exist_ok=True)
        screenshot_inputs = self.screenshot_input_mapping_resolver(config)

        if config.enable_screenshot_replacement:
            replacer = self.screenshot_replacer_resolver(
                config.screenshot_replacement_implementation
            )
            replacer(source_ppt, target_master_ppt, screenshot_inputs)
        else:
            self.ppt_copier(source_ppt, target_master_ppt)
            if screenshot_inputs:
                self.warnings.append(
                    "PPT screenshots replacement disabled; copied source deck to Master unchanged"
                )

        self.master_link_target_validator(
            source_pptx_path=source_ppt,
            master_pptx_path=target_master_ppt,
        )
        return (target_master_ppt,)
