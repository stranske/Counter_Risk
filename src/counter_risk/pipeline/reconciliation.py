"""Series/header reconciliation utilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from counter_risk.normalize import (
    canonicalize_name,
    normalize_counterparty,
    normalize_counterparty_with_source,
)
from counter_risk.pipeline.parsing_types import (
    ParsedDataInvalidShapeError,
    ParsedDataMissingKeyError,
    UnmappedCounterpartyError,
)


def reconcile_series_coverage(
    *,
    parsed_data_by_sheet: Mapping[str, Mapping[str, Any]],
    historical_series_headers_by_sheet: Mapping[str, tuple[str, ...] | list[str] | set[str]],
    variant: str | None = None,
    expected_segments_by_variant: (
        Mapping[str, tuple[str, ...] | list[str] | set[str]] | None
    ) = None,
    fail_policy: Literal["warn", "strict"] = "warn",
) -> dict[str, Any]:
    """Reconcile parsed series labels against historical workbook headers per sheet."""
    _validate_reconciliation_parsed_data_by_sheet(parsed_data_by_sheet=parsed_data_by_sheet)

    by_sheet: dict[str, dict[str, Any]] = {}
    missing_series: list[dict[str, Any]] = []
    missing_segments: list[dict[str, Any]] = []
    exceptions: list[UnmappedCounterpartyError] = []
    warnings: list[str] = []
    gap_count = 0

    expected_segments = _expected_segments_for_variant(
        variant=variant,
        expected_segments_by_variant=expected_segments_by_variant,
    )
    sheet_names = sorted(
        set(parsed_data_by_sheet).union(historical_series_headers_by_sheet), key=str.casefold
    )
    for sheet_name in sheet_names:
        parsed_sections = parsed_data_by_sheet.get(sheet_name, {})
        totals_records = _records(parsed_sections.get("totals", []))
        futures_records = _records(parsed_sections.get("futures", []))
        historical_series_headers = sorted(
            {
                value
                for value in (
                    canonicalize_name(str(header))
                    for header in historical_series_headers_by_sheet.get(sheet_name, ())
                )
                if value
            }
        )

        counterparties_in_data = sorted(
            {
                value
                for value in (
                    str(record.get("counterparty", "")).strip() for record in totals_records
                )
                if value
            }
        )
        (
            normalized_counterparties_in_data,
            counterparty_sources_by_raw_name,
        ) = _counterparty_resolution_maps_from_records(totals_records)
        raw_counterparties_by_normalized = _raw_counterparties_by_normalized_from_parsed_data(
            parsed_sections
        )
        clearing_houses_in_data = sorted(
            {
                value
                for value in (
                    canonicalize_name(str(record.get("clearing_house", "")))
                    for record in futures_records
                )
                if value
            }
        )
        normalized_historical_series_headers = {
            normalize_counterparty(header) for header in historical_series_headers
        }
        missing_normalized_counterparties = sorted(
            set(normalized_counterparties_in_data).difference(normalized_historical_series_headers),
            key=str.casefold,
        )
        missing_counterparty_labels = sorted(
            {
                canonicalize_name(raw_name)
                for normalized_name in missing_normalized_counterparties
                for raw_name in normalized_counterparties_in_data.get(normalized_name, ())
                if canonicalize_name(raw_name)
            },
            key=str.casefold,
        )
        missing_clearing_houses = sorted(
            set(clearing_houses_in_data).difference(historical_series_headers), key=str.casefold
        )
        current_series_labels = sorted(
            set(counterparties_in_data).union(clearing_houses_in_data), key=str.casefold
        )
        normalized_current_series_labels = set(normalized_counterparties_in_data).union(
            {normalize_counterparty(clearing_house) for clearing_house in clearing_houses_in_data}
        )
        missing_from_historical = sorted(
            set(missing_counterparty_labels).union(missing_clearing_houses), key=str.casefold
        )
        missing_from_data = sorted(
            {
                header
                for header in historical_series_headers
                if normalize_counterparty(header) not in normalized_current_series_labels
            },
            key=str.casefold,
        )
        parsed_segments = _extract_segments_from_records(parsed_sections)
        missing_expected_segments = sorted(
            expected_segments.difference(parsed_segments), key=str.casefold
        )

        if missing_from_historical:
            gap_count += len(missing_from_historical)
            missing_series.append(
                {
                    "variant": variant,
                    "sheet": sheet_name,
                    "missing_from_historical_headers": missing_from_historical,
                    "data_source_context": "counterparties_and_clearing_houses",
                }
            )
            warnings.append(
                "Reconciliation gap in sheet "
                f"{sheet_name!r}: series present in parsed data but missing from historical "
                f"headers ({', '.join(missing_from_historical)})"
            )

        if missing_from_data:
            gap_count += len(missing_from_data)
            warnings.append(
                "Reconciliation gap in sheet "
                f"{sheet_name!r}: series present in historical headers but missing from parsed "
                f"data ({', '.join(missing_from_data)})"
            )

        if missing_normalized_counterparties:
            sheet_exceptions: list[UnmappedCounterpartyError] = []
            raw_counterparties_for_metadata: list[str] = []
            for normalized_name in missing_normalized_counterparties:
                raw_names = sorted(
                    set(raw_counterparties_by_normalized.get(normalized_name, ())),
                    key=str.casefold,
                )
                raw_counterparties_for_metadata.extend(raw_names)
                raw_display = ", ".join(raw_names)
                warnings.append(
                    "Reconciliation unmapped counterparty in sheet "
                    f"{sheet_name!r}: raw={raw_display!r}, normalized={normalized_name!r}, "
                    "source="
                    + ",".join(
                        sorted(
                            {
                                counterparty_sources_by_raw_name.get(raw_name, "unmapped")
                                for raw_name in raw_names
                            }
                        )
                    )
                )
                for raw_name in raw_names:
                    error = UnmappedCounterpartyError(
                        normalized_counterparty=normalized_name,
                        raw_counterparty=raw_name,
                        sheet=sheet_name,
                    )
                    sheet_exceptions.append(error)
                    exceptions.append(error)

            if raw_counterparties_for_metadata:
                missing_series.append(
                    {
                        "variant": variant,
                        "sheet": sheet_name,
                        "error_type": "unmapped_counterparty",
                        "raw_counterparties": raw_counterparties_for_metadata,
                        "normalized_counterparties": missing_normalized_counterparties,
                    }
                )

            if fail_policy == "strict":
                if sheet_exceptions:
                    raise sheet_exceptions[0]
                raise UnmappedCounterpartyError(
                    normalized_counterparty=missing_normalized_counterparties[0],
                    raw_counterparty=missing_normalized_counterparties[0],
                    sheet=sheet_name,
                )

        if missing_expected_segments:
            gap_count += len(missing_expected_segments)
            missing_segments.append(
                {
                    "variant": variant,
                    "sheet": sheet_name,
                    "expected_segment_identifiers": missing_expected_segments,
                }
            )
            warnings.append(
                "Reconciliation gap in variant "
                f"{variant!r} sheet {sheet_name!r}: expected segments missing from parsed "
                f"results ({', '.join(missing_expected_segments)})"
            )

        canonical_key_by_series: dict[str, str] = {}
        for canonical_name, raw_name_set in normalized_counterparties_in_data.items():
            for raw in raw_name_set:
                canonical_key_by_series[raw] = canonical_name
        for ch in clearing_houses_in_data:
            canonical_key_by_series[ch] = normalize_counterparty(ch)

        by_sheet[sheet_name] = {
            "counterparties_in_data": counterparties_in_data,
            "normalized_counterparties_in_data": sorted(
                normalized_counterparties_in_data, key=str.casefold
            ),
            "clearing_houses_in_data": clearing_houses_in_data,
            "historical_series_headers": historical_series_headers,
            "normalized_historical_series_headers": sorted(
                normalized_historical_series_headers, key=str.casefold
            ),
            "current_series_labels": current_series_labels,
            "missing_from_historical_headers": missing_from_historical,
            "missing_normalized_counterparties": missing_normalized_counterparties,
            "missing_from_data": missing_from_data,
            "segments_in_data": sorted(parsed_segments, key=str.casefold),
            "missing_expected_segments": missing_expected_segments,
            "canonical_key_by_series": canonical_key_by_series,
        }
    result = {
        "by_sheet": by_sheet,
        "gap_count": gap_count,
        "warnings": warnings,
        "missing_series": missing_series,
        "missing_segments": missing_segments,
    }
    if exceptions:
        result["exceptions"] = list(exceptions)
    return result


def _validate_reconciliation_parsed_data_by_sheet(
    *, parsed_data_by_sheet: Mapping[str, Mapping[str, Any]]
) -> None:
    for raw_sheet_name, raw_sections in parsed_data_by_sheet.items():
        sheet_name = str(raw_sheet_name)
        if not isinstance(raw_sections, Mapping):
            raise ParsedDataInvalidShapeError(
                f"Invalid parsed_data shape for sheet {sheet_name!r}: expected a mapping/object"
            )

        missing_sections = [
            section for section in ("totals", "futures") if section not in raw_sections
        ]
        if missing_sections:
            raise ParsedDataMissingKeyError(
                f"Missing required parsed_data section(s) for sheet {sheet_name!r}: "
                f"{', '.join(missing_sections)}"
            )

        for section_name in ("totals", "futures"):
            section_value = raw_sections[section_name]
            if not _is_supported_table_shape(section_value):
                raise ParsedDataInvalidShapeError(
                    f"Invalid parsed_data shape for sheet {sheet_name!r} section "
                    f"{section_name!r}: expected list of mappings or tabular object with "
                    "to_dict(orient='records')/to_records()"
                )


def _is_supported_table_shape(table: Any) -> bool:
    if isinstance(table, list):
        return all(isinstance(record, Mapping) for record in table)
    return hasattr(table, "to_dict") or hasattr(table, "to_records")


def _expected_segments_for_variant(
    *,
    variant: str | None,
    expected_segments_by_variant: Mapping[str, tuple[str, ...] | list[str] | set[str]] | None,
) -> set[str]:
    if not variant or not expected_segments_by_variant:
        return set()

    for key, values in expected_segments_by_variant.items():
        if str(key).strip().casefold() != variant.strip().casefold():
            continue
        return {str(value).strip() for value in values if str(value).strip()}
    return set()


def _extract_segments_from_records(parsed_sections: Mapping[str, Any]) -> set[str]:
    segments: set[str] = set()
    for table in parsed_sections.values():
        for record in _records(table):
            raw_segment = record.get("segment", record.get("Segment", ""))
            label = str(raw_segment).strip()
            if label:
                segments.add(label)
    return segments


def _counterparty_resolution_maps_from_records(
    totals_records: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    normalized_to_raw: dict[str, set[str]] = {}
    sources_by_raw_name: dict[str, str] = {}
    for record in totals_records:
        raw_name = str(record.get("counterparty", "")).strip()
        if not raw_name:
            continue
        resolution = normalize_counterparty_with_source(raw_name)
        normalized_to_raw.setdefault(resolution.canonical_name, set()).add(raw_name)
        sources_by_raw_name[raw_name] = resolution.source
    return normalized_to_raw, sources_by_raw_name


def _normalized_counterparties_from_records(
    totals_records: list[dict[str, Any]],
) -> dict[str, set[str]]:
    normalized_to_raw, _ = _counterparty_resolution_maps_from_records(totals_records)
    return normalized_to_raw


def _raw_counterparties_by_normalized_from_records(
    totals_records: list[dict[str, Any]],
) -> dict[str, set[str]]:
    normalized_to_raw: dict[str, set[str]] = {}
    for record in totals_records:
        raw_value = record.get("counterparty", "")
        if raw_value is None:
            continue
        raw_name = str(raw_value)
        if not raw_name.strip():
            continue
        normalized_name = normalize_counterparty(raw_name)
        normalized_to_raw.setdefault(normalized_name, set()).add(raw_name)
    return normalized_to_raw


def _normalized_counterparties_from_parsed_data(
    parsed_sections: Mapping[str, Any],
) -> dict[str, set[str]]:
    totals_records = _records(parsed_sections.get("totals", []))
    return _normalized_counterparties_from_records(totals_records)


def _raw_counterparties_by_normalized_from_parsed_data(
    parsed_sections: Mapping[str, Any],
) -> dict[str, set[str]]:
    totals_records = _records(parsed_sections.get("totals", []))
    return _raw_counterparties_by_normalized_from_records(totals_records)


def _records(table: Any) -> list[dict[str, Any]]:
    if isinstance(table, list):
        return [dict(record) for record in table if isinstance(record, Mapping)]
    if hasattr(table, "to_dict"):
        to_dict = table.to_dict
        try:
            data = to_dict(orient="records")
        except TypeError:
            data = to_dict()
        if isinstance(data, list):
            return [dict(record) for record in data if isinstance(record, Mapping)]
    if hasattr(table, "to_records"):
        records = table.to_records(index=False)
        if records is not None:
            return [dict(record) for record in records]
    return []
