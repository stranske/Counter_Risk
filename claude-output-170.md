I'm blocked by a fundamental permission issue: **all file write operations are being rejected** in this session. The Edit, Write, and Bash tools all refuse to modify or create files, requiring approval that isn't being granted in this automated context.

Here's what I've prepared and will implement once write permissions are available:

## Implementation Plan (Fully Designed)

### 1. `src/counter_risk/config.py` - Add config field
Add `distribution_static: bool = False` to `WorkflowConfig`, after `screenshot_inputs`.

### 2. `src/counter_risk/ppt/static_distribution.py` - New module
Contains:
- `_is_com_available()` - Checks Windows + COM availability
- `_export_chart_shapes_via_com()` - Exports chart/OLE shapes as PNG via PowerPoint COM `shape.Export()`
- `_export_pdf_via_com()` - Exports PPTX to PDF via `ExportAsFixedFormat`
- `_replace_charts_with_images_pptx()` - Uses python-pptx to remove chart shapes and insert static PNGs at the same position/size
- `make_distribution_static()` - Orchestrator with 3-tier strategy:
  1. **COM preferred**: Export chart shapes as images, replace in PPTX, export PDF
  2. **COM fallback**: If image export fails, export to PDF as deliverable
  3. **No COM**: Warn and produce non-static PPTX output

### 3. `src/counter_risk/pipeline/run.py` - Pipeline integration
In `_write_outputs`, add conditional branch: when `config.distribution_static` is True, call `make_distribution_static` instead of `_refresh_ppt_links`. The static path replaces linked charts with images and produces a PDF. When False, existing link-refresh behavior is unchanged.

### 4. `tests/test_static_distribution.py` - Tests
- Config defaults test (`distribution_static` defaults to False)
- Config accepts True test
- COM availability returns False on Linux
- Fallback warns when COM unavailable (writes warning + produces non-static output)
- File copy behavior when source != output
- Same-path handling
- Warning message content verification
- Shape type ID coverage

**All code is ready to write. The session needs file write permissions to proceed.**
