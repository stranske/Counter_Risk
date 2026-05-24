"""Build dashboard-safe LangSmith fleet records for risk workflow runs."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal

SCHEMA_VERSION: Final = "langsmith-fleet/v1"
REPO: Final = "stranske/Counter_Risk"
SURFACE: Final = "risk-reporting"
GITHUB_ISSUE: Final = "stranske/Counter_Risk#610"
ARTIFACT_NAME: Final = "langsmith-fleet.ndjson"
ENV_COUNTER_RISK_LANGSMITH_PROJECT: Final = "COUNTER_RISK_LANGSMITH_PROJECT"
ENV_LANGSMITH_KEY: Final = "LANGSMITH_API_KEY"
ENV_LANGCHAIN_PROJECT: Final = "LANGCHAIN_PROJECT"
ENV_LANGSMITH_PROJECT: Final = "LANGSMITH_PROJECT"
ENV_LANGCHAIN_TRACING_V2: Final = "LANGCHAIN_TRACING_V2"
ENV_LANGCHAIN_API_KEY: Final = "LANGCHAIN_API_KEY"
REQUIRED_TOP_LEVEL_FIELDS: Final = frozenset(
    {
        "schema_version",
        "repo",
        "surface",
        "operation",
        "run_id",
        "as_of_date",
        "scenario",
        "status",
        "github_issue",
        "recorded_at",
        "domain",
        "error_category",
        "provider",
        "model",
        "trace_id",
        "trace_url",
        "latency_ms",
    }
)
REQUIRED_DOMAIN_FIELDS: Final = frozenset(
    {
        "as_of_date",
        "scenario",
        "data_quality_status",
        "risk_proxy_status",
        "concentration_metric_available",
        "limit_breach_count",
        "limit_max_severity",
        "limit_scope",
        "shared_metadata",
    }
)
ALLOWED_STATUS: Final = frozenset({"success", "error", "fallback", "no_secret", "skipped"})
SENSITIVE_FIELD_TOKENS: Final = (
    "counterparty",
    "exposure",
    "position",
    "notional",
    "prompt",
    "completion",
    "model_output",
    "report_payload",
)

Status = Literal["success", "error", "fallback", "no_secret", "skipped"]


def _repo_default_project_name(repo: str) -> str:
    """Return the repo-specific default LangSmith project slug."""

    repo_name = repo.split("/")[-1].strip().lower().replace("_", "-")
    return repo_name or "counter-risk"


DEFAULT_PROJECT: Final = _repo_default_project_name(REPO)


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
    recorded_at: str | None = None
    github_pr: str | None = None
    latency_ms: int | None = None
    error_category: str = "none"


def ensure_langsmith_project_defaults() -> bool:
    """Apply Counter_Risk LangSmith defaults when a key is present."""

    api_key = os.environ.get(ENV_LANGSMITH_KEY)
    if not api_key:
        return False
    project = resolve_langsmith_project_name()
    os.environ.setdefault(ENV_LANGCHAIN_TRACING_V2, "true")
    os.environ.setdefault(ENV_LANGCHAIN_PROJECT, project)
    os.environ.setdefault(ENV_LANGSMITH_PROJECT, project)
    os.environ.setdefault(ENV_LANGCHAIN_API_KEY, api_key)
    return True


def resolve_langsmith_project_name() -> str:
    """Return repo-specific LangSmith project name with optional env override."""

    configured = os.environ.get(ENV_COUNTER_RISK_LANGSMITH_PROJECT, "").strip()
    return configured or DEFAULT_PROJECT


def build_fleet_records(
    *,
    context: FleetRunContext,
    data_quality_status: str,
    risk_proxy_status: str,
    concentration_metric_count: int,
    limit_breach_count: int,
    limit_max_severity: str | None = None,
    report_artifacts: Iterable[str] = (),
    workflow_trace_events: Iterable[Mapping[str, Any]] = (),
    artifact_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Return Workflows-compatible records for the major risk/report stages."""

    tracing_enabled = ensure_langsmith_project_defaults()
    base_status: Status = "success" if tracing_enabled else "no_secret"
    recorded_at = context.recorded_at or _utc_timestamp()
    report_refs = tuple(sorted(str(item) for item in report_artifacts if str(item).strip()))
    resolved_limit_max_severity = limit_max_severity or "none"
    concentration_metric_count = max(0, int(concentration_metric_count))
    trace_events = _normalize_workflow_trace_events(workflow_trace_events)
    shared_domain = {
        "as_of_date": context.as_of_date,
        "scenario": context.scenario,
        "data_quality_status": data_quality_status,
        "risk_proxy_status": risk_proxy_status,
        "concentration_metric_available": concentration_metric_count > 0,
        "concentration_metric_count": concentration_metric_count,
        "limit_breach_count": int(limit_breach_count),
        "limit_max_severity": resolved_limit_max_severity,
        "limit_scope": "all-configured-limits",
        "report_artifact_count": len(report_refs),
        "report_artifacts": list(report_refs),
        "workflow_trace_events": trace_events,
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
                "stage_status": risk_proxy_status,
            },
            artifact_ref=artifact_ref,
        ),
        _record(
            context=context,
            operation="concentration-metrics",
            status=base_status if concentration_metric_count > 0 else "skipped",
            recorded_at=recorded_at,
            domain={
                **shared_domain,
                "stage_status": "success" if concentration_metric_count > 0 else "skipped",
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
            },
            artifact_ref=artifact_ref,
        ),
    ]
    return records


