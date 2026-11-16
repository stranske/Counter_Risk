# Issue #1248 linked PPT refresh deliberate-break evidence

Regression: `tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed`

Production behavior lives in `src/counter_risk/pipeline/run.py` inside `_refresh_ppt_links`
(per-shape `LinkFormat.Update` failure collection for required linked shapes).

## Procedure

1. Run the named pytest on unmodified branch `cursor/issue-1248` at `00e882d`.
2. Temporarily restore tolerant `except Exception: continue` around `shape.LinkFormat.Update()`
   (drops per-shape failure collection; refresh returns `SUCCESS` when a required linked shape fails).
3. Re-run the identical pytest command; capture the expected failure.
4. Restore production handling and re-run; capture pass.
5. Record literal transcripts below.

Executed from commit `00e882d6306cb2328798d2344eaa7747b25913b8` with Python 3.14.10.

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

Result: **FAILED** — `AssertionError: assert PptProcessingStatus.SUCCESS == PptProcessingStatus.FAILED`
(linked Chart B update error was swallowed; refresh incorrectly reported success).

## GREEN — production handling restored

Command:

```console
$ python3 -m pytest tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed -q
```

Result: **1 passed** — refresh returns `FAILED` with slide/shape/source context.

Production source bytes restored unchanged after the deliberate break.

<!-- deliberate-break: test=tests/unit/test_refresh_ppt_links_errors.py::test_failed_required_linked_shape_update_returns_failed, test-file=tests/unit/test_refresh_ppt_links_errors.py, break-file=src/counter_risk/pipeline/run.py -->