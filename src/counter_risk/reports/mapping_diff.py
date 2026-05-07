"""Deterministic mapping diff report generator."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from counter_risk.name_registry import load_name_registry
from counter_risk.normalize import canonicalize_name, resolve_counterparty, safe_display_name

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


def _sorted_raw_names(values: Iterable[str]) -> list[str]:
    """Sort names deterministically with case-insensitive primary ordering."""

    return sorted(values, key=lambda raw_name: (raw_name.casefold(), raw_name))


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
        if collect_strings and _is_nonblank(value):
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
    if isinstance(payload, (str, Mapping)):
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


def collect_mapping_diff_findings(
    registry_path: str | Path,
    input_sources: Mapping[str, Any],
) -> dict[str, Any]:
    """Collect unmapped and fallback-mapped raw names using mapping-diff scan semantics."""

    # Load once so missing/unreadable/invalid registry is treated as fatal for comparison.
    load_name_registry(registry_path)

    unmapped_names: dict[str, None] = {}
    fallback_mapped: dict[str, str] = {}
    all_resolutions: dict[str, dict[str, str]] = {}

    for raw_name in _iter_input_names(input_sources):
        result = resolve_counterparty(raw_name, registry_path=registry_path)
        if raw_name not in all_resolutions:
            all_resolutions[raw_name] = {
                "raw": raw_name,
                "display": safe_display_name(raw_name),
                "canonical_key": result.canonical_key or canonicalize_name(raw_name),
                "mapped": result.canonical_name,
                "source": result.source,
            }
        if result.source == "fallback":
            fallback_mapped.setdefault(raw_name, result.canonical_name)
            continue
        if result.source == "unmapped":
            unmapped_names.setdefault(raw_name, None)

    return {
        "unmapped_raw_names": _sorted_raw_names(unmapped_names),
        "fallback_mapped": {
            raw_name: fallback_mapped[raw_name] for raw_name in _sorted_raw_names(fallback_mapped)
        },
        "name_resolutions": [
            all_resolutions[raw_name] for raw_name in _sorted_raw_names(all_resolutions)
        ],
    }


def generate_mapping_diff_report(
    registry_path: str | Path,
    input_sources: Mapping[str, Any],
    *,
    output_format: str = "text",
) -> str:
    """Generate a deterministic mapping diff report."""

    if output_format != "text":
        raise ValueError(f"Unsupported output format: {output_format}")

    findings = collect_mapping_diff_findings(registry_path, input_sources)
    unmapped_names = findings["unmapped_raw_names"]
    fallback_mapped = findings["fallback_mapped"]
    name_resolutions: list[dict[str, str]] = findings.get("name_resolutions", [])

    lines: list[str] = ["UNMAPPED"]
    lines.extend(unmapped_names)
    lines.append("")

    lines.append("FALLBACK_MAPPED")
    for raw_name in fallback_mapped:
        lines.append(f"{raw_name} -> {fallback_mapped[raw_name]}")
    lines.append("")

    lines.append("SUGGESTIONS")
    for raw_name in _sorted_raw_names(unmapped_names):
        lines.append(f"{raw_name} -> {_title_case_suggestion(raw_name)}")
    lines.append("")

    lines.append("NAME_RESOLUTIONS")
    for entry in name_resolutions:
        lines.append(
            f"raw={entry['raw']!r} display={entry['display']!r} "
            f"key={entry['canonical_key']!r} -> {entry['mapped']!r} [{entry['source']}]"
        )

    return "\n".join(lines) + "\n"