def _normalize_workflow_trace_events(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in events:
        stage = str(raw.get("stage") or "").strip()
        if not stage:
            continue
        status = str(raw.get("status") or "").strip() or "unknown"
        latency_raw = raw.get("latency_ms")
        try:
            latency_ms = max(0, int(latency_raw)) if latency_raw is not None else 0
        except (TypeError, ValueError):
            latency_ms = 0
        normalized.append(
            {
                "stage": stage,
                "status": status,
                "latency_ms": latency_ms,
            }
        )
    return normalized


def write_fleet_records(path: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Write records as deterministic NDJSON and return the artifact path."""

    materialized = [dict(record) for record in records]
    validate_fleet_records(materialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(dict(record), sort_keys=True, separators=(",", ":")) for record in materialized
    ]
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
        "as_of_date": context.as_of_date,
        "scenario": context.scenario,
        "status": status,
        "github_issue": GITHUB_ISSUE,
        "recorded_at": recorded_at,
        "provider": context.provider,
        "model": context.model,
        "trace_id": context.trace_id,
        "trace_url": context.trace_url,
        "latency_ms": max(0, int(context.latency_ms)) if context.latency_ms is not None else None,
        "error_category": context.error_category or "none",
    }
    domain_with_shared = {
        **dict(domain),
        "shared_metadata": {
            "run_id": context.run_id,
            "as_of_date": context.as_of_date,
            "scenario": context.scenario,
            "provider": context.provider,
            "model": context.model,
            "status": status,
            "trace_id": context.trace_id,
            "trace_url": context.trace_url,
            "latency_ms": record["latency_ms"],
            "error_category": record["error_category"],
        },
    }
    record["domain"] = domain_with_shared
    if context.github_pr:
        record["github_pr"] = context.github_pr
    if artifact_ref:
        record["artifact_ref"] = artifact_ref
    return record


def validate_fleet_records(records: Iterable[Mapping[str, Any]]) -> None:
    """Validate records against the local Workflows fleet contract subset."""

    for index, record in enumerate(records):
        missing = sorted(REQUIRED_TOP_LEVEL_FIELDS.difference(record))
        if missing:
            raise ValueError(f"fleet record {index} missing top-level fields: {', '.join(missing)}")
        if record["schema_version"] != SCHEMA_VERSION:
            raise ValueError(
                f"fleet record {index} has invalid schema_version: "
                f"expected {SCHEMA_VERSION!r}, got {record['schema_version']!r}"
            )
        if record["repo"] != REPO:
            raise ValueError(
                f"fleet record {index} has invalid repo: expected {REPO!r}, got {record['repo']!r}"
            )
        if record["surface"] != SURFACE:
            raise ValueError(
                f"fleet record {index} has invalid surface: "
                f"expected {SURFACE!r}, got {record['surface']!r}"
            )
        if record["status"] not in ALLOWED_STATUS:
            raise ValueError(
                f"fleet record {index} has invalid status: "
                f"expected one of {sorted(ALLOWED_STATUS)!r}, got {record['status']!r}"
            )
        domain = record["domain"]
        if not isinstance(domain, Mapping):
            raise ValueError(f"fleet record {index} domain must be an object")
        domain_missing = sorted(REQUIRED_DOMAIN_FIELDS.difference(domain))
        if domain_missing:
            raise ValueError(
                f"fleet record {index} missing domain fields: {', '.join(domain_missing)}"
            )
        _validate_artifact_references(index=index, record=record)
        _validate_no_sensitive_payload(index=index, record=record)


def _validate_artifact_references(*, index: int, record: Mapping[str, Any]) -> None:
    artifact_ref = record.get("artifact_ref")
    if artifact_ref is not None and not _is_safe_artifact_ref(artifact_ref):
        raise ValueError(f"fleet record {index} artifact_ref must be an artifact: reference")
    domain = record["domain"]
    report_artifacts = domain.get("report_artifacts", [])
    if report_artifacts is None:
        return
    if not isinstance(report_artifacts, list):
        raise ValueError(f"fleet record {index} report_artifacts must be a list")
    for artifact in report_artifacts:
        if not _is_safe_artifact_ref(artifact):
            raise ValueError(
                f"fleet record {index} report_artifacts must contain artifact: references"
            )


def _is_safe_artifact_ref(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith("artifact:"):
        return False
    suffix = value.removeprefix("artifact:")
    if not suffix or suffix.strip() != suffix or "\\" in suffix:
        return False
    if suffix.startswith(("/", "\\")):
        return False
    path = PurePosixPath(suffix)
    if path.is_absolute() or not path.parts:
        return False
    if path.parts[0].endswith(":"):
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)


def _validate_no_sensitive_payload(*, index: int, record: Mapping[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                key_text = str(key).casefold()
                if any(token in key_text for token in SENSITIVE_FIELD_TOKENS):
                    raise ValueError(f"fleet record {index} includes sensitive field {path}.{key}")
                walk(nested, f"{path}.{key}")
            return
        if isinstance(value, list):
            for item_index, nested in enumerate(value):
                walk(nested, f"{path}[{item_index}]")

    walk(record, "record")


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
