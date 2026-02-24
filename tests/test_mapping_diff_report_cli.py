"""Tests for mapping_diff_report CLI behavior."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def _cli_cmd() -> list[str]:
    return [sys.executable, "-m", "counter_risk.cli.mapping_diff_report"]


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path("src").resolve())
    env["PYTHONPATH"] = (
        src_path if "PYTHONPATH" not in env else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def test_mapping_diff_report_help_exits_zero() -> None:
    result = subprocess.run(
        [*_cli_cmd(), "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_cli_env(),
    )
    assert result.returncode == 0
    assert "mapping_diff_report" in result.stdout


def test_mapping_diff_report_missing_registry_exits_nonzero(tmp_path: Path) -> None:
    missing_registry = tmp_path / "missing_registry.yml"
    result = subprocess.run(
        [*_cli_cmd(), "--registry", str(missing_registry)],
        check=False,
        capture_output=True,
        text=True,
        env=_cli_env(),
    )
    assert result.returncode != 0
    assert str(missing_registry) in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1


def test_mapping_diff_report_default_registry_missing_mentions_config_path(tmp_path: Path) -> None:
    result = subprocess.run(
        _cli_cmd(),
        check=False,
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "config/name_registry.yml" in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1


def test_mapping_diff_report_unreadable_registry_exits_nonzero(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text("schema_version: 1\nentries: []\n", encoding="utf-8")
    registry_path.chmod(0)
    try:
        result = subprocess.run(
            [*_cli_cmd(), "--registry", str(registry_path)],
            check=False,
            capture_output=True,
            text=True,
            env=_cli_env(),
        )
    finally:
        registry_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert result.returncode != 0
    assert str(registry_path) in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1


def test_mapping_diff_report_deterministic_sections(tmp_path: Path) -> None:
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "entries:",
                "  - canonical_key: bank_of_america",
                "    display_name: Bank of America",
                "    aliases:",
                "      - Bank of America",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = [
        *_cli_cmd(),
        "--registry",
        str(registry_path),
        "--normalization-name",
        "Societe Generale",
        "--normalization-name",
        "Unknown House",
        "--reconciliation-name",
        "Unknown House",
    ]
    first = subprocess.run(args, check=False, capture_output=True, text=True, env=_cli_env())
    second = subprocess.run(args, check=False, capture_output=True, text=True, env=_cli_env())

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout
    assert "UNMAPPED\nUnknown House\n" in first.stdout
    assert "FALLBACK_MAPPED\nSociete Generale -> Soc Gen\n" in first.stdout
    assert "SUGGESTIONS\nUnknown House -> Unknown House\n" in first.stdout
