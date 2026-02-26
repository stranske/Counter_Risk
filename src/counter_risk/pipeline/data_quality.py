"""Data-quality findings construction for run manifests."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

Severity = str
_SEVERITIES: tuple[Severity, ...] = ("info", "warn", "fail")


def build_data_quality(warnings: list[Any]) -> dict[str, Any]:
    """Build the manifest data_quality object from warning entries."""

    findings = _build_findings(warnings)
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


def _build_findings(warnings: list[Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for warning in warnings:
        if isinstance(warning, dict):
            message = str(warning.get("message", "")).strip()
            code = str(warning.get("code", "UNKNOWN")).strip() or "UNKNOWN"
            finding = {
                "category": _categorize(message=message, code=code),
                "severity": _classify_severity(message=message, code=code),
                "code": code,
                "message": message,
            }
            findings.append(finding)
            continue

        message = str(warning).strip()
        if not message:
            continue
        code = _code_from_message(message)
        findings.append(
            {
                "category": _categorize(message=message, code=code),
                "severity": _classify_severity(message=message, code=code),
                "code": code,
                "message": message,
            }
        )

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


def _classify_severity(*, message: str, code: str) -> str:
    message_lower = message.lower()
    code_upper = code.upper()
    fail_tokens = ("failed", "strict mode", "unmapped", "missing entities")
    info_tokens = ("generated", "summary", "appended")

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
    normalized = (
        message.upper().replace(" ", "_").replace("-", "_").replace("/", "_").replace(":", "")
    )
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
    return normalized[:64] or "WARNING"
