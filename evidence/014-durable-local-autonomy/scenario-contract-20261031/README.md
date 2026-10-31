# Declared API contract in SWE.6 scenarios and resource measurement

**Implementation tested and staged, not activated. The live Qwen run remains
unchanged and DF-M1 remains pending.**

Source **95250cf902afe404dc85d8337b05b98ebda77651** corrects two factory defects
observed during native01M67ETTPXS1Q73QPMQ98DNJX0/sourcea34fdd85:

- Delivery-First Robot prompts/scaffold imposed legacy register arrays and
  offset/mask macros, conflicting with the frozen typed-device-pointer API.
  This opt-in lane now refers to its declared contract, actual candidate and
  device inputs. Existing strict and prior demonstration prompts are unchanged.
- Robot flash/RAM/stack measurement omitted the selected adapter's include
  flags. The generated measurement unit could not include the declared device
  header, although the ordinary target compiler and independent verifier could.
  It now uses the same explicit adapter flags. Measurements and limits still
  execute; neither a build failure nor an over-budget object becomes PASS.

No driver names, register addresses or implementations were added to shared
measurement code. No runtime gate, authority, scheduling or model setting changed.
The active job was not patched or steered; separate source staging makes no
model call and submits no order.

## Real model observation

The [native Robot receipts](native-robot-observations.json) show 1/10 requirements
verified at00:21:21UTC, then7/10 at00:24:08 and00:29:30. Qwen repaired its own
scenario code without supplied fixes. Three resource checks still fail because
`forge_crc_device.h` is absent from the measurement compiler's include path;
the actual compiler messages are retained. Candidate SHA remains
855f53a6b3f90d83e60e03aacba50e953e9e3a2827c3730d6ae6746fff46b173.
This is job-local test correction, not proven factory self-healing, implementation
repair, promoted learning or measured benefit from this undeployed patch.

## Deterministic regressions on loop10

The prompt/scaffold regressions first failed2/3; after the prompt fix3/3 passed.
A real synthetic typed-C/Robot/Renode integration then exposed the missing
include path: both positive and negative cases failed their expected outcomes.
After the compiler fix both passed. The final six-case focused suite also adds
an actual one-byte flash limit: valid behavior passes, a wrong read assertion
fails, and an oversized measurement fails. Synthetic fixture C is never Qwen
authorship or live qualification evidence.

At the exact committed revision, the combined delivery, Robot, peripheral,
demonstration, finalizer/history, product-outcome and inherited v0.3 packager
cohort ran **88 tests:87PASS,1FAIL,0errors,0skips**. The sole failure is
`test_rcc_workflow_graphs_unchanged`: the historical Feature009 graph golden
already differs at the parent revision. An explicit [before/after comparison](inherited-strict-graph-comparison.json)
shows identical hashes for all five strict graph variants. The golden was not
rewritten, skipped or represented as passing. Ruff passes; specification and
14 static design checks pass, which is not runtime qualification.

Exact command, source and result counts are in [tested-revision.json](tested-revision.json).
Failed raw JUnit receipts are preserved as deterministic gzip, with readable
whitespace-normalized views and separate representation hashes. Counts overlap;
do not add focused and combined cohorts.

The [remote staging proof](source-stage-95250cf9.json) retains the old unused
dd36 staging and leaves current source/intent unchanged. Two existing untracked
launch records are preserved with hashes; tracked source is clean. Activation
requires terminal audit, physical inference quiescence and new exact-source-bound
qualification authority within the original07:57:59UTC deadline.

Traceability: supports DF-T005/006/007 and DF-AT-007/008 through correct declared
adapter use; no original DA task checkbox changes. DF-M1, fresh repeatability,
full LL/HAL success, release qualification, learning benefit and operational
availability remain separate and unproven at this checkpoint.
