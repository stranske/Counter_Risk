"""Runtime tweaks applied automatically when Python starts in this repo."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _is_pytest_invocation(argv: list[str]) -> bool:
    if not argv:
        return False
    stem = Path(argv[0]).stem
    return stem == "pytest" or stem == "py.test"


def _strip_pytest_xdist_args(argv: list[str]) -> list[str]:
    stripped: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-n":
            i += 2
            continue
        if arg.startswith("-n") and arg != "-n":
            i += 1
            continue
        if arg == "--dist":
            i += 2
            continue
        if arg.startswith("--dist="):
            i += 1
            continue
        stripped.append(arg)
        i += 1
    return stripped


def _xdist_is_available() -> bool:
    return importlib.util.find_spec("xdist") is not None


def _disable_xdist_cli_flags_for_pytest() -> None:
    if not _is_pytest_invocation(sys.argv):
        return
    if os.environ.get("COUNTER_RISK_KEEP_XDIST_ARGS") == "1":
        return
    if _xdist_is_available() and os.environ.get("COUNTER_RISK_STRIP_XDIST_ARGS") != "1":
        return

    sys.argv[:] = _strip_pytest_xdist_args(sys.argv)


_disable_xdist_cli_flags_for_pytest()
