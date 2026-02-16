"""Integration tests for packaged executable asset loading."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = pytest.mark.release

_REQUIRED_FIXTURE_KEYS = (
    "mosers_all_programs_xlsx",
    "mosers_ex_trend_xlsx",
    "mosers_trend_xlsx",
    "hist_all_programs_3yr_xlsx",
    "hist_ex_llc_3yr_xlsx",
    "hist_llc_3yr_xlsx",
    "monthly_pptx",
)


def _build_packaged_output(tmp_path: Path) -> Path:
    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller is None:
        pytest.skip("PyInstaller is not installed in this environment.")

    repo_root = Path(__file__).resolve().parents[2]
    build_root = tmp_path / "build"
    build_root.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [pyinstaller, "-y", str(repo_root / "release.spec")],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    produced_dir = repo_root / "dist" / "counter-risk"
    if not produced_dir.is_dir():
        pytest.fail(f"PyInstaller did not produce expected directory: {produced_dir}")

    isolated_bundle = build_root / "counter-risk"
    shutil.copytree(produced_dir, isolated_bundle)
    return isolated_bundle


def _load_default_bundle_config(bundle_dir: Path) -> dict[str, object]:
    config_path = bundle_dir / "config" / "fixture_replay.yml"
    if not config_path.is_file():
        pytest.fail(f"Bundled config missing: {config_path}")
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        pytest.fail(f"Bundled config must be a mapping: {config_path}")
    return parsed


def _seed_bundle_fixture_inputs(bundle_dir: Path, config: dict[str, object]) -> None:
    for key in _REQUIRED_FIXTURE_KEYS:
        value = config.get(key)
        if not isinstance(value, str):
            pytest.fail(f"Expected string path for config key '{key}', got: {value!r}")
        target = (bundle_dir / value).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"fixture-bytes-for-{key}".encode())


def _packaged_executable_path(bundle_dir: Path) -> Path:
    executable = bundle_dir / ("counter-risk.exe" if os.name == "nt" else "counter-risk")
    if not executable.is_file():
        pytest.fail(f"Packaged executable missing: {executable}")
    return executable


def _run_fixture_replay(
    *, bundle_dir: Path, output_dir: Path, config_override: Path | None = None
) -> subprocess.CompletedProcess[str]:
    executable = _packaged_executable_path(bundle_dir)
    args = [str(executable), "run", "--fixture-replay", "--output-dir", str(output_dir)]
    if config_override is not None:
        args.extend(["--config", str(config_override)])

    return subprocess.run(
        args,
        cwd=bundle_dir,
        text=True,
        capture_output=True,
        check=False,
    )


def test_packaged_executable_loads_default_config_and_bundled_template_from_isolated_dir(
    tmp_path: Path,
) -> None:
    bundle_dir = _build_packaged_output(tmp_path)
    config = _load_default_bundle_config(bundle_dir)
    _seed_bundle_fixture_inputs(bundle_dir, config)

    default_run_output = tmp_path / "run-default-config"
    default_run = _run_fixture_replay(bundle_dir=bundle_dir, output_dir=default_run_output)
    assert default_run.returncode == 0, (
        "Packaged executable failed to run fixture replay with bundled default config.\n"
        f"stdout:\n{default_run.stdout}\n"
        f"stderr:\n{default_run.stderr}"
    )

    manifest_path = default_run_output / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_config_path = (bundle_dir / "config" / "fixture_replay.yml").resolve()
    assert Path(manifest["config_path"]).resolve() == expected_config_path

    template_candidates = sorted((bundle_dir / "templates").glob("*.pptx"))
    if not template_candidates:
        pytest.fail("No bundled templates found in packaged output.")
    template_path = template_candidates[0]

    template_config = dict(config)
    template_config["monthly_pptx"] = str(Path("templates") / template_path.name)
    template_config_path = bundle_dir / "config" / "fixture_replay_template.yml"
    template_config_path.write_text(
        yaml.safe_dump(template_config, sort_keys=False), encoding="utf-8"
    )

    template_run_output = tmp_path / "run-template-input"
    template_run = _run_fixture_replay(
        bundle_dir=bundle_dir,
        output_dir=template_run_output,
        config_override=template_config_path,
    )
    assert template_run.returncode == 0, (
        "Packaged executable failed to read template asset from bundled templates directory.\n"
        f"stdout:\n{template_run.stdout}\n"
        f"stderr:\n{template_run.stderr}"
    )

    copied_template = template_run_output / template_path.name
    assert copied_template.is_file()
    assert copied_template.read_bytes() == template_path.read_bytes()
