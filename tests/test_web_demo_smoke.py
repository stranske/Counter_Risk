from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from counter_risk.web_demo import run_web_demo_pipeline


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
    )
    assert result.returncode == 0, result.stderr


def test_web_demo_artifact_uses_fixture_data_and_disables_chat(tmp_path: Path) -> None:
    run_dir = run_web_demo_pipeline(
        config_path=Path("config/fixture_replay.yml"),
        output_dir=tmp_path / "demo",
    )

    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "DATA_QUALITY_SUMMARY.txt"

    assert manifest_path.is_file()
    assert summary_path.is_file()
    assert os.environ["COUNTER_RISK_CHAT_OFFLINE_MODE"] == "1"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data_zone"] == "synthetic-fixtures-only"
    assert manifest["chat_offline_mode"] == "1"
    assert manifest["data_quality_summary"] == "DATA_QUALITY_SUMMARY.txt"
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

    summary = summary_path.read_text(encoding="utf-8")
    assert "bundled tests/fixtures only" in summary
    assert "COUNTER_RISK_CHAT_OFFLINE_MODE=1" in summary
    assert "ChatOpenAI" not in summary
    assert "ChatAnthropic" not in summary
