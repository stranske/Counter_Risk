from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from counter_risk.web_demo import run_web_demo_pipeline

_BLOCKED_CHAT_RUNTIME = "counter_risk.chat.providers.langchain_runtime"


def _assert_no_absolute_paths(value: object) -> None:
    if isinstance(value, str):
        assert not Path(value).is_absolute()
    elif isinstance(value, list):
        for item in value:
            _assert_no_absolute_paths(item)
    elif isinstance(value, dict):
        for item in value.values():
            _assert_no_absolute_paths(item)


def test_web_demo_import_does_not_load_chat_runtime() -> None:
    # The runtime no-egress guard in run_web_demo_pipeline only catches the demo
    # newly importing the LangChain chat runtime; it deliberately tolerates a
    # module already imported by a sibling test sharing the pytest-xdist worker.
    # Assert the actual no-egress guarantee deterministically in a fresh
    # interpreter, where no sibling import can mask a regression in the demo's
    # own import graph.
    code = (
        "import sys\n"
        "import counter_risk.web_demo  # noqa: F401\n"
        "blocked = 'counter_risk.chat.providers.langchain_runtime'\n"
        "loaded = sorted(m for m in sys.modules if 'langchain' in m)\n"
        "assert blocked not in sys.modules, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert result.returncode == 0, result.stderr


def test_web_demo_artifact_uses_fixture_data_and_disables_chat(tmp_path: Path) -> None:
    assert _BLOCKED_CHAT_RUNTIME not in sys.modules
    run_dir = run_web_demo_pipeline(
        config_path=Path("config/fixture_replay.yml"),
        output_dir=tmp_path / "demo",
    )

    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "DATA_QUALITY_SUMMARY.txt"

    assert manifest_path.is_file()
    assert summary_path.is_file()
    assert os.environ["COUNTER_RISK_CHAT_OFFLINE_MODE"] == "1"
    assert _BLOCKED_CHAT_RUNTIME not in sys.modules

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data_zone"] == "synthetic-fixtures-only"
    assert manifest["chat_offline_mode"] == "1"
    assert manifest["data_quality_summary"] == "DATA_QUALITY_SUMMARY.txt"
    if "config_path" in manifest:
        assert not Path(manifest["config_path"]).is_absolute()
    _assert_no_absolute_paths(manifest["output_paths"])
    config_snapshot = manifest["config_snapshot"]
    fixture_keys = (
        "mosers_all_programs_xlsx",
        "mosers_ex_trend_xlsx",
        "mosers_trend_xlsx",
        "hist_all_programs_3yr_xlsx",
        "hist_ex_llc_3yr_xlsx",
        "hist_llc_3yr_xlsx",
        "monthly_pptx",
    )
    for key in fixture_keys:
        assert "tests/fixtures/" in str(config_snapshot[key]).replace("\\", "/")
        assert not Path(config_snapshot[key]).is_absolute()

    summary = summary_path.read_text(encoding="utf-8")
    assert "bundled tests/fixtures only" in summary
    assert "COUNTER_RISK_CHAT_OFFLINE_MODE=1" in summary
    assert "ChatOpenAI" not in summary
    assert "ChatAnthropic" not in summary


def test_web_demo_rejects_non_fixture_optional_inputs(tmp_path: Path) -> None:
    raw_config = yaml.safe_load(Path("config/fixture_replay.yml").read_text(encoding="utf-8"))
    assert isinstance(raw_config, dict)
    raw_config["cash_source_path"] = str(tmp_path / "real_cash_source.csv")
    config_path = tmp_path / "unsafe_demo.yml"
    config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")

    with pytest.raises(ValueError, match="cash_source_path.*tests/fixtures"):
        run_web_demo_pipeline(config_path=config_path, output_dir=tmp_path / "demo")
