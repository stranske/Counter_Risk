"""Deterministic mapping diff report generator."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from counter_risk.name_registry import load_name_registry
from counter_risk.normalize import resolve_counterparty

_NORMALIZATION_NAME_KEYS = {
    "counterparty",
    "counterparty_name",
    "name",
    "raw_counterparty",
    "raw_name",
}
_RECONCILIATION_NAME_KEYS = {
    "counterparties_in_data",
    "raw_counterparty_labels",
}


def _title_case_suggestion(raw_name: str) -> str:
    return raw_name.title()


def _is_nonblank(value: str) -> bool:
    return bool(value.strip())


def _iter_string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        if _is_nonblank(value):
            yield value
        return
    if isinstance(value, Mapping):
        return
    if isinstance(value, Iterable):
        for item in value:
            yield from _iter_string_values(item)


def _iter_names_from_payload(
    value: Any,
    *,
    name_keys: set[str],
    collect_strings: bool = False,
) -> Iterator[str]:
    if isinstance(value, str):
        if collect_strings:
            if _is_nonblank(value):
                yield value
        return

    if isinstance(value, Mapping):
        for raw_key, raw_child in value.items():
            key = str(raw_key).strip().casefold()
            child_collect = collect_strings or key in name_keys
            yield from _iter_names_from_payload(
                raw_child,
                name_keys=name_keys,
                collect_strings=child_collect,
            )
        return

    if isinstance(value, Iterable):
        for child in value:
            yield from _iter_names_from_payload(
                child,
                name_keys=name_keys,
                collect_strings=collect_strings,
            )


def _iter_flat_string_sequence(payload: Any) -> Iterator[str]:
    if isinstance(payload, str) or isinstance(payload, Mapping):
        return
    if not isinstance(payload, Iterable):
        return

    values = list(payload)
    if not values or not all(isinstance(value, str) for value in values):
        return

    for value in values:
        if _is_nonblank(value):
            yield value


def _iter_input_names(input_sources: Mapping[str, Any]) -> Iterable[str]:
    for source_name in sorted(input_sources):
        payload = input_sources[source_name]
        source_key = str(source_name).strip().casefold()
        if source_key == "normalization":
            yield from _iter_flat_string_sequence(payload)
            yield from _iter_names_from_payload(payload, name_keys=_NORMALIZATION_NAME_KEYS)
            continue
        if source_key == "reconciliation":
            yield from _iter_flat_string_sequence(payload)
            yield from _iter_names_from_payload(payload, name_keys=_RECONCILIATION_NAME_KEYS)
            continue

        # Backward-compatible fallback for legacy callers that pass a flat list of names.
        yield from _iter_string_values(payload)


def generate_mapping_diff_report(
    registry_path: str | Path,
    input_sources: Mapping[str, Any],
) -> str:
    """Generate a deterministic mapping diff report."""

    # Load once so missing/unreadable/invalid registry is treated as fatal for report generation.
    load_name_registry(registry_path)

    unmapped_names: dict[str, None] = {}
    fallback_mapped: dict[str, str] = {}

    for raw_name in _iter_input_names(input_sources):
        result = resolve_counterparty(raw_name, registry_path=registry_path)
        if result.source == "fallback":
            fallback_mapped.setdefault(raw_name, result.canonical_name)
            continue
        if result.source == "unmapped":
            unmapped_names.setdefault(raw_name, None)

    lines: list[str] = ["UNMAPPED"]
    lines.extend(sorted(unmapped_names, key=str.casefold))
    lines.append("")

    lines.append("FALLBACK_MAPPED")
    for raw_name in sorted(fallback_mapped, key=str.casefold):
        lines.append(f"{raw_name} -> {fallback_mapped[raw_name]}")
    lines.append("")

    lines.append("SUGGESTIONS")
    for raw_name in sorted(unmapped_names, key=str.casefold):
        lines.append(f"{raw_name} -> {_title_case_suggestion(raw_name)}")

    return "\n".join(lines) + "\n"
