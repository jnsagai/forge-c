# Actual Qwen repair artifacts and retained-artifact rework

Runtime source is92c49a6adde181737af19bb32a5efbd2130e9cd4. Self-healing remains
**UNPROVEN**. The owner goal is to prove AFO with local Qwen; artifacts and checks
below are real, but an authored patch is not independently accepted correctness.

## V4: diagnosis and authoring occurred; independent correctness failed

Qwen native run **01M64RG1FV5Y0B7M0VGN213D42**, job
**afo-agent-239fde0d794a6068929fccc8**, completed19admitted requests with763063
reported tokens. It diagnosed missing FORGE_DATA_ROOT propagation, authored a
7-line runconfig diff and a6327-byte candidate-owned test/reproducer. Exact final
bytes match native write_source events120/100 and their recorded hashes; the
collector made no code edits or commits. Qwen itself ran baseline5FAIL and patched
5PASS (plus an earlier4PASS). These are candidate-owned tests, not independent
correctness evidence.

Two submit_candidate calls were rejected with INPUT_INVALID:summary. Their
summary lengths956/371 exceeded the declared300maximum; reproducer fields280/259
also exceeded their200maximum and contained prose instead of a plain relative
.py path. The twentieth model attempt then failed JOB_TOKEN_ENVELOPE_EXHAUSTED.
No broker receipt or candidate commit exists. Durable task FAILED_PROTOCOL is
independent of native traversal status; all19requests are independently QUIESCENT
and the inference lease RELEASED. The1m reservation, failed job and uncertainty
are retained. Actual aggregate historical mission usage remains UNKNOWN.

The frozen external checker, withheld before authoring, ran in the native scoped
bubblewrap verifier against baseline and an immutable reconstruction of the exact
Qwen-written bytes: **2FAIL/0ERROR on both**. Default generated hook execution
fails for paths with spaces. Explicit FORGE_DATA_ROOT overrides produce duplicate
TOML keys, rejected by tomllib with Cannot overwrite a value. Qwen's test used a
line parser that silently accepted duplicates. The standalone reproducer exits1
on baseline, but prints diagnostics after SYMPTOM_PRESENT, violating the CRE
runner's last-nonblank-line contract; the candidate exits0/SYMPTOM_ABSENT. These
checks created no broker receipt, commit, CRE acceptance or production change.

## V5: exact artifact continuation, not reconstruction by the operator

Order **afo-f516373e837db572**, job **afo-agent-97d070852addbf37acf1b7c9**,
native run **01M64TQWV0QAJ69YGBJSS2STN3** is RUNNING at the saved checkpoint.
Signed primary/role records bind the same source/profile, V4 artifact provenance
and independent-check hashes. Existing Store/Conductor/Maintainer APIs create a
fresh isolated baseline candidate and copy the two exact Qwen-authored files;
[seed receipt](v5/records/seed-receipt.json) binds every source/destination hash.
The operator authored no repair code. The old job was not revived or refilled.

The complete case supplies measured failure facts and tool input bounds. No
reference repair or grader source is given to Qwen. It has read the retained
runconfig and reproducer. Rework must preserve all existing quality gates,
correct the independent findings and make a valid broker submission. Same mission,
**22:25:58UTC** expiry and finite1m prospective new-job envelope; counters preserved.
Operator PAUSED43/RUNNING44 fenced policy enrollment, with the loaded provider
unchanged. At the first checkpoint:4product attempts/5maintenance jobs/397requests/
404131072conservative charged tokens. Native maintenance tool events remain
separate from the596mission-tool counter; no missing expenditure is invented.

## Verification readiness and remaining proof

The actual running Conductor's compiler is the pinned LLVM19.1.7, not the system
clang14 selected by the environment file alone. All13golden/holdout case static
prerequisites pass in the actual compiler environment, and all72frozen reproducer
hashes validate. This is a read-only prerequisite audit, not benchmark execution.

The original failed SWE.3 inputs are frozen in a private independent replay copy;
all14baseline file hashes were checked against the historical phase record.
Executable qualification tooling covers the frozen external regression, two
original diagrams and the deterministic SWE.3 phase through generated isolated
MCP context. Model/native liveness and any existing verifier must be quiescent
before these independent checks run. Receipt-bound source remains recoverable
from Git even if the broker quarantines its mutable worktree.

Still required: actual corrected Qwen submission and durable receipt, unchanged-
baseline causal reproduction, existing CRE gates and recovery of the affected
workflow. Complete SWE.1–6 product acceptance, general role capability, learning
benefit and24/72/168-hour availability remain unqualified. No feature task is
newly marked complete by this evidence.
