"""Shared YAML loading utilities for config, limits, and name-registry loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ValidationError


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys in mappings."""


def _construct_mapping_no_duplicates(
    loader: _NoDuplicateSafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = cast(Any, loader.construct_object(key_node, deep=deep))
        if key in mapping:
            raise ValueError(f"duplicate key '{key}'")
        mapping[key] = cast(Any, loader.construct_object(value_node, deep=deep))
    return mapping


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_no_duplicates
)


def _format_yaml_validation_error(error: ValidationError, kind: str) -> str:
    lines = [f"{kind} validation failed:"]
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        message = issue.get("msg", "Invalid value")
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def load_yaml_model[M: BaseModel](
    path: str | Path,
    model_cls: type[M],
    *,
    kind: str,
    reject_duplicate_keys: bool = True,
) -> M:
    """Load a YAML file and validate it against a Pydantic model."""
    config_path = Path(path)
    loader_cls: type[yaml.SafeLoader] = (
        _NoDuplicateSafeLoader if reject_duplicate_keys else yaml.SafeLoader
    )
    try:
        loader = loader_cls(config_path.read_text(encoding="utf-8"))
        try:
            raw = loader.get_single_data()
        finally:
            cast(Any, loader).dispose()
    except OSError as exc:
        raise ValueError(f"Unable to read {kind} file '{config_path}': {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"Invalid YAML in {kind} file '{config_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {kind} file '{config_path}': {exc}") from exc

    data: Any = raw if raw is not None else {}
    if not isinstance(data, dict):
        raise ValueError(f"{kind} file '{config_path}' must contain a top-level mapping/object.")

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ValueError(_format_yaml_validation_error(exc, kind)) from exc
