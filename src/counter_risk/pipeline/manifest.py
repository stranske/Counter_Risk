"""Manifest construction and persistence for pipeline runs."""

from __future__ import annotations

import json
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline.data_quality import build_data_quality
from counter_risk.pipeline.warnings import WarningsCollector

__all__ = ["ManifestBuilder", "WarningsCollector"]

_DATA_QUALITY_SUMMARY_FILENAME = "DATA_QUALITY_SUMMARY.txt"
_SEVERITY_DISPLAY_ORDER = ("info", "warn", "fail")
_STATUS_COLOR = {"info": "GREEN", "warn": "YELLOW", "fail": "RED"}
_STATUS_GUIDANCE = {
    "info": "Safe to send.",
    "warn": "Review warnings before sending.",
    "fail": "Do not send until failing checks are resolved.",
}


@dataclass(frozen=True)
class ManifestBuilder:
    """Build and write run manifests."""

    config: WorkflowConfig
    as_of_date: date
    run_date: date

    def build(
        self,
        *,
        run_dir: Path,
        input_hashes: dict[str, str],
        output_paths: list[Path],
        top_exposures: dict[str, list[dict[str, Any]]],
        top_changes_per_variant: dict[str, list[dict[str, Any]]],
        warnings: list[Any],
        unmatched_mappings: dict[str, Any] | None = None,
        missing_inputs: dict[str, Any] | None = None,
        reconciliation_results: dict[str, Any] | None = None,
        ppt_status: str = "success",
        concentration_metrics: list[dict[str, Any]] | None = None,
        limit_breach_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        valid_ppt_statuses = {"success", "skipped", "failed"}
        if ppt_status not in valid_ppt_statuses:
            raise ValueError(
                f"Invalid ppt_status {ppt_status!r}; expected one of: "
                f"{', '.join(sorted(valid_ppt_statuses))}"
            )

        normalized_output_paths = self._normalize_output_paths(
            run_dir=run_dir,
            output_paths=output_paths,
        )
        self._validate_artifact_paths_exist(run_dir=run_dir, relative_paths=normalized_output_paths)
        config_snapshot = self._serialize_config_snapshot(self.config)
        normalized_warnings = self._normalize_warnings(warnings)
        resolved_unmatched_mappings = (
            unmatched_mappings if unmatched_mappings is not None else {"count": 0, "by_variant": {}}
        )
        resolved_missing_inputs = (
            missing_inputs
            if missing_inputs is not None
            else {
                "required": [],
                "missing_required": [],
                "optional_missing": [],
                "is_complete": True,
            }
        )
        resolved_reconciliation_results = (
            reconciliation_results
            if reconciliation_results is not None
            else {
                "status": "not_run",
                "fail_policy": "warn",
                "total_gap_count": 0,
                "by_variant": {},
            }
        )
        manifest: dict[str, Any] = {
            "as_of_date": self.as_of_date.isoformat(),
            "run_date": self.run_date.isoformat(),
            "run_dir": ".",
            "config_snapshot": config_snapshot,
            "input_hashes": input_hashes,
            "output_paths": [str(path) for path in normalized_output_paths],
            "ppt_status": ppt_status,
            "top_exposures": top_exposures,
            "top_changes_per_variant": top_changes_per_variant,
            "warnings": normalized_warnings,
            "data_quality": build_data_quality(
                warnings,
                unmatched_mappings=resolved_unmatched_mappings,
                missing_inputs=resolved_missing_inputs,
                reconciliation_results=resolved_reconciliation_results,
                ppt_status=ppt_status,
                limit_breach_summary=limit_breach_summary,
            ),
            "unmatched_mappings": resolved_unmatched_mappings,
            "missing_inputs": resolved_missing_inputs,
            "reconciliation_results": resolved_reconciliation_results,
        }
        if concentration_metrics is not None:
            manifest["concentration_metrics"] = concentration_metrics
        if limit_breach_summary is not None:
            manifest["limit_breach_summary"] = limit_breach_summary
        return manifest

    def write(self, *, run_dir: Path, manifest: dict[str, Any]) -> Path:
        summary_path = run_dir / _DATA_QUALITY_SUMMARY_FILENAME
        path = run_dir / "manifest.json"
        try:
            summary_path.write_text(
                self._build_data_quality_summary(manifest),
                encoding="utf-8",
            )
            self._register_summary_artifact(manifest)
            path.write_text(
                json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to write manifest file: {path}") from exc
        return path

    def _register_summary_artifact(self, manifest: dict[str, Any]) -> None:
        output_paths = manifest.get("output_paths")
        if not isinstance(output_paths, list):
            return
        rendered_paths = [str(path) for path in output_paths]
        if _DATA_QUALITY_SUMMARY_FILENAME in rendered_paths:
            return
        output_paths.append(_DATA_QUALITY_SUMMARY_FILENAME)

    def _build_data_quality_summary(self, manifest: Mapping[str, Any]) -> str:
        data_quality = manifest.get("data_quality")
        as_of_date = str(manifest.get("as_of_date", "unknown"))
        run_date = str(manifest.get("run_date", "unknown"))

        status = "info"
        counts_by_severity: dict[str, int] = dict.fromkeys(_SEVERITY_DISPLAY_ORDER, 0)
        total_findings = 0
        counts_by_category: dict[str, dict[str, int]] = {}
        findings: list[Mapping[str, Any]] = []
        actions: list[Mapping[str, Any]] = []

        if isinstance(data_quality, Mapping):
            status_candidate = str(data_quality.get("overall_status", "info")).strip().lower()
            if status_candidate in _STATUS_COLOR:
                status = status_candidate

            counts = data_quality.get("counts")
            if isinstance(counts, Mapping):
                total_findings = self._safe_int(counts.get("total_findings", 0))
                by_severity_raw = counts.get("by_severity")
                if isinstance(by_severity_raw, Mapping):
                    for severity in _SEVERITY_DISPLAY_ORDER:
                        counts_by_severity[severity] = self._safe_int(
                            by_severity_raw.get(severity, 0)
                        )
                by_category_raw = counts.get("by_category")
                if isinstance(by_category_raw, Mapping):
                    for category, category_counts in by_category_raw.items():
                        if not isinstance(category_counts, Mapping):
                            continue
                        counts_by_category[str(category)] = {
                            "info": self._safe_int(category_counts.get("info", 0)),
                            "warn": self._safe_int(category_counts.get("warn", 0)),
                            "fail": self._safe_int(category_counts.get("fail", 0)),
                            "total": self._safe_int(category_counts.get("total", 0)),
                        }

            findings_raw = data_quality.get("findings")
            if isinstance(findings_raw, list):
                findings = [finding for finding in findings_raw if isinstance(finding, Mapping)]

            actions_raw = data_quality.get("recommended_actions")
            if isinstance(actions_raw, list):
                actions = [action for action in actions_raw if isinstance(action, Mapping)]

        lines = [
            "Counterparty Risk Data Quality Summary",
            "",
            f"As-of date: {as_of_date}",
            f"Run date: {run_date}",
            (
                f"Overall status: {status.upper()} ({_STATUS_COLOR[status]}) "
                f"- {_STATUS_GUIDANCE[status]}"
            ),
            "",
            "Finding counts:",
            f"- Total findings: {total_findings}",
            *[
                f"- {severity}: {counts_by_severity[severity]}"
                for severity in _SEVERITY_DISPLAY_ORDER
            ],
            "",
            "Findings by category:",
        ]

        if counts_by_category:
            for category in sorted(counts_by_category, key=str.casefold):
                category_counts = counts_by_category[category]
                lines.append(
                    "- "
                    f"{category}: total={category_counts['total']} "
                    f"(info={category_counts['info']}, "
                    f"warn={category_counts['warn']}, "
                    f"fail={category_counts['fail']})"
                )
        else:
            lines.append("- none")

        lines.append("")
        lines.append("Detailed findings:")
        if findings:
            for finding in findings:
                lines.append(
                    "- "
                    f"[{str(finding.get('severity', 'warn')).upper()}] "
                    f"{str(finding.get('category', 'pipeline'))} / "
                    f"{str(finding.get('code', 'UNKNOWN'))}: "
                    f"{str(finding.get('message', '')).strip()}"
                )
        else:
            lines.append("- none")

        lines.append("")
        lines.append("Recommended actions:")
        if actions:
            for action in actions:
                lines.append(
                    "- "
                    f"[{str(action.get('severity', 'warn')).upper()}] "
                    f"{str(action.get('category', 'pipeline'))}: "
                    f"{str(action.get('action', '')).strip()}"
                )
        else:
            lines.append("- none")

        lines.append("")
        return "\n".join(lines)

    def _safe_int(self, raw_value: Any) -> int:
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return 0

    def _serialize_config_snapshot(self, config: WorkflowConfig) -> dict[str, Any]:
        raw = config.model_dump(mode="python")
        snapshot: dict[str, Any] = {}
        for key, value in raw.items():
            if isinstance(value, Path):
                snapshot[key] = str(value)
            elif isinstance(value, date):
                snapshot[key] = value.isoformat()
            else:
                snapshot[key] = value
        return snapshot

    def _normalize_warnings(self, warnings: list[Any]) -> list[str]:
        normalized_warnings: list[str] = []
        for warning in warnings:
            normalized = self._normalize_warning(warning)
            if normalized is not None:
                normalized_warnings.append(normalized)
        return normalized_warnings

    def _normalize_warning(self, warning: Any) -> str | None:
        if warning is None:
            return None
        if isinstance(warning, str):
            stripped = warning.strip()
            return stripped if stripped else None
        if isinstance(warning, Mapping):
            message = str(warning.get("message", "")).strip()
            metadata = [
                f"{key}={value}"
                for key, value in warning.items()
                if key != "message" and value is not None and str(value).strip()
            ]
            if message and metadata:
                return f"{message} ({', '.join(metadata)})"
            if message:
                return message
            if metadata:
                return ", ".join(metadata)
            return None
        rendered = str(warning).strip()
        return rendered if rendered else None

    def _normalize_output_paths(self, *, run_dir: Path, output_paths: list[Path]) -> list[Path]:
        normalized_paths: list[Path] = []
        for artifact_path in output_paths:
            normalized = self._to_relative_artifact_path(
                run_dir=run_dir, artifact_path=artifact_path
            )
            normalized_paths.append(normalized)
        return normalized_paths

    def _to_relative_artifact_path(self, *, run_dir: Path, artifact_path: Path) -> Path:
        run_dir_resolved = run_dir.resolve()
        if artifact_path.is_absolute():
            normalized_absolute = artifact_path.resolve()
            try:
                relative_path = normalized_absolute.relative_to(run_dir_resolved)
            except ValueError as exc:
                raise ValueError(
                    f"Artifact path must be within run_dir '{run_dir}': {artifact_path}"
                ) from exc
        else:
            relative_path = artifact_path

        normalized_posix = PurePosixPath(posixpath.normpath(relative_path.as_posix()))
        if any(part == ".." for part in normalized_posix.parts):
            raise ValueError(f"Artifact path cannot contain '..' segments: {artifact_path}")

        if normalized_posix.as_posix() == ".":
            raise ValueError(
                f"Artifact path must reference a file, not run_dir itself: {artifact_path}"
            )

        return Path(normalized_posix.as_posix())

    def _validate_artifact_paths_exist(self, *, run_dir: Path, relative_paths: list[Path]) -> None:
        missing_paths: list[Path] = []
        for relative_path in relative_paths:
            resolved_path = run_dir / relative_path
            if not resolved_path.exists():
                missing_paths.append(resolved_path)

        if missing_paths:
            missing = ", ".join(str(path) for path in missing_paths)
            raise ValueError(f"Manifest output paths do not exist at write time: {missing}")
