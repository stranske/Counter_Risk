from scripts.langchain import issue_formatter


def test_normalize_checklist_lines_drops_separator_checkbox_placeholder() -> None:
    lines = ["- [ ] ---", "- [ ] Ship feature flag"]
    normalized = issue_formatter._normalize_checklist_lines(lines)
    assert normalized == ["- [ ] Ship feature flag"]


def test_normalize_checklist_lines_drops_filed_from_placeholder() -> None:
    lines = [
        "- [ ] _Filed from the 2026-05-29 design-vs-implementation + blueprint review (upgraded issue set)._",
        "- [ ] Add focused regression test",
    ]
    normalized = issue_formatter._normalize_checklist_lines(lines)
    assert normalized == ["- [ ] Add focused regression test"]


def test_normalize_checklist_lines_drops_not_provided_placeholder() -> None:
    lines = ["- [ ] _Not provided._", "- [ ] Add focused regression test"]
    normalized = issue_formatter._normalize_checklist_lines(lines)
    assert normalized == ["- [ ] Add focused regression test"]
