"""Compatibility checks for drop-in template tests when openpyxl is unavailable."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_dropin_template_pytest_run_skips_cleanly_without_openpyxl(tmp_path: Path) -> None:
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        "\n".join(
            [
                "import builtins",
                "import sys",
                "_original_import = builtins.__import__",
                "def _block_openpyxl(name, globals_=None, locals_=None, fromlist=(), level=0):",
                "    if name == 'openpyxl' and 'openpyxl' not in sys.modules:",
                "        raise ModuleNotFoundError(\"No module named 'openpyxl'\")",
                "    return _original_import(name, globals_, locals_, fromlist, level)",
                "builtins.__import__ = _block_openpyxl",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    extra_path = str(tmp_path)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{extra_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else extra_path
    )

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-k",
        "dropin_template and not openpyxl_absence",
        "-q",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, (
        "Expected `pytest -k dropin_template -q` to exit 0 when openpyxl is unavailable. "
        f"Return code: {result.returncode}. Output:\n{combined_output}"
    )
    assert "FAILED" not in combined_output, (
        "Expected zero FAILED tests for `pytest -k dropin_template -q` when openpyxl is unavailable. "
        f"Output:\n{combined_output}"
    )

    reason_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-k",
            "dropin_template and not openpyxl_absence",
            "-q",
            "-rs",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
    )

    reason_output = f"{reason_result.stdout}\n{reason_result.stderr}"
    assert reason_result.returncode == 0, (
        "Expected `pytest -k dropin_template -q -rs` to exit 0 when openpyxl is unavailable. "
        f"Return code: {reason_result.returncode}. Output:\n{reason_output}"
    )
    assert "SKIPPED" in reason_output and "openpyxl" in reason_output, (
        "Expected at least one skipped drop-in template test with a reason mentioning openpyxl. "
        f"Output:\n{reason_output}"
    )
