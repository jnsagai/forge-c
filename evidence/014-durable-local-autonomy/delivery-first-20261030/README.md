# Delivery-first native Qwen checkpoint — 30 October 2026

**A real Qwen-authored candidate passed host behavioral checks and target
compilation. Full functional qualification, six-phase product completion,
ASPICE acceptance, AFO integration and HAL remain unproven.** Formal Feature014
task progress remains30/58; no original task is closed by this checkpoint.

## What changed and why

The branch gained DELIVERY-FIRST-E2E.md in eeed84f5 while this work was active.
It was incorporated without dropping5222996d or resetting the integration line.
The immediate checkpoint is a separate CRC IDR job; it neither narrows nor
fulfills the historical full-RCC LL/HAL obligations.

- e9c06914460e61f71e258c8afce09f2746430a0d: opt-in delivery_first manifest/profile,
  genuine native C author, independent compiler/host oracle and at most two
  corrective author visits, then the existing six-phase graph/finalizer.
-155553dd43da45d7ab1a7bbfb5367123494e2d85: separate diagnostic service ports/root.
-2f60aa9a83f8cee8111d5ad837849182ce828474: complete native template/serialized/
  control measurement for explicitly opted-in standalone requests. Metadata is
  separate from provider-response accounting; no raw prompts/hidden reasoning.
- beb48b49d4ed7588798b964bc9da99ec47ff7251: profile2 reserves24576output tokens,
  keeping the measured initial17586input-token bound inside65536context.
  The original49152output reservation did not fit; inputs were not clipped.
-433254aabb1a5c421dcc773d8bad319e6586ef31: normal MCP build discovery uses the
  declared immutable build-only probe for a generated header-only candidate.
  This last fix is tested locally and **not deployed into the active run**.

Shared scheduling, strict release policy, storage and quality authorities were
not replaced. The new work order uses QM_DELIVERY_FIRST_DEMO reporting through
qm-pipeline-demonstration-v1, with preserved strict release blocks. The fixture
type/layout and tests are inputs; no ST function implementation is injected.
Read-only fixture files derive hardware facts from the declared manual/device
layout. The original reviewed-requirement reference is copied unchanged and is
not presented as a new review of generated code or this new scope.

## Real native evidence

Omniverse root R=/mnt/data/forge-c/delivery-first-014-20261030-v1.
Actual source is clean **beb48b49**, profile local-rtx-v2-omniverse2-q38-delivery-first
version2. Native **01M6788GYKREQSS1YTZHS9N3TV**, order
WO-F014-QWEN-CRC-IDR-DELIVERY-20261030-01, launched20:33:15UTC.

The header was initially absent. A successful native write_file from
df_author_0 submitted the exact2724bytes later tested; event and file SHA256 both:
511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5.
See [authorship proof](remote-export/authorship.json) and the
[actual candidate](remote-export/first-candidate/candidate/software/ll/stm32n6xx_ll_crc.h).
It contains static header functions; this snapshot does not claim compliance
with every style/inline or downstream measurement requirement.

At20:35:55UTC, the model-free verifier recorded first-candidate PASS for
Clang compilation, Cortex-M55 compilation and the preregistered host oracle:
**630checks, zero failures**, correction_count0. Full exact argv, exit codes,
timing and stdout/stderr hashes are in
[first-candidate result](remote-export/first-candidate/result.json).
This is roughly160seconds from launch to this limited functional result,
not time to a complete accepted package.

The native author stage nevertheless failed with provider HTTP429 after its
conversation grew beyond the configured context allowance. The successful
candidate was retained and independently tested; the execution failure remains.
Normal MCP configure also reported NO_SOURCES for a header-only candidate;
433254aa corrects that discovery defect prospectively. Native shell attempts
were refused by existing role/file policy. No unrestricted execution tool was
added. Do not interpret this trial as removal of every control.

At the [saved observation](live-snapshot-2040.json), the same run was RUNNING
in SWE.1 with the verified candidate unchanged. No post-launch engineering
patch, steering message or restarted run was supplied to this new job. Source
433254aa is a future correction, not a hot-patched success attribution.
The existing pipeline continues using actual model responses and tools.

## Native fixture and failed configuration evidence

First fixture01M6780ZA26M4GMCBT2YBFZDFK/source2f60aa9a captured context/output
over-reservation. It later made9 **fixture backend** response calls; it made
zero Qwen generation calls. It was externally superseded; terminal FAILED,
preserved package BLOCKED54gaps/integrityPASS. Do not count its transport or
fake responses as Qwen capability results. Earlier zero shim counts were
intermediate observations, not the final total.

Corrected fixture **01M6785DZFM30CS67KYZ9JNVWR**, sourcebeb48b49, reached all six
real native author/inspector stages and terminal packaging. Native SUCCEEDED,
product BLOCKED51gaps, functional FAIL because no candidate was supplied.
Zero actual Qwen generation calls. Immutable package integrity PASS, SHA256
4b9679f34c595c5106d814321142dd2619e33ece2bc361e395a8bcbc675df552.
See [six-phase terminal proof](remote-export/fixture-v2-terminal-proof.json).
This is FIXTURE_ONLY protocol/routing/finalizer evidence, not a successful product.

