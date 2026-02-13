"""Counter Risk pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig, load_config
from counter_risk.parsers import parse_fcm_totals, parse_futures_detail

LOGGER = logging.getLogger(__name__)

_EXPECTED_VARIANTS: tuple[str, ...] = ("all_programs", "ex_trend", "trend")
_REQUIRED_TOTAL_COLUMNS: tuple[str, ...] = ("counterparty", "Notional", "NotionalChange")
_REQUIRED_FUTURES_COLUMNS: tuple[str, ...] = (
    "account",
    "description",
    "class",
    "fcm",
    "clearing_house",
    "notional",
)


@dataclass(frozen=True)
class _VariantInputs:
    name: str
    workbook_path: Path
    historical_path: Path


class ManifestBuilder:
    """Build and write run manifests."""

    def __init__(self, *, run_dir: Path, config: WorkflowConfig) -> None:
        self._run_dir = run_dir
        self._config = config

    def build(
        self,
        *,
        input_hashes: dict[str, str],
        output_paths: list[Path],
        top_exposures: dict[str, list[dict[str, Any]]],
        top_changes_per_variant: dict[str, list[dict[str, Any]]],
        warnings: list[str],
    ) -> dict[str, Any]:
        config_snapshot = self._serialize_config_snapshot(self._config)
        return {
            "as_of_date": str(self._resolve_as_of_date(self._config)),
            "run_date": datetime.now(tz=UTC).isoformat(),
            "run_dir": str(self._run_dir),
            "config_snapshot": config_snapshot,
            "input_hashes": input_hashes,
            "output_paths": [str(path) for path in output_paths],
            "top_exposures": top_exposures,
            "top_changes_per_variant": top_changes_per_variant,
            "warnings": warnings,
        }

    def write(self, manifest: dict[str, Any]) -> Path:
        path = self._run_dir / "manifest.json"
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


def run_pipeline(config_path: str | Path) -> Path:
    """Run the Counter Risk pipeline and return the output run directory."""

    LOGGER.info("pipeline_start config_path=%s", config_path)
    try:
        config = load_config(config_path)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=config_load config_path=%s", config_path)
        raise RuntimeError(f"Pipeline failed during config load: {config_path}") from exc

    try:
        _validate_pipeline_config(config)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=config_validate config_path=%s", config_path)
        raise RuntimeError(f"Pipeline failed during config validation: {config_path}") from exc

    input_paths = _resolve_input_paths(config)
    _validate_input_files(input_paths)

    as_of_date = config.as_of_date or datetime.now(tz=UTC).date()
    run_dir = config.output_root / as_of_date.isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    try:
        parsed_by_variant = _parse_inputs(input_paths)
        _validate_parsed_inputs(parsed_by_variant)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=parse_inputs run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during parse stage") from exc

    try:
        top_exposures, top_changes_per_variant = _compute_metrics(parsed_by_variant)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=compute_metrics run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during compute stage") from exc

    try:
        historical_output_paths = _update_historical_outputs(
            run_dir=run_dir,
            config=config,
            parsed_by_variant=parsed_by_variant,
            as_of_date=as_of_date,
            warnings=warnings,
        )
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=historical_update run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during historical update stage") from exc

    try:
        output_paths = _write_outputs(
            run_dir=run_dir,
            config=config,
            warnings=warnings,
        )
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=write_outputs run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during output write stage") from exc
    output_paths = historical_output_paths + output_paths

    input_hashes = {name: _sha256_file(path) for name, path in input_paths.items()}
    manifest_builder = ManifestBuilder(run_dir=run_dir, config=config)
    manifest = manifest_builder.build(
        input_hashes=input_hashes,
        output_paths=output_paths,
        top_exposures=top_exposures,
        top_changes_per_variant=top_changes_per_variant,
        warnings=warnings,
    )
    manifest_path = manifest_builder.write(manifest)
    LOGGER.info("pipeline_complete run_dir=%s manifest=%s", run_dir, manifest_path)

    return run_dir


def _resolve_input_paths(config: WorkflowConfig) -> dict[str, Path]:
    return {
        "mosers_all_programs_xlsx": config.mosers_all_programs_xlsx,
        "mosers_ex_trend_xlsx": config.mosers_ex_trend_xlsx,
        "mosers_trend_xlsx": config.mosers_trend_xlsx,
        "hist_all_programs_3yr_xlsx": config.hist_all_programs_3yr_xlsx,
        "hist_ex_llc_3yr_xlsx": config.hist_ex_llc_3yr_xlsx,
        "hist_llc_3yr_xlsx": config.hist_llc_3yr_xlsx,
        "monthly_pptx": config.monthly_pptx,
    }


def _validate_pipeline_config(config: WorkflowConfig) -> None:
    if config.output_root.exists() and not config.output_root.is_dir():
        raise ValueError(f"output_root must be a directory path: {config.output_root}")

    _validate_extension(
        field_name="mosers_all_programs_xlsx",
        path=config.mosers_all_programs_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="mosers_ex_trend_xlsx",
        path=config.mosers_ex_trend_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="mosers_trend_xlsx",
        path=config.mosers_trend_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="hist_all_programs_3yr_xlsx",
        path=config.hist_all_programs_3yr_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="hist_ex_llc_3yr_xlsx",
        path=config.hist_ex_llc_3yr_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="hist_llc_3yr_xlsx",
        path=config.hist_llc_3yr_xlsx,
        expected_suffix=".xlsx",
    )
    _validate_extension(
        field_name="monthly_pptx",
        path=config.monthly_pptx,
        expected_suffix=".pptx",
    )


def _validate_extension(*, field_name: str, path: Path, expected_suffix: str) -> None:
    if path.suffix.lower() != expected_suffix:
        raise ValueError(
            f"Invalid file type for {field_name}: expected {expected_suffix}, got '{path.suffix}'"
        )


def _validate_input_files(input_paths: dict[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in input_paths.items() if not path.exists()]
    if missing:
        details = "; ".join(missing)
        raise FileNotFoundError(f"Missing pipeline input files: {details}")


def _parse_inputs(input_paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    variants = [
        ("all_programs", input_paths["mosers_all_programs_xlsx"]),
        ("ex_trend", input_paths["mosers_ex_trend_xlsx"]),
        ("trend", input_paths["mosers_trend_xlsx"]),
    ]

    parsed: dict[str, dict[str, Any]] = {}
    for variant, workbook_path in variants:
        LOGGER.info("parse_start variant=%s file=%s", variant, workbook_path)
        totals_df = parse_fcm_totals(workbook_path)
        futures_df = parse_futures_detail(workbook_path)
        parsed[variant] = {
            "totals": totals_df,
            "futures": futures_df,
        }
        LOGGER.info(
            "parse_complete variant=%s totals_rows=%s futures_rows=%s",
            variant,
            _row_count(totals_df),
            _row_count(futures_df),
        )

    return parsed


def _validate_parsed_inputs(parsed_by_variant: dict[str, dict[str, Any]]) -> None:
    missing_variants = [
        variant for variant in _EXPECTED_VARIANTS if variant not in parsed_by_variant
    ]
    if missing_variants:
        raise ValueError(f"Missing parsed variants: {', '.join(missing_variants)}")

    for variant in _EXPECTED_VARIANTS:
        parsed_sections = parsed_by_variant[variant]
        if not isinstance(parsed_sections, Mapping):
            raise ValueError(f"Parsed payload for variant '{variant}' must be a mapping")

        missing_sections = [
            section for section in ("totals", "futures") if section not in parsed_sections
        ]
        if missing_sections:
            raise ValueError(
                f"Parsed payload for variant '{variant}' is missing sections: "
                f"{', '.join(missing_sections)}"
            )

        totals_columns = _column_names(parsed_sections["totals"])
        futures_columns = _column_names(parsed_sections["futures"])

        _require_columns(
            section_name=f"{variant}.totals",
            columns=totals_columns,
            required_columns=_REQUIRED_TOTAL_COLUMNS,
        )
        _require_columns(
            section_name=f"{variant}.futures",
            columns=futures_columns,
            required_columns=_REQUIRED_FUTURES_COLUMNS,
        )


def _require_columns(
    *, section_name: str, columns: set[str], required_columns: tuple[str, ...]
) -> None:
    missing_columns = [column for column in required_columns if column not in columns]
    if missing_columns:
        raise ValueError(
            f"Parsed section '{section_name}' is missing required columns: "
            f"{', '.join(missing_columns)}"
        )


def _compute_metrics(
    parsed_by_variant: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    LOGGER.info("compute_start")
    top_exposures: dict[str, list[dict[str, Any]]] = {}
    top_changes_per_variant: dict[str, list[dict[str, Any]]] = {}

    for variant, parsed in parsed_by_variant.items():
        totals_df = parsed["totals"]
        totals_records = _records(totals_df)

        if not totals_records:
            top_exposures[variant] = []
            top_changes_per_variant[variant] = []
            continue

        sorted_exposures = sorted(
            totals_records,
            key=lambda record: abs(float(record.get("Notional", 0.0) or 0.0)),
            reverse=True,
        )
        top_exposures[variant] = [
            {
                "counterparty": str(record.get("counterparty", "")),
                "notional": float(record.get("Notional", 0.0) or 0.0),
            }
            for record in sorted_exposures[:5]
        ]

        change_column = "NotionalChange"
        if not all(change_column in record for record in totals_records):
            top_changes_per_variant[variant] = []
            continue

        sorted_changes = sorted(
            totals_records,
            key=lambda record: abs(float(record.get(change_column, 0.0) or 0.0)),
            reverse=True,
        )
        top_changes_per_variant[variant] = [
            {
                "counterparty": str(record.get("counterparty", "")),
                "notional_change": float(record.get(change_column, 0.0) or 0.0),
            }
            for record in sorted_changes[:5]
        ]

    LOGGER.info("compute_complete")
    return top_exposures, top_changes_per_variant


def _write_outputs(*, run_dir: Path, config: WorkflowConfig, warnings: list[str]) -> list[Path]:
    LOGGER.info("write_outputs_start run_dir=%s", run_dir)

    variant_inputs = [
        _VariantInputs(
            name="all_programs",
            workbook_path=config.mosers_all_programs_xlsx,
            historical_path=config.hist_all_programs_3yr_xlsx,
        ),
        _VariantInputs(
            name="ex_trend",
            workbook_path=config.mosers_ex_trend_xlsx,
            historical_path=config.hist_ex_llc_3yr_xlsx,
        ),
        _VariantInputs(
            name="trend",
            workbook_path=config.mosers_trend_xlsx,
            historical_path=config.hist_llc_3yr_xlsx,
        ),
    ]

    output_paths: list[Path] = []
    for variant_input in variant_inputs:
        source_mosers = variant_input.workbook_path
        target_monthly_book = run_dir / f"{variant_input.name}-mosers-input.xlsx"
        shutil.copy2(source_mosers, target_monthly_book)
        output_paths.append(target_monthly_book)

    source_ppt = config.monthly_pptx
    target_ppt = run_dir / source_ppt.name
    shutil.copy2(source_ppt, target_ppt)
    output_paths.append(target_ppt)

    warnings.append("PPT screenshots replacement not implemented; copied source deck unchanged")
    warnings.append("PPT links not refreshed; COM refresh skipped")

    LOGGER.info("write_outputs_complete output_count=%s", len(output_paths))
    return output_paths


def _update_historical_outputs(
    *,
    run_dir: Path,
    config: WorkflowConfig,
    parsed_by_variant: dict[str, dict[str, Any]],
    as_of_date: date,
    warnings: list[str],
) -> list[Path]:
    LOGGER.info("historical_update_start run_dir=%s as_of_date=%s", run_dir, as_of_date.isoformat())
    variant_inputs = [
        _VariantInputs(
            name="all_programs",
            workbook_path=config.mosers_all_programs_xlsx,
            historical_path=config.hist_all_programs_3yr_xlsx,
        ),
        _VariantInputs(
            name="ex_trend",
            workbook_path=config.mosers_ex_trend_xlsx,
            historical_path=config.hist_ex_llc_3yr_xlsx,
        ),
        _VariantInputs(
            name="trend",
            workbook_path=config.mosers_trend_xlsx,
            historical_path=config.hist_llc_3yr_xlsx,
        ),
    ]

    output_paths: list[Path] = []
    for variant_input in variant_inputs:
        source_hist = variant_input.historical_path
        target_hist = run_dir / source_hist.name
        shutil.copy2(source_hist, target_hist)
        totals_records = _records(parsed_by_variant[variant_input.name]["totals"])
        _merge_historical_workbook(
            workbook_path=target_hist,
            variant=variant_input.name,
            as_of_date=as_of_date,
            totals_records=totals_records,
            warnings=warnings,
        )
        output_paths.append(target_hist)

    LOGGER.info("historical_update_complete workbook_count=%s", len(output_paths))
    return output_paths


def _merge_historical_workbook(
    *,
    workbook_path: Path,
    variant: str,
    as_of_date: date,
    totals_records: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]
    except ImportError:
        message = (
            f"Historical workbook update skipped for variant '{variant}'; openpyxl unavailable"
        )
        LOGGER.warning("historical_update_skipped variant=%s reason=openpyxl_unavailable", variant)
        warnings.append(message)
        return

    workbook = None
    try:
        workbook = load_workbook(filename=workbook_path)
        worksheet = workbook.active
        append_row = int(getattr(worksheet, "max_row", 0)) + 1

        total_notional = sum(float(record.get("Notional", 0.0) or 0.0) for record in totals_records)
        counterparties = len(
            {
                str(record.get("counterparty", "")).strip()
                for record in totals_records
                if str(record.get("counterparty", "")).strip()
            }
        )

        worksheet.cell(row=append_row, column=1).value = as_of_date.isoformat()
        worksheet.cell(row=append_row, column=2).value = total_notional
        worksheet.cell(row=append_row, column=3).value = counterparties
        workbook.save(workbook_path)
        LOGGER.info(
            "historical_update_variant_complete variant=%s row=%s notional=%s counterparties=%s",
            variant,
            append_row,
            total_notional,
            counterparties,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to update historical workbook for variant '{variant}': {workbook_path}"
        ) from exc
    finally:
        if workbook is not None:
            workbook.close()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(table: Any) -> list[dict[str, Any]]:
    if isinstance(table, list):
        return [dict(record) for record in table if isinstance(record, Mapping)]
    if hasattr(table, "to_dict"):
        as_records = table.to_dict(orient="records")
        return [dict(record) for record in as_records if isinstance(record, Mapping)]
    if hasattr(table, "to_records"):
        as_records = table.to_records()
        return [dict(record) for record in as_records if isinstance(record, Mapping)]
    return []


def _column_names(table: Any) -> set[str]:
    if hasattr(table, "columns"):
        raw_columns = table.columns
        try:
            return {str(column) for column in raw_columns}
        except TypeError:
            return set()

    records = _records(table)
    if not records:
        return set()
    return {str(column) for column in records[0]}


def _row_count(table: Any) -> int:
    return len(_records(table))
