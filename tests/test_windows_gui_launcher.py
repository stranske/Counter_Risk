from __future__ import annotations

from pathlib import Path

import yaml


def test_double_click_gui_launcher_exists_and_keeps_errors_visible() -> None:
    launcher = Path(__file__).resolve().parent.parent / "run_counter_risk_gui.cmd"

    text = launcher.read_text(encoding="utf-8")
    raw = launcher.read_bytes()

    assert 'counter-risk.exe" gui' in text
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
    assert text.index(r"src\counter_risk\cli\__init__.py") < text.index(
        r".venv\Scripts\counter-risk.exe"
    )
    assert '1>>"%COUNTER_RISK_LAUNCHER_LOG%" 2>&1' in text
    assert b"\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_assembled_bin_executable_precedes_development_and_global_fallbacks() -> None:
    launcher = Path(__file__).resolve().parent.parent / "run_counter_risk_gui.cmd"
    text = launcher.read_text(encoding="utf-8")
    branch = 'if exist "%~dp0bin\\counter-risk.exe" ('
    start = text.index(branch)
    block = text[start : text.index("\n)", start)]
    assert 'call :run_and_log "%~dp0bin\\counter-risk.exe" gui' in block
    assert "goto :after_run" in block
    for fallback in (
        r"dist\counter-risk\counter-risk.exe",
        'if exist "%~dp0counter-risk.exe"',
        r"src\counter_risk\cli\__init__.py",
        r".venv\Scripts\counter-risk.exe",
        "where counter-risk",
    ):
        assert start < text.index(fallback)


def test_release_build_waits_for_native_gui_launcher_smoke() -> None:
    root = Path(__file__).resolve().parent.parent
    workflow = yaml.safe_load((root / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert jobs["build-windows"]["needs"] == "gui-launcher-smoke"
    smoke = jobs["gui-launcher-smoke"]
    assert smoke["runs-on"] == "windows-latest"
    command = next(
        step
        for step in smoke["steps"]
        if "scripts/windows/smoke_gui_launcher.ps1" in step.get("run", "")
    )
    assert command["shell"] == "pwsh"
    assert not command.get("continue-on-error", False)
    assert not smoke.get("continue-on-error", False)
    upload = next(step for step in smoke["steps"] if "upload-artifact" in step.get("uses", ""))
    assert upload["if"] == "always()"
    assert "gui-launcher-evidence" in upload["with"]["path"]
