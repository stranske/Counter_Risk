## Workflow Source

Started from:
- [x] GitHub issue: #1160
- [x] Local Codex/user request
- [x] Automation run

Automation intent:
- [x] Verifier should review this
- [x] Keepalive may manage this PR

Notes: Bounded accepted audit only. Refs #1160; parent owns acceptance and source closure. No production fixes, policy changes, new issue filing, or broader audit are authorized by this PR. Additional gaps remain report-only for human decision.

## Summary

Inventory the CPRS-FCM parser → exposure assembly → limits seam, with canonical identity and variant/segment contracts, exact source/test references, known merged repairs #1168/#1170, and the already-correct partitioned concentration control. Preserve the original reviewer disagreement explicitly.

Add six actual-XLSX regression cases for alias-only FCM/clearing-house caps, overlapping subsets, partitioned concentration, and explicit parser variant exclusions. Production files remain byte-identical to baseline `f8871b2971d34b6d1b26df17fea1f9ef9cf079df`.

Report: `docs/audit/2026-10-17-issue-1160-exposure-boundary.md`. Five remaining questions have explicit owners: mismatched variant provenance, staged custom-group enrichment, repeated-label evidence multiplicity, direct compute caller contracts, and raw-row top lists versus canonical concentration. These are unadjudicated questions, not newly approved defects.

## Testing

- `python -m pytest tests/compute/test_limits.py -q`: **103 passed** (97 existing, six new cases), with `-m "not slow"`.
- Seven serialized source mutations: **10 assertion failures**, zero errors/skips; every mutation restored, each selected regression returned GREEN. Actual pre-#1170 builder used for scope RED. Two full and fourteen selected runs total 226 executions: 216 passing, ten expected RED. Parser variant guards each fail their precise exclusion assertion when disconnected and pass after restoration.
- Original source bytes and Git-baseline equality verified. Portable proof script, normalized logs/JUnit and raw/public SHA-256 mapping: `docs/evidence/issue-1160/`.
- Whole-tree Black 26.10.1 and focused Ruff 0.17.1 passed for this follow-up. Earlier whole-tree Ruff and Mypy 2.4.0 evidence (106 source files) is retained; production source is unchanged. No ceilings changed.
- Source-baseline guard follow-up: `python -m pytest tests/compute/test_limits.py tests/docs/test_exposure_boundary_proof.py -q -m 'not slow'`: **105 passed**. The two proof-script tests verify source drift and Git errors stop execution before mutation or evidence publication. Whole-tree Black passed for 383 files; focused Ruff passed.

Local synthetic workbook evidence does not establish production-data acceptance or Office rendering. Hosted CI remains asynchronous. Capability consultation hit the sandbox-denied shared lock; PID liveness inspection was denied, while the existing dispatcher claim remained stable and matched this run. Shared audit ledger, event/workloop and automation memory are parent-owned.

<!-- pr-preamble:start -->
<!-- meta:related-issue:1160 -->
> **Source:** Issue #1160

Related to #1160

<!-- pr-preamble:end -->

<!-- auto-status-summary:start -->
## Automated Status Summary
#### Scope
Alias handling and portfolio-scope handling lose different dimensions at the exposure-to-limit boundary.

Two reproduced failures justify checking this particular seam. The audit is not jointly endorsed in its own evidence, so approval should explicitly choose a bounded inventory rather than assume consensus.

Reviewed evidence at `d816c23de06177ee239d96e37ccae306e01504a6`:

Retain this bounded audit in turn 3, while acknowledging Claude's turn-2 meta_candidate_proposal remains false: the meta is not jointly accepted. Codex candidates 1 and 2 expose two contract losses at the same parsed-exposure-to-limit boundary. Actual compute/limits.py:93 omits registered FCM/clearing-house identity; pipeline/run.py:2394 emits variant tags that limits.py:147/:268 ignore. Fresh in-memory alias and overlapping-subset probes independently reproduce both failures. In contrast, run.py:2318 preserves canonical_key and :2375 partitions concentration by variant/segment, an already-correct control. Enumerating exposure reshaping and numerical consumers can classify intentional versus accidental dimension loss and identify additional instances without assuming they exist. Neither date checking nor baseline coverage is used as support. The two per-instance fixes remain separate; absent counterpart agreement, the audit must remain a human-visible disagreement rather than silently count as converged.

Current source readback: `src/counter_risk/parsers/cprs_fcm.py:226` at `117fc794902140844ec178e015ff05a4db1bd142` (file SHA-256 `fb9e3b8c9ab063d17022ff63761414800b81c25aa5831cde3aad45cac99b79d9`). Earlier detailed line ranges and reproductions retain their reviewed-commit provenance; intervening anchor changes were checked for relevance.

#### Tasks
- [x] Inventory canonical identity and variant/segment dimensions from cprs_fcm parsing through pipeline exposure rows into compute/limits.py consumers.
- [x] Classify intentional aggregation, confirmed alias/scope losses and unknown boundaries; include the already-correct partitioned concentration path as a control.
- [x] Map the known alias and overlapping-subset instances to existing approved work, returning only uncovered gaps for human review without filing issues; target `src/counter_risk/parsers/cprs_fcm.py`.
- [x] Add the focused declared-contract regression-prevention check using alias-only and overlapping-subset probes; do not bundle production fixes; target `tests/compute/test_limits.py`.

#### Acceptance criteria
- [x] Inventory every entry within the explicitly bounded seam, recording its contract, producer/consumer, source/test evidence and confirmed, intentional or unknown disposition.
- [x] Use alias-only and overlapping-subset controls, including already-correct partitioned concentration; preserve unknowns rather than inventing defects.
- [x] Link known instances to existing owned work. Return additional findings for human review without automatic issue filing or bundled production repairs.
- [x] Run `python -m pytest tests/compute/test_limits.py -q` with nonzero collection and the named scope-specific behavior assertions passing; retain the actual command/result in the delivery evidence.
- [x] Deliberate-break gate: after adding the scope-specific regression in `tests/compute/test_limits.py`, temporarily disconnect its corresponding Scope change at `src/counter_risk/parsers/cprs_fcm.py`; that regression must fail on the described behavior. Restore the change and rerun it successfully, capturing both outcomes.

<!-- auto-status-summary:end -->


Reconciliation: reviewed `b4a55a0`, `ac2b1fe`, and `b2895ff`; all nine items verified locally. Automatic approval review again rejected publishing this body because the connector requires approval and this run uses approval policy `never`. This file is the prepared handoff body; live PR checkboxes remain unchanged.

Commit handoff: `git add` could not create `.git/index.lock` on the read-only filesystem. Verified changes remain uncommitted in the checkout.
