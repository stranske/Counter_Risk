"""Unit tests for bundled runtime path helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from counter_risk.runtime_paths import RuntimePathResolutionError, resolve_runtime_path


def test_resolve_runtime_path_keeps_relative_path_when_not_frozen() -> None:
    resolved = resolve_runtime_path("config/fixture_replay.yml")
    assert resolved == Path("config/fixture_replay.yml")


def test_resolve_runtime_path_prefers_bundle_root_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle_root = tmp_path / "bundle-root"
    config_path = bundle_root / "config" / "fixture_replay.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("as_of_date: 2025-12-31\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("COUNTER_RISK_BUNDLE_ROOT", str(bundle_root))
    monkeypatch.setattr(sys, "executable", str(tmp_path / "alt" / "counter-risk"), raising=False)

    resolved = resolve_runtime_path("config/fixture_replay.yml")
    assert resolved == config_path


def test_resolve_runtime_path_falls_back_to_executable_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable_dir = tmp_path / "dist" / "counter-risk"
    executable_dir.mkdir(parents=True)
    executable_path = executable_dir / "counter-risk"
    executable_path.write_text("", encoding="utf-8")
    config_path = executable_dir / "config" / "fixture_replay.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("as_of_date: 2025-12-31\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("COUNTER_RISK_BUNDLE_ROOT", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path), raising=False)

    resolved = resolve_runtime_path("config/fixture_replay.yml")
    assert resolved == config_path


def test_resolve_runtime_path_raises_for_missing_asset_and_lists_searched_locations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle_root = tmp_path / "bundle-root"
    bundle_root.mkdir(parents=True)

    executable_dir = tmp_path / "dist" / "counter-risk"
    executable_dir.mkdir(parents=True)
    executable_path = executable_dir / "counter-risk"
    executable_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("COUNTER_RISK_BUNDLE_ROOT", str(bundle_root))
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path), raising=False)

    requested_asset = Path("config") / "missing.yml"
    with pytest.raises(RuntimePathResolutionError, match="missing.yml") as excinfo:
        resolve_runtime_path(requested_asset)

    message = str(excinfo.value)
    assert "Searched locations:" in message
    assert str(bundle_root / requested_asset) in message
    assert str(executable_dir / requested_asset) in message


def test_resolve_runtime_path_surfaces_meipass_misconfiguration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    meipass_root = tmp_path / "bad-meipass"
    meipass_root.mkdir(parents=True)

    executable_dir = tmp_path / "dist" / "counter-risk"
    executable_dir.mkdir(parents=True)
    executable_path = executable_dir / "counter-risk"
    executable_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("COUNTER_RISK_BUNDLE_ROOT", raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_root), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path), raising=False)

    requested_asset = Path("config") / "fixture_replay.yml"
    with pytest.raises(RuntimePathResolutionError, match="fixture_replay.yml") as excinfo:
        resolve_runtime_path(requested_asset)

    message = str(excinfo.value)
    assert "Searched roots:" in message
    assert str(meipass_root / requested_asset) in message
    assert str(executable_dir / requested_asset) in message


def test_resolve_runtime_path_raises_when_frozen_has_no_bundle_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("COUNTER_RISK_BUNDLE_ROOT", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(sys, "executable", raising=False)

    requested_asset = Path("config") / "fixture_replay.yml"
    with pytest.raises(RuntimePathResolutionError, match="fixture_replay.yml") as excinfo:
        resolve_runtime_path(requested_asset)

    message = str(excinfo.value)
    assert "No bundle roots were discovered" in message
    assert "COUNTER_RISK_BUNDLE_ROOT" in message
