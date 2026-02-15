from __future__ import annotations

import sitecustomize


def test_strip_pytest_xdist_args_removes_parallel_flags() -> None:
    argv = [
        "pytest",
        "-q",
        "-n",
        "auto",
        "--dist=loadgroup",
        "tests/test_imports.py",
    ]

    stripped = sitecustomize._strip_pytest_xdist_args(argv)

    assert stripped == ["pytest", "-q", "tests/test_imports.py"]


def test_strip_pytest_xdist_args_keeps_other_args() -> None:
    argv = ["pytest", "-q", "--maxfail=1", "tests"]

    stripped = sitecustomize._strip_pytest_xdist_args(argv)

    assert stripped == argv
