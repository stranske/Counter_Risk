"""Limits configuration parsing and validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class LimitEntry(BaseModel):
    """A single limit policy target."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["counterparty", "fcm", "clearing_house", "segment", "custom_group"]
    entity_name: str = Field(min_length=1)
    limit_value: float = Field(gt=0)
    limit_kind: Literal["absolute_notional", "percent_of_total"]
    notes: str | None = None

    @field_validator("entity_name")
    @classmethod
    def _validate_entity_name(cls, value: str) -> str:
        normalized = "_".join(value.strip().split())
        if not normalized:
            raise ValueError("entity_name cannot be blank")
        return normalized.casefold()

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            return None
        return normalized


class LimitsConfig(BaseModel):
    """Top-level limits configuration schema."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    strict_missing_entities: bool = False
    limits: list[LimitEntry] = Field(min_length=1)


def _format_limits_validation_error(error: ValidationError) -> str:
    lines = ["Limits config validation failed:"]
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        message = issue.get("msg", "Invalid value")
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def load_limits_config(path: str | Path = Path("config/limits.yml")) -> LimitsConfig:
    """Load and validate a limits YAML configuration file from disk."""

    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read limits config file '{config_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in limits config file '{config_path}': {exc}") from exc

    data: Any = raw if raw is not None else {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Limits config file '{config_path}' must contain a top-level mapping/object."
        )

    try:
        return LimitsConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_format_limits_validation_error(exc)) from exc
