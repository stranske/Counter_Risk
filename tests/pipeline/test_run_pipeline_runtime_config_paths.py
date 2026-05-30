from pathlib import Path

import yaml

from counter_risk.config import WorkflowConfig
from counter_risk.pipeline import run as run_module


def test_run_pipeline_with_config_serializes_relative_paths_as_absolute(
    monkeypatch, tmp_path: Path
) -> None:
    config_dir = tmp_path / "repo-root"
    config_dir.mkdir()
    output_dir = tmp_path / "run-output"

    config = WorkflowConfig(
        as_of_date="2025-12-31",
        mosers_all_programs_xlsx=Path("tests/fixtures/all.xlsx"),
        mosers_ex_trend_xlsx=Path("tests/fixtures/ex.xlsx"),
        mosers_trend_xlsx=Path("tests/fixtures/trend.xlsx"),
        hist_all_programs_3yr_xlsx=Path("tests/fixtures/hist_all.xlsx"),
        hist_ex_llc_3yr_xlsx=Path("tests/fixtures/hist_ex.xlsx"),
        hist_llc_3yr_xlsx=Path("tests/fixtures/hist_llc.xlsx"),
        monthly_pptx=Path("tests/fixtures/monthly.pptx"),
        output_root=Path("runs"),
    )

    def _fake_run_pipeline(
        config_path: str | Path,
        *,
        output_dir: Path | None = None,
        formatting_profile: str | None = None,
    ) -> Path:
        del formatting_profile
        assert output_dir is not None
        serialized = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        assert serialized["mosers_all_programs_xlsx"] == str(
            (config_dir / "tests/fixtures/all.xlsx").resolve()
        )
        assert serialized["monthly_pptx"] == str(
            (config_dir / "tests/fixtures/monthly.pptx").resolve()
        )
        assert serialized["output_root"] == str((config_dir / "runs").resolve())
        return output_dir

    monkeypatch.setattr(run_module, "run_pipeline", _fake_run_pipeline)
    run_dir = run_module.run_pipeline_with_config(
        config, config_dir=config_dir, output_dir=output_dir
    )
    assert run_dir == output_dir
