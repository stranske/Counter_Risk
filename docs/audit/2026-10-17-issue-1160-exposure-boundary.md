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
| `parsers/cprs_fcm.py:256,280,307` section locators, `_variant_for_path` | Filename/sheet text → totals/futures inclusion. Trend totals and Ex Trend futures intentionally empty; variant is not a dataframe column. | I for declared variants; U1 for inconsistent configured path identity. Existing `test_parse_fcm_totals_trend_is_empty`, `test_parse_futures_detail_ex_trend_is_empty`; new concentration control covers both. |
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
Numerical oracles: FCM/house share 0.6; canonical counterparty gross 100 of 140;
125 cap clean, 75 cap breached by 25; concentration total HHI 29/49 vs 1/2 in
separate variants, equity/treasury HHI 1, empty segments 0.

`../evidence/issue-1160/prove_boundary.py` derives checkout from `__file__` and
uses `sys.executable`. It checks JUnit counts, zero errors/skips, assertion reasons,
and subprocess exit status. Five serialized mutations test parser futures identity,
limit alias resolution, the actual pre-#1170 builder, parser totals identity,
and concentration variant partitioning. All three production files are restored
byte-for-byte in `finally`; originals and raw logs/JUnit remain outside checkout.
The parser mutations also satisfy the issue's parser-anchor gate; the repaired
alias and scope behaviors actually live in limits/pipeline, not solely that anchor.

See `../evidence/issue-1160/results.json`, `baseline.json`, `hash-mapping.json`,
the named `*-mutation.json`, raw-normalized logs and JUnit for exact evidence.
Public paths/hostname are replaced by `<REPO>`, `<RAW>`, `<PYTHON>`, `<HOME>`,
`<HOST>`, `<PYTHON_ENV>`, `<TMP>`; mapping records SHA-256 of both original and public bytes. Public logs
are normalized transcripts, not represented as byte-identical raw logs.

Capability consultation was attempted for this exact bounded task before
validation, but shared `capabilities.json.lock` write was sandbox-denied. No
capability was invoked, no extra assessor/agent was launched, and no decline
was persisted to shared state. Parent owns canonical mirroring, handoff and
automation memory. Validation counts and ownership limitations are recorded in
the evidence receipt. Hosted checks remain asynchronous and unclaimed.

Validation: **101 passed** in the acceptance suite (four new cases; initial
collection was 97). Five mutants produced **8 assertion failures**, zero errors
and zero skips; each was restored and its selection passed. The two full runs
and ten selected runs account for 218 executions (210 passing, 8 intentional
RED). Configured whole-tree Ruff 0.17.1 and Black 26.10.1 passed; Mypy 2.4.0
passed all 106 source files. Tools were installed to an external temporary target,
without changing repository dependencies or ceilings. Existing optional pandas
accelerator-version warnings remain. See `validation-receipt.json`.
