"""Data-quality findings construction for run manifests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

Severity = str
_SEVERITIES: tuple[Severity, ...] = ("info", "warn", "fail")
_SEVERITY_BY_CODE: dict[str, Severity] = {
    "NO_FINDINGS": "info",
    "MISSING_REQUIRED_INPUTS": "fail",
    "MISSING_OPTIONAL_INPUTS": "warn",
    "UNMATCHED_MAPPINGS": "fail",
    "RECONCILIATION_GAPS": "fail",
    "RECONCILIATION_GAP_DETAIL": "fail",
    "PPT_GENERATION_FAILED": "fail",
    "PPT_GENERATION_SKIPPED": "warn",
    "LIMIT_BREACHES": "warn",
    "MISSING_NOTIONAL": "warn",
    "INVALID_NOTIONAL": "warn",
    "MISSING_DESCRIPTION": "warn",
    "MISSING_DATE_HEADER": "fail",
    "DATE_RESOLUTION_FALLBACK": "warn",
    "REPO_CASH_SOURCE_NOT_CONFIGURED": "warn",
    "REPO_CASH_SOURCE_USED": "info",
    "REPO_CASH_OVERRIDES_APPLIED": "info",
    "REPO_CASH_OVERRIDES_EMPTY": "warn",
    "REPO_CASH_LIMIT_BREACH": "warn",
    "REPO_CASH_MISSING_REQUIRED_COUNTERPARTIES": "warn",
    "REPO_CASH_APPLIED_TO_TOTALS": "info",
    "OUTPUT_GENERATION_SKIPPED": "warn",
    "OUTPUT_GENERATION_FAILED": "fail",
}
_CATEGORY_BY_CODE: dict[str, str] = {
    "NO_FINDINGS": "pipeline",
    "MISSING_REQUIRED_INPUTS": "input",
    "MISSING_OPTIONAL_INPUTS": "input",
    "UNMATCHED_MAPPINGS": "mapping",
    "RECONCILIATION_GAPS": "reconciliation",
    "RECONCILIATION_GAP_DETAIL": "reconciliation",
    "PPT_GENERATION_FAILED": "ppt",
    "PPT_GENERATION_SKIPPED": "ppt",
    "LIMIT_BREACHES": "limits",
    "MISSING_NOTIONAL": "data_validation",
    "INVALID_NOTIONAL": "data_validation",
    "MISSING_DESCRIPTION": "data_validation",
    "MISSING_DATE_HEADER": "date",
    "DATE_RESOLUTION_FALLBACK": "date",
    "REPO_CASH_SOURCE_NOT_CONFIGURED": "cash",
    "REPO_CASH_SOURCE_USED": "cash",
    "REPO_CASH_OVERRIDES_APPLIED": "cash",
    "REPO_CASH_OVERRIDES_EMPTY": "cash",
    "REPO_CASH_LIMIT_BREACH": "cash",
    "REPO_CASH_MISSING_REQUIRED_COUNTERPARTIES": "cash",
    "REPO_CASH_APPLIED_TO_TOTALS": "cash",
    "OUTPUT_GENERATION_SKIPPED": "output_generation",
    "OUTPUT_GENERATION_FAILED": "output_generation",
}


def build_data_quality(
    warnings: list[Any],
    *,
    unmatched_mappings: Mapping[str, Any] | None = None,
    missing_inputs: Mapping[str, Any] | None = None,
    reconciliation_results: Mapping[str, Any] | None = None,
    ppt_status: str = "success",
    limit_breach_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the manifest data_quality object from warning entries."""

    findings = _build_findings(
        warnings,
        unmatched_mappings=unmatched_mappings,
        missing_inputs=missing_inputs,
        reconciliation_results=reconciliation_results,
        ppt_status=ppt_status,
        limit_breach_summary=limit_breach_summary,
    )
    counts = _build_counts(findings)
    actions = _build_recommended_actions(findings)
    overall_status = _derive_overall_status(counts)

    return {
        "overall_status": overall_status,
        "severity_levels": list(_SEVERITIES),
        "findings": findings,
        "counts": counts,
        "recommended_actions": actions,
    }


