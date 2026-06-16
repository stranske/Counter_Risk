"""Limits configuration parsing and validation helpers."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from counter_risk.runtime_paths import RuntimePathResolutionError, resolve_runtime_path
from counter_risk.yaml_utils import load_yaml_model


class LimitEntry(BaseModel):
    """A single limit policy target."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["counterparty", "fcm", "clearing_house", "segment", "custom_group"]
    entity_name: str = Field(min_length=1)
    limit_value: float = Field(gt=0)
    limit_kind: Literal["absolute_notional", "percent_of_total"]
    severity: Literal["warning", "fail"] = "warning"
    enabled: bool = True
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

    @model_validator(mode="after")
    def _validate_unique_limit_keys(self) -> LimitsConfig:
        seen: set[tuple[str, str, str]] = set()
        duplicates: list[str] = []
        for limit in self.limits:
            key = (limit.entity_type, limit.entity_name, limit.limit_kind)
            if key in seen:
                duplicates.append(":".join(key))
            seen.add(key)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate limit keys are not allowed: {duplicate_list}")
        return self


def load_limits_config(path: str | Path = Path("config/limits.yml")) -> LimitsConfig:
    """Load and validate a limits YAML configuration file from disk."""

    config_path = Path(path)
    # In a frozen PyInstaller build a relative default like "config/..." is
    # resolved against the bundle roots; in source mode resolve_runtime_path
    # returns the path unchanged, preserving existing behavior.
    if not config_path.is_absolute() and getattr(sys, "frozen", False):
        with contextlib.suppress(RuntimePathResolutionError):
            config_path = resolve_runtime_path(config_path)
    return load_yaml_model(config_path, LimitsConfig, kind="Limits config")