## Verification record

- e9c06914:34PASS, zero skip/failure/error, existing demonstration/native scope
  and repair regressions plus the new delivery fixture.
- Broader intermediate cohort:72PASS/two explicitly disabled live checks skipped.
  Source changed during that development interval; treat it as a development
  regression record, not an exact433254aa qualification.
-2f60aa9a:48PASS, zero skip/failure/error, gateway/template/measurement plus
  compiler/oracle/finalizer cases.
- beb48b49:49PASS, zero skip/failure/error, including measured reserve regression.
- **433254aa:50PASS**, zero skip/failure/error; exact source with the header
  discovery correction. Real host/Arm compilers and a target-image build run
  locally. Mock transport cases are labeled tests, not native Qwen inference.
- Frozen155553dd gateway counterexample: four new standalone measurement cases
  FAIL before the change. Header-discovery counterexample: normal configure
  BLOCKED with NO_SOURCES before433254aa. Both failed XMLs are retained.
- First development packaging test failed because it omitted the existing
  archive's evidence/ prefix; the test path was corrected. The packager/oracle
  was not weakened to turn failing engineering work into PASS.
- Spec/contracts/design validation PASS58mappings/six schemas/38contract fixtures/
 14static design tests. These are **documentation checks**, not runtime qualification.

Exact focused command:
```text
python -m pytest -q factory/python/tests/test_native_standalone_measurement.py factory/python/tests/test_lrtx_native_request_measurement.py factory/python/tests/test_llm_gateway.py factory/python/tests/test_qwen_system_messages.py factory/python/tests/test_delivery_first.py
```
Use the pinned loop10 Python/toolchain environment recorded by the handover.
Cohorts overlap; counts must not be added.

## Remaining execution and qualification

### Later checkpoint —20:49UTC; prospective context fix

The same native job reached SWE.2 at20:45:19. SWE.1 author/export gate completed;
its inspector failed on the experimental64K bound, not on a recorded semantic
inspection verdict. Measurements show42404+24576 and47917+24576exceeding65536.
These are complete request bounds, not a GPU memory shortage. Active source/profile
remainbeb48b49/v2 and were not hot-patched.

Latest tested source **b1e092d03026011a9f0c0b848d7851455d9495e9** restores the
already-loaded262144physical capacity for a **future** profile3 trial. It keeps
the24576output reservation and every input. Permanent standalone context/template
errors now return400with their cause instead of429/rate-limit; transport
unavailability remains503. Two before-change cases fail with429; the exact
corrected cohort passes **51/51**, zero skip/failure/error. This prospective
framework/configuration correction is not a qualified new live result.

The read-only dashboard now follows R and the CRC native handle at
http://100.118.28.92:8786. The exact old dashboard PID was stopped; no workflow,
model or inference service was signalled. Its first verification used the wrong
probe path; /api/v1/runs returned200with the current run without another service
restart. The [proof](dashboard-proof.json) records that correction. Local archive
collection remains active. See live-snapshot-latest.json for the later observation.

1. Observe the same native handle until terminal; retain every failed node and
   actual phase artifact. The first valid C candidate alone does not finish G1.
2. Independently verify simulation/performance, startup/no-polling and resource
   obligations. Existing host/target-compilation checks are explicitly narrower.
   The full functional report remains INCONCLUSIVE when only those checks pass.
3. Confirm final candidate hashes still match the independent verifier. Any
   later changed code needs new verification, not reused PASS.
4. Apply433254aa in a fresh, source-pinned retry after reconciling current
   execution/provider liveness. Diagnose remaining context/protocol failures
   from the exact measurement/error, rather than blindly increasing budgets.
5. Finish the source-pinned, independently tested six-phase package, repeat
   fresh runs, then the provisional LL-to-HAL experiment and broader LL/HAL
   goal. No30-product/learning-benefit/24-72-168h result is established here.
6. Integrate the proven path back through the existing AFO admission/native
   reconciliation. This new job is standalone, not evidence that production
   AFO can already deliver the whole scope unattended.

Local read-only collector session62942 follows this new job and will copy its
terminal archive under B/inspection/feature014/2026-10-30-qwen/full-pipeline-delivery-first/.
Its existing observation end is31October02:46:24UTC; this renews no inference
grant. Old trial outcomes were copied separately to full-pipeline-native-qm-artifacts/.
Remote source-preparation.json describes the initial155553dd staging; the later
launch/runtime-inventory records identify actualbeb48b49. Profile model digest
is declared; no new full weight-file hash was performed. The effective process
inventory confirms one physical262144-context slot, f16cache and draft-MTP,
while this experiment advertises65536context to Fabro.

Scripts are evidence of exact scoped operations. Do not blindly replay stop,
activation or steering after newer operator intent. Storage remains on loop10
locally. Proprietary primary contents, credentials and hidden reasoning are
excluded from this public checkpoint; transfer manifests and SHA256SUMS verify
the published records.

