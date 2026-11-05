"""Demo configuration and command-line behavior without replaying large fixtures."""

from pathlib import Path

import pytest
import yaml

from counter_risk import demo_artifact


def test_demo_config_rejects_a_sequence(tmp_path: Path) -> None:
    config = tmp_path / "demo.yml"
    config.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Demo config must be a mapping"):
        demo_artifact._materialize_source_checkout_config(
            config_path=config, output_dir=tmp_path / "output"
        )


def test_local_demo_config_preserves_existing_paths_and_non_string_values(tmp_path: Path) -> None:
    source = tmp_path / "local.xlsx"
    source.touch()
    config = tmp_path / "demo.yml"
    content = yaml.safe_dump({"monthly_pptx": 17, "mosers_all_programs_xlsx": source.name})
    config.write_text(content, encoding="utf-8")
    assert (
        demo_artifact._materialize_source_checkout_config(
            config_path=config, output_dir=tmp_path / "output"
        )
        == config
    )
    assert config.read_text(encoding="utf-8") == content
    assert not (tmp_path / "demo_fixture_replay.yml").exists()


def test_demo_path_falls_back_to_config_parent(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    source = tmp_path / "parent-source.xlsx"
    source.touch()
    assert demo_artifact._resolve_config_path(Path(source.name), config_dir=config_dir) == source


@pytest.mark.parametrize("explicit", [False, True])
def test_demo_main_passes_cli_paths_to_builder_and_reports_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    explicit: bool,
) -> None:
    calls = []
    result = tmp_path / "completed"

    def build(**kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr(demo_artifact, "build_demo_artifact", build)
    args = ["--config", "custom.yml", "--output-dir", "custom-output"] if explicit else []
    assert demo_artifact.main(args) == 0
    assert calls == [
        {
            "config_path": Path("custom.yml" if explicit else "config/fixture_replay.yml"),
            "output_dir": Path("custom-output" if explicit else "runs/demo"),
        }
    ]
    assert capsys.readouterr().out == f"Demo artifact written to {result}\n"
