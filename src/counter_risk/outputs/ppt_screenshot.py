"""Output generator for monthly PPT screenshot replacement."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
