"""Finite notional breakdown validation through the workbook writer."""

from pathlib import Path
from typing import Any

import pytest

from counter_risk.writers.dropin_templates import fill_dropin_template

openpyxl = pytest.importorskip("openpyxl")


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), "NaN", "inf", "-inf", "1e309"]
)
@pytest.mark.parametrize("metric", ["Total", "Cash", "unrecognized metric"])
def test_non_finite_breakdown_rejected_before_workbook_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: Any, metric: str
) -> None:
    template = tmp_path / "template.xlsx"
    template.write_bytes(b"template must not be loaded")
    output = tmp_path / "existing-output.xlsx"
    output.write_bytes(b"previous report")

    def unexpected_load(*args: Any, **kwargs: Any) -> None:
        pytest.fail("invalid breakdown reached workbook loading")

    monkeypatch.setattr(openpyxl, "load_workbook", unexpected_load)
    with pytest.raises(ValueError, match=f"breakdown value for {metric!r} must be finite"):
        fill_dropin_template(
            template,
            [],
            {"Tips": 12.5, metric: value},
            output_path=output,
        )

    assert output.read_bytes() == b"previous report"
    assert template.read_bytes() == b"template must not be loaded"


def test_finite_breakdown_preserves_signed_values_in_saved_workbook(tmp_path: Path) -> None:
    template = tmp_path / "template.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.append(["Counterparty / Clearing House", "Cash", "Tips", "Treasury", "Notional"])
    worksheet.append(["Notional Breakdown", 999, 999, 999, 999])
    workbook.save(template)
    workbook.close()

    output = tmp_path / "output.xlsx"
    result = fill_dropin_template(
        template,
        [],
        {"Cash": 12.5, "Tips": 0.0, "Treasury": -7.25, "Total": "5.25"},
        output_path=output,
    )

    assert result == output
    saved = openpyxl.load_workbook(output)
    try:
        assert saved.active is not None
        assert list(saved.active.values)[1] == ("Notional Breakdown", 12.5, 0, -7.25, 5.25)
    finally:
        saved.close()
