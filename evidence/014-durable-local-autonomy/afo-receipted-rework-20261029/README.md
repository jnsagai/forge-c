# Qwen V7 receipt-bound repair: independently correct within the frozen scope

Runtime **f9e7f54b1838be2560d00117c1725f8d1d74d4c8**, RUNNING epoch48.
Actual local Qwen3.8 Q8_0/f16/MTP3/xhigh,262144context, one inference on Omniverse2.
Order afo-dba0cf206b8b0f2b; job afo-agent-64eb264a0be0ab8584ea42da;
native **01M64Z8NA11GPWQP2DEKEQW3G4** completed **25requests/766152reported
tokens**, native SUCCEEDED, all requests and execution QUIESCENT, capacity RELEASED.

Qwen submitted candidate **375a12950d45b6ce2ae54d32fc559118a798f1ff** with durable
receipt SHA **9ff1b8f8aef1a7da5a20215e41460f76d3eeed5ea7f128ba06f70493f96627ec**.
The three exact Git/native/receipt-bound files, raw commit and provenance are in
[terminal/submitted-artifacts](terminal/submitted-artifacts). The controller seeded
the previous Qwen candidate; Qwen authored the engineering changes. No reference
repair or frozen grader was supplied. Prior failures and charges remain.

Independent results:

- Frozen external oracle **2PASS/0FAIL**, after native quiescence.
- Original two real diagram inputs: baseline both PLANTUML_NOT_AVAILABLE;
  candidate renders both SVGs. Scoped historical path recovery is measured.
- Causal runner: unchanged baseline exit1/SYMPTOM_PRESENT; candidate
  exit0/SYMPTOM_ABSENT. CRE **ELIGIBLE_FOR_OFFLINE_REVIEW**, decision
  **pd-8945c1b48fdc257c0348**, all hard gates pass.
- Full original SWE.3 replay **FAIL_OR_INCOMPLETE**. Both baseline and candidate
  retain two CODE:TRACE_MAP_FUNCTION_NOT_IN_SCOPE findings for LL_CRC_Write_IDR
  and LL_CRC_Read_IDR. Product-versus-replay-context origin remains unresolved.
- Optional proposal publication raised MaintainerDenied after CRE eligibility.
  Current old worker reports review_state BLOCKED; eligibility is independently
  preserved in CRE. Local proposal branch exists, veto empty, allow_proposal_pr
  true. Exact transport failure code was not saved; its cause is unresolved.
  No candidate deployment/merge is claimed.

The frozen scope does not qualify every current runconfig behavior, model role,
complete driver, learning benefit or availability. Preserve current controller
quoting of Python executable/PYTHONPATH when considering integration; do not
replace the entire current file with this historical-base candidate. Golden
19.4s to20.1s is n=1 informational, not measured benefit.

Same mission F014-IDR-M1-HIGH-20261028 and30Oct02:40:24UTC expiry; no new time
extension or allowance refill. Cumulative checkpoint:4product attempts,7maintenance
jobs,441requests,596ledger tools,406131072conservatively charged tokens;
usage UNKNOWN remains. Native maintenance tool events are not fully represented
by the historical tool count. [Terminal observations](terminal) preserve actual
facts separately from claim limits.

External trial preparation means this is not end-to-end unattended self-healing.
The bounded same-order retained-rework implementation is separately qualified in
[maintenance-rework-20261030](../maintenance-rework-20261030/README.md); it is not
retroactive proof that V7 used that loop. Full ASPICE LL/HAL NOT_RUN, learning
benefit and24/72/168-hour availability unproven. Formal Feature01430/58 unchanged.

The existing recorder publishes every300seconds on
[the progress branch](https://github.com/jnsagai/forge-c/tree/overnight/2026-10-29-local-qwen-afo),
preserving V6 history; recorder expiry does not stop factory supervision.
