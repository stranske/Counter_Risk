"""Integration tests for the Windows runner command shim."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from counter_risk.build import release

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="Windows-only integration test for run_counter_risk.cmd",
)


def _create_source_bundle(tmp_path: Path) -> Path:
    source_bundle = tmp_path / "source-bundle"
    source_bundle.mkdir(parents=True, exist_ok=True)
    release._create_runner_file(source_bundle)

    # We provide a command-script executable stand-in so the runner's
    # extensionless fallback path can execute in Windows shell environments.
    fake_executable = source_bundle / "bin" / "counter-risk.cmd"
    fake_executable.parent.mkdir(parents=True, exist_ok=True)
    fake_executable.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal",
                'set "OUTPUT_FILE=%~dp0..\\captured-runner-output.txt"',
                '> "%OUTPUT_FILE%" (',
                "  echo EXE_SELF=%~f0",
                "  echo CWD=%CD%",
                "  echo ARG1=%~1",
                "  echo ARG2=%~2",
                "  echo ARG3=%~3",
                "  echo RAW_ARGS=%*",
                ")",
                "exit /b 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return source_bundle


def _parse_capture_file(capture_file: Path) -> dict[str, str]:
    lines = capture_file.read_text(encoding="utf-8").splitlines()
    parsed: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def test_windows_runner_cmd_uses_relative_executable_and_forwards_cli_args(tmp_path: Path) -> None:
    source_bundle = _create_source_bundle(tmp_path)
    isolated_bundle = tmp_path / "isolated-bundle"
    isolated_bundle.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_bundle / "run_counter_risk.cmd", isolated_bundle / "run_counter_risk.cmd")
    shutil.copytree(source_bundle / "bin", isolated_bundle / "bin")

    run_result = subprocess.run(
        [str(isolated_bundle / "run_counter_risk.cmd"), "--flag", "value", "tail-arg"],
        cwd=isolated_bundle,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run_result.returncode == 0, run_result.stderr

    capture_file = isolated_bundle / "captured-runner-output.txt"
    assert capture_file.is_file()
    captured = _parse_capture_file(capture_file)

    exe_self = Path(captured["EXE_SELF"]).resolve()
    assert exe_self == (isolated_bundle / "bin" / "counter-risk.cmd").resolve()

    cwd = Path(captured["CWD"]).resolve()
    assert cwd == isolated_bundle.resolve()

    assert captured["ARG1"] == "--flag"
    assert captured["ARG2"] == "value"
    assert captured["ARG3"] == "tail-arg"
    assert captured["RAW_ARGS"] == "--flag value tail-arg"


def test_windows_runner_cmd_does_not_call_python_entrypoints(tmp_path: Path) -> None:
    source_bundle = _create_source_bundle(tmp_path)
    runner_contents = (source_bundle / "run_counter_risk.cmd").read_text(encoding="utf-8")
    assert "%*" in runner_contents

    forbidden_pattern = re.compile(r"\bpython(?:\.exe)?\b|\bpy(?:\.exe)?\b|\.py\b", re.IGNORECASE)
    assert forbidden_pattern.search(runner_contents) is None
