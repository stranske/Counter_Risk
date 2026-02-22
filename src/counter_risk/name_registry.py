"""Name registry parsing and validation helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_CANONICAL_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _normalize_alias_token(value: str) -> str:
    return " ".join(value.split()).casefold()


class SeriesIncludedFlags(BaseModel):
    """Optional per-variant inclusion flags for a canonical series."""

    model_config = ConfigDict(extra="forbid")

    all_programs: bool = True
    ex_trend: bool = True
    trend: bool = True


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
            normalized = " ".join(alias.split())
            if not normalized:
                raise ValueError("aliases cannot contain blank values.")
            dedupe_key = normalized.casefold()
            if dedupe_key in normalized_seen:
                raise ValueError(
                    f"aliases contains duplicate value after normalization: {normalized!r}"
                )
            normalized_seen.add(dedupe_key)
            normalized_aliases.append(normalized)
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

    schema_version: int
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


def _format_registry_validation_error(error: ValidationError) -> str:
    lines = ["Name registry validation failed:"]
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        message = issue.get("msg", "Invalid value")
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def load_name_registry(path: str | Path = Path("config/name_registry.yml")) -> NameRegistryConfig:
    """Load and validate a name registry YAML file from disk."""

    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read name registry file '{config_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in name registry file '{config_path}': {exc}") from exc

    data: Any = raw if raw is not None else {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Name registry file '{config_path}' must contain a top-level mapping/object."
        )

    try:
        return NameRegistryConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_format_registry_validation_error(exc)) from exc
