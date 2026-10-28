# Incremental IDR delivery and verified phase references

Source implementation is prospective. Production remains
`fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61`. M1 product acceptance,
unassisted M2, repair M3, learning benefit and 24/7 availability are **NOT proven**.

## Exact verification

| Revision | Host | Result | Scope |
| --- | --- | --- | --- |
| `7a4bc51abb200b074e2a2e3ecf962298901c0808` | local loop10 | 120 PASS, 0 skips; 166.956s | IDR anchor, reference intake, inherited brownfield/learning/profile behavior |
| same `7a4bc51` | Omniverse2 | 169 PASS, 0 skips; 289.440s | Real installed compilers, host tests, Renode, Robot, packaging, inherited fixtures |
| `545e1024f396a039d3107279fd040eac83a1e51c` | local loop10 | 11 PASS, 0 skips; 45.976s | IDR integration and incident resume after reservation-status correction |
| `41a6c2832b14332125b7c37ce798a8117b6a4a78` | local loop10 | 23 PASS, 0 skips; 5.289s | Complete-role request preflight, over-context diagnosis refusal/advisory resume, inherited recovery |

These cohorts overlap; do not add their counts. XML and artifact hashes are in
[verification.json](verification.json). The exact native command, clean start/end
revision and unchanged production revision are in
[omniverse2-invocation.json](omniverse2-invocation.json).

The native run used an isolated checkout/data namespace, original pinned inputs
linked read-only, LLVM19.1.7 and the installed target toolchain. Its executable
[harness](run-native-7a4bc51.py) requires physical quiescence and operator epoch22,
stops its own process group on changed intent/resource use or600s, and never
starts inference or changes production services, policy, missions or source.
The old epoch is deliberately not a reusable permission to run it later.

Local commands used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=$W/factory/python`,
`FORGE_DATA_ROOT=$B`, loop10 `TMPDIR`, and the pinned LLVM19 PATH:

```sh
# Exact7a4bc51: 120 tests; inspect XML for the individual node IDs.
$B/venv/bin/python -m pytest -q \
  factory/python/tests/test_incremental_delivery.py \
  factory/python/tests/test_phase_references.py \
  factory/python/tests/test_brownfield_dispositions.py \
  factory/python/tests/test_da014_learning.py \
  factory/python/tests/test_da014_lesson_delivery.py \
  factory/python/tests/test_aspice_development.py \
  factory/python/tests/test_lrtx_stack_cli.py \
  factory/python/tests/test_brownfield_resume.py

# Exact41a6c28: 23 tests.
$B/venv/bin/python -m pytest -q \
  factory/python/tests/test_da014_product_role_trial.py \
  factory/python/tests/test_incremental_incident_resume.py \
  factory/python/tests/test_da014_advisory_recovery.py
```

## What the fixture proves

The two original ST CRC IDR functions remain FROZEN. Real preparation binds their
scope and sources. A synthetic external-review input and scripted semantic
author/inspector artifacts are explicit test substitutions. Normal requirement,
trace, baseline, deterministic inspection, authorization-ticket and release checks
still run. Compilers, analyzers, measurements, host execution, coverage, Renode
and Robot results are actual tool executions, not mocked PASS records.

The complete fixture produces READY_FOR_OFFLINE_REVIEW; a broken required trace
blocks release. A separately compiled wrong-register read mutant fails independent
host checks. This is plumbing evidence, not a real reviewed/Qwen-authored M1 product.
The accepted naming disposition is the existing owner's All5LLheaders decision,
applied to the identical frozen header's smaller scope; no new waiver is invented.

The incident test exercises the real admission context limit with complete
serialized administrative bytes plus reasoning/output in a qualification-only
identity fixture. It preserves a failed SWE.1 inspection across advisory resume at
SWE.1, keeps unknown usage and charged mission expenditure, refuses further
generation on exhaustion, and rejects an incompatible destination before copying.
Fake signature/native-status fixtures are explicit; this is not live recovery.

## MTP/xhigh backend smoke: PASS, separate from product qualification

The actual Omniverse2 Qwen3.8-27B Q8_0 backend used MTP3, thinking on, requested
xhigh, one slot,65536 context and full GPU/f16 KV. Exact source was
`d3f0b28a12ce789658ddccaa714d3b785fa42f87` and profilev2 SHA
`65ef1b9b008fb3ef0b53c623f1e4827b13db8010ddbd260974c8ea188c4dd88f`.

Two real requests passed: Qwen called configure through actual MCP stdio and its
normal one-use authorization ticket, then returned JSON matching the independently
observed tool result. Request walls were1.980s and2.239s; reported usage1295 tokens,
conservative reservation73949. Requests were quiescent. Production was paused at
epoch21 and restored RUNNING22 only after stopping the experiment's own processes.
Original policy/mission allowances and production backend/source were unchanged.

[Machine-readable result](mtp-xhigh-backend-smoke.json),
[expired scoped experiment](mtp-smoke-scope.json), and
[executable smoke harness](run-mtp-xhigh-smoke-v2.py) retain exact bindings.
The first attempt made zero inference calls and failed on an MCP Python field-name
mismatch. V2 retained parent/cumulative bounds and the original deadline. Do not
replay the expired scope. No raw hidden reasoning is published.

This qualifies the small backend/MCP smoke only. It does not qualify all Fabro
roles, inspector accuracy, long context, M1 delivery or the semantic degree of xhigh.

## Reference context and remaining work

CRC, SPI, USART and GPIO cloud successes appear in historical inspector holdout
reports and are excluded from training references. The successful TIM package's
complete540-character verification-handoff section was prepared as a607-character
wrapped candidate, with artifact/archive/source/scope provenance and author-only
applicability. It remains **PENDING_INDEPENDENT_QUALIFICATION; exposed=false**.
No production lesson database or cloud benchmark workspace was modified.
See [preparation](tim-reference-preparation.json) and the
[reference runbook](../../../specs/014-durable-local-autonomy/REFERENCE-ARTIFACTS.md).

The [M1 static report](m1-preflight-NOT_RUN.json) records missing genuine requirements
review. Complete live role bodies have not been captured; prospective job is not
submitted and current authority for this distinct objective is not established.
Source-level tooling measures the whole supplied body after gateway reasoning
adjustments, includes release, delegates to existing role admission, and cannot
launch/reserve anything. Real gateway admission remains mandatory at execution.

IE-T001/002/003/005/006 have scoped evidence. IE-T004 remains partial: shared repair
limits/deferred rungs exist, but positive dependency-independent provisional
continuation is not implemented/qualified; current routing conservatively blocks.
IE-T007 remains partial pending complete actual role inputs and bounded current
runtime bindings. IE-T008/009 remain NOT_RUN. Formal DA ledger remains30/58.

Next execution: obtain the pending requirements review; reprepare at the selected
clean source; finish phase-input/dependency-safe continuation and actual per-role
request admission; bind a prospectively authorized finite M1 order through existing
AFO/Conductor/MissionLedger. Preserve the old CRC mission's3/3attempts,
38requests,1.9m conservative expenditure/UNKNOWN actual usage. Do not renew its
expired engineering window or rename it to reset its allowance.

Initial failures and their corrections are retained in
[known-initial-failures.json](known-initial-failures.json), with full private logs
on loop10. Spec/contracts/design validation is documentation evidence only.
