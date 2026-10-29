"""Focused branch coverage for the fixture-only web demo helpers."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import counter_risk.web_demo as web_demo

_FIXTURE_SOURCE_FIELDS = (
    "mosers_all_programs_xlsx",
    "raw_nisa_all_programs_xlsx",
    "mosers_ex_trend_xlsx",
    "raw_nisa_ex_trend_xlsx",
    "mosers_trend_xlsx",
    "raw_nisa_trend_xlsx",
    "daily_holdings_pdf",
    "cash_source_path",
    "cash_overrides_csv",
    "dropin_all_programs_template_xlsx",
    "exposure_summary_xlsx",
    "hist_all_programs_3yr_xlsx",
    "hist_ex_llc_3yr_xlsx",
    "hist_llc_3yr_xlsx",
    "monthly_pptx",
)


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


@pytest.mark.parametrize("preferred", ["absolute", "config", "repository"])
def test_resolve_config_path_selects_preferred_source_when_fallbacks_also_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, preferred: str
) -> None:
    repo_root = tmp_path / "repo"
    config_dir = tmp_path / "project" / "config"
    relative = Path("fixtures/input.csv")
    candidates = {
        "absolute": tmp_path / "absolute" / relative,
        "config": config_dir / relative,
        "repository": repo_root / "tests" / relative,
        "parent": config_dir.parent / relative,
    }
    for label, candidate in candidates.items():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(label, encoding="utf-8")
    if preferred == "repository":
        candidates["config"].unlink()
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    requested = candidates["absolute"] if preferred == "absolute" else relative
    resolved = web_demo._resolve_config_path(requested, config_dir=config_dir)

    assert resolved == candidates[preferred]
    assert resolved.read_text(encoding="utf-8") == preferred


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


@pytest.mark.parametrize(
    "naming_patterns", [{}, {"monthly": ["*.xlsx"]}], ids=["empty", "patterns"]
)
def test_relocated_config_accepts_discovery_without_directory_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, naming_patterns: dict[str, list[str]]
) -> None:
    repo_root = tmp_path / "repo"
    fixture_dir = repo_root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    source = fixture_dir / "history.xlsx"
    source.write_text("synthetic history", encoding="utf-8")
    config_dir = repo_root / "config"
    config_dir.mkdir()
    discovery = {"naming_patterns": naming_patterns} if naming_patterns else {}
    raw_config = dict.fromkeys(
        (
            "hist_all_programs_3yr_xlsx",
            "hist_ex_llc_3yr_xlsx",
            "hist_llc_3yr_xlsx",
            "monthly_pptx",
        ),
        "fixtures/history.xlsx",
    )
    config_path = config_dir / "demo.yml"
    original_config = yaml.safe_dump({**raw_config, "input_discovery": discovery})
    config_path.write_text(original_config, encoding="utf-8")
    output_dir = tmp_path / "output" / "run"
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    materialized = web_demo._materialize_web_demo_config(
        config_path=config_path, output_dir=output_dir
    )

    assert materialized == output_dir.parent / "web_demo_fixture_replay.yml"
    assert yaml.safe_load(materialized.read_text(encoding="utf-8")) == {
        **dict.fromkeys(raw_config, str(source)),
        "input_discovery": discovery,
    }
    config = web_demo.load_config(materialized)
    assert config.input_discovery.directory_roots == {}
    assert config.input_discovery.naming_patterns == naming_patterns
    assert web_demo._assert_fixture_only(config, config_path=materialized) == [source] * 4
    assert config_path.read_text(encoding="utf-8") == original_config


@pytest.mark.parametrize("fallback_exists", [True, False], ids=["existing", "missing"])
def test_materialize_config_relocates_only_for_an_existing_parent_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fallback_exists: bool
) -> None:
    repo_root = tmp_path / "repo"
    fixture_dir = repo_root / "tests" / "fixtures"
    config_dir = fixture_dir / "config"
    config_dir.mkdir(parents=True)
    fallback = fixture_dir / "history.xlsx"
    if fallback_exists:
        fallback.write_text("synthetic history", encoding="utf-8")
    config_path = config_dir / "demo.yml"
    original_config = (
        "# Preserve the original config and its diagnostics.\nmonthly_pptx: history.xlsx\n"
    )
    config_path.write_text(original_config, encoding="utf-8")
    output_dir = tmp_path / "output" / "run"
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)

    materialized = web_demo._materialize_web_demo_config(
        config_path=config_path, output_dir=output_dir
    )

    if fallback_exists:
        assert materialized == output_dir.parent / "web_demo_fixture_replay.yml"
        assert yaml.safe_load(materialized.read_text(encoding="utf-8")) == {
            "monthly_pptx": str(fallback)
        }
    else:
        assert materialized == config_path
        assert not output_dir.parent.exists()
    assert config_path.read_text(encoding="utf-8") == original_config
    assert not output_dir.exists()


@pytest.mark.parametrize(
    "local_key",
    [*_FIXTURE_SOURCE_FIELDS, "screenshot_inputs", "input_discovery"],
)
def test_relocated_config_preserves_config_relative_fixture_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, local_key: str
) -> None:
    repo_root = tmp_path / "repo"
    fixture_dir = repo_root / "tests" / "fixtures"
    config_dir = fixture_dir / "config"
    config_dir.mkdir(parents=True)
    history = fixture_dir / "history.xlsx"
    history.write_text("synthetic history", encoding="utf-8")
    local_source = config_dir / "local.csv"
    local_source.write_text("synthetic local input", encoding="utf-8")
    raw_config: dict[str, object] = dict.fromkeys(
        ("hist_all_programs_3yr_xlsx", "hist_ex_llc_3yr_xlsx", "hist_llc_3yr_xlsx", "monthly_pptx"),
        "fixtures/history.xlsx",
    )
    if local_key == "screenshot_inputs":
        raw_config[local_key] = {"cprs_ch": "local.csv"}
    elif local_key == "input_discovery":
        raw_config[local_key] = {"directory_roots": {"monthly_inputs": "."}}
    else:
        raw_config[local_key] = "local.csv"
    config_path = config_dir / "demo.yml"
    original_config = yaml.safe_dump(raw_config)
    config_path.write_text(original_config, encoding="utf-8")
    run_dir = tmp_path / "output" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(web_demo, "_chat_runtime_loaded", lambda: False)
    monkeypatch.setenv(web_demo._OFFLINE_ENV_VAR, "0")
    calls = []

    def run_pipeline(
        config: web_demo.WorkflowConfig, *, config_dir: Path, output_dir: Path
    ) -> Path:
        assert config.hist_all_programs_3yr_xlsx == (
            local_source if local_key == "hist_all_programs_3yr_xlsx" else history
        )
        if local_key == "screenshot_inputs":
            assert config.screenshot_inputs["cprs_ch"] == local_source
        elif local_key == "input_discovery":
            assert config.input_discovery.directory_roots["monthly_inputs"] == config_path.parent
        else:
            assert getattr(config, local_key) == local_source
        assert config_dir == run_dir.parent
        assert output_dir == run_dir
        calls.append(config)
        return run_dir

    monkeypatch.setattr(web_demo, "run_pipeline_with_config", run_pipeline)

    assert web_demo.run_web_demo_pipeline(config_path=config_path, output_dir=run_dir) == run_dir
    assert len(calls) == 1
    assert config_path.read_text(encoding="utf-8") == original_config
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_zone"] == "synthetic-fixtures-only"


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
        exposure_summary_xlsx=None,
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


@pytest.mark.parametrize("runtime_preloaded", [False, True], ids=["new-runtime", "preloaded"])
def test_pipeline_checks_runtime_transition_before_publishing_demo_annotations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runtime_preloaded: bool
) -> None:
    repo_root = tmp_path / "repo"
    fixture_dir = repo_root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    source = fixture_dir / "input.xlsx"
    source.write_text("synthetic fixture", encoding="utf-8")
    config_path = fixture_dir / "demo.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                key: str(source)
                for key in (
                    "hist_all_programs_3yr_xlsx",
                    "hist_ex_llc_3yr_xlsx",
                    "hist_llc_3yr_xlsx",
                    "monthly_pptx",
                )
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest_path = run_dir / "manifest.json"
    original_manifest = json.dumps({"output": str(run_dir / "out.csv")})
    manifest_path.write_text(original_manifest, encoding="utf-8")
    runtime = object()
    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)
    monkeypatch.setenv(web_demo._OFFLINE_ENV_VAR, "0")
    monkeypatch.delitem(sys.modules, web_demo._BLOCKED_CHAT_RUNTIME, raising=False)
    if runtime_preloaded:
        monkeypatch.setitem(sys.modules, web_demo._BLOCKED_CHAT_RUNTIME, runtime)

    calls = []

    def run_pipeline(
        config: web_demo.WorkflowConfig, *, config_dir: Path, output_dir: Path
    ) -> Path:
        assert config.hist_all_programs_3yr_xlsx == source
        assert config_dir == fixture_dir
        assert output_dir == run_dir
        assert os.environ[web_demo._OFFLINE_ENV_VAR] == "1"
        calls.append(config)
        monkeypatch.setitem(sys.modules, web_demo._BLOCKED_CHAT_RUNTIME, runtime)
        return run_dir

    monkeypatch.setattr(web_demo, "run_pipeline_with_config", run_pipeline)

    if runtime_preloaded:
        assert (
            web_demo.run_web_demo_pipeline(config_path=config_path, output_dir=run_dir) == run_dir
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["data_zone"] == "synthetic-fixtures-only"
        assert (run_dir / manifest["data_quality_summary"]).is_file()
    else:
        with pytest.raises(RuntimeError, match="unexpectedly loaded chat provider module"):
            web_demo.run_web_demo_pipeline(config_path=config_path, output_dir=run_dir)
        assert manifest_path.read_text(encoding="utf-8") == original_manifest
        assert not (run_dir / "DATA_QUALITY_SUMMARY.txt").exists()

    assert len(calls) == 1
    assert sys.modules[web_demo._BLOCKED_CHAT_RUNTIME] is runtime


@pytest.mark.parametrize(
    "source_key",
    [
        *_FIXTURE_SOURCE_FIELDS,
        "screenshot_inputs.cprs_ch",
        "input_discovery.directory_roots.monthly_inputs",
    ],
)
def test_pipeline_rejects_optional_fixture_symlinks_before_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source_key: str
) -> None:
    repo_root = tmp_path / "repo"
    fixture_dir = repo_root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    source = fixture_dir / "input.xlsx"
    source.write_text("synthetic fixture", encoding="utf-8")
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "input.csv").write_text("outside fixture boundary", encoding="utf-8")
    linked_dir = fixture_dir / "linked"
    linked_dir.symlink_to(external_dir, target_is_directory=True)
    linked_source = (
        linked_dir if source_key.startswith("input_discovery.") else linked_dir / "input.csv"
    )

    raw_config = {
        key: str(source)
        for key in (
            "hist_all_programs_3yr_xlsx",
            "hist_ex_llc_3yr_xlsx",
            "hist_llc_3yr_xlsx",
            "monthly_pptx",
        )
    }
    optional_config: object = str(linked_source)
    for key in reversed(source_key.split(".")):
        optional_config = {key: optional_config}
    assert isinstance(optional_config, dict)
    raw_config.update(optional_config)
    config_path = fixture_dir / "demo.yml"
    config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest_path = run_dir / "manifest.json"
    original_manifest = '{"existing": true}\n'
    manifest_path.write_text(original_manifest, encoding="utf-8")

    def unexpected_pipeline(*_args: object, **_kwargs: object) -> Path:
        pytest.fail("Pipeline must not run with sources outside the fixture boundary")

    monkeypatch.setattr(web_demo, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(web_demo, "run_pipeline_with_config", unexpected_pipeline)
    monkeypatch.setenv(web_demo._OFFLINE_ENV_VAR, "0")

    with pytest.raises(ValueError) as exc_info:
        web_demo.run_web_demo_pipeline(config_path=config_path, output_dir=run_dir)

    message = str(exc_info.value)
    assert f"Web demo fixture source {source_key} must live under {fixture_dir}:" in message
    assert str(linked_source.resolve()) in message
    assert manifest_path.read_text(encoding="utf-8") == original_manifest
    assert not (run_dir / "DATA_QUALITY_SUMMARY.txt").exists()