def _build_findings(
    warnings: list[Any],
    *,
    unmatched_mappings: Mapping[str, Any] | None,
    missing_inputs: Mapping[str, Any] | None,
    reconciliation_results: Mapping[str, Any] | None,
    ppt_status: str,
    limit_breach_summary: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = _build_warning_findings(warnings)
    findings.extend(
        _collect_validation_findings(
            unmatched_mappings=unmatched_mappings,
            missing_inputs=missing_inputs,
            reconciliation_results=reconciliation_results,
            ppt_status=ppt_status,
            limit_breach_summary=limit_breach_summary,
        )
    )
    findings = _dedupe_findings(findings)

    if findings:
        return findings

    return [
        {
            "category": "pipeline",
            "severity": "info",
            "code": "NO_FINDINGS",
            "message": "No data quality findings detected for this run.",
        }
    ]


def _build_warning_findings(warnings: list[Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for warning in warnings:
        if isinstance(warning, dict):
            message = str(warning.get("message", "")).strip()
            if not message:
                continue
            code = str(warning.get("code", "UNKNOWN")).strip() or "UNKNOWN"
            category = _categorize(message=message, code=code)
            finding = _make_finding(category=category, code=code, message=message)
            findings.append(finding)
            continue

        message = str(warning).strip()
        if not message:
            continue
        code = _code_from_message(message)
        category = _categorize(message=message, code=code)
        findings.append(_make_finding(category=category, code=code, message=message))
    return findings


def _collect_validation_findings(
    *,
    unmatched_mappings: Mapping[str, Any] | None,
    missing_inputs: Mapping[str, Any] | None,
    reconciliation_results: Mapping[str, Any] | None,
    ppt_status: str,
    limit_breach_summary: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    missing_inputs = missing_inputs or {}
    unmatched_mappings = unmatched_mappings or {}
    reconciliation_results = reconciliation_results or {}
    limit_breach_summary = limit_breach_summary or {}

    missing_required = _string_list(missing_inputs.get("missing_required", []), max_items=8)
    if missing_required:
        findings.append(
            _make_finding(
                category="input",
                code="MISSING_REQUIRED_INPUTS",
                message=f"Missing required inputs: {', '.join(missing_required)}.",
            )
        )

    optional_missing = _string_list(missing_inputs.get("optional_missing", []), max_items=8)
    if optional_missing:
        findings.append(
            _make_finding(
                category="input",
                code="MISSING_OPTIONAL_INPUTS",
                message=f"Optional inputs unavailable: {', '.join(optional_missing)}.",
            )
        )

    unmatched_count = _safe_int(unmatched_mappings.get("count", 0))
    if unmatched_count > 0:
        findings.append(
            _make_finding(
                category="mapping",
                code="UNMATCHED_MAPPINGS",
                message=f"Found {unmatched_count} unmatched mapping entr{'y' if unmatched_count == 1 else 'ies'}.",
            )
        )

    gap_count = _safe_int(reconciliation_results.get("total_gap_count", 0))
    reconciliation_status = str(reconciliation_results.get("status", "")).strip().lower()
    if reconciliation_status == "failed" or gap_count > 0:
        findings.append(
            _make_finding(
                category="reconciliation",
                code="RECONCILIATION_GAPS",
                message=f"Reconciliation reported {gap_count} gap{'s' if gap_count != 1 else ''}.",
            )
        )
        findings.extend(_build_reconciliation_gap_detail_findings(reconciliation_results))

    normalized_ppt_status = str(ppt_status).strip().lower()
    if normalized_ppt_status == "failed":
        findings.append(
            _make_finding(
                category="ppt",
                code="PPT_GENERATION_FAILED",
                message="PowerPoint generation failed.",
            )
        )
    elif normalized_ppt_status == "skipped":
        findings.append(
            _make_finding(
                category="ppt",
                code="PPT_GENERATION_SKIPPED",
                message="PowerPoint generation was skipped.",
            )
        )

    has_breaches = bool(limit_breach_summary.get("has_breaches"))
    breach_count = _safe_int(limit_breach_summary.get("breach_count", 0))
    if has_breaches and breach_count > 0:
        findings.append(
            _make_finding(
                category="limits",
                code="LIMIT_BREACHES",
                message=f"Detected {breach_count} limit breach{'es' if breach_count != 1 else ''}.",
            )
        )

    return findings


def _build_reconciliation_gap_detail_findings(
    reconciliation_results: Mapping[str, Any],
) -> list[dict[str, str]]:
    by_variant = reconciliation_results.get("by_variant")
    if not isinstance(by_variant, Mapping):
        return []

    findings: list[dict[str, str]] = []
    for variant, variant_result in by_variant.items():
        if not isinstance(variant_result, Mapping):
            continue
        missing_series = variant_result.get("missing_series")
        if not isinstance(missing_series, Sequence) or isinstance(missing_series, (str, bytes)):
            continue
        for entry in missing_series:
            if not isinstance(entry, Mapping):
                continue
            sheet = str(entry.get("sheet", "unknown")).strip() or "unknown"
            impacted_rows = _safe_int(entry.get("impacted_rows", 0))
            issue = _reconciliation_issue_summary(entry)
            findings.append(
                _make_finding(
                    category="reconciliation",
                    code="RECONCILIATION_GAP_DETAIL",
                    message=(
                        "Reconciliation gap detail: "
                        f"variant={variant}, sheet={sheet}, impacted_rows={impacted_rows}, "
                        f"issue={issue}."
                    ),
                )
            )
    return findings


def _reconciliation_issue_summary(entry: Mapping[str, Any]) -> str:
    error_type = str(entry.get("error_type", "")).strip()
    if error_type == "unmapped_counterparty":
        raw_names = _string_list(entry.get("raw_counterparties", []), max_items=3)
        if raw_names:
            return "unmapped_counterparty(" + ", ".join(raw_names) + ")"
        return "unmapped_counterparty"

    missing_headers = _string_list(entry.get("missing_from_historical_headers", []), max_items=3)
    if missing_headers:
        return "missing_from_historical_headers(" + ", ".join(missing_headers) + ")"

    source_context = str(entry.get("data_source_context", "")).strip()
    if source_context:
        return source_context
    return "reconciliation_gap"


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for finding in findings:
        category = str(finding.get("category", "pipeline"))
        severity = str(finding.get("severity", "warn"))
        code = str(finding.get("code", "UNKNOWN"))
        message = str(finding.get("message", ""))
        key = (category, severity, code, message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "category": category,
                "severity": severity,
                "code": code,
                "message": message,
            }
        )
    return deduped


def _string_list(raw_values: Any, *, max_items: int) -> list[str]:
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
        return []
    cleaned = sorted(
        {
            str(value).strip()
            for value in raw_values
            if isinstance(value, str) and str(value).strip()
        },
        key=str.casefold,
    )
    return cleaned[:max_items]


def _safe_int(raw_value: Any) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def _build_counts(findings: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = dict.fromkeys(_SEVERITIES, 0)
    by_category: dict[str, dict[str, int]] = defaultdict(
        lambda: {"info": 0, "warn": 0, "fail": 0, "total": 0}
    )

    for finding in findings:
        severity = str(finding.get("severity", "warn"))
        category = str(finding.get("category", "uncategorized"))
        if severity not in severity_counts:
            severity = "warn"
        severity_counts[severity] += 1
        by_category[category][severity] += 1
        by_category[category]["total"] += 1

    return {
        "total_findings": len(findings),
        "by_severity": severity_counts,
        "by_category": dict(by_category),
    }


def _build_recommended_actions(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        category = str(finding.get("category", "pipeline"))
        severity = str(finding.get("severity", "warn"))
        key = (category, severity)
        if key in seen:
            continue
        seen.add(key)
        actions.append(
            {
                "category": category,
                "severity": severity,
                "action": _recommended_action(category=category, severity=severity),
            }
        )
    return actions


def _derive_overall_status(counts: dict[str, Any]) -> str:
    by_severity = counts.get("by_severity", {})
    if isinstance(by_severity, dict) and int(by_severity.get("fail", 0)) > 0:
        return "fail"
    if isinstance(by_severity, dict) and int(by_severity.get("warn", 0)) > 0:
        return "warn"
    return "info"


def _make_finding(*, category: str, code: str, message: str) -> dict[str, str]:
    return {
        "category": category,
        "severity": _classify_severity(message=message, code=code),
        "code": code,
        "message": message,
    }


def _classify_severity(*, message: str, code: str) -> str:
    message_lower = message.lower()
    code_upper = code.upper()
    fail_tokens = ("failed", "strict mode", "unmapped", "missing entities")
    info_tokens = ("generated", "summary", "appended")

    mapped_severity = _SEVERITY_BY_CODE.get(code_upper)
    if mapped_severity in _SEVERITIES:
        return mapped_severity
    if any(token in message_lower for token in fail_tokens):
        return "fail"
    if "FAILED" in code_upper or "ERROR" in code_upper:
        return "fail"
    if any(token in message_lower for token in info_tokens):
        return "info"
    return "warn"


def _categorize(*, message: str, code: str) -> str:
    message_lower = message.lower()
    code_upper = code.upper()
    category_from_code = _CATEGORY_BY_CODE.get(code_upper)
    if category_from_code:
        return category_from_code
    if "ppt" in message_lower:
        return "ppt"
    if "limit" in message_lower:
        return "limits"
    if "reconciliation" in message_lower:
        return "reconciliation"
    if "mapping" in message_lower or "unmapped" in message_lower:
        return "mapping"
    if code_upper in {"MISSING_NOTIONAL", "INVALID_NOTIONAL", "MISSING_DESCRIPTION"}:
        return "data_validation"
    return "pipeline"


def _recommended_action(*, category: str, severity: str) -> str:
    if severity == "fail":
        if category == "mapping":
            return "Resolve unmapped counterparties before distributing results."
        if category == "reconciliation":
            return "Investigate reconciliation gaps and rerun in strict mode."
        if category == "limits":
            return "Review breach details and escalate to risk owners."
        return "Investigate and resolve failing checks before sending outputs."
    if severity == "warn":
        if category == "ppt":
            return "Verify PPT links/slides manually before distribution."
        if category == "data_validation":
            return "Review source data anomalies and confirm expected values."
        return "Review warnings and confirm run artifacts are acceptable."
    return "No immediate action required."


def _code_from_message(message: str) -> str:
    message_lower = message.casefold()
    if "missing a date header" in message_lower:
        return "MISSING_DATE_HEADER"
    if "date derivation" in message_lower:
        return "DATE_RESOLUTION_FALLBACK"
    if "repo cash source is not configured" in message_lower:
        return "REPO_CASH_SOURCE_NOT_CONFIGURED"
    if "repo cash source used:" in message_lower:
        return "REPO_CASH_SOURCE_USED"
    if "repo cash overrides applied" in message_lower:
        return "REPO_CASH_OVERRIDES_APPLIED"
    if "repo cash overrides file present but empty" in message_lower:
        return "REPO_CASH_OVERRIDES_EMPTY"
    if "repo cash total" in message_lower and (
        "below configured minimum" in message_lower or "exceeds configured maximum" in message_lower
    ):
        return "REPO_CASH_LIMIT_BREACH"
    if "repo cash missing required counterparties" in message_lower:
        return "REPO_CASH_MISSING_REQUIRED_COUNTERPARTIES"
    if "applied repo cash values to all_programs totals" in message_lower:
        return "REPO_CASH_APPLIED_TO_TOTALS"
    if " skipped" in message_lower and (
        "change_attribution" in message_lower
        or "risk_rankings.csv" in message_lower
        or "risk_top_movers.csv" in message_lower
        or "historical workbook update skipped" in message_lower
        or "distribution ppt standalone validation skipped" in message_lower
    ):
        return "OUTPUT_GENERATION_SKIPPED"
    if " generation failed" in message_lower and (
        "distribution_static" in message_lower or "chart_replacement" in message_lower
    ):
        return "OUTPUT_GENERATION_FAILED"

    normalized = (
        message.upper().replace(" ", "_").replace("-", "_").replace("/", "_").replace(":", "")
    )
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
    return normalized[:64] or "WARNING"
