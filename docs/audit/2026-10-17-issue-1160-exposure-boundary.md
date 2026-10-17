# Issue #1160: bounded exposure identity and scope audit

Baseline: `f8871b2971d34b6d1b26df17fea1f9ef9cf079df` (fetched main).
Scope: CPRS-FCM parsed exposures → pipeline reshaping → limit evaluation,
with partitioned concentration as the control. This is a repository-owned
mirror; the parent maintains `Code/Audits/Counter_Risk/2026-10-17-issue-1160-audit-run.md`
and the canonical ledger. No production changes, policy changes, issue filing,
review-hold release, shared framework, or wider audit are included.

## Judgment and original disagreement

The two historical losses are repaired in the audited baseline. Alias repair
[#1168](https://github.com/stranske/Counter_Risk/pull/1168), merged as
`7d66f8380a57f395cef6c085a0d8a1fbeb6a0e3f`, resolves FCM/clearing-house identity.
Scope repair [#1170](https://github.com/stranske/Counter_Risk/pull/1170), merged as
`c06f1cda48848a26e1e1a5c53421bea6a2728886`, selects All Programs once for
unscoped caps (source policy issue #1161). Neither is an outstanding finding.
Confidence is high for the tested synthetic boundary; real workbook policy
acceptance, Office rendering and hosted CI are separate, unclaimed boundaries.

The source issue explicitly records that Codex retained this bounded inventory
while Claude's turn-2 `meta_candidate_proposal` remained false: the audit was
**not jointly endorsed**. Human approval authorized this scope; it did not turn
that disagreement into reviewer consensus. No additional defects are presumed.

## Inventory

Paths below are relative to `src/counter_risk/`; line anchors refer to the full
baseline above. I = intentional/preserved; C = confirmed historical loss, now
repaired; U = policy/caller intent unknown. Test references are exact function
names; listing existing coverage does not claim it was rerun in this round.

| Entry / source | Producer → consumer; identity and dimensions | Disposition / evidence |
| --- | --- | --- |
| `parsers/cprs_fcm.py:316,333,340` `_read_fcm_sheet`, `_normalize_text`, `_matching_key` | XLSX strings → section/header matchers and raw entity fields. Whitespace is cleaned; registry matching is for structural tokens, not destructive entity consolidation. | I. `tests/parsers/test_cprs_fcm.py::test_parse_fcm_with_shifted_columns`; new `boundary_parsed_workbooks` uses actual XLSX. |
| `parsers/cprs_fcm.py:256,280,307` section locators, `_variant_for_path` | Filename/sheet text → totals/futures inclusion. Trend totals and Ex Trend futures intentionally empty; variant is not a dataframe column. | I for declared variants; U1 for inconsistent configured path identity. Existing `test_parse_fcm_totals_trend_is_empty`, `test_parse_futures_detail_ex_trend_is_empty`; new `test_boundary_audit_parser_variant_scope` proves both exclusions with same-bytes positive controls; concentration control preserves the resulting partitions. |
| `parsers/cprs_fcm.py:344,369,377,392,429,454` numeric/header/dataframe helpers | Located cells → fixed typed columns. Accounting numbers retained; extra source columns are omitted. No entity/variant grouping occurs. | I. Existing fixture numeric/dtype/shifted-column tests. U2: custom-group enrichment is not produced here. |
| `parsers/cprs_fcm.py:99,111,142` totals parsing | Workbook → source-label rows with five asset classes, Notional and change; aliases remain separate. Zero-only rows, totals/subtotals and structural markers excluded; variant remains external. | I. New overlap and concentration checks consume parsed positive/negative registered aliases. Downstream consumers must canonicalize before entity aggregation. |
| `parsers/cprs_fcm.py:122,127` evidence wrappers | Raw totals → source-sheet/row map keyed by source label; numeric dataframe omits provenance columns. | I for separate provenance. Repeated identical source labels overwrite earlier evidence locations; multiplicity/provenance intent U3, no demonstrated numeric loss. |
| `parsers/cprs_fcm.py:204` futures parsing | Workbook → account, description, class, raw FCM, raw house, signed notional; variant external, segment represented by `class`. | I. New alias-only checks exercise parser → builder → canonical limits. Account/description are intentionally not limit dimensions. |
| `pipeline/run.py:1800,1819,1849` generated-input contract, `_parse_inputs`, `_validate_parsed_inputs` | Parsers → sections stored under configured variant keys; column checks preserve totals/futures tables and evidence. | I. No cross-variant aggregation. U1 remains: parser inclusion derives from filename while wrapper variant derives from configuration. |
| `pipeline/run.py:1223`; `compute/rollups.py:244,327,343` Repo Cash enrichment | Optional canonical cash → All Programs totals, then both numerical paths; asset-class columns preserved and total/change aliases updated. Cash is not a separate concentration segment. | I, conditional upstream producer. Existing `test_apply_daily_holdings_repo_cash_updates_all_programs_totals`, `test_authoritative_repo_cash_normalizes_new_mapping_aliases`. Cash policy not newly tested. |
| `pipeline/run.py:4671,4956` `_records`, `_to_float` | Tables → dictionaries/numbers for both row builders; dictionary keys preserved, invalid/nonfinite numeric values become zero in the builders. | I for current adapter behavior; not a claim that invalid source data is acceptable. Existing `test_concentration_metrics_write_finite_values`. |
| `pipeline/run.py:2424` concentration reshaper | Totals → long rows: raw display label **and canonical_key**, external variant, each present asset class and overall total. | I. New concentration control; existing `test_alias_reshaper_emits_identity_for_every_segment_and_variant` in `tests/compute/test_concentration_metrics.py`. |
| `pipeline/run.py:2471`; `compute/rollups.py:522,644` concentration computation/output | Long rows → groups by **variant, segment**, then canonical identity; gross magnitudes summed before HHI/Top-5/Top-10; CSV and returned manifest rows retain partitions. | I, already-correct control. New `test_boundary_audit_partitioned_concentration_control`; existing `test_registered_aliases_preserve_variant_and_segment_boundaries`. |
| `pipeline/run.py:2496` authoritative selection and totals assembly | All parsed variants → All Programs totals only, tagged `counterparty_total`; label preserved for downstream canonical resolution; overall Notional, not asset-class rows. | C repaired by #1170. New overlap check proves both share sides, true/false absolute breach and subset-only missing coverage; existing `all_programs_` tests cover all five dimensions and missing authority. |
| `pipeline/run.py:2521` futures assembly (within same builder) | All Programs futures → `futures_dimension` rows; raw FCM/house retained, class → segment, optional segment overrides class, group → custom_group. Account/description dropped; rows with no dimension omitted. | I for parser output. C repaired by #1170; new alias controls. U2 for enriched/conflicting optional fields. |
| `compute/limits.py:46,50,69,84,175` row/config/result adapters | Dataframe or mapping rows + validated limit config → evaluator inputs/results. Dimensions preserved; no portfolio selection in this public API. | I. Existing `test_check_limits_accepts_limits_config_object`, input validation and CSV tests. U4 for callers bypassing builder. |
| `compute/limits.py:89,93,137` name lookup/canonicalization | Exposure labels → canonical counterparty/FCM/house keys; segment/custom_group keep policy identity. Unknown names use whitespace/case fallback. Policy targets are required canonical keys. | C repaired by #1168. New alias-only checks plus existing `test_registered_futures_alias_has_identical_limits_and_missing_results`, `test_policy_group_aliases_are_not_resolved_through_registry`. |
| `compute/limits.py:104,111` notional/magnitude | Signed row notionals → finite gross magnitudes; notional alias precedence, zero and boolean rejection retained. | I. Existing fallback/boolean tests; new overlap check counts 60 and -40 as 100, not 20. |
| `compute/limits.py:129,150,164` denominator | Uniform granularity tags → appropriate counterparty or futures universe, including unlabeled rows within that universe; otherwise fallback to presence of dimension. No variant selector. | I for pipeline-built rows. New FCM/house shares are 60/100 despite 140 of counterparty totals. Existing `test_percent_of_total_scopes_denominator_to_matching_granularity`. Mixed/direct callers U4. |
| `compute/limits.py:205` missing targets | Selected rows → canonical identity sets; enabled targets absent from those sets reported deterministically. Variant and segment are not independently selected here. | C repairs #1168/#1170 applied before/within this entry. New alias and subset-only checks; disabled/unknown cases already covered. |
| `compute/limits.py:245` cap evaluation | Same selected rows → canonical matching, sum of gross magnitudes, absolute amount or granularity-matched share; threshold/severity preserved; deterministic breach rows. | C repairs #1168/#1170 verified; new absolute/share assertions. Aggregation across classes for an unscoped entity cap is I. |
| `compute/limits.py:318`; `pipeline/run.py:2543,2604,2611,2639,2651` artifacts/escalation | Missing-target warning/strict gate → evaluator → deterministic CSV and severity/count summary → warnings/fail exit. Breach rows omit variant because current policy has one universe. | I. Existing pipeline `test_all_programs_limit_scope_propagates_to_pipeline_and_exit` and `test_limit_alias_pipeline_csv_and_manifest_are_identical_under_strict_missing`. No new Office or CLI claim. |
| Adjacent readers: `pipeline/run.py:1904,1972,2129,2277,2320,2355` metrics/risk ranking/mover helpers | Totals → per-variant top raw rows or optional volatility proxies. Identity used for display/evidence or tie-breaking, not canonical exposure consolidation; asset segments omitted from top lists. | Confirmed representation difference; policy intent U5. Existing pipeline `test_write_risk_outputs_writes_rankings_and_top_movers`, canonical tie-break tests. These readers do not feed limits/concentration; no broader redesign proposed. |

## Remaining decisions (report-only)

| ID | Before → after audit disposition | Concrete next owner / decision |
| --- | --- | --- |
| U1 | Filename-derived variant inclusion vs configuration-derived variant key → UNKNOWN for mismatched input assignments; no new failure claimed. | Counter_Risk input-contract maintainer: decide whether existing operator filename requirements suffice or a separate provenance guard is wanted. |
| U2 | Parser has no custom_group producer, while builder accepts enriched optional fields; shipped custom-group cap is disabled → intentionally staged, enrichment/precedence contract UNKNOWN. | Risk-policy owner with parser maintainer: identify an authoritative group producer and class/segment precedence before enabling such caps. |
| U3 | Source evidence dictionary retains one row per repeated exact label → confirmed representation limit, downstream provenance requirements UNKNOWN. | Reporting/evidence maintainer: decide whether repeated identical labels require multiple source locations. Numeric rows themselves are retained. |
| U4 | Direct `check_limits` / missing-target callers do not enforce All Programs or uniform granularity; pipeline builder does → intentional composition boundary, broader caller guarantees UNKNOWN. | Compute API maintainer: decide whether direct heterogeneous callers are supported before requesting guards or tests. No claim of a pipeline defect. |
| U5 | Top exposure/change/proxy outputs rank source rows, concentration ranks canonical entities → confirmed semantic difference, desired consistency UNKNOWN. | Product/risk reporting owner: decide whether row-level top lists are intentional. Existing alias/overlap repairs do not settle that policy. |

These are decision requests, not automatically approved bugs. No new repair is
bundled or filed. A changed policy contract or a discriminating production-data
counterexample would change the dispositions.

## Regression and causal evidence

New checks in `tests/compute/test_limits.py`: alias-only parser→limit (two
parameter cases), overlapping-subset parser→limit, partitioned concentration.
They parse actual small XLSX files derived from the existing registered-alias
fixture; no parser doubles, empty helper checks, or copied production algorithms.
The overlap case also writes its subset-only entity into the Ex Trend XLSX and
reparses it, then verifies both absolute thresholds with and without overlapping
variants; no hand-built rows replace the parser's subset totals.
Numerical oracles: FCM/house share 0.6; canonical counterparty gross 100 of 140;
125 cap clean, 75 cap breached by 25; concentration total HHI 29/49 vs 1/2 in
separate variants, equity/treasury HHI 1, empty segments 0.

`../evidence/issue-1160/prove_boundary.py` derives checkout from `__file__` and
uses `sys.executable`. It checks JUnit counts, zero errors/skips, assertion reasons,
and subprocess exit status. Five serialized mutations test parser futures identity,
limit alias resolution, the actual pre-#1170 builder, parser totals identity,
and concentration variant partitioning. All three production files are restored
byte-for-byte in `finally`; originals and raw logs/JUnit remain outside checkout.
The identity mutations demonstrate identity propagation; they do not by themselves
prove the parser's variant-scope contract. The repaired alias and overlapping-subset
behaviors live in limits/pipeline, not solely that parser anchor. The follow-up
below directly disconnects the parser's declared variant exclusions instead.

See `../evidence/issue-1160/results.json`, `baseline.json`, `hash-mapping.json`,
the named `*-mutation.json`, raw-normalized logs and JUnit for exact evidence.
Public paths/hostname are replaced by `<REPO>`, `<RAW>`, `<PYTHON>`, `<HOME>`,
`<HOST>`, `<PYTHON_ENV>`, `<TMP>`; mapping records SHA-256 of both original and public bytes. Public logs
also trim trailing whitespace and are normalized transcripts, not represented as
byte-identical raw logs. The proof checks all tracked `src/` files against the
fixed Git baseline before and after mutation testing, separately from restoring
the three mutated files. Each pytest command explicitly selects `not slow`.

During initial validation, capability consultation was attempted for this exact
bounded task, but shared `capabilities.json.lock` write was sandbox-denied. No
capability was invoked, no extra assessor/agent was launched, and no decline
was persisted to shared state. Parent owns canonical mirroring, handoff and
automation memory. Validation counts and ownership limitations are recorded in
the evidence receipt under `initial_run_context`. Hosted checks remain unclaimed.

Initial validation: **101 passed** in the acceptance suite (four new cases; initial
collection was 97). Five mutants produced **8 assertion failures**, zero errors
and zero skips; each was restored and its selection passed. The two full runs
and ten selected runs account for 218 executions (210 passing, 8 intentional
RED). Configured whole-tree Ruff 0.17.1 and Black 26.10.1 passed; Mypy 2.4.0
passed all 106 source files. The follow-up reran the same preinstalled tool
versions on Linux/Python 3.14.8 without changing dependencies or ceilings.
Black's default multiprocessing IPC is blocked in this sandbox; a temporary
single-worker runtime with periodic asyncio wakeups completed the configured
whole-tree check for all 382 files. Its exact environment and portable helper
(`black-runtime.txt`, saved externally as `sitecustomize.py`) are recorded in
`validation-receipt.json`; no formatter checks were disabled.

Verified acceptance checklist:

- [x] Limits suite: 101 passed (97 existing, four XLSX regression cases).
- [x] Five serialized mutations: eight assertion failures, zero errors/skips;
  all restored selections green; two full and ten selected runs, 218 executions.
- [x] Original bytes restored and production equals fixed Git baseline;
  portable proof, normalized logs/JUnit and raw/public SHA-256 mapping retained.
- [x] Whole-tree Ruff 0.17.1 and Black 26.10.1 passed; Mypy 2.4.0 passed all
  106 source files. No ceilings changed.

The earlier follow-up could not write `.git/index.lock`; its changes were
subsequently recorded in `ac2b1fe019b3b4c773aa759f30da479912939367`.

## Parser scope gate follow-up

`test_boundary_audit_parser_variant_scope` adds two actual-XLSX cases in
`tests/compute/test_limits.py`: Trend must omit totals, and Ex Trend must omit
futures. Each copies the same workbook bytes to an All Programs filename and
parses both sections as a positive control. Both sections contain real rows;
the supported section survives unchanged and only the variant-excluded section
is empty. This verifies the declared parser contract already inventoried above,
without changing production policy or treating any unknown as a defect.

The proof script now temporarily disconnects each corresponding
`_variant_for_path(...)` guard in `src/counter_risk/parsers/cprs_fcm.py` separately.
Each named case must fail with its precise scope assertion, rather than merely
any assertion or collection error. The script restores original bytes in
`finally` and reruns that case successfully. Logs, JUnit and source hashes are
the `parser-trend-totals-scope-*` and `parser-ex-trend-futures-scope-*` artifacts.
These gates exercise parser exclusions; the separate actual pre-#1170 builder
mutation continues to establish the overlapping-subset limit failure.

Task reconciliation after reviewing `b4a55a0` and `ac2b1fe`: the inventory,
classification, mapping and original four regressions were already implemented
and the 101-case suite passed again before further edits. Updating PR #1172's
first eight checkboxes was rejected by automatic approval review: the connector
requires approval while this run uses approval policy `never`.
`../evidence/issue-1160/reconciled-pr-body.md` preserves the proposed PR body
for handoff. No new issues or production repairs were made.

Follow-up verification: `python -m pytest tests/compute/test_limits.py -q -m
"not slow"` collected **103 cases, all passed**. The portable proof completed
seven serialized mutations and 16 runs: 226 test executions, 216 passes and
10 expected assertion failures, with zero errors/skips. Both new parser scope
failures named the required exclusion behavior, and both restored runs passed.
All production source files still match the fixed baseline. The configured
whole-tree Black check passed for 382 files and focused Ruff passed for both
changed Python files. Initial Mypy evidence remains from the earlier run;
production code was unchanged.

- [x] Inventory, classification and mapping to #1168/#1170 verified.
- [x] Alias-only, overlapping-subset and partitioned-concentration controls pass.
- [x] Variant-scope tests fail when their parser guards are disconnected, and
  pass after byte-identical restoration; logs/JUnit retained.
- [x] Remaining U1–U5 decisions stay report-only for their named human owners.

All nine implementation/acceptance items are verified locally. Publishing the
reconciled PR checkboxes is still blocked by connector approval policy.

Commit handoff: the current run's `git add` also failed because `.git/index.lock`
is on a read-only filesystem. The verified source/test and evidence changes
remain uncommitted in the checkout; writable Git metadata is required to commit.

## Source-baseline guard verification

Reviewed `b4a55a0`, `ac2b1fe`, and `b2895ff` before continuing. The inventory,
classification, owned-work mapping and parser scope gates are already verified;
the live checkboxes remain stale. A new attempt to publish the reconciled body
was rejected because the connector requires approval and this run's approval
policy is `never`. PR #1172 was read back as open and ready for review.

`tests/docs/test_exposure_boundary_proof.py` now verifies that the proof script
stops before mutation, test execution or evidence publication when its initial
Git baseline check reports source drift or a Git error. Both cases assert that
source bytes remain unchanged and no raw evidence is written. These tests are
separate from the limits acceptance suite and add no production repair.

Current verification:

- `python -m pytest tests/compute/test_limits.py -q -m 'not slow'`: **103 passed**.
- `python -m pytest tests/docs/test_exposure_boundary_proof.py -q -m 'not slow'`:
  **2 passed**.
- `python -m pytest tests/compute/test_limits.py tests/docs/test_exposure_boundary_proof.py -q -m 'not slow'`:
  **105 passed**, zero skips or failures.
- Focused Ruff and `git diff --check` passed. Whole-tree
  `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
  passed: **383 files unchanged**, using the previously recorded temporary
  asyncio runtime and `BLACK_NUM_WORKERS=1` after the default multiprocessing
  invocation failed on the sandbox's IPC restriction.
- `git diff --exit-code f8871b2971d34b6d1b26df17fea1f9ef9cf079df -- src`
  passed; production remains identical to the audited baseline.

## Partition isolation control follow-up

The remaining acceptance item already had passing alias-only and overlapping-subset
probes. The concentration control now additionally compares every parsed variant
in isolation against its results alongside the overlapping portfolios, including
Trend's intentionally empty totals. It also rejects duplicate variant/segment
results before building the lookup used by the numerical assertions. This makes
the already-correct concentration partition contract explicit without changing
production code or reclassifying any U1–U5 policy question as a defect.

- [x] Use alias-only and overlapping-subset controls, including already-correct
  partitioned concentration; preserve unknowns rather than inventing defects.

Verification after the test change:

- `python -m pytest tests/compute/test_limits.py -q -m 'not slow'`: **103 collected,
  103 passed in 1.31s**, including the strengthened concentration control and
  existing alias-only, overlap and parser scope assertions.
- `ruff check tests/compute/test_limits.py` and `git diff --check` passed.
- `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`:
  **383 files unchanged**, after formatting the modified test. The default
  multiprocessing run was sandbox-denied; the passing check used
  `BLACK_NUM_WORKERS=1` and the existing `black-runtime.txt` helper copied to
  `/tmp/counter-risk-black-runtime/sitecustomize.py` via `PYTHONPATH`.
- Production still matches baseline
  `f8871b2971d34b6d1b26df17fea1f9ef9cf079df` (`git diff --exit-code` over `src`).

The follow-up commit was attempted after these checks; `git add` failed because
`.git/index.lock` cannot be created on the read-only filesystem. These test and
evidence changes remain in the working tree pending writable Git metadata.

## CSV partition control and checkbox reconciliation

Reviewed the five audit commits through `bc9073a`, including the proof-script
baseline guard and variant-isolation assertions. The remaining acceptance item
was implemented already: the baseline limit suite collected and passed 103 tests.
The concentration control now additionally reads the actual exported CSV and
requires unique variant/segment pairs, the exact returned partition set, and
matching HHI, Top-5 and Top-10 values for each partition. This extends the
already-correct control through artifact output; U1–U5 remain unknown decisions.

Verification after the CSV assertions:

- `python -m pytest tests/compute/test_limits.py tests/docs/test_exposure_boundary_proof.py -q -m 'not slow'`:
  **105 collected, 105 passed in 1.24s**.
- Focused Ruff and Black checks passed. The required whole-tree
  `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
  passed: **383 files unchanged**, using the previously documented temporary
  runtime helper and `BLACK_NUM_WORKERS=1` after the unpatched run stalled.
- `git diff --check` passed; `git diff --exit-code` against baseline over `src`
  passed. No production repair was added.

PR #1172 was verified open with `draft=false`. Its remaining unchecked item
should be checked, as reflected in `docs/evidence/issue-1160/reconciled-pr-body.md`.
Automatic approval review rejected the live body update because the GitHub
connector requires approval and this run's approval policy is `never`.

After validation, the commit attempt failed at `git add`: Git could not create
`.git/index.lock` on the read-only filesystem. The CSV regression and handoff
updates remain uncommitted; no push was attempted.

## Muse keepalive follow-up: combined declared-contract check

Re-verified the bounded seam at current HEAD (`a904171`, which already merged
the audit above): `parsers/cprs_fcm.py:152,215` variant Scope guards →
`pipeline/run.py:2503` `_build_limit_exposure_rows` (All Programs only) and
`:2431,2478` partitioned concentration control → `compute/limits.py` canonical
alias resolution and granularity denominators. Dispositions unchanged:
alias/scope losses are confirmed-historical and repaired by #1168/#1170,
concentration is the already-correct control, and U1–U5 remain unknown
(report-only, no issue filed, no production fix bundled).

New `test_boundary_audit_declared_contract_alias_and_overlap_combined` in
`tests/compute/test_limits.py` exercises alias-only and overlapping-subset
probes in a single evaluation: futures FCM/clearing-house shares (0.6) and the
counterparty share (5/7) breach simultaneously without denominator
contamination, the 125 absolute cap stays clean, and `subset_only` stays
missing.

Delivery evidence (`docs/evidence/issue-1160/muse-round-deliberate-break.log`):

- `python -m pytest tests/compute/test_limits.py -q -m "not slow"`: **104
  passed** (103 prior + 1 combined).
- Deliberate-break gate: disconnecting the Trend totals Scope guard at
  `src/counter_risk/parsers/cprs_fcm.py:152` made
  `test_boundary_audit_parser_variant_scope[trend]` fail (1 failed, 1 passed,
  exit 1); the file was restored byte-identical (`git diff --exit-code`) and
  the full file reran **104 passed**.

## Muse keepalive classification follow-up

Classification is now executable, not only tabular. New
`test_boundary_audit_classification_intentional_aggregation_vs_segment_partition`
in `tests/compute/test_limits.py` separates the three dispositions at the
`compute/limits.py` boundary:

- **Intentional aggregation (I):** an unscoped `fcm` cap for
  `bank_of_america` sums two registered alias spellings
  (`Bank of America, NA` in Equity, `Bank of America NA` in Treasury) across
  segments to 0.6 of the futures universe. Segment is aggregated only
  because the policy entity type does not select it.
- **Preserved dimension / control:** a `segment`-typed cap still partitions
  -- Equity breaches at 0.7 while Treasury (0.3) does not -- matching the
  already-correct partitioned concentration control
  (`pipeline/run.py:2431,2478` grouping by variant/segment), which remains
  unchanged and passing.
- **Confirmed alias loss (C, repaired):** the same test fails when canonical
  alias resolution in `compute/limits.py:_canonical_entity_key` is
  disconnected (deliberate-break: 1 failed, `bank_of_america` breach
  missing; restored byte-identical, 1 passed). This is the #1168 repair
  surface; no new production fix is bundled.
- **Unknown (U):** U1-U5 above remain report-only. This test asserts nothing
  about them; no issue is filed and no defect is invented for them.

Known-instance mapping is unchanged: alias loss -> #1168, overlapping-subset
scope loss -> #1170 (policy #1161), both merged. The new test returns no
uncovered gap: it only pins the intentional-vs-preserved classification
between them. `src/counter_risk/parsers/cprs_fcm.py` is not modified by
this follow-up; its variant Scope guards (`:152` totals, `:215` futures)
remain the deliberate-break target already logged in
`docs/evidence/issue-1160/muse-round-deliberate-break.log`.

## Muse keepalive mapping follow-up (cprs_fcm producer boundary)

The known-instance mapping is now pinned at the producer named by the task,
`src/counter_risk/parsers/cprs_fcm.py`, by new
`test_boundary_audit_cprs_fcm_known_instances_map_to_approved_work` in
`tests/compute/test_limits.py`:

| Known instance | Producer contract at `cprs_fcm.py` | Approved work | Uncovered gap returned |
| --- | --- | --- | --- |
| Registered FCM/clearing-house + counterparty alias loss | Parser preserves raw spellings (`Bank of America, NA`, `CME Clearing House`, `Citibank`/`Citigroup`) as separate signed rows; it does not merge, net (60/-40), or canonicalise | #1168 canonicalisation in `compute/limits.py` | None at parser |
| Overlapping-subset (All Programs vs Trend/Ex Trend) scope loss | Scope guards `:152` (Trend totals empty) and `:215` (Ex Trend futures empty); retained sections carry scaled source rows; only `all_programs` reaches `_build_limit_exposure_rows` | #1170, policy #1161 | None at parser |

Returned for human review, without filing issues and without bundled
production repairs: only the pre-existing report-only unknowns U1-U5
above. They are not parser gaps, are not reclassified as defects, and are
not asserted by the new test. `cprs_fcm.py` itself is unchanged.

Deliberate-break gate for this mapping check: disconnecting the Trend
totals Scope guard at `cprs_fcm.py:152` made the new test fail (1 failed;
Trend totals leaked 6000/-3000/9000 rows); restored byte-identical
(`git diff --exit-code -- src` clean) and the full limits file reran
**106 passed** (105 prior + 1 mapping). Recorded in
`docs/evidence/issue-1160/muse-round-deliberate-break.log`.
