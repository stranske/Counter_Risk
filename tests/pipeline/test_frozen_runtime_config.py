"""Frozen-build config resolution for reconciliation and limit-breach detection.

Regression coverage for the PyInstaller one-dir build: bundled ``config`` files
must be resolved through ``resolve_runtime_path`` (searching the bundle root)
rather than the source-tree ``Path(__file__).resolve().parents[3]`` layout, which
does not exist inside a frozen ``.exe``.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pytest

from counter_risk.limits_config import load_limits_config
from counter_risk.name_registry import load_name_registry
from counter_risk.normalize import _DEFAULT_REGISTRY_RELATIVE_PATH, _resolve_registry_path
from counter_risk.pipeline import reconciliation
from counter_risk.pipeline.run import _compute_and_write_limit_breaches

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_CONFIG = _REPO_ROOT / "config"


@pytest.fixture()
def frozen_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Simulate a frozen one-dir build whose bundle root holds ``config/``."""

    bundle_root = tmp_path / "bundle-root"
    bundle_config = bundle_root / "config"
    bundle_config.mkdir(parents=True)
    for name in ("name_registry.yml", "limits.yml"):
        shutil.copyfile(_REPO_CONFIG / name, bundle_config / name)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("COUNTER_RISK_BUNDLE_ROOT", str(bundle_root))
    # Point the executable dir somewhere without a config/ so the env root is
    # the only thing that can satisfy resolution.
    monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "counter-risk"), raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    return bundle_root


def test_reconciliation_registry_resolves_from_bundle_root(frozen_bundle: Path) -> None:
    resolved = reconciliation._name_registry_path()

    assert resolved == frozen_bundle / "config" / "name_registry.yml"
    assert resolved.exists()
    # The file the reconciliation pass loads is valid and parses cleanly.
    load_name_registry(resolved)


def test_normalize_default_registry_resolves_from_bundle_root(frozen_bundle: Path) -> None:
    resolved = _resolve_registry_path(_DEFAULT_REGISTRY_RELATIVE_PATH)

    assert resolved == frozen_bundle / "config" / "name_registry.yml"
    assert resolved.exists()


def test_limit_breach_resolution_finds_bundled_limits_config(
    frozen_bundle: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    warnings: list[str] = []

    with caplog.at_level(logging.INFO, logger="counter_risk.pipeline.run"):
        evaluation = _compute_and_write_limit_breaches(
            parsed_by_variant={},
            run_dir=run_dir,
            warnings=warnings,
        )

    # With no exposures there are no breaches, but the limits config must have
    # been located: the silent "missing config" skip branch must NOT fire.
    assert evaluation.csv_path is None
    assert "limit_breaches_skipped" not in caplog.text
    # Sanity check the bundled file the run path now resolves is loadable.
    load_limits_config(frozen_bundle / "config" / "limits.yml")
