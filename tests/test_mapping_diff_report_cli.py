"""Tests for mapping_diff_report CLI behavior."""

from __future__ import annotations

import csv
import os
import stat
import subprocess
import sys
from pathlib import Path

from counter_risk.cli import mapping_diff_report


def _cli_cmd() -> list[str]:
    return [sys.executable, "-m", "counter_risk.cli.mapping_diff_report"]


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path("src").resolve())
    env["PYTHONPATH"] = (
        src_path if "PYTHONPATH" not in env else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def _load_fixture_names(filename: str) -> list[str]:
    fixture_path = Path("tests/fixtures") / filename
    with fixture_path.open(newline="", encoding="utf-8") as fixture_file:
        reader = csv.DictReader(fixture_file)
        return [row["raw_name"] for row in reader]


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


def test_mapping_diff_report_with_repo_registry_exits_zero() -> None:
    result = subprocess.run(
        [*_cli_cmd(), "--registry", "config/name_registry.yml"],
        check=False,
        capture_output=True,
        text=True,
        env=_cli_env(),
    )
    assert result.returncode == 0
    assert "UNMAPPED" in result.stdout
    assert "FALLBACK_MAPPED" in result.stdout
    assert "SUGGESTIONS" in result.stdout


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
    # When running as root, chmod(0) doesn't prevent reads; the empty entries
    # list triggers a validation error instead of a permission error.
    assert result.stderr.strip()
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


def test_mapping_diff_report_with_fixture_inputs_contains_required_sections() -> None:
    fallback_names = _load_fixture_names("fallback_mapped_names.csv")
    unmapped_names = _load_fixture_names("unmapped_names.csv")

    args: list[str] = [*_cli_cmd(), "--registry", "config/name_registry.yml"]
    for name in fallback_names + unmapped_names:
        args.extend(["--normalization-name", name])
    for name in unmapped_names:
        args.extend(["--reconciliation-name", name])

    result = subprocess.run(args, check=False, capture_output=True, text=True, env=_cli_env())

    assert result.returncode == 0
    assert "UNMAPPED" in result.stdout
    assert "FALLBACK_MAPPED" in result.stdout
    assert "SUGGESTIONS" in result.stdout


def test_mapping_diff_report_forwards_registry_path_parameter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_call: dict[str, object] = {}

    def _fake_generate_mapping_diff_report(
        registry_path: Path,
        input_sources: dict[str, list[str]],
        *,
        output_format: str = "text",
    ) -> str:
        captured_call["registry_path"] = registry_path
        captured_call["input_sources"] = input_sources
        captured_call["output_format"] = output_format
        return "UNMAPPED\n\nFALLBACK_MAPPED\n\nSUGGESTIONS\n"

    monkeypatch.setattr(
        mapping_diff_report,
        "generate_mapping_diff_report",
        _fake_generate_mapping_diff_report,
    )
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text("schema_version: 1\nentries: []\n", encoding="utf-8")

    exit_code = mapping_diff_report.main(["--registry", str(registry_path)])

    assert exit_code == 0
    assert captured_call["registry_path"] == registry_path
    assert captured_call["input_sources"] == {"normalization": [], "reconciliation": []}
    assert captured_call["output_format"] == "text"


def test_mapping_diff_report_forwards_output_format_parameter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured_call: dict[str, object] = {}

    def _fake_generate_mapping_diff_report(
        registry_path: Path,
        input_sources: dict[str, list[str]],
        *,
        output_format: str = "text",
    ) -> str:
        captured_call["registry_path"] = registry_path
        captured_call["input_sources"] = input_sources
        captured_call["output_format"] = output_format
        return "UNMAPPED\n\nFALLBACK_MAPPED\n\nSUGGESTIONS\n"

    monkeypatch.setattr(
        mapping_diff_report,
        "generate_mapping_diff_report",
        _fake_generate_mapping_diff_report,
    )
    registry_path = tmp_path / "name_registry.yml"
    registry_path.write_text("schema_version: 1\nentries: []\n", encoding="utf-8")

    exit_code = mapping_diff_report.main(
        [
            "--registry",
            str(registry_path),
            "--output-format",
            "text",
            "--normalization-name",
            "Societe Generale",
        ]
    )

    assert exit_code == 0
    assert captured_call["registry_path"] == registry_path
    assert captured_call["input_sources"] == {
        "normalization": ["Societe Generale"],
        "reconciliation": [],
    }
    assert captured_call["output_format"] == "text"
