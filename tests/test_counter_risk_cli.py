"""Unit tests for counter_risk CLI helpers."""

from __future__ import annotations

from counter_risk import cli


def test_main_without_command_prints_help(capsys) -> None:
    result = cli.main([])
    captured = capsys.readouterr()

    assert result == 0
    assert "usage:" in captured.out.lower()


def test_main_run_command_returns_zero(capsys) -> None:
    result = cli.main(["run"])
    captured = capsys.readouterr()

    assert result == 0
    assert "not implemented yet" in captured.out.lower()
