# Qwen AFO native maximum context — 29 October 2026

Runtime **92c49a6adde181737af19bb32a5efbd2130e9cd4** is active on Omniverse2.
The installed model metadata reports `qwen35.context_length=262144` for the pinned
Qwen3.8 alias, 27.3B Q8_0 GGUF. The new prospective maintenance profile
`local-rtx-v2-omniverse2-q38-afo-max-mtp` sets the provider, Fabro and role trial to
**262144 tokens**, retains f16 KV, MTP3, xhigh and one inference slot, and uses
1024/512 batch/microbatch sizes. Actual allocation reports262144/one slot and all
four services healthy, with46608MiB used and1893MiB free GPU memory. This is an
allocation check, not a local-model capability qualification.

## Why the preceding trial stopped

Native run `01M64QNGNT3VAEYGHBBBDATFK3`, source979dcb4, used the new32768-character
pages and200-call allowance. Qwen read the incident, runconfig, common, the first
swtrace page and two further files. Its fifth request was refused before upstream:
**89824 conservative input tokens +49152 output cap >131072 context**. The input
measurement is the complete canonical request's UTF-8 byte upper bound, not an
actual tokenizer count. Three refusals of the identical body are preserved.
Four admitted requests completed; reported total47792 tokens. No source edits,
reproducer or candidate submission occurred. Native traversal success is not task
success: the durable job is FAILED_PROTOCOL for the missing maintenance receipt,
independently QUIESCENT/RELEASED. Its wrapper was subsequently settled BLOCKED with
`SERIALIZED_CONTEXT_CAPABILITY_LIMIT_NO_CANDIDATE`. No old job was revived/refilled.

## Checks and activation

- Local:37PASS, zero failures/errors/skips on exact runtime92c49a6.
- Native:36PASS and one inherited product-preparation setup ERROR. First the
  isolated checkout lacked ignored reference documents; seven existing inputs
  were then copied with recorded hashes. The remaining setup error is
  `DELIVERY_BUILD_NOT_RUN`: no `arm-none-eabi-gcc` in the native test environment.
  Both full native XML/logs are retained. No test was relaxed or reported passing.
- The actual generated provider command/Fabro configuration agree on262144,
  Q8/f16/MTP3/xhigh and one slot. The prior89824+49152 refusal is reproduced at
  131072 and admitted only in the separately signed262144 experiment; over-limit
  requests and changed allocation evidence remain refused.
- Static design14PASS and RuffPASS are separate from live qualification.
- Owner explicitly requested the maximum context and previously delegated exact
  development signing/activation. Signed primary/role records bind the source,
  profile, single candidate, original faulty baseline9b4c390 and same finite
  **22:25:58UTC** expiry. Operator PAUSED41 fenced the restart; RUNNING42 resumed
  the prepared trial. Only verified-quiescent provider/control processes stopped.
  Model and all services were measured healthy before enrollment.

## Continuation and independent evidence still required

Order **afo-77ab6ea67e02ba0a**, job **afo-agent-239fde0d794a6068929fccc8**,
native run **01M64RG1FV5Y0B7M0VGN213D42**, is RUNNING at the captured checkpoint.
The existing Conductor dispatched it. A hash-bound source catalog provides only
baseline paths, bytes, hashes and AST symbol names; reference repair and checker
remain withheld. Scope remains the runconfig fix and candidate-owned tests.
Historical product attempts remain4; maintenance jobs4; at the first checkpoint
377requests and403131072 conservative charged tokens, aggregate actual historical
usage UNKNOWN. The mission tool counter596 omits native maintenance tool events;
retain native event counts separately. No mission deadline/counter reset occurred.

Self-healing is **UNPROVEN** at this checkpoint. Required next evidence: Qwen's
broker-sealed candidate and baseline-failing reproducer, existing CRE independent
review, frozen external tests and comparison on the two original SWE.3 diagrams.
Qualification scripts recover receipt-bound candidate source from Git even if the
broker quarantines its mutable worktree. They never revive a rejected job or
change production source. Any affected component recovery must be distinguished
from a complete SWE.1–6 product, general role capability and24/72/168h availability.
