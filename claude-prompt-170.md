## Keepalive Next Task

Your objective is to satisfy the **Acceptance Criteria** by completing each **Task** within the defined **Scope**.

**This round you MUST:**
1. Implement actual code or test changes that advance at least one incomplete task toward acceptance.
2. Commit meaningful source code (.py, .yml, .js, etc.)—not just status/docs updates.
3. Mark a task checkbox complete ONLY after verifying the implementation works.
4. Focus on the FIRST unchecked task unless blocked, then move to the next.

**Guidelines:**
- Keep edits scoped to the current task rather than reshaping the entire PR.
- Use repository instructions, conventions, and tests to validate work.
- Prefer small, reviewable commits; leave clear notes when follow-up is required.
- Do NOT work on unrelated improvements until all PR tasks are complete.

## Pre-Commit Formatting Gate (Black)

Before you commit or push any Python (`.py`) changes, you MUST:
1. Run Black to format the relevant files (line length 100).
2. Verify formatting passes CI by running:
   `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
3. If the check fails, do NOT commit/push; format again until it passes.

**COVERAGE TASKS - SPECIAL RULES:**
If a task mentions "coverage" or a percentage target (e.g., "≥95%", "to 95%"), you MUST:
1. After adding tests, run TARGETED coverage verification to avoid timeouts:
   - For a specific script like `scripts/foo.py`, run:
     `pytest tests/scripts/test_foo.py --cov=scripts/foo --cov-report=term-missing -m "not slow"`
   - If no matching test file exists, run:
     `pytest tests/ --cov=scripts/foo --cov-report=term-missing -m "not slow" -x`
2. Find the specific script in the coverage output table
3. Verify the `Cover` column shows the target percentage or higher
4. Only mark the task complete if the actual coverage meets the target
5. If coverage is below target, add more tests until it meets the target

IMPORTANT: Always use `-m "not slow"` to skip slow integration tests that may timeout.
IMPORTANT: Use targeted `--cov=scripts/specific_module` instead of `--cov=scripts` for faster feedback.

A coverage task is NOT complete just because you added tests. It is complete ONLY when the coverage command output confirms the target is met.

**The Tasks and Acceptance Criteria are provided in the appendix below.** Work through them in order.

## Run context
---
## PR Tasks and Acceptance Criteria

**Progress:** 0/9 tasks complete, 9 remaining

### ⚠️ IMPORTANT: Task Reconciliation Required

The previous iteration changed **1 file(s)** but did not update task checkboxes.

**Before continuing, you MUST:**
1. Review the recent commits to understand what was changed
2. Determine which task checkboxes should be marked complete
3. Update the PR body to check off completed tasks
4. Then continue with remaining tasks

_Failure to update checkboxes means progress is not being tracked properly._

### Scope
Non-technical recipients shouldn’t deal with OLE link prompts or Office “Update Links” dialogs. A static deliverable is the boring kind of reliable.

### Tasks
Complete these in order. Mark checkbox done ONLY after implementation is verified:

- [ ] Add a pipeline output mode: `distribution_static=true`
- [ ] Implement chart-to-image conversion strategy:
- [ ] Preferred: PowerPoint COM export slide(s) to images, then reinsert images (Windows-only)
- [ ] Fallback: export entire PPT to PDF (COM), keep PDF as deliverable, note limitations
- [ ] Replace embedded chart shapes with images while keeping titles/positions stable
- [ ] Add tests for fallback logic when COM not available (writes a clear warning + still produces non-static outputs)

### Acceptance Criteria
The PR is complete when ALL of these are satisfied:

- [ ] Distribution PPT opens with no link update prompts
- [ ] Distribution PPT retains slide count and basic layout
- [ ] If PDF export is enabled and COM available, a PDF is produced in the run folder

### Recently Attempted Tasks
Avoid repeating these unless a task needs explicit follow-up:

- Replace embedded chart shapes with images while keeping titles/positions stable
- Add tests for fallback logic when COM not available (writes a clear warning + still produces non-static outputs)
- Add a pipeline output mode: `distribution_static=true`

### Suggested Next Task
- Add a pipeline output mode: `distribution_static=true`

---
