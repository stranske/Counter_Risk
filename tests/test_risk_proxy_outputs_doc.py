"""Validation tests for risk proxy output documentation."""

from __future__ import annotations

from pathlib import Path


def test_risk_proxy_outputs_doc_covers_formulas_inputs_and_missing_data() -> None:
    doc_path = Path(__file__).resolve().parents[1] / "docs" / "risk_proxy_outputs.md"
    assert doc_path.is_file()

    contents = doc_path.read_text(encoding="utf-8")

    assert "risk_proxy_notional_annualized_volatility" in contents
    assert "Notional * AnnualizedVolatility" in contents
    assert "risk_proxy_position_usd_vol" in contents
    assert "PositionUSD * Vol" in contents
    assert "NotionalChange" in contents
    assert "NotionalChangeFromPriorMonth" in contents
    assert "PositionUSDChange" in contents
    assert "PositionChangeFromPriorMonth" in contents
    assert "prior_proxy_value = current_proxy_value - delta" in contents
    assert 'manifest["risk_proxy_summary"]["by_variant"]' in contents
    assert "risk_rankings.csv" in contents
    assert "risk_top_movers.csv" in contents
    assert "skipped with a warning" in contents
