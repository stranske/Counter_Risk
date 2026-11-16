# Issue #1248 linked PPT refresh deliberate-break evidence

Regression: `tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed`

Production behavior lives in `src/counter_risk/pipeline/run.py` inside `_refresh_ppt_links`
(per-shape `LinkFormat.Update` failure collection for required linked shapes).

## Procedure

1. Run the named pytest on unmodified branch `cursor/issue-1248` at HEAD.
2. Temporarily restore tolerant `except Exception: continue` around `shape.LinkFormat.Update()`
   (drops per-shape failure collection; refresh returns `SUCCESS` when a required linked shape fails).
3. Re-run the identical pytest command; capture the expected failure.
4. Restore production handling and re-run; capture pass.
5. Record literal transcripts below.

Executed on branch `cursor/issue-1248` with Python 3.14.10 (re-verified keepalive 2026-11-16 UTC: hollow `except Exception: continue` at HEAD → named test FAILED with SUCCESS vs FAILED assertion; production handler restored → 1 passed; full file 17 passed; `test_run_link_refresh_failures.py` 5 passed; `scripts/check_deliberate_break.py --base 8ed8630^ --pr-body-file docs/evidence/issue-1248/reconciled-pr-body.md` → `verdict: PASS`, `reason: head-passed-base-failed`).

## RED — failure collection deliberately disabled

Temporary mutation in `src/counter_risk/pipeline/run.py`:

```diff
                 try:
                     shape.LinkFormat.Update()
                     updated += 1
-                except Exception as exc:
-                    if is_required:
-                        shape_name = getattr(shape, "Name", "<unknown>")
-                        linked_update_failures.append(
-                            "slide="
-                            f"{slide_index} shape={shape_name!r} source={source!r} error={exc}"
-                        )
-                    continue
+                except Exception:
+                    continue
```

Command:

```console
$ python3 -m pytest tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed -q
```

Result (exit code 1): **FAILED**

```text
FAILED tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed
AssertionError: assert <PptProcessingStatus.SUCCESS: 'success'> == <PptProcessingStatus.FAILED: 'failed'>
======================== 1 failed, 13 warnings in 0.19s ========================
```

Linked Chart B update error was swallowed; refresh incorrectly reported success.

## GREEN — production handling restored

Command:

```console
$ python3 -m pytest tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed -q
```

Result (exit code 0): **1 passed**

```text
tests/unit/test_refresh_ppt_links_errors.py .                            [100%]
======================== 1 passed, 13 warnings in 0.17s ========================
```

Refresh returns `FAILED` with `required linked shape update failed:` prefix and slide/shape/source context.

Production source bytes restored unchanged after the deliberate break.

<!-- deliberate-break: test=tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed test-file=tests/unit/test_refresh_ppt_links_errors.py break-file=src/counter_risk/pipeline/run.py -->