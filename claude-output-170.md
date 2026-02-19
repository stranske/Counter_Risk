I'm unable to proceed because file write permissions haven't been granted. I need permission to modify the source files in `src/counter_risk/` and create test files in `tests/` to implement the required changes.

The implementation plan is:

1. **`src/counter_risk/config.py`** - Add `distribution_static: bool = False` field to `WorkflowConfig`

2. **`src/counter_risk/distribution/__init__.py`** + **`src/counter_risk/distribution/static_pptx.py`** - New module that:
   - Uses python-pptx to find chart shapes (`shape.has_chart`)
   - On Windows with COM: exports slides containing charts to images via PowerPoint COM, then replaces chart shapes with picture shapes at the same position/size
   - Fallback (no COM): exports entire PPT to PDF via COM if available; if not, logs a warning and produces the non-static PPT unchanged
   - Handles the static output file naming (`*-static.pptx`)

3. **`src/counter_risk/pipeline/run.py`** - After `_write_outputs`, if `config.distribution_static` is True, call the distribution module to produce static variant

4. **`tests/test_distribution_static.py`** - Tests for:
   - Config flag acceptance
   - Chart shape replacement logic
   - Fallback warning when COM unavailable
   - Non-static outputs still produced when COM unavailable

Could you grant write permissions so I can proceed with the implementation?
