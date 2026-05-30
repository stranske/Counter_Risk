"""Synthetic fixture browser-demo artifact generation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from counter_risk.config import WorkflowConfig, load_config
from counter_risk.pipeline.fixture_replay import run_fixture_replay

_OFFLINE_ENV_VAR = "COUNTER_RISK_CHAT_OFFLINE_MODE"
_SUMMARY_NAME = "DATA_QUALITY_SUMMARY.txt"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_config_path(path: Path, *, config_dir: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    primary = (config_dir / path).resolve()
    if primary.exists():
        return primary
    repo_fixture = (_repo_root() / "tests" / path).resolve()
    if repo_fixture.exists():
        return repo_fixture
    return (config_dir.parent / path).resolve()


def _materialize_source_checkout_config(*, config_path: Path, output_dir: Path) -> Path:
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw_config, dict):
        raise ValueError(f"Demo config must be a mapping: {config_path}")

    config_dir = config_path.resolve().parent
    path_keys = {
        "mosers_all_programs_xlsx",
        "mosers_ex_trend_xlsx",
        "mosers_trend_xlsx",
        "hist_all_programs_3yr_xlsx",
        "hist_ex_llc_3yr_xlsx",
        "hist_llc_3yr_xlsx",
        "monthly_pptx",
    }
    normalized = dict(raw_config)
    changed = False
    for key in path_keys:
        value = raw_config.get(key)
        if not isinstance(value, str):
            continue
        source_path = Path(value)
        resolved = _resolve_config_path(source_path, config_dir=config_dir)
        if resolved != (config_dir / source_path).resolve() and resolved.exists():
            normalized[key] = str(resolved)
            changed = True

    if not changed:
        return config_path

    config_copy = output_dir.resolve().parent / "demo_fixture_replay.yml"
    config_copy.parent.mkdir(parents=True, exist_ok=True)
    config_copy.write_text(yaml.safe_dump(normalized, sort_keys=False), encoding="utf-8")
    return config_copy


def _fixture_sources(config: WorkflowConfig) -> dict[str, Path]:
    sources = {
        "mosers_all_programs_xlsx": config.mosers_all_programs_xlsx,
        "mosers_ex_trend_xlsx": config.mosers_ex_trend_xlsx,
        "mosers_trend_xlsx": config.mosers_trend_xlsx,
        "hist_all_programs_3yr_xlsx": config.hist_all_programs_3yr_xlsx,
        "hist_ex_llc_3yr_xlsx": config.hist_ex_llc_3yr_xlsx,
        "hist_llc_3yr_xlsx": config.hist_llc_3yr_xlsx,
        "monthly_pptx": config.monthly_pptx,
    }
    return {key: value for key, value in sources.items() if value is not None}


def _assert_fixture_only(config: WorkflowConfig, *, config_path: Path) -> list[Path]:
    fixture_root = (_repo_root() / "tests" / "fixtures").resolve()
    config_dir = config_path.resolve().parent
    resolved_sources: list[Path] = []
    for key, source in _fixture_sources(config).items():
        resolved = _resolve_config_path(source, config_dir=config_dir)
        try:
            resolved.relative_to(fixture_root)
        except ValueError as exc:
            raise ValueError(
                f"Demo fixture source {key} must live under {fixture_root}: {resolved}"
            ) from exc
        resolved_sources.append(resolved)
    return resolved_sources


def _write_data_quality_summary(
    *, run_dir: Path, config_path: Path, fixture_sources: list[Path]
) -> Path:
    summary_path = run_dir / _SUMMARY_NAME
    source_lines = "\n".join(f"- {source.name}" for source in sorted(fixture_sources))
    summary_path.write_text(
        "\n".join(
            [
                "Counter Risk browser demo data-quality summary",
                "",
                "Mode: synthetic fixture replay",
                "Data zone: no real/proprietary data; bundled tests/fixtures only",
                "Network/LLM boundary: chat disabled via COUNTER_RISK_CHAT_OFFLINE_MODE=1",
                f"Config: {config_path.as_posix()}",
                "",
                "Fixture sources:",
                source_lines,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary_path


def build_demo_artifact(*, config_path: Path, output_dir: Path) -> Path:
    """Build a browser-downloadable synthetic fixture artifact folder."""

    os.environ[_OFFLINE_ENV_VAR] = "1"
    demo_config_path = _materialize_source_checkout_config(
        config_path=config_path,
        output_dir=output_dir,
    )
    config = load_config(demo_config_path)
    fixture_sources = _assert_fixture_only(config, config_path=demo_config_path)
    run_dir = run_fixture_replay(config_path=demo_config_path, output_dir=output_dir)
    summary_path = _write_data_quality_summary(
        run_dir=run_dir,
        config_path=config_path.resolve(),
        fixture_sources=fixture_sources,
    )

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_zone"] = "synthetic-fixtures-only"
    manifest["chat_offline_mode"] = os.environ[_OFFLINE_ENV_VAR]
    manifest["data_quality_summary"] = summary_path.name
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m counter_risk.demo_artifact",
        description="Build the synthetic, no-egress browser-demo artifact folder.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/fixture_replay.yml"),
        help="Fixture replay config. Inputs must resolve under tests/fixtures.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/demo"),
        help="Directory that will be uploaded as the browser demo artifact.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = build_demo_artifact(config_path=args.config, output_dir=args.output_dir)
    print(f"Demo artifact written to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
