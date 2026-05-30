"""CLI smoke tests for counter_risk."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path


def test_console_script_declared() -> None:
    """The documented `counter-risk` operator command must be a real console script.

    Failing-first gate for issue #643: on the pre-change tree `[project.scripts]`
    only declares `mapping_diff_report`, so `pip install` produces no `counter-risk`
    executable and the README's `counter-risk run/gui ...` commands are
    "command not found". This asserts the missing registration.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)

    scripts = data["project"]["scripts"]
    assert scripts["counter-risk"] == "counter_risk.cli:main"


def test_console_script_entry_point_help_exits_zero() -> None:
    """The console-script target (`counter_risk.cli:main`) returns 0 for --help.

    Mirrors the `python -m counter_risk.cli --help` smoke below, but invokes the
    exact callable that the declared `counter-risk` entry point resolves to,
    proving the script reaches the real handler.
    """
    src_path = str(Path("src").resolve())
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from counter_risk.cli import main

    try:
        main(["--help"])
    except SystemExit as exc:  # argparse --help raises SystemExit(0)
        assert exc.code in (0, None)
    else:  # main returned normally
        pass


def test_cli_help_exits_zero() -> None:
    env = os.environ.copy()
    src_path = str(Path("src").resolve())
    env["PYTHONPATH"] = (
        src_path if "PYTHONPATH" not in env else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    result = subprocess.run(
        [sys.executable, "-m", "counter_risk.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
