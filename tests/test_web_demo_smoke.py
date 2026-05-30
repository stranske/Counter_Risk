from __future__ import annotations

import json
import os
from pathlib import Path

from counter_risk.demo_artifact import build_demo_artifact


def test_web_demo_artifact_uses_fixture_data_and_disables_chat(tmp_path: Path) -> None:
    run_dir = build_demo_artifact(
        config_path=Path("config/fixture_replay.yml"),
        output_dir=tmp_path / "demo",
    )

    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "DATA_QUALITY_SUMMARY.txt"

    assert manifest_path.is_file()
    assert summary_path.is_file()
    assert os.environ["COUNTER_RISK_CHAT_OFFLINE_MODE"] == "1"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["mode"] == "fixture_replay"
    assert manifest["data_zone"] == "synthetic-fixtures-only"
    assert manifest["chat_offline_mode"] == "1"
    assert manifest["data_quality_summary"] == "DATA_QUALITY_SUMMARY.txt"

    outputs = manifest["outputs"]
    assert outputs
    for output_path in outputs.values():
        assert Path(output_path).resolve().parent == run_dir.resolve()

    summary = summary_path.read_text(encoding="utf-8")
    assert "bundled tests/fixtures only" in summary
    assert "COUNTER_RISK_CHAT_OFFLINE_MODE=1" in summary
    assert "ChatOpenAI" not in summary
    assert "ChatAnthropic" not in summary
