from __future__ import annotations

from datetime import date
from pathlib import Path

from counter_risk.config import WorkflowConfig
from counter_risk.outputs.base import OutputContext, OutputGenerator


class _DummyGenerator:
    name = "dummy"

    def generate(self, *, context: OutputContext) -> tuple[Path, ...]:
        return (context.run_dir / "dummy.txt",)


def _minimal_config(tmp_path: Path) -> WorkflowConfig:
    for filename in (
        "all.xlsx",
        "ex.xlsx",
        "trend.xlsx",
        "hist_all.xlsx",
        "hist_ex.xlsx",
        "hist_llc.xlsx",
        "monthly.pptx",
    ):
        (tmp_path / filename).write_bytes(b"placeholder")

    return WorkflowConfig(
        mosers_all_programs_xlsx=tmp_path / "all.xlsx",
        mosers_ex_trend_xlsx=tmp_path / "ex.xlsx",
        mosers_trend_xlsx=tmp_path / "trend.xlsx",
        hist_all_programs_3yr_xlsx=tmp_path / "hist_all.xlsx",
        hist_ex_llc_3yr_xlsx=tmp_path / "hist_ex.xlsx",
        hist_llc_3yr_xlsx=tmp_path / "hist_llc.xlsx",
        monthly_pptx=tmp_path / "monthly.pptx",
    )


def test_output_generator_protocol_contract(tmp_path: Path) -> None:
    config = _minimal_config(tmp_path)
    context = OutputContext(
        config=config,
        run_dir=tmp_path / "run",
        as_of_date=date(2026, 2, 25),
        run_date=date(2026, 2, 25),
    )

    generator: OutputGenerator = _DummyGenerator()
    assert generator.name == "dummy"
    assert generator.generate(context=context) == (tmp_path / "run" / "dummy.txt",)
