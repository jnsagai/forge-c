# Bounded ST3 diagnosis on Omniverse2 — 2026-10-27

The owner asked to use remote Qwen to advance work while local tests ran. This
**external engineering study** made three serial structured requests through the
existing isolated local gateway/GPU queue, on source `9a88fbc`. It was not an AFO
recovery campaign, inspector calibration, driver retry or production activation.

[Measured evidence](summary.json): 15,803 prompt tokens, 3,498 output tokens;
24.004 seconds of request wall time, 144.122 seconds elapsed including queue and
repartition. The initial complete-context refusal cost no additional model call;
the continuation retained the first call and the original three-call/ten-minute
limit. Complete requested register groups (all sibling fields for RMW analysis),
full request/result and source hashes replaced an oversized packet. No required
field of the scoped register obligation was truncated.

Two responses passed reference checks; LPTIM's included a nonexistent diagnostic
ID and failed that check. Reference validity is not semantic correctness. The
pinned SafeC engine independently tested four selected suggestions:

- WWDG `write_field(WDGA, 1)`: UNSUPPORTED / RIO-ACCESS-UNSUPPORTED.
- WWDG `write_field(T, 127)`: UNSUPPORTED / RIO-RMW-SIDE-EFFECT.
- RNG `write_field(CONDRST, 1)`: UNSUPPORTED / RIO-RMW-SIDE-EFFECT.
- LPTIM `read_field(DIEROK)`: PASS for this isolated operation only; it does not
  satisfy a request to clear a status flag or establish complete driver correctness.

Useful next engineering work is to reproduce the unsupported access/RMW cases
against the frozen RM/domain and design a scoped, independently verified semantic
extension. Merely changing an action name or in-range value does not resolve the
profile limit. Removing requirements, changing HSI or assuming hardware behavior
from model prose is not an accepted repair. Engine/profile changes require their
external engineering boundary and new qualification; no gate was relaxed here.

Existing LessonStore experience/disposition APIs retained eight factual outcomes:
seven DEFERRED_BUDGET and one NO_NEW_LESSON. No candidate was qualified, exposed,
applied or promoted; no repair incident was invented. Study records are excluded
from lesson distillation (`evaluation_holdout` exclusion metadata); these previously
seen cases are **not** a newly frozen held-out inspector cohort. No learning-benefit,
self-healing or product-success claim follows.

Raw model prose, prompts, vendor/domain contents and engine artifacts remain private
under the study output on Omniverse2 and loop10. The summary publishes hashes and
codes only. The original three BLOCKED pilot runs and all expenditure remain intact.
Inspector development stays frozen. No Feature 014 task checkbox changes.
