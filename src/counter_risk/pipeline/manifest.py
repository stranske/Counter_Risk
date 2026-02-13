"""Manifest construction and persistence for pipeline runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig


@dataclass(frozen=True)
class ManifestBuilder:
    """Build and write run manifests."""

    config: WorkflowConfig

    def build(
        self,
        *,
        run_dir: Path,
        input_hashes: dict[str, str],
        output_paths: list[Path],
        top_exposures: dict[str, list[dict[str, Any]]],
        top_changes_per_variant: dict[str, list[dict[str, Any]]],
        warnings: list[str],
    ) -> dict[str, Any]:
        config_snapshot = self._serialize_config_snapshot(self.config)
        return {
            "as_of_date": str(self._resolve_as_of_date(self.config)),
            "run_date": datetime.now(tz=UTC).isoformat(),
            "run_dir": str(run_dir),
            "config_snapshot": config_snapshot,
            "input_hashes": input_hashes,
            "output_paths": [str(path) for path in output_paths],
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

    def _resolve_as_of_date(self, config: WorkflowConfig) -> date:
        return config.as_of_date or datetime.now(tz=UTC).date()
