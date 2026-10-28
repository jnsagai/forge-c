# Real M1 admission with owner-approved high development quotas

Runtime revision: **e098b515a421900131b05a6763029d20b3a8b09d**.
Execution host: Omniverse2. Owner reviewed the unchanged requirements payload in
a9d0ddb, approved M1 with “I approve, go”, then requested extraordinary high limits.
This is a prospective two-function IDR objective; the exhausted full-CRC mission
is unchanged. No gate, functional resource requirement or frozen delivery was relaxed.

## Active scope

| Setting | Applied value |
|---|---:|
| Per-native-execution conservative token reservation | 100,000,000 |
| Cumulative mission token ceiling | 100,000,000,000 |
| Requests / tools per mission | 100,000 / 1,000,000 |
| Execution attempts / phase repairs / upstream loops | 1,000 each |
| Author calls per task / tool calls per visit | 1,001 / 10,000 |
| Context / answer / xhigh reasoning reserve | 131,072 / 16,384 / 32,768 |
| Inference concurrency / verification workers | 1 / 1 |
| Gateway/structured visit timeout / native timeout scale | 21,600 s / 10 |
| Current signed deadline | 2026-10-29 05:00 UTC |

The large mission ceiling covers 1,000 conservative execution reservations, without
refunds or allowance resets. These values are ceilings, not measured consumption.
Legacy development v1 retains one repair; other profiles retain their defaults.
Repeated deterministic rejection still blocks the affected job for external diagnosis.
Global supervision and reconciliation continue. Product diagnosis/advisory relaunch
and maintenance remain explicitly deferred for this M1 scope.

## Verification and admission

- **79 native tests PASS**, zero skipped, clean source before/after: exact invocation
  and environment boundary in [native-invocation.json](native-invocation.json), results
  in [native-tests.xml](native-tests.xml). Includes the real-tool six-phase fixture,
  negative controls, quota/accounting conservation, legacy development limits,
  product-role admission, gateway/stack, inherited resume and primary CRC checks.
  Model answers/review in the fixture remain explicit substitutions; zero Qwen calls.
- **29 exact-revision local tests PASS** for gateway and workflow capacity:
  [local-exact-tests.xml](local-exact-tests.xml). Command:
  `python -m pytest -q factory/python/tests/test_da014_workflow_capacity.py factory/python/tests/test_llm_gateway.py`.
  Earlier 38 local and 92 regression passes are preparatory checks, not additional
  exact-revision or runtime qualification claims.
- Omniverse [context allocation](context-allocation.json) passed at131072 with Q8_0,
  f16 KV, MTP3/xhigh, one slot and about9.7GiB free VRAM. Zero generations.
  Allocation is neither context-quality nor model-capability evidence.
- Exact builder/Fabro native instructions and actual SKILL loading were captured
  for18 native nodes through an isolated scripted read-only provider, with zero
  model calls. Structured SWE.1 inspection packets used the actual reviewed baseline.
  [role-preflight.json](role-preflight.json) records75 rows: all13 roles covered,
  imported SWE.1 authorship makes no inference, other bodies pass static admission.
  The largest complete serialized byte-bound plus effective output cap is76302.
  This is a conservative UTF-8 bound, not native-tokenizer measurement. Subsequent
  tool histories must pass ordinary live admission; no decisive evidence is truncated.
- Current source/profile/model/allocation identities are bound to separately signed
  qualification-only role authority and a new primary M1 scope. No existing grant
  was renewed. [activation.json](activation.json) records exact policy/scope hashes,
  all mission limits, healthy services and operator epoch24. Role competence remains
  unqualified; a signed experiment is not a capability receipt.

`python tests/spec/validate_design.py` passed14 static design checks. Feature014
specification/contracts validation is documentation verification, never runtime qualification.

## Actual Qwen execution, not product acceptance

Order **afo-cf20126621ac2673**, native **01M627SG16KEX8E9MS736GJRCG** was RUNNING
in the initial21:51 snapshot below. It subsequently settled **BLOCKED**; see the
final result immediately after that historical observation.
[Snapshot](live-snapshot.json) at21:51:06UTC records one completed provider request,
one active request, SWE.1 baseline frozen, no completed inspection or downstream
baselines yet. Conductor, watchdog and finite Git recorder are active. GPU utilization
was98%. Historical mission snapshots compare identical. The100m conservative mission
charge is an execution reservation; aggregate actual usage remains UNKNOWN.

