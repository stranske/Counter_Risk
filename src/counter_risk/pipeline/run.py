"""Counter Risk pipeline orchestration."""

from __future__ import annotations

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
from counter_risk.dates import derive_as_of_date, derive_run_date
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

    try:
        cprs_headers = _collect_cprs_header_candidates(config=config)
        as_of_date = derive_as_of_date(config, cprs_headers)
        run_date = derive_run_date(config)
        run_date_for_directory = config.run_date
    except Exception as exc:
        LOGGER.exception("pipeline_failed stage=date_derivation config_path=%s", config_path)
        raise RuntimeError("Pipeline failed during date derivation stage") from exc

    try:
        run_dir = _create_run_directory(as_of_date=as_of_date, run_date=run_date_for_directory)
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
        manifest_builder = ManifestBuilder(config=config, as_of_date=as_of_date, run_date=run_date)
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


def _create_run_directory(*, as_of_date: date, run_date: date | None = None) -> Path:
    runs_root = _resolve_repo_root() / "runs"
    base_name = (
        as_of_date.isoformat()
        if run_date is None
        else f"{as_of_date.isoformat()}__run_{run_date.isoformat()}"
    )
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


def _collect_cprs_header_candidates(*, config: WorkflowConfig) -> list[str]:
    header_candidates: list[str] = []
    candidate_paths = [
        config.mosers_all_programs_xlsx,
        config.mosers_ex_trend_xlsx,
        config.mosers_trend_xlsx,
    ]
    for path in candidate_paths:
        if path is None:
            continue
        header_candidates.extend(_extract_header_text_lines(path))
    return header_candidates


def _extract_header_text_lines(
    workbook_path: Path, *, max_rows: int = 15, max_cols: int = 6
) -> list[str]:
    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return []
    except Exception:
        return []

    workbook = None
    try:
        workbook = load_workbook(filename=workbook_path, read_only=True, data_only=True)
        if not workbook.sheetnames:
            return []
        worksheet = workbook[workbook.sheetnames[0]]
        lines: list[str] = []
        for row in range(1, min(int(worksheet.max_row), max_rows) + 1):
            pieces: list[str] = []
            for col in range(1, max_cols + 1):
                value = worksheet.cell(row=row, column=col).value
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    pieces.append(text)
            if pieces:
                lines.append(" ".join(pieces))
        return lines
    except Exception:
        return []
    finally:
        if workbook is not None:
            workbook.close()


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
        from openpyxl import load_workbook
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

        worksheet.cell(row=append_row, column=1).value = as_of_date
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
