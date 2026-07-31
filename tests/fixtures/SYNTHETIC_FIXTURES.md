# Synthetic Office fixtures

The Office files listed in `SYNTHETIC_FIXTURES.sha256` are reconstructed test
fixtures. They are not approved production reports and contain no production
amounts, percentages, amount-to-entity pairings, reporting notes, embedded
screenshots, comments, connections, or external workbook links.

The workbook fixtures retain the public entity and instrument labels, structural
headers, styles, month sequence, and sheet layouts required to exercise parsers,
normalization, calculations, and output generators. All values associated with
those labels are deterministic synthetic values; source narrative notes are
genericized. The presentation retains the production-like slide/layout structure
needed by the screenshot and postprocess tests, but uses generic series labels,
synthetic chart values, cleared notes, and a generated “NO PRODUCTION DATA”
placeholder for every embedded image.

If a fixture is intentionally regenerated, review every sheet or slide, rerun
the fixture guard and full test suite, and update `SYNTHETIC_FIXTURES.sha256`.
Never generate these fixtures from a production artifact inside Git history.
