I'm unable to proceed because file write permissions haven't been granted. I need permission to write to the source files in order to implement the requested changes. Could you please approve the write permissions so I can continue with the implementation?

The implementation plan is:

1. **`src/counter_risk/config.py`** - Add `distribution_static: bool = False` field to `WorkflowConfig`
2. **`src/counter_risk/integrations/static_distribution.py`** (new) - Module with:
   - `make_distribution_static()` - main entry point
   - COM-based approach: export slides to images via PowerPoint COM, then replace chart/OLE shapes with static images using python-pptx
   - PDF fallback: export to PDF via COM when image-per-slide isn't feasible
   - No-COM fallback: warn clearly and still produce the non-static PPTX
3. **`src/counter_risk/pipeline/run.py`** - Add a post-processing step after `_write_outputs` that calls the static distribution logic when `distribution_static=true`
4. **`tests/integrations/test_static_distribution.py`** (new) - Tests for fallback logic when COM is unavailable
