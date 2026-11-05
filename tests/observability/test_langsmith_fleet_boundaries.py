"""Fleet contract rejection paths without network or tracing side effects."""

import pytest

from counter_risk.observability import langsmith_fleet as fleet


@pytest.fixture
def valid_record(monkeypatch):
    monkeypatch.setattr(fleet, "ensure_langsmith_project_defaults", lambda: False)
    return fleet.build_fleet_records(
        context=fleet.FleetRunContext(
            run_id="test-run", as_of_date="2026-01-31", scenario="monthly"
        ),
        data_quality_status="info",
        risk_proxy_status="success",
        concentration_metric_count=0,
        limit_breach_count=0,
    )[0]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("schema_version", "invalid", "invalid schema_version"),
        ("repo", "other/repo", "invalid repo"),
        ("surface", "other", "invalid surface"),
        ("domain", [], "domain must be an object"),
        ("domain", {}, "missing domain fields"),
    ],
)
def test_fleet_rejects_invalid_contract_fields(valid_record, field, value, reason):
    valid_record[field] = value
    with pytest.raises(ValueError, match=reason):
        fleet.validate_fleet_records([valid_record])


def test_fleet_reports_missing_top_level_fields():
    with pytest.raises(ValueError, match="missing top-level fields"):
        fleet.validate_fleet_records([{}])


def test_report_artifacts_can_be_explicitly_absent(valid_record):
    valid_record["domain"]["report_artifacts"] = None
    assert fleet.validate_fleet_records([valid_record]) is None


def test_report_artifacts_require_a_list(valid_record):
    valid_record["domain"]["report_artifacts"] = "artifact:report.json"
    with pytest.raises(ValueError, match="report_artifacts must be a list"):
        fleet.validate_fleet_records([valid_record])


def test_top_level_artifact_reference_is_validated(valid_record):
    valid_record["artifact_ref"] = 42
    with pytest.raises(ValueError, match="artifact_ref must be an artifact:"):
        fleet.validate_fleet_records([valid_record])


@pytest.mark.parametrize("value", [None, 42, "report.json", "artifact:."])
def test_artifact_reference_requires_relative_artifact_scheme(value):
    assert fleet._is_safe_artifact_ref(value) is False


@pytest.mark.parametrize("value", [None, 42, "artifact:report.json"])
def test_sha_reference_requires_string_and_sha_scheme(value):
    assert fleet._is_safe_sha256_ref(value) is False


def test_workflow_events_ignore_blank_stages_and_sanitize_latency():
    assert fleet._normalize_workflow_trace_events(
        [
            {"stage": " "},
            {"stage": " parse ", "latency_ms": "invalid"},
            {"stage": "write", "status": "success", "latency_ms": -3},
        ]
    ) == [
        {"stage": "parse", "status": "unknown", "latency_ms": 0},
        {"stage": "write", "status": "success", "latency_ms": 0},
    ]
