"""Counter Risk pipeline orchestration."""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import platform
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from counter_risk.config import WorkflowConfig, load_config
from counter_risk.parsers import parse_fcm_totals, parse_futures_detail
from counter_risk.pipeline.manifest import ManifestBuilder
from counter_risk.writers import generate_mosers_workbook

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
_PREFERRED_HISTORICAL_SHEET_BY_VARIANT: dict[str, str] = {
    "all_programs": "Total",
    "ex_trend": "Total",
    "trend": "Total",
}
_DATE_HEADER_CANDIDATES: tuple[str, ...] = ("date", "as of date", "as-of date")
_REQUIRED_HISTORICAL_APPEND_HEADERS: tuple[str, ...] = (
    "date",
    "value series 1",
    "value series 2",
)


@dataclass(frozen=True)
class _VariantInputs:
    name: str
    workbook_path: Path
    historical_path: Path


class PptProcessingStatus(StrEnum):
    """Machine-readable statuses for PPT processing."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class PptProcessingResult:
    """Result envelope for PPT processing and link refresh."""

    status: PptProcessingStatus
    error_detail: str | None = None


ScreenshotReplacer = Callable[[Path, Path, dict[str, Path]], None]


def reconcile_series_coverage(
    *,
    parsed_data_by_sheet: Mapping[str, Mapping[str, Any]],
    historical_series_headers_by_sheet: Mapping[str, tuple[str, ...] | list[str] | set[str]],
    variant: str | None = None,
    expected_segments_by_variant: (
        Mapping[str, tuple[str, ...] | list[str] | set[str]] | None
    ) = None,
) -> dict[str, Any]:
    """Reconcile parsed series labels against historical workbook headers per sheet.

    Compares current-month series labels from parsed tables against historical workbook
    headers and optionally validates variant-specific segment expectations.
    """

    by_sheet: dict[str, dict[str, Any]] = {}
    missing_series: list[dict[str, Any]] = []
    missing_segments: list[dict[str, Any]] = []
    warnings: list[str] = []
    gap_count = 0

    expected_segments = _expected_segments_for_variant(
        variant=variant,
        expected_segments_by_variant=expected_segments_by_variant,
    )
    sheet_names = sorted(
        set(parsed_data_by_sheet).union(historical_series_headers_by_sheet), key=str.casefold
    )
    for sheet_name in sheet_names:
        parsed_sections = parsed_data_by_sheet.get(sheet_name, {})
        totals_records = _records(parsed_sections.get("totals", []))
        futures_records = _records(parsed_sections.get("futures", []))
        historical_series_headers = sorted(
            {
                value
                for value in (
                    str(header).strip()
                    for header in historical_series_headers_by_sheet.get(sheet_name, ())
                )
                if value
            }
        )

        counterparties_in_data = sorted(
            {
                value
                for value in (
                    str(record.get("counterparty", "")).strip() for record in totals_records
                )
                if value
            }
        )
        clearing_houses_in_data = sorted(
            {
                value
                for value in (
                    str(record.get("clearing_house", "")).strip() for record in futures_records
                )
                if value
            }
        )
        current_series_labels = sorted(set(counterparties_in_data).union(clearing_houses_in_data))
        missing_from_historical = sorted(
            set(current_series_labels).difference(historical_series_headers), key=str.casefold
        )
        missing_from_data = sorted(
            set(historical_series_headers).difference(current_series_labels), key=str.casefold
        )
        parsed_segments = _extract_segments_from_records(parsed_sections)
        missing_expected_segments = sorted(
            expected_segments.difference(parsed_segments), key=str.casefold
        )

        if missing_from_historical:
            gap_count += len(missing_from_historical)
            missing_series.append(
                {
                    "sheet": sheet_name,
                    "missing_from_historical_headers": missing_from_historical,
                    "data_source_context": "counterparties_and_clearing_houses",
                }
            )
            warnings.append(
                "Reconciliation gap in sheet "
                f"{sheet_name!r}: series present in parsed data but missing from historical "
                f"headers ({', '.join(missing_from_historical)})"
            )

        if missing_expected_segments:
            gap_count += len(missing_expected_segments)
            missing_segments.append(
                {
                    "variant": variant,
                    "sheet": sheet_name,
                    "expected_segment_identifiers": missing_expected_segments,
                }
            )
            warnings.append(
                "Reconciliation gap in variant "
                f"{variant!r} sheet {sheet_name!r}: expected segments missing from parsed "
                f"results ({', '.join(missing_expected_segments)})"
            )

        by_sheet[sheet_name] = {
            "counterparties_in_data": counterparties_in_data,
            "clearing_houses_in_data": clearing_houses_in_data,
            "historical_series_headers": historical_series_headers,
            "current_series_labels": current_series_labels,
            "missing_from_historical_headers": missing_from_historical,
            "missing_from_data": missing_from_data,
            "segments_in_data": sorted(parsed_segments, key=str.casefold),
            "missing_expected_segments": missing_expected_segments,
        }

    return {
        "by_sheet": by_sheet,
        "gap_count": gap_count,
        "warnings": warnings,
        "missing_series": missing_series,
        "missing_segments": missing_segments,
    }


def _expected_segments_for_variant(
    *,
    variant: str | None,
    expected_segments_by_variant: Mapping[str, tuple[str, ...] | list[str] | set[str]] | None,
) -> set[str]:
    if not variant or not expected_segments_by_variant:
        return set()

    for key, values in expected_segments_by_variant.items():
        if str(key).strip().casefold() != variant.strip().casefold():
            continue
        return {str(value).strip() for value in values if str(value).strip()}
    return set()


def _extract_segments_from_records(parsed_sections: Mapping[str, Any]) -> set[str]:
    segments: set[str] = set()
    for table in parsed_sections.values():
        for record in _records(table):
            raw_segment = record.get("segment", record.get("Segment", ""))
            label = str(raw_segment).strip()
            if label:
                segments.add(label)
    return segments


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

    try:
        input_paths = _resolve_input_paths(config)
        _validate_input_files(input_paths)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=input_validation config_path=%s", config_path)
        raise RuntimeError("Pipeline failed during input validation stage") from exc

    as_of_date = config.as_of_date or _dt.datetime.now(tz=UTC).date()
    try:
        run_dir = _create_run_directory(as_of_date=as_of_date)
    except Exception as exc:
        LOGGER.exception(
            "pipeline_failed stage=run_dir_setup run_dir=%s",
            _resolve_repo_root() / "runs" / as_of_date.isoformat(),
        )
        raise RuntimeError("Pipeline failed during run directory setup stage") from exc

    warnings: list[str] = []
    runtime_config = config
    try:
        runtime_config = _prepare_runtime_config(
            config=config,
            run_dir=run_dir,
            as_of_date=as_of_date,
            warnings=warnings,
        )
        parsed_by_variant = _parse_inputs(_resolve_input_paths(runtime_config))
        _validate_parsed_inputs(parsed_by_variant)
        _run_reconciliation_checks(
            run_dir=run_dir,
            config=runtime_config,
            parsed_by_variant=parsed_by_variant,
            warnings=warnings,
        )
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
            config=runtime_config,
            parsed_by_variant=parsed_by_variant,
            as_of_date=as_of_date,
            warnings=warnings,
        )
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=historical_update run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during historical update stage") from exc

    try:
        output_result = _write_outputs(
            run_dir=run_dir,
            config=runtime_config,
            warnings=warnings,
        )
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=write_outputs run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during output write stage") from exc
    if isinstance(output_result, tuple):
        output_paths, ppt_result = output_result
    else:
        output_paths = output_result
        ppt_result = PptProcessingResult(status=PptProcessingStatus.SUCCESS)
    output_paths = historical_output_paths + output_paths

    try:
        input_hashes = {
            name: _sha256_file(path) for name, path in _resolve_input_paths(runtime_config).items()
        }
        manifest_builder = ManifestBuilder(config=config)
        output_paths_for_manifest = [path.relative_to(run_dir) for path in output_paths]
        manifest = manifest_builder.build(
            run_dir=run_dir,
            input_hashes=input_hashes,
            output_paths=output_paths_for_manifest,
            top_exposures=top_exposures,
            top_changes_per_variant=top_changes_per_variant,
            warnings=warnings,
            ppt_status=ppt_result.status.value,
        )
        manifest_path = manifest_builder.write(run_dir=run_dir, manifest=manifest)
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=manifest_write run_dir=%s", run_dir)
        raise RuntimeError("Pipeline failed during manifest generation stage") from exc

    LOGGER.info("pipeline_complete run_dir=%s manifest=%s", run_dir, manifest_path)

    return run_dir


def _create_run_directory(*, as_of_date: date) -> Path:
    runs_root = _resolve_repo_root() / "runs"
    base_name = as_of_date.isoformat()
    candidate_names = [base_name, *(f"{base_name}_{index}" for index in range(1, 10_000))]

    for candidate_name in candidate_names:
        run_dir = runs_root / candidate_name
        if run_dir.exists():
            continue
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    raise RuntimeError(f"Unable to create unique run directory for as_of_date {base_name}")


def _resolve_repo_root() -> Path:
    """Resolve the repository root for deterministic run output layout."""

    return Path(__file__).resolve().parents[3]


def _resolve_input_paths(config: WorkflowConfig) -> dict[str, Path]:
    paths: dict[str, Path] = {
        "mosers_ex_trend_xlsx": config.mosers_ex_trend_xlsx,
        "mosers_trend_xlsx": config.mosers_trend_xlsx,
        "hist_all_programs_3yr_xlsx": config.hist_all_programs_3yr_xlsx,
        "hist_ex_llc_3yr_xlsx": config.hist_ex_llc_3yr_xlsx,
        "hist_llc_3yr_xlsx": config.hist_llc_3yr_xlsx,
        "monthly_pptx": config.monthly_pptx,
    }
    if config.mosers_all_programs_xlsx is not None:
        paths["mosers_all_programs_xlsx"] = config.mosers_all_programs_xlsx
    if config.raw_nisa_all_programs_xlsx is not None:
        paths["raw_nisa_all_programs_xlsx"] = config.raw_nisa_all_programs_xlsx
    return paths


def _validate_pipeline_config(config: WorkflowConfig) -> None:
    if config.output_root.exists() and not config.output_root.is_dir():
        raise ValueError(f"output_root must be a directory path: {config.output_root}")

    if config.mosers_all_programs_xlsx is None and config.raw_nisa_all_programs_xlsx is None:
        raise ValueError(
            "One of mosers_all_programs_xlsx or raw_nisa_all_programs_xlsx must be configured"
        )
    if config.mosers_all_programs_xlsx is not None:
        _validate_extension(
            field_name="mosers_all_programs_xlsx",
            path=config.mosers_all_programs_xlsx,
            expected_suffix=".xlsx",
        )
    if config.raw_nisa_all_programs_xlsx is not None:
        _validate_extension(
            field_name="raw_nisa_all_programs_xlsx",
            path=config.raw_nisa_all_programs_xlsx,
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


def _prepare_runtime_config(
    *,
    config: WorkflowConfig,
    run_dir: Path,
    as_of_date: date,
    warnings: list[str],
) -> WorkflowConfig:
    raw_nisa_path = config.raw_nisa_all_programs_xlsx
    if raw_nisa_path is None:
        return config

    generated_dir = run_dir / "_generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    generated_mosers_path = generated_dir / "all_programs-generated-mosers.xlsx"
    canonical_mosers_path = run_dir / "all_programs-mosers-input.xlsx"
    generate_mosers_workbook(
        raw_nisa_path=raw_nisa_path,
        output_path=generated_mosers_path,
        as_of_date=as_of_date,
    )
    shutil.copy2(generated_mosers_path, canonical_mosers_path)
    warnings.append("Generated All Programs MOSERS workbook from raw NISA input")
    return config.model_copy(update={"mosers_all_programs_xlsx": canonical_mosers_path})


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


def _write_outputs(
    *, run_dir: Path, config: WorkflowConfig, warnings: list[str]
) -> tuple[list[Path], PptProcessingResult]:
    LOGGER.info("write_outputs_start run_dir=%s", run_dir)

    variant_inputs = [
        _VariantInputs(
            name="all_programs",
            workbook_path=_require_path(
                config.mosers_all_programs_xlsx, field_name="mosers_all_programs_xlsx"
            ),
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
        if source_mosers.resolve() != target_monthly_book.resolve():
            shutil.copy2(source_mosers, target_monthly_book)
        output_paths.append(target_monthly_book)

    source_ppt = config.monthly_pptx
    target_ppt = run_dir / source_ppt.name
    screenshot_inputs = _resolve_screenshot_input_mapping(config)
    if config.enable_screenshot_replacement:
        replacer = _get_screenshot_replacer(config.screenshot_replacement_implementation)
        replacer(source_ppt, target_ppt, screenshot_inputs)
    else:
        shutil.copy2(source_ppt, target_ppt)
        if screenshot_inputs:
            warnings.append("PPT screenshots replacement disabled; copied source deck unchanged")
    output_paths.append(target_ppt)

    refresh_result = _refresh_ppt_links(target_ppt)
    if isinstance(refresh_result, bool):
        refresh_result = PptProcessingResult(
            status=PptProcessingStatus.SUCCESS if refresh_result else PptProcessingStatus.SKIPPED
        )

    if refresh_result.status == PptProcessingStatus.SKIPPED:
        warnings.append("PPT links not refreshed; COM refresh skipped")
    elif refresh_result.status == PptProcessingStatus.FAILED:
        warnings.append(
            "PPT links refresh failed; COM refresh encountered an error"
            if not refresh_result.error_detail
            else f"PPT links refresh failed; {refresh_result.error_detail}"
        )

    LOGGER.info("write_outputs_complete output_count=%s", len(output_paths))
    return output_paths, refresh_result


def _resolve_screenshot_input_mapping(config: WorkflowConfig) -> dict[str, Path]:
    raw_inputs = config.screenshot_inputs
    normalized_pairs: list[tuple[str, Path]] = []
    seen_keys: set[str] = set()
    for raw_key, raw_path in raw_inputs.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("Screenshot input keys must be non-empty")
        if key in seen_keys:
            raise ValueError(f"Screenshot input key is duplicated after normalization: {key!r}")
        seen_keys.add(key)

        image_path = Path(raw_path).expanduser().resolve()
        if image_path.suffix.lower() != ".png":
            raise ValueError(f"Screenshot input '{key}' must point to a PNG file: {image_path}")
        if not image_path.exists() or not image_path.is_file():
            raise FileNotFoundError(f"Screenshot input '{key}' file does not exist: {image_path}")

        normalized_pairs.append((key, image_path))

    normalized = dict(sorted(normalized_pairs, key=lambda item: item[0]))
    if config.enable_screenshot_replacement and not normalized:
        raise ValueError("Screenshot replacement is enabled but no screenshot_inputs were provided")
    return normalized


def _get_screenshot_replacer(implementation: str) -> ScreenshotReplacer:
    if implementation == "zip":
        return _replace_screenshots_with_zip_backend
    if implementation == "python-pptx":
        return _replace_screenshots_with_python_pptx_backend
    raise ValueError(f"Unsupported screenshot replacement implementation: {implementation}")


def _replace_screenshots_with_python_pptx_backend(
    source_pptx_path: Path, output_pptx_path: Path, screenshot_inputs: dict[str, Path]
) -> None:
    from counter_risk.writers.pptx_screenshots import replace_screenshot_pictures

    replace_screenshot_pictures(
        pptx_in=source_pptx_path,
        images_by_section=screenshot_inputs,
        pptx_out=output_pptx_path,
    )


def _replace_screenshots_with_zip_backend(
    source_pptx_path: Path, output_pptx_path: Path, screenshot_inputs: dict[str, Path]
) -> None:
    from counter_risk.ppt.replace_screenshots import (
        ScreenshotReplacement,
        replace_screenshots_in_pptx,
    )

    replacements = [
        ScreenshotReplacement(
            slide_number=slide_number,
            picture_index=picture_index,
            image_bytes=image_path.read_bytes(),
        )
        for screenshot_key, image_path in screenshot_inputs.items()
        for slide_number, picture_index in [_parse_zip_screenshot_key(screenshot_key)]
    ]
    replace_screenshots_in_pptx(
        source_pptx_path=source_pptx_path,
        output_pptx_path=output_pptx_path,
        replacements=replacements,
    )


def _parse_zip_screenshot_key(key: str) -> tuple[int, int]:
    slide_token, separator, picture_token = key.partition(":")
    normalized_slide = slide_token.strip().lower()
    if normalized_slide.startswith("slide"):
        normalized_slide = normalized_slide.removeprefix("slide").strip()
    if not normalized_slide.isdigit():
        raise ValueError(f"Invalid screenshot key for zip backend: {key!r}")

    picture_index = 0
    if separator:
        picture_candidate = picture_token.strip()
        if not picture_candidate.isdigit():
            raise ValueError(f"Invalid screenshot key for zip backend: {key!r}")
        picture_index = int(picture_candidate)

    return int(normalized_slide), picture_index


def _refresh_ppt_links(pptx_path: Path) -> PptProcessingResult:
    """Best-effort refresh of linked PowerPoint content via COM automation."""

    if platform.system().lower() != "windows":
        LOGGER.info("ppt_link_refresh_skipped file=%s reason=unsupported_platform", pptx_path)
        return PptProcessingResult(
            status=PptProcessingStatus.SKIPPED,
            error_detail="unsupported platform",
        )

    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        LOGGER.info("ppt_link_refresh_skipped file=%s reason=win32com_unavailable", pptx_path)
        return PptProcessingResult(
            status=PptProcessingStatus.SKIPPED,
            error_detail="win32com unavailable",
        )

    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = False
        presentation = app.Presentations.Open(str(pptx_path), WithWindow=False)
        presentation.UpdateLinks()
        presentation.Save()
        LOGGER.info("ppt_link_refresh_complete file=%s", pptx_path)
        return PptProcessingResult(status=PptProcessingStatus.SUCCESS)
    except Exception as exc:
        LOGGER.exception("ppt_link_refresh_failed file=%s", pptx_path)
        raise RuntimeError(f"PPT link refresh failed for '{pptx_path}': {exc}") from exc
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()


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
            workbook_path=_require_path(
                config.mosers_all_programs_xlsx, field_name="mosers_all_programs_xlsx"
            ),
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
        preferred_sheet = _PREFERRED_HISTORICAL_SHEET_BY_VARIANT.get(variant)
        worksheet = _select_historical_worksheet(
            workbook=workbook,
            preferred_sheet_name=preferred_sheet,
        )
        _validate_historical_headers(worksheet=worksheet)
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


def _normalize_header(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def _select_historical_worksheet(*, workbook: Any, preferred_sheet_name: str | None) -> Any:
    sheet_names = list(getattr(workbook, "sheetnames", []))
    if not sheet_names:
        raise ValueError("Historical workbook has no worksheets")

    if preferred_sheet_name and preferred_sheet_name in sheet_names:
        return workbook[preferred_sheet_name]

    fallback_sheet_name = sorted(sheet_names, key=str.casefold)[0]
    if preferred_sheet_name:
        LOGGER.warning(
            "historical_sheet_preferred_missing preferred=%s fallback=%s",
            preferred_sheet_name,
            fallback_sheet_name,
        )
    return workbook[fallback_sheet_name]


def _validate_historical_headers(*, worksheet: Any) -> None:
    worksheet_title = str(getattr(worksheet, "title", "<unknown>"))
    header_row = _find_historical_header_row(worksheet=worksheet)
    date_value = _normalize_header(worksheet.cell(row=header_row, column=1).value)
    first_series_value = _normalize_header(worksheet.cell(row=header_row, column=2).value)
    second_series_value = _normalize_header(worksheet.cell(row=header_row, column=3).value)

    missing: list[str] = []
    if date_value not in _DATE_HEADER_CANDIDATES:
        missing.append(_REQUIRED_HISTORICAL_APPEND_HEADERS[0])
    if not first_series_value:
        missing.append(_REQUIRED_HISTORICAL_APPEND_HEADERS[1])
    if not second_series_value:
        missing.append(_REQUIRED_HISTORICAL_APPEND_HEADERS[2])

    if missing:
        raise ValueError(
            "Historical workbook sheet "
            f"{worksheet_title!r} is missing required columns for append: {', '.join(missing)}"
        )


def _find_historical_header_row(*, worksheet: Any, max_scan_rows: int = 25) -> int:
    max_row = int(getattr(worksheet, "max_row", max_scan_rows))
    for row in range(1, min(max_row, max_scan_rows) + 1):
        if _normalize_header(worksheet.cell(row=row, column=1).value) in _DATE_HEADER_CANDIDATES:
            return row
    raise ValueError(
        "Historical workbook sheet "
        f"{getattr(worksheet, 'title', '<unknown>')!r} is missing a date header in column A"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_path(path: Path | None, *, field_name: str) -> Path:
    if path is None:
        raise ValueError(f"{field_name} is required for pipeline execution")
    return path


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


def _has_reconciliation_rows(parsed_sections: Any) -> bool:
    if not isinstance(parsed_sections, Mapping):
        return False
    return any(_row_count(table) > 0 for table in parsed_sections.values())


def _run_reconciliation_checks(
    *,
    run_dir: Path,
    config: WorkflowConfig,
    parsed_by_variant: dict[str, dict[str, Any]],
    warnings: list[str],
) -> None:
    variant_historical_paths: dict[str, Path] = {
        "all_programs": config.hist_all_programs_3yr_xlsx,
        "ex_trend": config.hist_ex_llc_3yr_xlsx,
        "trend": config.hist_llc_3yr_xlsx,
    }

    total_gap_count = 0
    impacted_series_count = 0
    impacted_rows_count = 0
    reconciliation_by_variant: dict[str, dict[str, Any]] = {}
    for variant, historical_path in variant_historical_paths.items():
        parsed_sections = parsed_by_variant.get(variant, {})
        if not _has_reconciliation_rows(parsed_sections):
            continue
        parsed_data_by_sheet = {"Total": parsed_sections}
        historical_headers_by_sheet = _extract_historical_series_headers_by_sheet(historical_path)
        result = reconcile_series_coverage(
            parsed_data_by_sheet=parsed_data_by_sheet,
            historical_series_headers_by_sheet=historical_headers_by_sheet,
            variant=variant,
            expected_segments_by_variant=config.reconciliation.expected_segments_by_variant,
        )
        reconciliation_by_variant[variant] = result
        total_gap_count += int(result.get("gap_count", 0))
        impacted_series_count += sum(
            len(item.get("missing_from_historical_headers", []))
            for item in result.get("missing_series", [])
            if isinstance(item, Mapping)
        )
        if int(result.get("gap_count", 0)) > 0:
            impacted_rows_count += _row_count(parsed_sections.get("totals", []))
            impacted_rows_count += _row_count(parsed_sections.get("futures", []))
        for warning in result.get("warnings", []):
            warnings.append(f"Reconciliation ({variant}): {warning}")

    if total_gap_count == 0:
        return

    warnings.append(
        "Reconciliation summary: "
        f"gaps={total_gap_count}, impacted_series={impacted_series_count}, "
        f"impacted_rows={impacted_rows_count}"
    )
    _write_needs_mapping_updates(
        run_dir=run_dir,
        fail_policy=config.reconciliation.fail_policy,
        reconciliation_by_variant=reconciliation_by_variant,
        total_gap_count=total_gap_count,
        impacted_series_count=impacted_series_count,
        impacted_rows_count=impacted_rows_count,
    )
    if config.reconciliation.fail_policy == "strict":
        raise ValueError(
            "Reconciliation strict mode failed due to missing/unmapped series; "
            f"gap_count={total_gap_count}"
        )


def _extract_historical_series_headers_by_sheet(workbook_path: Path) -> dict[str, tuple[str, ...]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "Reconciliation requires openpyxl to read historical workbook headers"
        ) from exc

    workbook = None
    try:
        workbook = load_workbook(filename=workbook_path, read_only=True, data_only=True)
        headers_by_sheet: dict[str, tuple[str, ...]] = {}
        for sheet_name in getattr(workbook, "sheetnames", []):
            worksheet = workbook[sheet_name]
            try:
                header_row = _find_historical_header_row(worksheet=worksheet)
            except ValueError:
                continue
            max_column = int(getattr(worksheet, "max_column", 0))
            headers = [
                label
                for label in (
                    str(worksheet.cell(row=header_row, column=column_index).value or "").strip()
                    for column_index in range(2, max_column + 1)
                )
                if label
            ]
            headers_by_sheet[sheet_name] = tuple(headers)
        return headers_by_sheet
    except Exception as exc:
        raise RuntimeError(
            f"Unable to extract historical series headers from workbook: {workbook_path}"
        ) from exc
    finally:
        if workbook is not None:
            workbook.close()


def _write_needs_mapping_updates(
    *,
    run_dir: Path,
    fail_policy: str,
    reconciliation_by_variant: Mapping[str, Mapping[str, Any]],
    total_gap_count: int,
    impacted_series_count: int,
    impacted_rows_count: int,
) -> Path:
    timestamp = _dt.datetime.now(tz=UTC).isoformat()
    lines: list[str] = [
        "Counter Risk Reconciliation Gaps",
        f"timestamp_utc: {timestamp}",
        f"run_identifier: {run_dir.name}",
        f"fail_policy: {fail_policy}",
        f"total_gap_count: {total_gap_count}",
        f"impacted_series_count: {impacted_series_count}",
        f"impacted_rows_count: {impacted_rows_count}",
        "",
    ]

    for variant in sorted(reconciliation_by_variant, key=str.casefold):
        payload = reconciliation_by_variant[variant]
        lines.append(f"[variant: {variant}]")

        missing_series = payload.get("missing_series", [])
        if isinstance(missing_series, list):
            for item in missing_series:
                if not isinstance(item, Mapping):
                    continue
                sheet_name = str(item.get("sheet", "unknown"))
                missing_labels = item.get("missing_from_historical_headers", [])
                if isinstance(missing_labels, list) and missing_labels:
                    lines.append(
                        f"- sheet {sheet_name}: missing_from_historical_headers="
                        f"{', '.join(str(label) for label in missing_labels)}"
                    )

        missing_segments = payload.get("missing_segments", [])
        if isinstance(missing_segments, list):
            for item in missing_segments:
                if not isinstance(item, Mapping):
                    continue
                sheet_name = str(item.get("sheet", "unknown"))
                expected_labels = item.get("expected_segment_identifiers", [])
                if isinstance(expected_labels, list) and expected_labels:
                    lines.append(
                        f"- sheet {sheet_name}: missing_expected_segments="
                        f"{', '.join(str(label) for label in expected_labels)}"
                    )

        lines.append("")

    output_path = run_dir / "NEEDS_MAPPING_UPDATES.txt"
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path
try:
    UTC = _dt.UTC
except AttributeError:  # pragma: no cover -- Python <3.11 fallback
    UTC = _dt.timezone.utc  # noqa: UP017
