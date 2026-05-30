from scripts.langchain import followup_issue_generator


def test_parse_checklist_drops_separator_checkbox_placeholder() -> None:
    lines = ["- [ ] ---", "- [ ] Ship feature flag"]
    assert followup_issue_generator._parse_checklist(lines) == ["Ship feature flag"]


def test_parse_checklist_drops_filed_from_placeholder() -> None:
    lines = [
        "- [ ] _Filed from the 2026-05-29 design-vs-implementation + blueprint review"
        " (upgraded issue set)._",
        "- [ ] Add focused regression test",
    ]
    assert followup_issue_generator._parse_checklist(lines) == ["Add focused regression test"]
