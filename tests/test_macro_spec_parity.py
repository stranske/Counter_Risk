"""Macro parity harness.

Bidirectional checks that ``docs/macro_spec.md`` stays aligned with the source-of-
truth constants and public click handlers in ``assets/vba/RunnerLaunch.bas``. Each
assertion failure points at the Spec ID section in ``macro_spec.md`` that protects
the invariant, so a maintainer can update the spec or the macro deliberately.
"""

from __future__ import annotations

import re
from pathlib import Path

VBA_MODULE_PATH = Path("assets/vba/RunnerLaunch.bas")
MACRO_SPEC_PATH = Path("docs/macro_spec.md")

# Constants in the .bas file we expect to find documented in macro_spec.md.
# (constant_name, expected_address, spec_section_id)
RUNNER_CELL_CONSTANTS: tuple[tuple[str, str, str], ...] = (
    ("STATUS_CELL", "B7", "MS-RUNNER-CELLS"),
    ("RESULT_CELL", "B8", "MS-RUNNER-CELLS"),
    ("DQ_STATUS_CELL", "B9", "MS-RUNNER-CELLS"),
)

# Public click handlers (Sub <Name>_Click) every spec must document with a Spec ID.
EXPECTED_CLICK_HANDLERS: tuple[tuple[str, str], ...] = (
    ("RunAll_Click", "MS-RUN-ALL"),
    ("RunExTrend_Click", "MS-RUN-EX-TREND"),
    ("RunTrend_Click", "MS-RUN-TREND"),
    ("OpenOutputFolder_Click", "MS-OPEN-OUTPUT"),
    ("OpenSummary_Click", "MS-OPEN-SUMMARY"),
    ("OpenManifest_Click", "MS-OPEN-MANIFEST"),
    ("OpenPPTFolder_Click", "MS-OPEN-PPT"),
)

CLICK_HANDLER_PATTERN = re.compile(r"^Public Sub ([A-Za-z0-9_]+_Click)\(\)", re.MULTILINE)
CONSTANT_PATTERN = re.compile(
    r'^Private Const\s+([A-Z0-9_]+)\s+As String\s*=\s*"([^"]+)"', re.MULTILINE
)


def _read_module_source() -> str:
    assert VBA_MODULE_PATH.is_file(), (
        f"Expected VBA source at {VBA_MODULE_PATH}; macro parity harness cannot run "
        f"without it. See docs/macro_spec.md section 'Scope'."
    )
    return VBA_MODULE_PATH.read_text(encoding="utf-8")


def _read_spec_text() -> str:
    assert MACRO_SPEC_PATH.is_file(), (
        f"Expected macro spec at {MACRO_SPEC_PATH}; the parity harness has nothing "
        f"to compare against."
    )
    return MACRO_SPEC_PATH.read_text(encoding="utf-8")


def _bas_constants(module_source: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in CONSTANT_PATTERN.finditer(module_source)}


def _click_handlers(module_source: str) -> set[str]:
    return set(CLICK_HANDLER_PATTERN.findall(module_source))


def test_runner_cell_constants_match_bas_source() -> None:
    """The expected cell-name table must match the live ``.bas`` constants.

    If a constant was renamed or its address changed in ``RunnerLaunch.bas``, update
    section ``MS-RUNNER-CELLS`` in ``docs/macro_spec.md`` (and the per-macro
    ``Required inputs`` / ``Output expectations`` lists for `MS-RUN-*`) before
    relaxing this assertion.
    """

    constants = _bas_constants(_read_module_source())
    for constant_name, expected_address, spec_section_id in RUNNER_CELL_CONSTANTS:
        assert constant_name in constants, (
            f"VBA constant {constant_name!r} is missing from {VBA_MODULE_PATH}. "
            f"Update macro_spec.md section [{spec_section_id}] or restore the "
            f"constant — they must agree."
        )
        actual_address = constants[constant_name]
        assert actual_address == expected_address, (
            f"VBA constant {constant_name} = {actual_address!r} but macro_spec.md "
            f"section [{spec_section_id}] documents {expected_address!r}. "
            f"Update either the constant or the spec section so they agree."
        )


def test_macro_spec_documents_each_runner_cell_constant() -> None:
    """``MS-RUNNER-CELLS`` must mention each cell constant + address pair.

    A failed assertion means a Runner-sheet cell constant exists in
    ``RunnerLaunch.bas`` but is not documented in ``docs/macro_spec.md``. Add the
    constant to the cell-layout table under section ``MS-RUNNER-CELLS``.
    """

    spec_text = _read_spec_text()
    for constant_name, expected_address, spec_section_id in RUNNER_CELL_CONSTANTS:
        assert constant_name in spec_text, (
            f"macro_spec.md is missing reference to VBA constant {constant_name!r}. "
            f"Add it to section [{spec_section_id}] in {MACRO_SPEC_PATH}."
        )
        assert f"`{expected_address}`" in spec_text, (
            f"macro_spec.md does not mention cell address {expected_address!r}, "
            f"which is bound to {constant_name!r} in {VBA_MODULE_PATH}. "
            f"Update section [{spec_section_id}]."
        )


