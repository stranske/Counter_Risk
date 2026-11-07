"""Regression coverage for the repo-owned product contract."""

from pathlib import Path


def test_product_contract_reports_current_maintainer_cli_status() -> None:
    contract = Path("docs/PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
    rows = {
        columns[1].strip(): columns[-2].strip()
        for line in contract.splitlines()
        if line.startswith("| C") and len(columns := line.split("|")) >= 6
    }

    assert rows["C1"] == "WORKS (maintainer CLI)"
    assert rows["C3"] == "WORKS (maintainer CLI)"
    assert rows["C4"] == "WORKS (maintainer CLI)"
    assert "## Known gaps at draft time" not in contract
    assert "The Windows release bundle" in contract
    assert "`Ask about this run` label without a bound Form Control or VBA handler" in contract
