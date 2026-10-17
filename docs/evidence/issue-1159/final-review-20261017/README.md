# Final review corrections for PR #1169

Both review findings are valid. Reporting snapshots now load a formula-preserving
view and freeze a formula only when its cached result is not None. Uncached
formulas remain available to Excel, including outside Repo/FCM. Zero and string
caches (including strings beginning with `=`), unrelated literals, and source
workbook bytes have focused coverage.

The cash mutation verifier now reads the JUnit failure `message` attribute,
never traceback text. The pipeline test checks authoritative cash before path
containment and recognizes both the original workbook and adjusted snapshot.
`cash-mutation/` is a retained insufficient attempt: after merely moving the
assertion, the original filename bypassed the cash check and failed containment.
The corrected oracle rejected it. Its raw evidence is retained unchanged.
`cash-mutation-confirmed/` contains the initial cash-specific RED/restored GREEN.
`cash-mutation-final/` repeats that proof against the final source preserving cached cell types.
`formula-mutation/` independently restores cached-only production loading to
prove the uncached-formula regression fails, then restores production bytes.
Each proof records actual argv/cwd and production/test hashes, raw JUnit/log
hashes, and byte-identical production restoration.

All pre-existing raw XML/log evidence is immutable. The historical
pipeline-break-proof.json and its earlier source-text-based conclusion are not
cash-specific proof; the new confirmed proof supersedes that claim without
rewriting the historical files.

Native Excel/PowerPoint execution remains UNKNOWN. OFFICE_HANDOFF.md remains
the executable handoff; no waiver or source acceptance is implied. Uncached
formulas require Excel to evaluate them; this portable proof establishes their
preservation, not Office recalculation. Existing row-insertion behavior and
uncached formula-reference translation remain outside this bounded repair.
