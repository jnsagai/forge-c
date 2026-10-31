# Preserve constraints in the schema actually served by MCP

> Later activation: the qualified bootstrap is now deployed as sourcec1f1378 in the
> [focused continuation](../afo-focused-continuation-20261029/README.md).
> The NOT_DEPLOYED statements below describe the preserved earlier checkpoint.

Source **6cd238088b84ec67df3b59e88a22b6576e0d9412** fixes a broker-contract mismatch:
`build_server` constructed callable annotations/signatures from bare field types,
dropping Pydantic FieldInfo. The actual native submit_candidate schema exposed
three strings with no minLength/maxLength, although SDK invocation enforced those
limits. Qwen's V4 summaries956/371characters were rejected at a300character bound;
its annotated reproducer paths also exceeded the declared200character limit.
This does not establish that the schema bug alone caused the model's choices.

The existing SDK now retains FieldInfo in both annotations and callable signatures.
Bounds, descriptions, nested models, defaults/factories and enums survive MCP
argument-model construction. Existing broker validation, policy/tickets and role
permissions remain. Maintainer submission fields describe the compact summary,
plain relative .py path and exact symptom signature. No field is silently clipped
or converted into a valid proposal. Invalid native calls are rejected before the
broker runs; a300character boundary summary reaches it unchanged in the test.

Three focused tests inspect actual `MCPServer.list_tools()` schemas and exercise
`call_tool`, rather than checking a source Pydantic class in isolation:

- Unchanged source:3FAIL/0ERROR, recording missing bounds, missing list constraints
  and an overlong summary reaching the broker stub.
- Fixed exact source: **73PASS/1explicit SKIP**,74cases across SDK, existing MCP,
  maintainer, pagination and native-endpoint regressions, zero failures/errors. The
  skip is the live Fabro test, disabled for this deterministic local cohort.
- The3focused cases also pass after final formatting/import normalization. Ruff
  and14static design checks pass; static checks are not runtime qualification.

The original native schema probe is retained and made zero generation calls.
The native corrected-source test command is prepared with one CPU,1GiB address
space,45CPU-seconds/60wall-seconds, network off and no GPU devices. It refuses to
start while inference or an existing CRE verification worker owns capacity.
**Exact corrected native6cd2380 qualification:3PASS**, zero errors/failures, with no model calls or production change. [Native provenance](native-qualified/provenance.json) records the command and bounds. This SDK fix
is **NOT_DEPLOYED** into the running Qwen trial; Omniverse2 remains on92c49a6 and
its exact signed role identity. No production source was hot-edited or rebound.

This is an external implementation change, not a Qwen-authored repair and not
proof of self-healing. The retained-artifact Qwen trial and independent correctness
results are tracked separately in the sibling afo-brownfield-repair evidence.
