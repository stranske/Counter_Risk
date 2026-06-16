"""Name registry parsing and validation helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from counter_risk.name_matching import canonicalize_match_key
from counter_risk.runtime_paths import resolve_runtime_path
from counter_risk.yaml_utils import load_yaml_model

_CANONICAL_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _normalize_alias_token(value: str) -> str:
    """Return the canonical match key for an alias (apostrophe + dash + whitespace + casefold)."""
    return canonicalize_match_key(value)


class SeriesIncludedFlags(BaseModel):
    """Optional per-variant and per-segment inclusion flags for a canonical series."""

    model_config = ConfigDict(extra="forbid")

    all_programs: bool = True
    ex_trend: bool = True
    trend: bool = True
    by_segment: dict[str, dict[str, bool]] = Field(default_factory=dict)

    @field_validator("by_segment")
    @classmethod
    def _validate_by_segment(
        cls, by_segment: dict[str, dict[str, bool]]
    ) -> dict[str, dict[str, bool]]:
        normalized: dict[str, dict[str, bool]] = {}
        for raw_variant, raw_segment_flags in by_segment.items():
            variant_key = str(raw_variant).strip().casefold()
            if not variant_key:
                raise ValueError("series_included.by_segment variant keys cannot be blank.")
            if variant_key not in {"all_programs", "ex_trend", "trend"}:
                raise ValueError(
                    "series_included.by_segment variant keys must be one of: "
                    "all_programs, ex_trend, trend."
                )
            if not isinstance(raw_segment_flags, dict):
                raise ValueError(
                    "series_included.by_segment values must be mappings of segment -> boolean."
                )
            segment_flags: dict[str, bool] = {}
            for raw_segment, flag in raw_segment_flags.items():
                segment_key = str(raw_segment).strip().casefold()
                if not segment_key:
                    raise ValueError("series_included.by_segment segment keys cannot be blank.")
                if segment_key in segment_flags:
                    raise ValueError(
                        f"series_included.by_segment duplicate segment key: {segment_key!r}"
                    )
                if not isinstance(flag, bool):
                    raise ValueError(
                        "series_included.by_segment flags must be boolean true/false values."
                    )
                segment_flags[segment_key] = flag
            normalized[variant_key] = segment_flags
        return normalized


class NameRegistryEntry(BaseModel):
    """A single canonical mapping entry."""

    model_config = ConfigDict(extra="forbid")

    canonical_key: str
    aliases: list[str] = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=80)
    series_included: SeriesIncludedFlags | None = None

    @field_validator("canonical_key")
    @classmethod
    def _validate_canonical_key(cls, value: str) -> str:
        if not _CANONICAL_KEY_PATTERN.fullmatch(value):
            raise ValueError(
                "canonical_key must match ^[a-z0-9]+(?:_[a-z0-9]+)*$ (snake_case lowercase)."
            )
        return value

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, aliases: list[str]) -> list[str]:
        normalized_seen: set[str] = set()
        normalized_aliases: list[str] = []

        for alias in aliases:
            if not isinstance(alias, str):
                raise ValueError("aliases entries must be strings.")
            display_form = " ".join(alias.split())
            if not display_form:
                raise ValueError("aliases cannot contain blank values.")
            dedupe_key = _normalize_alias_token(alias)
            if dedupe_key in normalized_seen:
                raise ValueError(
                    f"aliases contains duplicate value after normalization: {display_form!r}"
                )
            normalized_seen.add(dedupe_key)
            normalized_aliases.append(display_form)
        return normalized_aliases

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("display_name cannot be blank.")
        return normalized


class NameRegistryConfig(BaseModel):
    """Top-level registry schema."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    entries: list[NameRegistryEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_global_uniqueness(self) -> NameRegistryConfig:
        canonical_keys: set[str] = set()
        alias_index: dict[str, str] = {}

        for entry in self.entries:
            if entry.canonical_key in canonical_keys:
                raise ValueError(f"Duplicate canonical_key found: {entry.canonical_key!r}")
            canonical_keys.add(entry.canonical_key)

            for alias in entry.aliases:
                alias_token = _normalize_alias_token(alias)
                existing = alias_index.get(alias_token)
                if existing is None:
                    alias_index[alias_token] = entry.canonical_key
                    continue
                if existing != entry.canonical_key:
                    raise ValueError(
                        "Alias collision across entries: "
                        f"{alias!r} maps to both {existing!r} and {entry.canonical_key!r}"
                    )
        return self


def load_name_registry(path: str | Path = Path("config/name_registry.yml")) -> NameRegistryConfig:
    """Load and validate a name registry YAML file from disk."""

    config_path = Path(path)
    # In a frozen PyInstaller build a relative default like "config/..." is
    # resolved against the bundle roots; in source mode resolve_runtime_path
    # returns the path unchanged, preserving existing behavior.
    if not config_path.is_absolute() and getattr(sys, "frozen", False):
        config_path = resolve_runtime_path(config_path)
    return load_yaml_model(config_path, NameRegistryConfig, kind="Name registry")
