I'm unable to make progress on the implementation because the Claude Code session doesn't have file write permissions. Every approach I've tried — Edit tool, Write tool, Bash with Python scripts, sed, git apply — is blocked by the sandbox permission system with "requires approval" or "permissions not granted yet."

**What was accomplished this iteration:**
- Reviewed all recent commits: confirmed no source code changes have been made (only `claude-output-170.md` and `claude-prompt-170.md` modified)
- Confirmed all 9 PR task checkboxes are correctly unchecked (no reconciliation needed)
- Thoroughly analyzed the codebase structure and identified all files that need changes

**Implementation plan ready to execute once permissions are granted:**

1. **`src/counter_risk/config.py`** — Add `distribution_static: bool = False` to `WorkflowConfig`

2. **`src/counter_risk/integrations/distribution_static.py`** — New module implementing:
   - `make_distribution_static(pptx_path, run_dir)` → `DistributionStaticResult`
   - **Preferred (COM)**: Export slides with charts to PNG images via `Slide.Export()`, then use python-pptx + Pillow to crop each chart shape's bounding box from the slide image, remove the chart/OLE shape, and insert a picture at the same position/size
   - **Fallback (COM, no image export)**: Export entire PPT to PDF via `Presentation.SaveAs(path, 32)`  
   - **No COM**: Log warning, skip static conversion, return non-static output

3. **`src/counter_risk/pipeline/run.py`** — After `_write_outputs`, if `config.distribution_static is True`, call `make_distribution_static` on the output PPT

4. **`tests/integrations/test_distribution_static.py`** — Tests for:
   - Config flag acceptance (default False)
   - Chart shape detection using python-pptx
   - Fallback logic when COM unavailable (warning + non-static outputs still produced)
   - PDF export path when COM available but image export fails

5. **`src/counter_risk/integrations/__init__.py`** — Export new symbols
