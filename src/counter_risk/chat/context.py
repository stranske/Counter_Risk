"""Run-folder context loader for chat workflows."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

_TABLE_SUFFIXES: tuple[str, ...] = (".csv", ".parquet")


class RunContextError(ValueError):
    """Raised when a run directory cannot be loaded into chat context."""


@dataclass(frozen=True)
class RunContext:
    """Loaded context for a single pipeline run directory."""

    run_dir: Path
    manifest: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]]
    warnings: list[str]
    deltas: dict[str, list[dict[str, Any]]]

    def summary(self) -> str:
        """Build a compact summary string for chat prompt bootstrap."""

        variants = sorted(set(self.manifest.get("top_exposures", {})) | set(self.deltas))
        variant_summary = ", ".join(variants) if variants else "none"
        table_summary = ", ".join(sorted(self.tables)) if self.tables else "none"
        return (
            f"Run date: {self.manifest.get('run_date', 'unknown')}; "
            f"As-of date: {self.manifest.get('as_of_date', 'unknown')}; "
            f"Warnings: {len(self.warnings)}; "
            f"Variants: {variant_summary}; "
            f"Tables: {table_summary}"
        )


def load_run_context(run_dir: Path | str) -> RunContext:
    """Load manifest and table payloads from a run directory."""

    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists() or not run_path.is_dir():
        raise RunContextError(f"Run directory does not exist or is not a directory: {run_dir}")

    manifest = load_manifest(run_path)
    tables = discover_tables(run_path)
    warnings, deltas = extract_key_warnings_and_deltas(manifest)

    return RunContext(
        run_dir=run_path,
        manifest=manifest,
        tables=tables,
        warnings=warnings,
        deltas=deltas,
    )


def load_manifest(run_dir: Path | str) -> dict[str, Any]:
    """Parse run manifest JSON from the provided run directory."""

    manifest_path = Path(run_dir) / "manifest.json"
    if not manifest_path.exists():
        raise RunContextError(f"manifest.json is missing: {manifest_path}")

    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunContextError(f"manifest.json is malformed: {manifest_path}") from exc
    except OSError as exc:
        raise RunContextError(f"Failed to read manifest.json: {manifest_path}") from exc

    if not isinstance(raw_manifest, dict):
        raise RunContextError("manifest.json must contain a JSON object")

    return raw_manifest


def discover_tables(run_dir: Path | str) -> dict[str, list[dict[str, Any]]]:
    """Discover and load CSV/Parquet tables inside the run directory."""

    run_path = Path(run_dir)
    tables: dict[str, list[dict[str, Any]]] = {}

    for table_path in sorted(_iter_table_paths(run_path)):
        table_key = str(table_path.relative_to(run_path))
        if table_path.suffix.lower() == ".csv":
            tables[table_key] = _load_csv_table(table_path)
        elif table_path.suffix.lower() == ".parquet":
            tables[table_key] = _load_parquet_table(table_path)

    return tables


def extract_key_warnings_and_deltas(
    manifest: dict[str, Any],
) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    """Return warnings and top change deltas from manifest payload."""

    warnings_raw = manifest.get("warnings", [])
    warnings = [str(item) for item in warnings_raw] if isinstance(warnings_raw, list) else []

    deltas_raw = manifest.get("top_changes_per_variant", {})
    deltas: dict[str, list[dict[str, Any]]] = {}
    if isinstance(deltas_raw, dict):
        for variant, records in deltas_raw.items():
            if not isinstance(records, list):
                continue
            normalized_records: list[dict[str, Any]] = []
            for record in records:
                if isinstance(record, dict):
                    normalized_records.append(dict(record))
            deltas[str(variant)] = normalized_records

    return warnings, deltas


def _iter_table_paths(run_dir: Path) -> list[Path]:
    try:
        return [
            path
            for path in run_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in _TABLE_SUFFIXES
        ]
    except OSError as exc:
        raise RunContextError(
            f"Failed while discovering tables in run directory: {run_dir}"
        ) from exc


def _load_csv_table(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    except OSError as exc:
        raise RunContextError(f"Failed to read CSV table: {path}") from exc
    except csv.Error as exc:
        raise RunContextError(f"Malformed CSV table: {path}") from exc


def _load_parquet_table(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RunContextError(f"Parquet table found but pandas is unavailable: {path}") from exc

    try:
        dataframe = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - backend-specific parser errors
        raise RunContextError(f"Failed to read Parquet table: {path}") from exc
    return cast(list[dict[str, Any]], dataframe.to_dict(orient="records"))