def test_every_public_click_handler_has_spec_section() -> None:
    """Every ``*_Click`` macro in the source module must appear in ``macro_spec.md``.

    Each handler must show up by name AND have its expected Spec ID present in the
    spec doc. If a new click handler is added in ``RunnerLaunch.bas``, extend
    ``EXPECTED_CLICK_HANDLERS`` here AND add a corresponding section to
    ``docs/macro_spec.md`` with a fresh ``MS-*`` Spec ID.
    """

    module_source = _read_module_source()
    spec_text = _read_spec_text()
    handlers_in_source = _click_handlers(module_source)
    expected_handler_names = {name for name, _ in EXPECTED_CLICK_HANDLERS}

    extra_in_source = sorted(handlers_in_source - expected_handler_names)
    assert not extra_in_source, (
        "RunnerLaunch.bas exposes click handlers that the macro parity harness does "
        "not know about: "
        + ", ".join(extra_in_source)
        + ". Add a Spec ID section to docs/macro_spec.md and extend "
        "EXPECTED_CLICK_HANDLERS in tests/test_macro_spec_parity.py."
    )

    missing_in_source = sorted(expected_handler_names - handlers_in_source)
    assert not missing_in_source, (
        "Expected click handlers not found in RunnerLaunch.bas: "
        + ", ".join(missing_in_source)
        + ". Restore the handler or remove its section from docs/macro_spec.md."
    )

    for handler_name, spec_section_id in EXPECTED_CLICK_HANDLERS:
        assert handler_name in spec_text, (
            f"macro_spec.md does not document click handler {handler_name!r}. "
            f"Add a section with Spec ID [{spec_section_id}]."
        )
        assert f"Spec ID: `{spec_section_id}`" in spec_text, (
            f"macro_spec.md is missing Spec ID anchor [{spec_section_id}] for "
            f"{handler_name!r}. Add a 'Spec ID: `{spec_section_id}`' line under the "
            f"section heading so failed parity assertions can be cross-referenced."
        )


def test_macro_spec_lists_pipeline_input_fixtures_per_run_mode() -> None:
    """Each ``MS-RUN-*`` spec section must name its concrete input-workbook fixture.

    Acceptance criterion: ``docs/macro_spec.md`` maps every covered macro to its
    fixture, affected ranges, and invariants. This test enforces the fixture
    mapping for the three pipeline-invoking handlers; the per-macro ``Required
    inputs`` block must mention the corresponding ``tests/fixtures/NISA Monthly *
    - Raw.xlsx`` workbook.
    """

    spec_text = _read_spec_text()
    expected_fixtures: tuple[tuple[str, str], ...] = (
        ("MS-RUN-ALL", "tests/fixtures/NISA Monthly All Programs - Raw.xlsx"),
        ("MS-RUN-EX-TREND", "tests/fixtures/NISA Monthly Ex Trend - Raw.xlsx"),
        ("MS-RUN-TREND", "tests/fixtures/NISA Monthly Trend - Raw.xlsx"),
    )
    for spec_section_id, fixture_path in expected_fixtures:
        assert spec_section_id in spec_text, (
            f"Spec ID [{spec_section_id}] is missing from macro_spec.md; cannot "
            f"verify fixture mapping for {fixture_path!r}."
        )
        assert fixture_path in spec_text, (
            f"macro_spec.md section [{spec_section_id}] does not reference its "
            f"required pipeline input fixture {fixture_path!r}. Add it to the "
            f"'Fixture sources' list for that macro."
        )


def test_macro_spec_documents_macro_enabled_workbook_fixtures() -> None:
    """Both macro-enabled workbook fixtures must be named in the spec scope.

    These fixtures are the inventory source for ``assets/vba/*.bas`` and are
    enforced by ``tests/test_vba_module_inventory.py``. Keeping them in the spec
    means a maintainer who breaks inventory parity gets a pointer to both surfaces.
    """

    spec_text = _read_spec_text()
    for workbook_path in ("Runner.xlsm", "assets/templates/counter_risk_template.xlsm"):
        assert workbook_path in spec_text, (
            f"macro_spec.md does not name macro-enabled workbook fixture "
            f"{workbook_path!r}. Add it to the 'Scope' section so VBA inventory "
            f"failures (test_vba_module_inventory.py) and macro parity failures "
            f"share a single source of truth."
        )
