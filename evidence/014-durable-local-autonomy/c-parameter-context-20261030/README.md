# C parameter-list clarification for future local roles

## Actual observed issue

The first repaired RCC baseline e1df47dbf49cb165 received the following SWE1-02 finding:
“The scope describes the LL functions as '(void) functions', while those requirements require query
or is-enabled functions to return1U or0U.”
[Actual complete review findings](actual-second-review-findings.json).

In C, the parameter list and return type are separate: uint32_t query(void) takes no arguments
and returns a value; void update(void) takes no arguments and returns no value.
The independent real C compiler test executes the former successfully, while the genuine
void-returning-value counterexample fails compilation as expected.
This refutes the inference that a (void) parameter list alone establishes a void return type.
It does not settle unspecified API contracts or establish that all other review findings are false.
The set-bit verification and missing CPU-allocation findings remain unresolved engineering issues.

## Source37c0c35, not deployed

**37c0c354629312a70eb6a199989477036bb674d9** adds an explicitly selected
structured.c_parameter_list_note flag to the Qwen repair and medium-trial profiles only.

The same generic C-notation note reaches:
- structured SWE.1 register and cross-cutting authors;
- structured SWE.1 inspectors;
- native SWE.1 author/inspector prompts, including HAL.

It is independent of driver/peripheral identity. RCC and IWDG, LL and HAL are exercised.
The note directs roles to resolve return contracts from explicit requirements or baselined
declarations and to retain genuine ambiguity. It cannot assign a return type or change scope.

The note is included in complete serialized context/accounting and checkpoint input hashes.
No gate, criterion, authority, role permission, artifact or recorded verdict is changed.
In particular the original FAIL is still a valid FAIL and fact_conflicts does not suppress it.
Unselected profiles and all five inherited RCC graph hashes remain unchanged.

## Tests and exact-source preparation

Local initial cohort **19PASS**, then selected regression **92PASS,0failures/errors/skips**:
new C context tests, inherited RCC graph/register-map equivalence, peripheral prompts,
structured SWE.1, startup-refutation scope, product role trial, bounded demonstration
and reasoning-comparison preparation. Four actual Fabro graph-parser cases passed.
[Initial JUnit](initial-local.xml), [final JUnit](regression-local.xml).

Command:

    env FORGE_FABRO_BIN=/home/jefferson/.fabro/bin/fabro python -m pytest -q -p no:cacheprovider \
      factory/python/tests/test_c_parameter_list_context.py \
      factory/python/tests/test_peripheral_rcc_equivalence.py \
      factory/python/tests/test_peripheral_prompts.py \
      factory/python/tests/test_lrtx_swe1.py \
      factory/python/tests/test_lrtx_startup_refutation_scope.py \
      factory/python/tests/test_da014_product_role_trial.py \
      factory/python/tests/test_demonstration_repair.py \
      factory/python/tests/test_reasoning_comparison_preparation.py

Selected Ruff E9/F and git diff checksPASS. These are local CPU/model-free tests.
A clean exact-source37c0 reasoning-comparison CLI preparation also passed:
[record](clean-source-reasoning-preparation.json). No inference, queue, job or mission was created.
The previous reasoning-only94b5 preparation remains historical, not the final combined qualification.

## Actual native effort control additionally verified

The actual top-level reasoning_effort wire shape used by the gateway was rendered natively:
xhigh→HTTP200/xhigh instruction; medium→HTTP200/no xhigh instruction;
high→HTTP500/unsupported. Rendered hashes match the earlier explicit-template-kwargs preflight.
[Actual native wire-shape proof](native-top-level-effort-preflight.json).
No model generation, prompt content or hidden reasoning was collected.

Thus medium is supported, high unsupported; no speed for medium is claimed before inference.
The eight-case/configuration pilot remains diagnosis-only, with full mixed author/reviewer
pipeline evaluation separate. MTP is a later controlled factor.

## Current production execution, unchanged

Runtime **899865d5f256e3c2fbdd836ba8696ef9cdb6fa8f**, RUNNING epoch72,
LL afo-f3ad027406784ef7/native01M65TR9K7DRDTM8AX8ZTP445G,
Q8_0/f16/MTP3/xhigh/262144/one inference/QM/SafeC disabled.
At 2026-10-30T08:51:22.222147Z: nativeRUNNING/LIVE/HELD, 32 requests complete/oneSENT.
[Observation](current-native-observation.json).
First author return completed; its review retained four model criteriaPASS and twoFAIL.
At08:57:03UTC the second author return completed; new baseline ad64dceaa4f94435 is being
reviewed, its first criterionPASS,34 requests complete/oneSENT. This later checkpoint
supersedes the earlier in-progress snapshot above. No live workproduct, prompt or serving setting
was edited by this prospective source change. Same RCC history/counters/uncertainty/spent
correction and existing13:52:52UTC deadline remain. HAL and model benchmarks not submitted.

## Combined native qualification prepared, not run

Use these uploaded P/deployment files after the current LL finishes and native/resource
quiescence plus local outcome copy are verified:

- qualify-native-reasoning-context-37c0c35.py
- qualify-reasoning-context-maintenance-window.py
- reasoning-context-37c0c35.bundle

Reviewable [worker](qualify-native.py) and [fenced window](qualify-fenced-window.py).
They supersede the94b5-only prepared worker/window; no earlier failure/history is erased.
Two serial cohorts at the same37c0 source: reasoning96 and context92 (overlapping tests;
do not sum as distinct cases). One verifier,4CPU/8GiB physical RAM/no swap/finite limits,
no GPU/network/owner identity/SSHagent, zero model requests. The verifier cancellation
function has the identical AST to the five passing local owned-process fence tests.

Actual --check-only correctly refused LIVE/RUNNING:
[native prerequisite record](native-precondition-NOT-RUN.json).
This is not native test qualification and performs no pause/deployment/generation.
The real fenced window requires RUNNING72 and quiescence, pauses73 and resumes74 only
without newer operator intent. It stops and verifies its owned verifier scopes before resume.

After both cohorts pass, prepare exact finite/source-bound benchmark authority under standing
owner delegation and run xhigh/medium serially through existing qualification/Conductor/gateway/
shared accounting and independent audits. Existing RCC/xhigh grants do not admit medium.
Do not silently renew/reset the RCC mission. Retain original package and failed costs.
Dependent HAL follows the owner-requested comparison under then-current exact authority.

Formal Feature01430/58 unchanged; no task IDs closed. Native candidate qualification,
medium speed, mixed pipeline benefit, clean LL/HAL, learning benefit and operational soaks
remain NOT_RUN/UNPROVEN. Static specification validation is separate.
