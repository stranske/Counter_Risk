"""Manifest construction and persistence for pipeline runs."""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from counter_risk.config import WorkflowConfig


class WarningsCollector:
    """Accumulates structured warnings for manifest and logging integration.

    Pass an instance to computation functions that support a *collector* parameter
    so that warnings are centralised and can be forwarded to :meth:`ManifestBuilder.build`
    via the ``warnings`` argument.

    Warning codes
    -------------
    INVALID_NOTIONAL
        The notional field was found but its value is blank, non-numeric, or NaN.
    MISSING_DESCRIPTION
        The ``Description`` field is absent or blank after stripping.
    MISSING_NOTIONAL
        No notional field was found in the row.
    NO_PRIOR_MONTH_MATCH
        A current-month row has no matching prior-month row.
    """

    INVALID_NOTIONAL: str = "INVALID_NOTIONAL"
    MISSING_DESCRIPTION: str = "MISSING_DESCRIPTION"
    MISSING_NOTIONAL: str = "MISSING_NOTIONAL"
    NO_PRIOR_MONTH_MATCH: str = "NO_PRIOR_MONTH_MATCH"

    def __init__(self) -> None:
        self._entries: list[str] = []

    def warn(self, message: str, *, code: str | None = None, **_extra: object) -> None:
        """Record a warning, optionally tagged with a reason *code*.

        The entry stored is ``"[CODE] message"`` when a code is supplied,
        otherwise just ``"message"``.
        """
        entry = f"[{code}] {message}" if code else message
        self._entries.append(entry)

    @property
    def warnings(self) -> list[str]:
        """Return a copy of all accumulated warning strings."""
        return list(self._entries)


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
        warnings: list[str],
        ppt_status: str = "success",
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
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "run_date": self.run_date.isoformat(),
            "run_dir": ".",
            "config_snapshot": config_snapshot,
            "input_hashes": input_hashes,
            "output_paths": [str(path) for path in normalized_output_paths],
            "ppt_status": ppt_status,
            "top_exposures": top_exposures,
            "top_changes_per_variant": top_changes_per_variant,
            "warnings": warnings,
        }

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
