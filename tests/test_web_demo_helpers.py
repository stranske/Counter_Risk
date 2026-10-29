"""Focused branch coverage for the fixture-only web demo helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import counter_risk.web_demo as web_demo


def test_resolve_config_path_prefers_absolute_config_then_test_fixture(tmp_path: Path) -> None:
    absolute = tmp_path / "absolute.csv"
    absolute.write_text("absolute", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    local = config_dir / "local.csv"
    local.write_text("local", encoding="utf-8")
    fallback = tmp_path / "fallback.csv"

    assert web_demo._resolve_config_path(absolute, config_dir=config_dir) == absolute.resolve()
    assert (
        web_demo._resolve_config_path(Path("local.csv"), config_dir=config_dir) == local.resolve()
    )
    assert (
        web_demo._resolve_config_path(Path("fallback.csv"), config_dir=config_dir)
        == fallback.resolve()
    )


def test_resolve_config_path_uses_repo_test_path_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    fixture = repo_root / "tests" / "fixtures" / "input.csv"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("fixture", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    assert (
        web_demo._resolve_config_path(Path("fixtures/input.csv"), config_dir=config_dir) == fixture
    )


def test_materialize_config_only_writes_relocated_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    fixture = repo_root / "tests" / "fixtures" / "source.xlsx"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("fixture", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "demo.yml"
    config_path.write_text(
        yaml.safe_dump({"mosers_all_programs_xlsx": "fixtures/source.xlsx", "ignored": 3}),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    copied = web_demo._materialize_web_demo_config(
        config_path=config_path, output_dir=tmp_path / "output" / "run"
    )

    assert copied == tmp_path / "output" / "web_demo_fixture_replay.yml"
    assert yaml.safe_load(copied.read_text(encoding="utf-8")) == {
        "mosers_all_programs_xlsx": str(fixture),
        "ignored": 3,
    }


def test_materialize_config_preserves_local_config_and_rejects_non_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "demo.yml"
    config_path.write_text(yaml.safe_dump({"monthly_pptx": 7}), encoding="utf-8")

    assert (
        web_demo._materialize_web_demo_config(
            config_path=config_path, output_dir=tmp_path / "output"
        )
        == config_path
    )

    config_path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a mapping"):
        web_demo._materialize_web_demo_config(
            config_path=config_path, output_dir=tmp_path / "output"
        )


def test_fixture_sources_and_assertion_cover_optional_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    fixture_root = repo_root / "tests" / "fixtures"
    fixture_root.mkdir(parents=True)
    source = fixture_root / "input.csv"
    source.write_text("fixture", encoding="utf-8")
    config = SimpleNamespace(
        mosers_all_programs_xlsx=Path("input.csv"),
        raw_nisa_all_programs_xlsx=None,
        mosers_ex_trend_xlsx=None,
        raw_nisa_ex_trend_xlsx=None,
        mosers_trend_xlsx=None,
        raw_nisa_trend_xlsx=None,
        daily_holdings_pdf=None,
        cash_source_path=None,
        cash_overrides_csv=None,
        dropin_all_programs_template_xlsx=None,
        hist_all_programs_3yr_xlsx=None,
        hist_ex_llc_3yr_xlsx=None,
        hist_llc_3yr_xlsx=None,
        monthly_pptx=None,
        screenshot_inputs={"main": Path("input.csv"), "empty": None},
        input_discovery=SimpleNamespace(directory_roots={"source": Path("input.csv")}),
    )
    config_path = fixture_root / "config.yml"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    assert set(web_demo._fixture_sources(config)) == {
        "mosers_all_programs_xlsx",
        "screenshot_inputs.main",
        "input_discovery.directory_roots.source",
    }
    assert web_demo._assert_fixture_only(config, config_path=config_path) == [
        source,
        source,
        source,
    ]

    config.cash_source_path = tmp_path / "outside.csv"
    with pytest.raises(ValueError, match="cash_source_path.*must live under"):
        web_demo._assert_fixture_only(config, config_path=config_path)


def test_chat_runtime_guard_only_rejects_new_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, web_demo._BLOCKED_CHAT_RUNTIME, raising=False)
    assert not web_demo._chat_runtime_loaded()
    web_demo._assert_chat_runtime_not_newly_loaded(loaded_before=True)
    sys.modules[web_demo._BLOCKED_CHAT_RUNTIME] = object()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="unexpectedly loaded"):
        web_demo._assert_chat_runtime_not_newly_loaded(loaded_before=False)
    monkeypatch.delitem(sys.modules, web_demo._BLOCKED_CHAT_RUNTIME, raising=False)


def test_summary_and_manifest_path_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    fixture = repo_root / "tests" / "fixtures" / "input.csv"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("fixture", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    local_output = run_dir / "child.csv"
    local_output.write_text("output", encoding="utf-8")
    config = repo_root / "config" / "fixture.yml"
    config.parent.mkdir(parents=True)
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    summary = web_demo._write_data_quality_summary(
        run_dir=run_dir, config_path=config, fixture_sources=[fixture]
    )
    assert "Config: config/fixture.yml" in summary.read_text(encoding="utf-8")
    assert web_demo._artifact_relative_path(str(local_output), run_dir=run_dir) == "child.csv"
    assert (
        web_demo._artifact_relative_path(str(fixture), run_dir=run_dir)
        == "tests/fixtures/input.csv"
    )
    assert web_demo._artifact_relative_path(str(config), run_dir=run_dir) == "config/fixture.yml"
    assert (
        web_demo._artifact_relative_path(str(tmp_path / "outside.csv"), run_dir=run_dir)
        == "outside.csv"
    )
    assert web_demo._artifact_relative_path("relative.csv", run_dir=run_dir) == "relative.csv"
    assert web_demo._normalize_manifest_paths(
        {"paths": [str(local_output), {"fixture": str(fixture)}], "count": 1}, run_dir=run_dir
    ) == {"paths": ["child.csv", {"fixture": "tests/fixtures/input.csv"}], "count": 1}


def test_run_web_demo_pipeline_annotates_manifest_and_preserves_offline_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"output": str(run_dir / "out.csv")}), encoding="utf-8"
    )
    config_path = tmp_path / "fixture.yml"
    config_path.write_text("{}", encoding="utf-8")
    config = object()
    fixture = tmp_path / "input.csv"
    fixture.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(web_demo, "_materialize_web_demo_config", lambda **_: config_path)
    monkeypatch.setattr(web_demo, "load_config", lambda _: config)
    monkeypatch.setattr(web_demo, "_assert_fixture_only", lambda *_args, **_kwargs: [fixture])
    monkeypatch.setattr(web_demo, "run_pipeline_with_config", lambda _config, **_kwargs: run_dir)
    monkeypatch.setattr(web_demo, "_chat_runtime_loaded", lambda: False)

    assert (
        web_demo.run_web_demo_pipeline(config_path=config_path, output_dir=tmp_path / "output")
        == run_dir
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["output"] == "out.csv"
    assert manifest["data_zone"] == "synthetic-fixtures-only"
    assert manifest["chat_offline_mode"] == "1"
    assert manifest["data_quality_summary"] == "DATA_QUALITY_SUMMARY.txt"
