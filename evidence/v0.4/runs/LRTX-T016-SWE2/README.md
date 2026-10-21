# LRTX-T016 — fresh local SWE.2 author trials (qwen3-coder:30b)

No local work order has passed the local SWE.1 inspection, so SWE.2 never ran inside a local work order (LRTX-TRIAL,
lrtx1–lrtxq2). The structured SWE.2 author is therefore measured on its own:
- **Start:** copies of the READY rc1 IWDG LL work order (WO-0009A-STM32N6-IWDG-LL-rc1), whose SWE.1 baseline the
  Claude inspector passed.
- **Each attempt:** removes only the SWE.2 authorship from its copy, runs the real structured SWE.2 visit (interfaces
  task, then design task) and freezes the result through the unchanged SWE.2 author gate.
- **Command:** `python -m forge_factory.lrtx.modelcmp --phase SWE.2 --model qwen3-coder:30b --repeat 3`, run inside
  the profile namespace.
- **Start copy:** never written. Its tree hash is unchanged after both trials (`start-workspace.tree.sha256`,
  `3e77b745…`).

| Trial | Factory | Record | Visits PASS / frozen by the gate | Median calls | Median wall time |
|---|---|---|---|---|---|
| 1 | 2c0c739 | `20261021T211223.*`, `modelcmp-report-trial1.json` | 0/3 / 0/3 | 3 | 236 s |
| 2 | 184f17c (pd-5a91e536) | `20261021T213259.*`, `modelcmp-report-trial2.json` | **1/3 / 1/3** | 3 | 274 s |

**Trial 1:**
- The frozen SWE.1 requirements SWR-011/012 name `LL_IWDG_IsEnabled`. In every attempt the interfaces task defined
  `LL_IWDG_IsActive` instead and kept it through both repairs.
- The validator's finding was correct but did not say what to change.
- **Factory defect, fixed in 7afa77d (pd-5a91e536):** the finding now says to define the required name, rename the
  other function and allocate the SWR to it.

**Trial 2:**
- **Attempt 2:** renamed after one repair (7 -> 0 findings). The design task was valid at once, and the unchanged
  SWE.2 author gate froze BL-SWE.2-001 (`trial2-frozen-swe2/`). This is the first local SWE.2 work product accepted by
  the gate.
- **Attempts 1 and 3:** kept `LL_IWDG_IsActive` despite the explicit instruction (13 -> 2 -> 2 and 7 -> 2 -> 2
  findings). That is model quality.
  - The repair extension only applies while findings fall, so these visits ended after 3 calls.

**What is not measured here:**
- The local SWE.2 inspection.
- SWE.3 and later phases with the local model inside a work order.

The SWE.3–SWE.6 structured tasks are covered by scripted-model tests against the real tools (T022).
