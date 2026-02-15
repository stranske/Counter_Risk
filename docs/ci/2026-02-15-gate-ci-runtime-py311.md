# Counter_Risk CI performance note (2026-02-15)

## Summary (what the data says)

Recent measurements of Counter_Risk GitHub Actions runs show that **Gate and CI runtime is dominated by pytest execution time**, not dependency installation or caching.

- **Gate → “Python CI / python 3.11”** (sample n=29)
  - avg: **~7m47s**
  - p50: **~10m05s**
  - p90: **~16m02s**
- **CI → “Python CI / python 3.11”** (sample n=22)
  - avg: **~8m47s**
  - p50: **~9m18s**
  - p90: **~10m10s**

In step-level timing for representative Gate runs, the bottleneck is consistently:

- **“Pytest (unit tests with coverage)”**: **~9m47s–10m41s** of a **~10–11 minute** job
- **“Install dependencies”**: typically **~seconds** (not the dominant factor)

This explains why prior “speed” changes focused on install/caching did not significantly reduce end-to-end Gate time.

## Relevant recent workflow work (context)

### Workflows repo (shared reusable workflow)

Recent Workflows changes that affect consumers (including Counter_Risk):

- **Workflows PR #1502**: reduced implicit / heavyweight baseline dependency behavior in the reusable Python CI.
- **Workflows PR #1508**: added a `pytest_args` input wiring so callers can pass sharding/scoping flags to pytest.
- **Workflows PR #1518**: ensured CI honors `.github/workflows/autofix-versions.env` even when `requirements.lock` exists.

Net: installs are now more predictable, and the reusable workflow has a hook (`pytest_args`) for test sharding/scoping.

### Counter_Risk repo

- **Counter_Risk PR #125**: reduced duplicate CI runs (CI not on PR trigger) and simplified PR Gate matrix to python 3.11.

Net: this helped total compute cost by removing redundant jobs, but **did not reduce the single-job runtime** because pytest is still the critical path.

## Why runtime is still ~10 minutes

- The pytest+coverage step dominates total time.
- Improvements to dependency installation and caching are valuable (correctness + avoiding tool drift), but they do not move the needle when installs are already fast.

## What to do next (options)

There are only a few levers that materially reduce a job where tests dominate:

1. **Scope PR Gate tests** (fast subset), keep **full suite on main**
   - Use the reusable workflow’s `pytest_args` input to run a smaller, high-signal subset on PRs.
   - Full suite runs on `push` to `main` and/or nightly.

2. **Shard tests across multiple jobs** (parallelize at the workflow level)
   - Split into 2–4 shards using `pytest_args` (e.g., via `pytest -k`/markers, or a split plugin).
   - This reduces wall time but increases total compute; works best if shards are balanced.

3. **Remove or reduce coverage on PR Gate** (if policy allows)
   - Coverage adds overhead; if the goal of Gate is fast feedback, consider running coverage only on main.

4. **Profile and fix the slow tests** (best long-term)
   - Add `--durations=25` to identify slow tests.
   - Optimize I/O-heavy tests (xlsx parsing, file comparisons, external tool calls) or refactor fixtures.

## Recommendation (minimum-risk change)

If we want a tangible Gate wall-time reduction without weakening main-branch confidence:

- **PR Gate**: run a targeted subset using `pytest_args` (fast feedback)
- **Main CI**: run full suite + coverage

This keeps correctness guarantees where they matter (main) while keeping PR iteration loops tight.

## Reproducing the measurements

If you want to re-run the same style of analysis:

- Pull recent runs for Gate and CI via the Actions API.
- For a few representative slow runs, inspect job step durations and confirm pytest dominates.

(These were computed using `gh api` calls against workflow runs/jobs and summarizing durations locally.)
