from __future__ import annotations

from pathlib import Path


def test_double_click_gui_launcher_exists_and_keeps_errors_visible() -> None:
    launcher = Path(__file__).resolve().parent.parent / "run_counter_risk_gui.cmd"

    text = launcher.read_text(encoding="utf-8")
    raw = launcher.read_bytes()

    assert "counter-risk.exe\" gui" in text
    assert "counter-risk gui" in text
    assert "counter-risk-gui-launcher.log" in text
    assert "py -3.12 -m counter_risk.cli gui" in text
    assert "py -m counter_risk.cli gui" in text
    assert "python -m counter_risk.cli gui" in text
    assert "PYTHONPATH=%~dp0src;%PYTHONPATH%" in text
    assert "pause" in text.lower()
    assert "copy the messages above" in text
    assert "COUNTER_RISK_NO_PAUSE" in text
    assert "stale venv or global install" in text
    assert text.index(r'src\counter_risk\cli\__init__.py') < text.index(
        r'.venv\Scripts\counter-risk.exe'
    )
    assert '1>>"%COUNTER_RISK_LAUNCHER_LOG%" 2>&1' in text
    assert b"\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")
