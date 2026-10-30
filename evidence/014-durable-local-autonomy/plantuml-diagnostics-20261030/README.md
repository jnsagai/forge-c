# PlantUML feedback scope and failing-view diagnostics

Native `01M67ETTPXS1Q73QPMQ98DNJX0` at clean `a34fdd85` made nine
PlantUML validation calls, including four calls with debug-file paths. Each
received the same generic syntax failure. The existing operation always checks
the two canonical architecture views, irrespective of the requested path. This
made the scope of the reported failure ambiguous. The retained native tool
feedback contains no prompts, hidden reasoning, manual contents or credentials.

The shared checker now checks syntax per canonical view and names the failing
file. Its complete semantic checks and strict FAIL behavior remain. The MCP
response explicitly identifies the canonical-view scope, requested path, actual
static/dynamic paths and each syntax outcome. A debug path cannot be mistaken
for a validated diagram. No acceptance rule or release gate was relaxed.

Three focused regressions failed before the change: each canonical failure
lacked its file name, and debug-path feedback did not disclose the real scope.
Afterwards all three pass; the inherited real PlantUML valid/render/broken-view
test also passed. The broader cohort has58PASS/one disabled live Fabro skip,
zero failures/errors. Counts overlap; do not add cohorts. Lint and source diff
checks pass. Source-specific post-commit evidence is recorded separately.

```text
python -m pytest factory/python/tests/test_plantuml_diagnostics.py -q
python -m pytest factory/python/tests/test_plantuml_diagnostics.py factory/python/tests/test_reqif_plantuml.py -q
python -m pytest factory/python/tests/test_plantuml_diagnostics.py factory/python/tests/test_reqif_plantuml.py factory/python/tests/test_swe2_architecture.py factory/python/tests/test_m2_mcp.py factory/python/tests/test_pipeline_demonstration.py factory/python/tests/test_delivery_first.py -q
python -m ruff check factory/python/forge_factory/inspection/views.py factory/python/forge_factory/mcp/servers/docs.py factory/python/tests/test_plantuml_diagnostics.py
python specs/014-durable-local-autonomy/validate_spec.py
```

All deterministic tests ran locally on loop10 with the pinned Python,
compiler and simulator environment. No Qwen inference ran locally. Specification
validation is SPEC_CONTRACTS_ONLY_NOT_RUNTIME. The active remote run was not
patched, steered or supplied any changed artifact. Its original tool failures
remain; this fix has **NOT_DEPLOYED / NO_MEASURED_MODEL_BENEFIT** status.
