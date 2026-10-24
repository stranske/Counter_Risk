from pathlib import Path

HISTORICAL_BANNER = (
    "Historical audit snapshot (superseded 2026-09-23):**"
    " The BLOCKER-class findings in this report were addressed on `main`"
    " in merged PRs #1081–#1090 and #1103–#1107."
)


def test_in_repo_audit_logs_marked_historical() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    audit_report = (repo_root / "docs/audit/AUDIT_REPORT.md").read_text(encoding="utf-8")
    remaining_work = (repo_root / "docs/audit/REMAINING_WORK.md").read_text(encoding="utf-8")
    assert HISTORICAL_BANNER in audit_report
    assert HISTORICAL_BANNER in remaining_work
    assert "docs/PRODUCT_CONTRACT.md" in audit_report
    assert "docs/PRODUCT_CONTRACT.md" in remaining_work


def test_dimension_audit_logs_marked_historical() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    audit_files = (
        "10-calc-core.md",
        "10-io-config.md",
        "10-outputs.md",
        "10-parsers.md",
        "10-pipeline.md",
        "10-ui.md",
        "20-functionality-wiring.md",
        "21-duplication.md",
        "22-design-ux.md",
        "23-windows-readiness.md",
        "IMPLEMENTATION_SUMMARY.md",
    )
    for filename in audit_files:
        content = (repo_root / "docs/audit" / filename).read_text(encoding="utf-8")
        assert HISTORICAL_BANNER in content, filename
        assert "docs/PRODUCT_CONTRACT.md" in content, filename
