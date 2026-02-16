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


def test_disable_xdist_cli_flags_for_pytest_keeps_when_xdist_available(monkeypatch) -> None:
    argv = ["pytest", "-q", "-n", "auto", "--dist", "loadscope"]
    monkeypatch.setattr(sitecustomize, "sys", type("_Sys", (), {"argv": argv})())
    monkeypatch.setattr(sitecustomize, "_xdist_is_available", lambda: True)
    monkeypatch.delenv("COUNTER_RISK_KEEP_XDIST_ARGS", raising=False)
    monkeypatch.delenv("COUNTER_RISK_STRIP_XDIST_ARGS", raising=False)

    sitecustomize._disable_xdist_cli_flags_for_pytest()
    assert sitecustomize.sys.argv == argv


def test_disable_xdist_cli_flags_for_pytest_strips_when_xdist_missing(monkeypatch) -> None:
    argv = ["pytest", "-q", "-n", "auto", "--dist", "loadscope"]
    monkeypatch.setattr(sitecustomize, "sys", type("_Sys", (), {"argv": argv})())
    monkeypatch.setattr(sitecustomize, "_xdist_is_available", lambda: False)
    monkeypatch.delenv("COUNTER_RISK_KEEP_XDIST_ARGS", raising=False)
    monkeypatch.delenv("COUNTER_RISK_STRIP_XDIST_ARGS", raising=False)

    sitecustomize._disable_xdist_cli_flags_for_pytest()
    assert sitecustomize.sys.argv == ["pytest", "-q"]


def test_disable_xdist_cli_flags_for_pytest_strips_when_env_set(monkeypatch) -> None:
    argv = ["pytest", "-q", "-n", "auto", "--dist", "loadscope"]
    monkeypatch.setattr(sitecustomize, "sys", type("_Sys", (), {"argv": argv})())
    monkeypatch.setattr(sitecustomize, "_xdist_is_available", lambda: True)
    monkeypatch.setenv("COUNTER_RISK_STRIP_XDIST_ARGS", "1")

    sitecustomize._disable_xdist_cli_flags_for_pytest()
    assert sitecustomize.sys.argv == ["pytest", "-q"]


def test_disable_xdist_cli_flags_for_pytest_keeps_when_keep_env_set(monkeypatch) -> None:
    argv = ["pytest", "-q", "-n", "auto", "--dist", "loadscope"]
    monkeypatch.setattr(sitecustomize, "sys", type("_Sys", (), {"argv": argv})())
    monkeypatch.setattr(sitecustomize, "_xdist_is_available", lambda: False)
    monkeypatch.setenv("COUNTER_RISK_KEEP_XDIST_ARGS", "1")
    monkeypatch.delenv("COUNTER_RISK_STRIP_XDIST_ARGS", raising=False)

    sitecustomize._disable_xdist_cli_flags_for_pytest()
    assert sitecustomize.sys.argv == argv
