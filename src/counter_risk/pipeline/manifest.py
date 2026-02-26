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
from counter_risk.pipeline.warnings import WarningsCollector

__all__ = ["ManifestBuilder", "WarningsCollector"]


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
            "unmatched_mappings": (
                unmatched_mappings
                if unmatched_mappings is not None
                else {"count": 0, "by_variant": {}}
            ),
            "missing_inputs": (
                missing_inputs
                if missing_inputs is not None
                else {
                    "required": [],
                    "missing_required": [],
                    "optional_missing": [],
                    "is_complete": True,
                }
            ),
            "reconciliation_results": (
                reconciliation_results
                if reconciliation_results is not None
                else {
                    "status": "not_run",
                    "fail_policy": "warn",
                    "total_gap_count": 0,
                    "by_variant": {},
                }
            ),
        }
        if concentration_metrics is not None:
            manifest["concentration_metrics"] = concentration_metrics
        if limit_breach_summary is not None:
            manifest["limit_breach_summary"] = limit_breach_summary
        return manifest

    def write(self, *, run_dir: Path, manifest: dict[str, Any]) -> Path:
        path = run_dir / "manifest.json"
        try:
            path.write_text(
                json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to write manifest file: {path}") from exc
        return path

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
