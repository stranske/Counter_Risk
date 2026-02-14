"""Fixture replay helpers for release-bundle execution."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from counter_risk.config import WorkflowConfig, load_config


def _resolve_config_path(path: Path, *, config_dir: Path) -> Path:
    if path.is_absolute():
        return path
    primary = (config_dir / path).resolve()
    if primary.exists():
        return primary
    return (config_dir.parent / path).resolve()


def _copy_output_file(*, src_path: Path, output_dir: Path) -> Path:
    if not src_path.exists():
        raise FileNotFoundError(f"Fixture input not found: {src_path}")
    if not src_path.is_file():
        raise ValueError(f"Fixture input path must be a file: {src_path}")

    destination = output_dir / src_path.name
    shutil.copy2(src_path, destination)
    return destination


def _resolve_output_dir(
    config: WorkflowConfig, *, config_path: Path, output_dir: Path | None
) -> Path:
    if output_dir is not None:
        return output_dir.resolve()
    if config.output_root.is_absolute():
        return config.output_root
    return (config_path.parent / config.output_root).resolve()


def run_fixture_replay(*, config_path: Path, output_dir: Path | None = None) -> Path:
    """Replay fixture artifacts into a deterministic run-output folder."""

    config = load_config(config_path)
    config_dir = config_path.resolve().parent
    run_dir = _resolve_output_dir(config, config_path=config_path, output_dir=output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    sources = {
        "mosers_all_programs_xlsx": config.mosers_all_programs_xlsx,
        "mosers_ex_trend_xlsx": config.mosers_ex_trend_xlsx,
        "mosers_trend_xlsx": config.mosers_trend_xlsx,
        "hist_all_programs_3yr_xlsx": config.hist_all_programs_3yr_xlsx,
        "hist_ex_llc_3yr_xlsx": config.hist_ex_llc_3yr_xlsx,
        "hist_llc_3yr_xlsx": config.hist_llc_3yr_xlsx,
        "monthly_pptx": config.monthly_pptx,
    }

    copied_outputs: dict[str, str] = {}
    for key, source_path in sources.items():
        if source_path is None:
            continue
        resolved = _resolve_config_path(source_path, config_dir=config_dir)
        copied_path = _copy_output_file(src_path=resolved, output_dir=run_dir)
        copied_outputs[key] = str(copied_path)

    manifest = {
        "mode": "fixture_replay",
        "run_date_utc": datetime.now(UTC).isoformat(),
        "as_of_date": None if config.as_of_date is None else config.as_of_date.isoformat(),
        "config_path": str(config_path.resolve()),
        "outputs": copied_outputs,
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return run_dir