### Final observed result — 21:59:54 UTC

[Six actual Qwen inspection responses](qwen-inspection-results.json) contain four
PASS and two FAIL verdicts. Provider-reported output was17,340 tokens across six
completed requests; each request has usage, while the conservative execution charge
remains100m and cumulative execution usage is UNKNOWN. These are aggregate provider
output tokens, including any counted reasoning; hidden reasoning text was not captured.

- SWE1-03 failed on failure handling/safe-state applicability. The approved scope
  supports valid accessible calls and explicitly excludes safety allocation. Resolve
  the checklist/purpose applicability conflict rather than inventing a safe state.
- SWE1-04 failed for absent measurable CPU/timing requirements. Flash/RAM/stack
  requirements do not establish those missing allocations; do not manufacture them.
- The workflow then rerecorded the same failed frozen baseline using cached verdicts,
  without additional Qwen inference. The external engineer applied the owner's earlier
  stop-and-rethink instruction to this order at66 inspection records. This was not an
  autonomous self-healing success and not token exhaustion.
- [Containment](unchanged-loop-containment.json) requested cancellation of only that
  exact native handle, without provider signals or service shutdown. [Final observation](live-contained.json)
  shows native FAILED, order BLOCKED/DEFERRED_BY_DEVELOPMENT_POLICY, all six requests
  QUIESCENT, execution QUIESCENT and inference lease RELEASED. Release followed normal
  reconciliation; no terminal-state shortcut was used. Conductor/watchdog/recorder
  stayed active and old mission snapshots remained identical. SWE.2–SWE.6 were NOT_RUN.

Candidate **1dd54a0ea7887221910e1857a1b11f5dc5b28645** adds a narrow progress guard:
two identical failed inspections on the same unchanged frozen baseline stop the affected
job, retaining all findings and high quotas. Changed evidence/findings can progress;
legacy v1 behavior is preserved. It is not deployed to the current signed e098b51 scope.
Focused regressions passed3 cases locally and3 cases on Omniverse, with zero model calls;
[candidate native results](cached-loop-native-tests.xml) and [exact clean invocation](cached-loop-native-invocation.json)
are retained. Production remained e098b51 throughout. The first local test
assertion overlooked the fixture's pre-existing inspection; it was corrected to verify
preservation of the initial count plus two new failures. No production verdict changed.

The deployment needed two external operational corrections: initial short readiness
checks preceded the23-second model load, so admission waited for observed health;
the new recorder unit needed explicit Python/module environment variables. The latter
is recorded in [recorder-env-correction.json](recorder-env-correction.json), with zero
provider signals or new inference. Neither is autonomous self-healing evidence.

Runtime implementation, static admission, local-model capability, M1 product acceptance,
learning benefit and continuous availability remain separate. IE-T007's preparation
harness is complete; IE-T004 remains partial and IE-T008 is executed/blocked/unaccepted.
Formal Feature014 completion stays30/58. M2–M5, RCC, product cohorts, learning-benefit
comparison and24/72/168-hour campaigns remain unqualified/NOT_RUN as previously recorded.

## Continue and monitor

Status/phase gates:

```bash
ssh -t omniverse2@100.118.28.92 'watch -n 10 /mnt/data/forge-c/production-local-014/venv/bin/python /mnt/data/forge-c/production-local-014/deployment/observe-high-m1.py --compact'
```

Visible completed Qwen JSON answers and provider-reported output tokens:

```bash
ssh -t omniverse2@100.118.28.92 '/mnt/data/forge-c/production-local-014/venv/bin/python /mnt/data/forge-c/production-local-014/deployment/watch-qwen-outputs.py'
```

The running request does not expose a live visible-text tap; completed structured
answers are followed without restarting/interfering with inference. Hidden reasoning
is excluded. Output-token usage is the provider's aggregate, not a count of only the
visible JSON characters. Ctrl+C closes either viewer and leaves the factory running.
Viewer source is retained beside this report. Git status snapshots are recorded on
branch `e2e/2026-10-28-idr-m1-high`; the source PR remains draft42 and is not merged.

Next: resolve the supported-scope/checklist applicability and actual CPU/timing input
gaps, then prepare an authorized source-bound continuation with the tested loop guard for
this same M1 mission. Preserve its100m charge and the original full-CRC history.
Then execute all six phases and independently recompute the package verdict. Do not
mark M1 accepted before READY_FOR_OFFLINE_REVIEW or silently extend05:00UTC authority.
