"""Reconciliation adapters and fallback contracts."""

import sys
from types import SimpleNamespace

import pytest

from counter_risk.pipeline import reconciliation as reconcile
from counter_risk.pipeline.parsing_types import (
    ParsedDataInvalidShapeError,
    UnmappedCounterpartyError,
)


def test_frozen_registry_falls_back_when_bundle_asset_is_missing(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    def missing_asset(path):
        raise reconcile.RuntimePathResolutionError(path)

    monkeypatch.setattr(reconcile, "resolve_runtime_path", missing_asset)
    assert reconcile._name_registry_path() == reconcile._REPO_NAME_REGISTRY_PATH


def test_present_series_ignores_blank_entries():
    result = reconcile.reconcile_series_coverage(
        parsed_data_by_sheet={"Total": {"totals": [], "futures": []}},
        historical_series_headers_by_sheet={"Total": ["CIBC"]},
        series_present_by_sheet={"Total": ["  ", "CIBC"]},
    )
    assert result["gap_count"] == 0
    assert result["by_sheet"]["Total"]["missing_from_data"] == []


def test_strict_custom_resolver_retains_canonical_name_without_raw_metadata():
    with pytest.raises(UnmappedCounterpartyError) as caught:
        reconcile.reconcile_series_coverage(
            parsed_data_by_sheet={"Total": {"totals": [{"counterparty": "CIBC"}], "futures": []}},
            historical_series_headers_by_sheet={"Total": []},
            counterparty_resolver=lambda name: SimpleNamespace(
                canonical_name="custom", source="registry"
            ),
            fail_policy="strict",
        )
    assert caught.value.normalized_counterparty == "custom"
    assert caught.value.raw_counterparty == "custom"


def test_section_mapping_is_required_before_reconciling():
    with pytest.raises(ParsedDataInvalidShapeError, match="expected a mapping/object"):
        reconcile.reconcile_series_coverage(
            parsed_data_by_sheet={"Total": []}, historical_series_headers_by_sheet={}
        )


def test_expected_segments_match_variant_case_and_ignore_blank_values():
    assert reconcile._expected_segments_for_variant(
        variant=" TREND ",
        expected_segments_by_variant={"all_programs": ["repo"], "trend": ["futures", " "]},
    ) == {"futures"}
    assert (
        reconcile._expected_segments_for_variant(
            variant="trend", expected_segments_by_variant={"all_programs": ["repo"]}
        )
        == set()
    )


def test_raw_counterparty_metadata_ignores_none_and_preserves_original_spacing():
    assert reconcile._raw_counterparties_by_normalized_from_records(
        [{"counterparty": None}, {"counterparty": "  "}, {"counterparty": " CIBC "}]
    ) == {"CIBC": {" CIBC "}}


class _LegacyTable:
    def to_dict(self):
        return [{"counterparty": "CIBC"}, "ignore"]


class _RecordTable:
    def __init__(self, records):
        self.records = records

    def to_dict(self, *, orient):
        assert orient == "records"
        return None

    def to_records(self, *, index):
        assert index is False
        return self.records


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        (_LegacyTable(), [{"counterparty": "CIBC"}]),
        (_RecordTable([{"counterparty": "CIBC"}]), [{"counterparty": "CIBC"}]),
        (_RecordTable(None), []),
        (object(), []),
    ],
)
def test_records_adapts_legacy_and_record_table_protocols(table, expected):
    assert reconcile._records(table) == expected
