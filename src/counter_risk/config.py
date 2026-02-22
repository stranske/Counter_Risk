"""Workflow configuration models and loaders."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class WorkflowConfig(BaseModel):
    """Configuration for a single Counter Risk workflow execution.

    This model captures all input artifacts needed for the three workflow
    variants (All Programs, Ex Trend, Trend), along with the optional report
    date and output root directory.
    """

    model_config = ConfigDict(extra="forbid")

    as_of_date: date | None = None
    mosers_all_programs_xlsx: Path | None = None
    raw_nisa_all_programs_xlsx: Path | None = None
    mosers_ex_trend_xlsx: Path
    mosers_trend_xlsx: Path
    hist_all_programs_3yr_xlsx: Path
    hist_ex_llc_3yr_xlsx: Path
    hist_llc_3yr_xlsx: Path
    monthly_pptx: Path
    enable_screenshot_replacement: bool = False
    screenshot_replacement_implementation: Literal["zip", "python-pptx"] = "zip"
    screenshot_inputs: dict[str, Path] = Field(default_factory=dict)
    distribution_static: bool = False
    output_root: Path = Path("runs")


def _format_validation_error(error: ValidationError) -> str:
    lines = ["Configuration validation failed:"]
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        message = issue.get("msg", "Invalid value")
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def load_config(path: str | Path) -> WorkflowConfig:
    """Load a YAML workflow configuration file from disk."""

    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read config file '{config_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file '{config_path}': {exc}") from exc

    data: Any = raw if raw is not None else {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Configuration file '{config_path}' must contain a top-level mapping/object."
        )

    try:
        return WorkflowConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_format_validation_error(exc)) from exc
