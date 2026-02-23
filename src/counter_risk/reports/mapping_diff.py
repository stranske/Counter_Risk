"""Deterministic mapping diff report generator."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from counter_risk.name_registry import load_name_registry
from counter_risk.normalize import resolve_counterparty


def _title_case_suggestion(raw_name: str) -> str:
    return raw_name.title()


def _iter_input_names(input_sources: Mapping[str, Iterable[str]]) -> Iterable[str]:
    for source_name in sorted(input_sources):
        for raw_name in input_sources[source_name]:
            yield raw_name


def generate_mapping_diff_report(
    registry_path: str | Path,
    input_sources: Mapping[str, Iterable[str]],
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
