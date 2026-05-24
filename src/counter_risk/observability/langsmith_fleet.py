"""Build dashboard-safe LangSmith fleet records for risk workflow runs."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

SCHEMA_VERSION: Final = "langsmith-fleet/v1"
REPO: Final = "stranske/Counter_Risk"
SURFACE: Final = "risk-reporting"
GITHUB_ISSUE: Final = "stranske/Counter_Risk#610"
ARTIFACT_NAME: Final = "langsmith-fleet.ndjson"
DEFAULT_PROJECT: Final = "counter-risk"
ENV_LANGSMITH_KEY: Final = "LANGSMITH_API_KEY"
ENV_LANGCHAIN_PROJECT: Final = "LANGCHAIN_PROJECT"
ENV_LANGSMITH_PROJECT: Final = "LANGSMITH_PROJECT"
ENV_LANGCHAIN_TRACING_V2: Final = "LANGCHAIN_TRACING_V2"
ENV_LANGCHAIN_API_KEY: Final = "LANGCHAIN_API_KEY"

Status = Literal["success", "error", "fallback", "no_secret", "skipped"]


@dataclass(frozen=True)
class FleetRunContext:
    """Shared trace context for a Counter_Risk workflow run."""

    run_id: str
    as_of_date: str
    scenario: str
    provider: str | None = None
    model: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
    latency_ms: int | None = None
    error_category: str | None = None
    recorded_at: str | None = None
    github_pr: str | None = None


def ensure_langsmith_project_defaults() -> bool:
    """Apply Counter_Risk LangSmith defaults when a key is present."""

    api_key = os.environ.get(ENV_LANGSMITH_KEY)
    if not api_key:
        return False
    os.environ.setdefault(ENV_LANGCHAIN_TRACING_V2, "true")
    os.environ.setdefault(ENV_LANGCHAIN_PROJECT, DEFAULT_PROJECT)
    os.environ.setdefault(ENV_LANGSMITH_PROJECT, DEFAULT_PROJECT)
    os.environ.setdefault(ENV_LANGCHAIN_API_KEY, api_key)
    return True


def build_fleet_records(
    *,
    context: FleetRunContext,
    data_quality_status: str,
    risk_proxy_status: str,
    concentration_metric_count: int,
    limit_breach_count: int,
    limit_max_severity: str | None = None,
    report_artifacts: Iterable[str] = (),
    artifact_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Return Workflows-compatible records for the major risk/report stages."""

    tracing_enabled = ensure_langsmith_project_defaults()
    base_status: Status = "success" if tracing_enabled else "no_secret"
    recorded_at = context.recorded_at or _utc_timestamp()
    report_refs = tuple(sorted(str(item) for item in report_artifacts if str(item).strip()))
    shared_domain = {
        "as_of_date": context.as_of_date,
        "scenario": context.scenario,
        "data_quality_status": data_quality_status,
        "limit_breach_count": int(limit_breach_count),
    }
    records = [
        _record(
            context=context,
            operation="data-quality",
            status=base_status,
            recorded_at=recorded_at,
            domain={
                **shared_domain,
                "stage_status": data_quality_status,
            },
            artifact_ref=artifact_ref,
        ),
        _record(
            context=context,
            operation="risk-proxy",
            status=base_status if risk_proxy_status != "skipped" else "skipped",
            recorded_at=recorded_at,
            domain={
                **shared_domain,
                "risk_proxy_status": risk_proxy_status,
                "concentration_metric_count": max(0, int(concentration_metric_count)),
            },
            artifact_ref=artifact_ref,
        ),
        _record(
            context=context,
            operation="limit-monitoring",
            status=base_status,
            recorded_at=recorded_at,
            domain={
                **shared_domain,
                "limit_max_severity": limit_max_severity or "none",
            },
            artifact_ref=artifact_ref,
        ),
        _record(
            context=context,
            operation="report-generation",
            status=base_status,
            recorded_at=recorded_at,
            domain={
                **shared_domain,
                "report_artifact_count": len(report_refs),
                "report_artifacts": list(report_refs),
            },
            artifact_ref=artifact_ref,
        ),
    ]
    return records


def write_fleet_records(path: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Write records as deterministic NDJSON and return the artifact path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(dict(record), sort_keys=True, separators=(",", ":")) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _record(
    *,
    context: FleetRunContext,
    operation: str,
    status: Status,
    recorded_at: str,
    domain: Mapping[str, Any],
    artifact_ref: str | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repo": REPO,
        "surface": SURFACE,
        "operation": operation,
        "run_id": context.run_id,
        "status": status,
        "github_issue": GITHUB_ISSUE,
        "recorded_at": recorded_at,
        "domain": dict(domain),
    }
    if context.github_pr:
        record["github_pr"] = context.github_pr
    if context.provider:
        record["provider"] = context.provider
    if context.model:
        record["model"] = context.model
    if context.trace_id:
        record["trace_id"] = context.trace_id
    if context.trace_url:
        record["trace_url"] = context.trace_url
    if context.latency_ms is not None:
        record["latency_ms"] = int(context.latency_ms)
    if context.error_category:
        record["error_category"] = context.error_category
    if artifact_ref:
        record["artifact_ref"] = artifact_ref
    return record


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
