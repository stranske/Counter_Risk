# Product contract — stranske/Counter_Risk
_First draft generated 2026-09-20 from the audit scorecard; the repo owns this file from now on. A PR that adds a user-facing route, command or page adds a line here. The audit's Phase 1.5 scores every line below and prints any surface not listed as UNSCORED._

## Purpose
Turn exposure workbooks into consolidated counterparty-risk outputs, alerts and monthly Excel/PowerPoint deliverables.

## Primary journey
Supply all workbook variants → run pipeline → review consolidated exposures, limits and concentration → receive reporting package.

## Core functions
| id | a user can … and sees … | entry point | probe (how to exercise it; vary these determinants) | status 2026-09-27 |
|---|---|---|---|---|
| C1 | an operator can load positions and sees coherent exposure by counterparty and variant | `counter-risk run --config <workflow.yml>` | run shipped three variants; vary synthetic position rows at concentration boundary | WORKS (maintainer CLI) |
| C2 | an operator can apply identity and limits and sees aliases resolve with breached-cap warning | `counter-risk run --config <workflow.yml>` | use shipped absolute-notional Citibank cap; vary Citibank/Citigroup rows; inspect `limit_breaches.csv` and summary | WORKS |
| C3 | an operator can compute concentration and sees HHI, Top-5 and Top-10 reflecting consolidated gross exposure | `counter-risk run --config <workflow.yml>` | compare concentrated/even and registered-alias split portfolios; inspect metrics CSV and manifest | WORKS (maintainer CLI) |
| C4 | an operator can produce monthly reporting and sees newly generated, consistent report artifacts and warnings | `counter-risk run --config <workflow.yml>` | compare fixture replay to live calculation; inspect XLSX, PPTX/PDF and manifest/run folder | WORKS (maintainer CLI) |

| C5 | an operator sees source report-date conflicts with workbook/variant provenance while configured `as_of_date` remains authoritative; final history/publication blocks conflicts unless a run-level reason is recorded | `counter-risk run --config <workflow.yml> [--report-date-override "audit reason"]` | vary first/later variant dates, unset config, ambiguous/generated headers, diagnostic versus strict/final mode; inspect manifest/quality summary and CLI exit | regression covered |

## Current operator gaps and boundaries
- The Windows release bundle and final `Runner.xlsm` click behavior still require a Windows build plus the manual checks in `docs/RELEASE_CHECKLIST.md`; passing maintainer CLI coverage does not claim that operator release verification is complete.
- `Runner.xlsm` binds `Ask about this run` to `AskAbout_Click`, which explains that run Q&A is not available in Excel and points to `counter-risk gui`; it does not open a chat session. Provider-backed chat also requires configured credentials.
- `counter-risk run --fixture-replay` is a packaging-validation path that copies checked-in fixtures by design. Monthly operators use workflow mode for current calculations.

## Accepted unscoped limit universe (U04 / #1161)

Current unscoped caps evaluate All Programs exactly once. Ex Trend and Trend
remain reporting variants; their overlapping positions cannot change a cap's
absolute exposure, percentage numerator/denominator, or missing-entity coverage.
Missing authoritative All Programs fails explicitly; an empty authoritative table
uses the existing missing-entity warning/strict policy and never substitutes a
subset. Existing canonical alias resolution, cap amounts, gross-notional semantics,
concentration metrics, historical reporting and operator release exclusions remain
in force. No per-variant policy schema is introduced.

Observable verification: named `all_programs_` compute and pipeline scope gates
prove 200m All Programs + 150m Ex Trend does not breach a 250m cap, while 300m
All Programs writes one 50m fail breach, consistent manifest/data-quality RED
status and pipeline failure / CLI exit 1. Percentage shares stay invariant under
subset changes. Serialized original-builder RED and byte-identical restored GREEN
evidence is retained in `docs/evidence/issue-1161/`. These gates use real limit and
pipeline orchestration with synthetic parsed frames and report-output doubles;
CI, native Office rendering and production-data acceptance are separate boundaries.

Follow-up verification covers subset-first input order, negative authoritative
notionals and subsets matching either the capped entity or an unrelated entity.
All 34 absolute/share cases pass; restoring the original builder causes 29 failures
with five subset-free controls still passing, then restoring the fixed bytes returns
all 34 to green (`docs/evidence/issue-1161/followup-scope.txt`). The complete named
scope suite passes 45 cases, and the broader limit/configuration/pipeline checks
pass 284 cases with `-m "not slow"`.
