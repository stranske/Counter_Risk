"""Tests for LangSmith fleet artifact records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk.observability import langsmith_fleet


def test_build_fleet_records_use_counter_risk_project_and_no_secret_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(langsmith_fleet.ENV_LANGSMITH_KEY, raising=False)
    context = langsmith_fleet.FleetRunContext(
        run_id="2025-12-31",
        as_of_date="2025-12-31",
        scenario="monthly-risk-report",
    )

    records = langsmith_fleet.build_fleet_records(
        context=context,
        data_quality_status="success",
        risk_proxy_status="success",
        concentration_metric_count=3,
        limit_breach_count=2,
        limit_max_severity="warning",
        report_artifacts=["artifact:manifest.json"],
        artifact_ref="artifact:langsmith-fleet.ndjson",
    )

    assert {record["operation"] for record in records} == {
        "data-quality",
        "risk-proxy",
        "limit-monitoring",
        "report-generation",
    }
    assert {record["status"] for record in records} == {"no_secret"}
    assert all(record["schema_version"] == langsmith_fleet.SCHEMA_VERSION for record in records)
    assert all(record["repo"] == "stranske/Counter_Risk" for record in records)
    assert all(record["surface"] == "risk-reporting" for record in records)
    assert all(record["github_issue"] == "stranske/Counter_Risk#610" for record in records)
    assert all(record["domain"]["as_of_date"] == "2025-12-31" for record in records)
    assert all(record["domain"]["scenario"] == "monthly-risk-report" for record in records)
    assert all("raw" not in json.dumps(record).lower() for record in records)


def test_build_fleet_records_enable_langsmith_defaults_when_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(langsmith_fleet.ENV_LANGSMITH_KEY, "test-key")
    monkeypatch.delenv(langsmith_fleet.ENV_LANGCHAIN_TRACING_V2, raising=False)
    monkeypatch.delenv(langsmith_fleet.ENV_LANGCHAIN_API_KEY, raising=False)
    monkeypatch.delenv(langsmith_fleet.ENV_LANGCHAIN_PROJECT, raising=False)

    records = langsmith_fleet.build_fleet_records(
        context=langsmith_fleet.FleetRunContext(
            run_id="run-1",
            as_of_date="2025-12-31",
            scenario="monthly-risk-report",
            trace_id="trace-123",
            trace_url="https://smith.langchain.com/r/trace-123",
        ),
        data_quality_status="success",
        risk_proxy_status="success",
        concentration_metric_count=1,
        limit_breach_count=0,
    )

    assert {record["status"] for record in records} == {"success"}
    assert records[0]["trace_id"] == "trace-123"
    assert records[0]["trace_url"] == "https://smith.langchain.com/r/trace-123"
    assert (
        langsmith_fleet.os.environ[langsmith_fleet.ENV_LANGCHAIN_PROJECT]
        == langsmith_fleet.DEFAULT_PROJECT
    )
    assert langsmith_fleet.os.environ[langsmith_fleet.ENV_LANGCHAIN_TRACING_V2] == "true"
    assert langsmith_fleet.os.environ[langsmith_fleet.ENV_LANGCHAIN_API_KEY] == "test-key"


def test_write_fleet_records_emits_deterministic_ndjson(tmp_path: Path) -> None:
    path = tmp_path / langsmith_fleet.ARTIFACT_NAME
    records = [
        {
            "schema_version": langsmith_fleet.SCHEMA_VERSION,
            "repo": "stranske/Counter_Risk",
            "surface": "risk-reporting",
            "operation": "data-quality",
            "run_id": "run-1",
            "status": "no_secret",
            "github_issue": "stranske/Counter_Risk#610",
            "domain": {
                "as_of_date": "2025-12-31",
                "scenario": "monthly-risk-report",
                "data_quality_status": "success",
                "limit_breach_count": 0,
            },
        }
    ]

    langsmith_fleet.write_fleet_records(path, records)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == records[0]

