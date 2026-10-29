# Prepared AFO maintenance trial

**F014-AFO-MCP-ROOT-REPAIR-20261029: PREPARED, NOT ENROLLED, NOT RUN.**
No Qwen request, order, grant, restart or deployment was made. Owner STOPPED
epoch33 remains effective. No feature task is newly complete.

Replay the actual historical SWE.3 MCP context failure in an isolated candidate
based on `9b4c390e1605d11c4865bdeea382df74a0078692`. Original failures remain
failures; this is not a new natural outage. The controller is CPU-qualified
`3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6`, not deployed.

Use existing AFO maintenance, Conductor, shared mission ledger, maintainer broker,
VerificationJobs and CAPA/CRE. Qwen3.8-27B Q8_0, MTP draft3, xhigh, one inference,
one candidate and one bounded verifier. Strict QM/MTP profile v3 provides131072
maintenance tokens. The old demonstration profile explicitly defers maintenance;
do not edit its frozen policy or reuse it for this trial.

Qwen receives only `model-input/` and isolated baseline source through scoped
maintenance MCP. It must diagnose, patch and submit its own baseline-failing
reproducer. Candidate edits are limited to
`factory/python/forge_factory/fabro/runconfig.py` and
`factory/python/tests/afo_candidate/**`; independently enforce this narrower
trial scope in addition to the existing global allowlist.

Keep the reference revision/patch, frozen verifier and operator files outside
model inputs. Do not mount this entire packet or allow controller shell/git access.
Factory-code routing is deterministic; maintenance performs the diagnosis here.
No separate planner qualification is claimed.

## Measured preparation

- Frozen external checker on historical source: **2 FAIL**, exit1.
- Same checker on corrected reference: **2 PASS**, exit0.
- Actual bubblewrap smoke: **PASS** for read-only source, writable scratch,
  hidden synthetic private canary and absent GPU devices. Namespace UID2003
  does not establish a separate host UID. No real credential was probed.
- Private native V2 archive copied to loop10: **1488 listed files**, every
  hash/size verified. Four unlisted pytest directory symlinks were not extracted;
  the original archive is retained. See [review](review.json).

[Manifest](preparation.json) records commands, exact source/profile/model bindings,
mission charges and blockers. JUnit/logs are under `operator/`. The frozen checker
uses a labelled location-only dummy JAR; it tests generated MCP/hook environment
resolution, not actual rendering. Actual diagram rendering was separately checked
in the preceding native CPU qualification. The V1 sandbox smoke is separate from
the V2 preparation inventory. `inventory.json` binds the full private native packet,
not just Git's published subset.

Executable helper: `factory/qualification/014/prepare_afo_repair.py --help`.
The exact tested copy is under `scripts/`. It requires a new private output path,
the original mission, historical source and a stopped/quiescent snapshot; exports
Git-pinned controls; and checks actual subprocess/JUnit results. It never enrols,
authorizes or launches work. The snapshots are preparation evidence, not a future
live admission check.

## Before live execution

1. Bind a fresh finite window. Proposed duration is14400seconds, unsigned.
   Prior authority ends2026-10-29 at18:05:39UTC; it is not renewed here. Preserve
   `F014-IDR-M1-HIGH-20261028`: four attempts,345requests,596tools,400m conservative
   charged tokens and UNKNOWN aggregate actual usage.
2. Prepare exact primary and maintenance product-role trial records binding
   controller, profile, model, mission, order, operator intent and finite limits.
   These signing payloads are **not created by this helper**. Recheck current
   authority before using the applicable existing signing delegation.
3. Recheck resources and perform actual allocation/native maintenance preflight.
   The snapshot had49140MiB GPU total,26982used,21519free, below Q8 weights plus
   KV needs. Do not terminate another account's work or assume allocation passed.
4. Obtain newer explicit RUNNING intent through existing fenced startup.
   Current STOPPED intent wins over older approvals. No18:00 restart is scheduled.
5. Factually settle the original stopped parent before single-order intake.
   Its job is blocked OPERATOR_SHUTDOWN and native execution quiescent/released;
   the parent remained RUNNING. Preserve history and charges; do not reset them.
6. Enrol one neutral role-only AFO wrapper using existing Store admission, shared
   mission lineage and immutable non-demo workspace/product-role binding before
   any maintenance reservation. Neutral qualification admission creates no product
   launch outbox and needs no invented SWE failure. Perform this authority-bound
   setup while Conductor is inactive, using its existing lease/intent fences;
   its normal maintenance sweep must own execution afterward. **An automated
   enrol/start command is not supplied by this preparation.** Do not substitute
   the planner-only protocol qualification runner for maintenance admission.
7. Collect Qwen's actual patch, reproducer, durable receipt, request/tool records,
   native quiescence and cumulative charges. Independently run the frozen checker
   on the candidate, narrow-scope checks, existing veto, regression and CRE
   holdouts. Record factual learning disposition, without inventing an incident.
   Copy live outcomes to local loop10 for inspection.

Success means an **independently verified Qwen-authored factory repair candidate**.
Automatic deployment, original driver recovery, M1 acceptance, general role
qualification, learning benefit and24/7 availability remain separate and unproven.
Existing external promotion remains required; do not auto-activate a patch.
