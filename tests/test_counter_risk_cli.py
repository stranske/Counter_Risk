"""Unit tests for counter_risk CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from counter_risk import cli


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.main([])
    captured = capsys.readouterr()

    assert result == 0
    assert "usage:" in captured.out.lower()


def test_main_run_command_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "workflow.yml"
    config_path.write_text(
        "\n".join(
            [
                "hist_all_programs_3yr_xlsx: placeholder-all.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder-ex.xlsx",
                "hist_llc_3yr_xlsx: placeholder-trend.xlsx",
                "monthly_pptx: placeholder.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = tmp_path / "run-output"

    def fake_run_pipeline_with_config(
        config, *, config_dir, output_dir=None, formatting_profile=None
    ):
        _ = (config, config_dir, output_dir, formatting_profile)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(cli, "run_pipeline_with_config", fake_run_pipeline_with_config)

    result = cli.main(["run", "--config", str(config_path), "--as-of-date", "2025-12-31"])
    captured = capsys.readouterr()

    assert result == 0
    assert "counter risk run completed" in captured.out.lower()


def test_run_parser_accepts_export_pdf_flags() -> None:
    parser = cli.build_parser()

    args_true = parser.parse_args(["run", "--export-pdf"])
    assert args_true.export_pdf is True

    args_false = parser.parse_args(["run", "--no-export-pdf"])
    assert args_false.export_pdf is False


def test_run_parser_accepts_dry_run_discovery_and_as_of_month() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["run", "--dry-run-discovery", "--as-of-month", "2025-12-31"])
    assert args.dry_run_discovery is True
    assert args.as_of_date == "2025-12-31"


def test_main_run_dry_run_discovery_lists_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monthly_root = tmp_path / "monthly"
    historical_root = tmp_path / "historical"
    template_root = tmp_path / "templates"
    for root in (monthly_root, historical_root, template_root):
        root.mkdir(parents=True)

    (monthly_root / "NISA Monthly All Programs - Raw.xlsx").write_text("x", encoding="utf-8")
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "Daily Holdings 2025-12-31.pdf").write_text("x", encoding="utf-8")
    (historical_root / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (template_root / "Monthly Counterparty Exposure Report.pptx").write_text("x", encoding="utf-8")

    config_path = tmp_path / "dry_run_discovery.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: tests/fixtures/Monthly Counterparty Exposure Report.pptx",
                "input_discovery:",
                "  directory_roots:",
                f"    monthly_inputs: {monthly_root}",
                f"    historical_inputs: {historical_root}",
                f"    template_inputs: {template_root}",
                "  naming_patterns:",
                "    raw_nisa_all_programs_xlsx:",
                "      - NISA Monthly All Programs - Raw.xlsx",
                "    mosers_all_programs_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx",
                "    mosers_ex_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Ex Trend.xlsx",
                "    mosers_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Trend.xlsx",
                "    daily_holdings_pdf:",
                "      - Daily Holdings {as_of_date}.pdf",
                "    hist_all_programs_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "    hist_ex_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "    hist_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "    monthly_pptx:",
                "      - Monthly Counterparty Exposure Report*.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "run",
            "--dry-run-discovery",
            "--config",
            str(config_path),
            "--as-of-month",
            "2025-12-31",
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "Discovery dry-run for as-of date 2025-12-31" in captured.out
    assert "- monthly_pptx: 1 match(es)" in captured.out
    assert "Monthly Counterparty Exposure Report.pptx" in captured.out
    assert "- raw_nisa_all_programs_xlsx: 1 match(es)" in captured.out
    assert "NISA Monthly All Programs - Raw.xlsx" in captured.out


def test_main_run_dry_run_discovery_applies_runner_settings_input_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "dry_run_discovery_settings.yml"
    config_path.write_text(
        "\n".join(
            [
                "hist_all_programs_3yr_xlsx: placeholder-all.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder-ex.xlsx",
                "hist_llc_3yr_xlsx: placeholder-trend.xlsx",
                "monthly_pptx: placeholder.pptx",
                "input_discovery:",
                "  directory_roots:",
                "    monthly_inputs: monthly",
                "    historical_inputs: historical",
                "    template_inputs: templates",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings_path = tmp_path / "runner-settings.json"
    settings_path.write_text(
        json.dumps({"input_root": str(tmp_path / "shared-inputs")}),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_format_discovery_dry_run(*, config, as_of_date):
        captured["as_of_date"] = as_of_date.isoformat()
        captured["roots"] = dict(config.input_discovery.directory_roots)
        return "ok"

    monkeypatch.setattr(cli, "_format_discovery_dry_run", fake_format_discovery_dry_run)

    result = cli.main(
        [
            "run",
            "--dry-run-discovery",
            "--config",
            str(config_path),
            "--as-of-month",
            "2025-12-31",
            "--settings",
            str(settings_path),
        ]
    )

    assert result == 0
    assert captured["as_of_date"] == "2025-12-31"
    assert captured["roots"] == {
        "historical_inputs": Path(str(tmp_path / "shared-inputs")),
        "monthly_inputs": Path(str(tmp_path / "shared-inputs")),
        "template_inputs": Path(str(tmp_path / "shared-inputs")),
    }


def test_main_run_dry_run_discovery_requires_as_of_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "dry_run_discovery_missing_as_of.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: tests/fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: tests/fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: tests/fixtures/Monthly Counterparty Exposure Report.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.main(["run", "--dry-run-discovery", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert result == 2
    assert "requires an as-of date" in captured.out


def test_main_run_fixture_replay_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_names = [
        "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
        "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
        "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
        "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
        "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
        "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
        "Monthly Counterparty Exposure Report.pptx",
    ]
    for name in fixture_names:
        (fixtures_dir / name).write_text(name, encoding="utf-8")

    config_path = tmp_path / "fixture_replay.yml"
    config_path.write_text(
        "\n".join(
            [
                "as_of_date: 2025-12-31",
                "mosers_all_programs_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx",
                "mosers_ex_trend_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx",
                "mosers_trend_xlsx: fixtures/MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx",
                "hist_all_programs_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "hist_ex_llc_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "hist_llc_3yr_xlsx: fixtures/Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "monthly_pptx: fixtures/Monthly Counterparty Exposure Report.pptx",
                "output_root: run-output",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "run-output"
    result = cli.main(
        [
            "run",
            "--fixture-replay",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "fixture replay completed" in captured.out.lower()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "fixture_replay"


def test_main_run_discover_mode_auto_selects_and_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--discover with single-match inputs auto-selects and runs the pipeline."""

    monthly_root = tmp_path / "monthly"
    historical_root = tmp_path / "historical"
    template_root = tmp_path / "templates"
    for root in (monthly_root, historical_root, template_root):
        root.mkdir(parents=True)

    # Create exactly one file per discoverable input
    (monthly_root / "NISA Monthly All Programs - Raw.xlsx").write_text("x", encoding="utf-8")
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - All Programs.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Ex Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "MOSERS Counterparty Risk Summary 12-31-2025 - Trend.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (monthly_root / "Daily Holdings 2025-12-31.pdf").write_text("x", encoding="utf-8")
    (historical_root / "Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (historical_root / "Historical Counterparty Risk Graphs - LLC 3 Year.xlsx").write_text(
        "x", encoding="utf-8"
    )
    (template_root / "Monthly Counterparty Exposure Report.pptx").write_text("x", encoding="utf-8")

    config_path = tmp_path / "discover_run.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: placeholder.xlsx",
                "mosers_trend_xlsx: placeholder.xlsx",
                "hist_all_programs_3yr_xlsx: placeholder.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder.xlsx",
                "hist_llc_3yr_xlsx: placeholder.xlsx",
                "monthly_pptx: placeholder.pptx",
                "output_root: run-output",
                "input_discovery:",
                "  directory_roots:",
                f"    monthly_inputs: {monthly_root}",
                f"    historical_inputs: {historical_root}",
                f"    template_inputs: {template_root}",
                "  naming_patterns:",
                "    raw_nisa_all_programs_xlsx:",
                "      - NISA Monthly All Programs - Raw.xlsx",
                "    mosers_all_programs_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - All Programs.xlsx",
                "    mosers_ex_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Ex Trend.xlsx",
                "    mosers_trend_xlsx:",
                "      - MOSERS Counterparty Risk Summary {as_of_date:%m-%d-%Y} - Trend.xlsx",
                "    daily_holdings_pdf:",
                "      - Daily Holdings {as_of_date}.pdf",
                "    hist_all_programs_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - All Programs 3 Year.xlsx",
                "    hist_ex_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - ex LLC 3 Year.xlsx",
                "    hist_llc_3yr_xlsx:",
                "      - Historical Counterparty Risk Graphs - LLC 3 Year.xlsx",
                "    monthly_pptx:",
                "      - Monthly Counterparty Exposure Report*.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "run-output"
    run_dir = output_dir.resolve()

    def fake_run_pipeline_with_config(
        config, *, config_dir, output_dir=None, formatting_profile=None
    ):
        _ = (config_dir, formatting_profile)
        output = run_dir if output_dir is None else Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        manifest = {
            "mode": "discovery",
            "as_of_date": None if config.as_of_date is None else config.as_of_date.isoformat(),
            "outputs": {
                "mosers_ex_trend_xlsx": str(config.mosers_ex_trend_xlsx),
                "monthly_pptx": str(config.monthly_pptx),
            },
        }
        (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return output

    monkeypatch.setattr(cli, "run_pipeline_with_config", fake_run_pipeline_with_config)

    result = cli.main(
        [
            "run",
            "--discover",
            "--config",
            str(config_path),
            "--as-of-date",
            "2025-12-31",
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "discovery run completed" in captured.out.lower()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "discovery"
    assert manifest["as_of_date"] == "2025-12-31"
    # Discovered files should have been copied to the output directory
    assert any("Ex Trend" in v for v in manifest["outputs"].values())


def test_main_run_discover_mode_requires_as_of_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "discover_no_date.yml"
    config_path.write_text(
        "\n".join(
            [
                "mosers_ex_trend_xlsx: placeholder.xlsx",
                "mosers_trend_xlsx: placeholder.xlsx",
                "hist_all_programs_3yr_xlsx: placeholder.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder.xlsx",
                "hist_llc_3yr_xlsx: placeholder.xlsx",
                "monthly_pptx: placeholder.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.main(["run", "--discover", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert result == 2
    assert "requires an as-of date" in captured.out


def test_run_parser_accepts_discover_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["run", "--discover", "--as-of-month", "2025-12-31"])
    assert args.discover is True
    assert args.as_of_date == "2025-12-31"


def test_run_parser_accepts_settings_path(tmp_path: Path) -> None:
    parser = cli.build_parser()

    settings_path = tmp_path / "runner-settings.json"
    args = parser.parse_args(["run", "--settings", str(settings_path)])

    assert args.settings == settings_path


def test_main_run_applies_runner_settings_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "workflow.yml"
    config_path.write_text(
        "\n".join(
            [
                "hist_all_programs_3yr_xlsx: placeholder-all.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder-ex.xlsx",
                "hist_llc_3yr_xlsx: placeholder-trend.xlsx",
                "monthly_pptx: placeholder.pptx",
                "input_discovery:",
                "  directory_roots:",
                "    monthly_inputs: monthly",
                "    historical_inputs: historical",
                "    template_inputs: templates",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings_path = tmp_path / "runner-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "strict_policy": "strict",
                "formatting_profile": "accounting",
                "input_root": str(tmp_path / "shared-inputs"),
                "output_root": str(tmp_path / "shared-runs"),
            }
        ),
        encoding="utf-8",
    )

    captured_config: dict[str, object] = {}

    def fake_run_pipeline_with_config(
        config, *, config_dir, output_dir=None, formatting_profile=None
    ):
        captured_config["fail_policy"] = config.reconciliation.fail_policy
        captured_config["output_root"] = config.output_root
        captured_config["discovery_roots"] = dict(config.input_discovery.directory_roots)
        captured_config["config_dir"] = config_dir
        captured_config["output_dir"] = output_dir
        captured_config["formatting_profile"] = formatting_profile
        run_dir = tmp_path / "run-output"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(cli, "run_pipeline_with_config", fake_run_pipeline_with_config)

    result = cli.main(
        [
            "run",
            "--config",
            str(config_path),
            "--as-of-date",
            "2025-12-31",
            "--settings",
            str(settings_path),
        ]
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "selected profile: accounting" in captured.out
    assert captured_config["fail_policy"] == "strict"
    assert captured_config["output_root"] == Path(str(tmp_path / "shared-runs"))
    assert captured_config["discovery_roots"] == {
        "historical_inputs": Path(str(tmp_path / "shared-inputs")),
        "monthly_inputs": Path(str(tmp_path / "shared-inputs")),
        "template_inputs": Path(str(tmp_path / "shared-inputs")),
    }
    assert captured_config["output_dir"] is None
    assert captured_config["formatting_profile"] == "accounting"


def test_main_run_uses_discovery_mode_from_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "workflow.yml"
    config_path.write_text(
        "\n".join(
            [
                "hist_all_programs_3yr_xlsx: placeholder-all.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder-ex.xlsx",
                "hist_llc_3yr_xlsx: placeholder-trend.xlsx",
                "monthly_pptx: placeholder.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings_path = tmp_path / "runner-settings.json"
    settings_path.write_text(json.dumps({"discovery_mode": "discover"}), encoding="utf-8")

    calls: dict[str, int] = {"discover": 0, "workflow": 0}

    def fake_run_with_discovery(_args: object) -> int:
        calls["discover"] += 1
        return 0

    def fake_run_workflow_mode(_args: object) -> int:
        calls["workflow"] += 1
        return 0

    monkeypatch.setattr(cli, "_run_with_discovery", fake_run_with_discovery)
    monkeypatch.setattr(cli, "_run_workflow_mode", fake_run_workflow_mode)

    result = cli.main(
        [
            "run",
            "--config",
            str(config_path),
            "--as-of-date",
            "2025-12-31",
            "--settings",
            str(settings_path),
        ]
    )

    assert result == 0
    assert calls["discover"] == 1
    assert calls["workflow"] == 0


def test_main_run_rejects_invalid_settings_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "workflow.yml"
    config_path.write_text(
        "\n".join(
            [
                "hist_all_programs_3yr_xlsx: placeholder-all.xlsx",
                "hist_ex_llc_3yr_xlsx: placeholder-ex.xlsx",
                "hist_llc_3yr_xlsx: placeholder-trend.xlsx",
                "monthly_pptx: placeholder.pptx",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings_path = tmp_path / "runner-settings.json"
    settings_path.write_text("{not-valid-json", encoding="utf-8")

    result = cli.main(["run", "--config", str(config_path), "--settings", str(settings_path)])
    captured = capsys.readouterr()

    assert result == 2
    assert "runner settings error" in captured.out.lower()
