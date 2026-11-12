# Inspector omission test on Omniverse2, 31 October 2026

This is a measurement, not a qualification. The owner decided on 2026-10-31 ("Inspector omission test"). The question
was whether the Qwen SWE.1 inspector catches **missing** obligations.

The target was the Ornith arm's attempt-2 baseline. Compared with Ornith attempt 1, it lacks the requirements for
three obligations:
- no wait on a status flag;
- no error code on a valid call;
- changing only the IDR field.

Two inspections ran, each on its own fresh copy: Qwen3.8-27B at medium and Qwen3.8-27B at xhigh. AFO, Fabro and every
existing process were not involved.

**Result: neither run flagged any of the three missing obligations.**

| Run | Inspection | Findings | Names a missing obligation? | Inspect gate |
|---|---|---|---|---|
| medium | PASS, 8/8 items PASS | 0 | no | **PASS** (rc 0) |
| xhigh | FAIL, 1 item FAIL (SWE1-02) | 1 | no. It is about the SWR-003 verification wording. | **REWORK** (rc 11, failed_inspections 1) |

## Target

The baseline is BL-SWE.1-001 of `/mnt/data/forge-c/operations/swe1-ornith-20261031/report-workspaces/ornith-1.5-35b-a3b-q8-02/workspace`:
- hash `c566b006b392caf1…`;
- author gate FROZEN at 13:43:31.77Z;
- 8 SWRs: write IDR, read IDR, no register write after reset, and 5 budget rows.

These requirements of Ornith a01 (`…/ornith-1.5-35b-a3b-q8-01/workspace/workproducts/SWE.1/software_requirements.md`)
have no counterpart in a02. They are quoted as model output:

| Obligation | Ornith a01 requirement (absent in a02) |
|---|---|
| no polling | SWR-004 "When the caller invokes LL_CRC_Read_IDR with a valid CRC peripheral instance, the CRC LL driver shall not wait on any status flag of the CRC peripheral." |
| no error code | SWR-005 "When the caller invokes LL_CRC_Read_IDR with a valid CRC peripheral instance, the CRC LL driver shall not return an error code for the valid accessible call." |
| preservation | SWR-006 "When the caller invokes LL_CRC_Write_IDR with a valid CRC peripheral instance, the CRC LL driver shall change only the IDR field of CRC_IDR and no other field of the register." |

The owner contract in the workspace inputs, `inputs/IDR-CONTRACT.md`, says: "Preserve every other register and other
peripheral instances. No startup accesses, status polling, allocation or setup occur in this scope."
`inputs/provided-requirements.json` also has a `no_polling` requirement.

### What the inspector could see

`lrtx.review.evidence()` gives each item packet the following, and nothing else:
- the frozen baseline's files, except `.reqif`;
- `.forge-run/manifest.json#scope-target-budgets`;
- `.forge-run/manifest.json#inspection-assessment-context`.

`inputs/IDR-CONTRACT.md` and `inputs/provided-requirements.json` are **not** inspector sources. Every item's
`evidence_checked` lists only the baseline files and the two manifest views. The obligations reach the inspector as
follows:

| Obligation | Present in inspector evidence? |
|---|---|
| no polling, no error code | Only as one sentence of the manifest scope and the assessment context's `declared_work_order_scope`: "Within this slice no LL call occurs automatically at startup, no status-flag polling or error return is specified for valid accessible calls, and invalid pointers or inaccessible hardware are outside the supported invocation domain." The a02 document repeats it in its scope header. No a02 SWR states it. |
| preservation | **Nowhere.** None of the baseline files or manifest views contains "preserv", "other field" or "only the IDR". The scope sentence covers write/read of CRC_IDR.IDR only. |

## Which checklist item judges completeness?

The inspector used checklist v0.4 for SWE.1 (`factory/checklists/v0.4/SWE.1.yaml`, which extends
`factory/release-manager/checklists/SWE.1.yaml`). It was QM-tailored by `inspection.assessment_context.checklist`, with
checklist sha `baffe47e…` as recorded in INS-SWE.1-001. The criteria the inspector received:

| Item | Criterion (exact text) |
|---|---|
| SWE1-01 | The hardware/software interface and allocated functional software requirements are baselined and traceable. |
| SWE1-02 | Requirements are atomic, consistent, feasible and objectively verifiable. |
| SWE1-03 | Failure/error behavior, reset/startup actions and caller responsibilities are source-supported within the declared invocation domain. An explicitly specified absence of error signaling or startup actions is valid when supported by that contract; behavior outside the domain is explicitly identified rather than invented. |
| SWE1-04 | Flash/RAM/stack/CPU/timing constraints are explicit and measurable. |
| SWE1-05 | Bidirectional upstream-to-SWE.1 trace and coverage gaps are recorded. |
| SWE1-06 | Verification criteria and unresolved ambiguities are documented. |
| SWE1-07 | EARS conformance (deterministic) |
| SWE1-08 | ReqIF 1.2 export validates (deterministic) |

**No item asks whether every obligation of the owner contract or the declared scope has a requirement.** The closest
items are these:
- **SWE1-01** ("allocated functional software requirements are baselined and traceable"). This is the only
  functional-coverage wording, but it asks for baselined and traceable, not complete.
- **SWE1-05** ("coverage gaps are recorded"). It asks that gaps be *recorded*. The a02 `upstream_gaps.md` records
  the upstream inputs as NOT_PROVIDED, so a recorded gap satisfies it.
- **SWE1-03** covers error behaviour "within the declared invocation domain", and explicitly accepts "an explicitly
  specified absence of error signaling". This is the item where the missing no-error-code requirement would belong.
  The a02 document states that absence only in its scope header, not as a requirement.

## Runs

Both runs used the same clone (`/mnt/data/forge-c/operations/swe1-qwen-20261031/repo` at `2d91c2fa`, clean) and the
command
`python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace <copy> --model qwen3.8:27b-q8_0 --time-budget 1200`.

The environment was:
- `FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first`;
- `FORGE_STATE_DIR=<scratch>/inspect-state-<run>` (fresh);
- `FORGE_DATA_ROOT=/mnt/data/forge-c`;
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`.

Each run had its own server, gateway and gateway state, with argv and env from `work/spec.py`:

| | medium | xhigh |
|---|---|---|
| Copy | `/mnt/data/forge-c/operations/swe1-omission-20261031/inspect-medium` | `…/inspect-xhigh` |
| Server argv | `stack.llama_server_spec` of the workspace profile, port 18602, `--reasoning-effort medium` | `stack.llama_server_spec` of `local-rtx-v2-omniverse2-q38-aspice-max-mtp`, port 18605, `--reasoning-effort xhigh` |
| `FORGE_GATEWAY_REASONING` | `{"qwen3.8:27b-q8_0": {"effort": "medium", "extra_output_tokens": 8192, "role_efforts": {}, "system_message_order": "merge_first"}}` | `{"qwen3.8:27b-q8_0": {"effort": "xhigh", "extra_output_tokens": 32768}}` |
| Other gateway env | as in the medium arm, route → 18602 | as in the xhigh arm, route → 18605 |
| Output reserve per call (measured) | 10240 | 34816 |
| Server / gateway PID | 2756923 / 2757171 | 2762164 / 2762413 |
| Health OK / VRAM after load / peak | 4.86 s / 46558 / 46590 MiB | 4.89 s / 46558 / 46590 MiB |
| Runner passes | 1 (status PASS) | 1 (status REWORK; not CONTINUE, so no `--resume`) |
| Calls / pass wall | 6 / 123.3 s | 6 / 644.1 s |
| Prompt / output tokens (sum) | 27114 / 7642 | 27342 / 34540 |

All 12 calls ended with `finish_reason: stop` in schema mode json_schema, and each first answer was valid, so there were
no repair calls. Every meter row has `reasoning_stripped: true`.

Scratch-copy edits, made in each copy only (`work-<run>/isolation-edits.json`):
- `binding.json`: the trial-06 path → the copy (1 occurrence);
- `workflow.toml`: the same (2 occurrences);
- `durable-binding.json`: moved to `work-<run>/isolated/`;
- 25 historical files still name the trial-06 path and were left unchanged.

The copies carried no earlier SWE.1 inspector checkpoints.

### Per item: medium

| Item | Verdict | Findings (quoted) | Calls | Prompt / output | Call wall | Names a missing obligation |
|---|---|---|---|---|---|---|
| SWE1-01 | PASS | none | 1 | 4514 / 1174 | 19.1 s | no |
| SWE1-02 | PASS | none | 1 | 4504 / 1736 | 27.5 s | no |
| SWE1-03 | PASS | none | 1 | 4578 / 1201 | 19.0 s | no |
| SWE1-04 | PASS | none | 1 | 4510 / 955 | 16.8 s | no |
| SWE1-05 | PASS | none | 1 | 4510 / 1440 | 22.4 s | no |
| SWE1-06 | PASS | none | 1 | 4498 / 1136 | 17.9 s | no |
| SWE1-07 | PASS (deterministic; 8 SWRs: EVENT 4, STATE 1, UBIQUITOUS 3) | none | — | — | — | no |
| SWE1-08 | PASS (deterministic; 16 spec objects) | none | — | — | — | no |

Total: 6 calls, 122.7 s of call wall. Inspect gate: **PASS** (reason INS-SWE.1-001, failed_inspections 0, rc 0).

### Per item: xhigh

| Item | Verdict | Findings (quoted) | Calls | Prompt / output | Call wall | Names a missing obligation |
|---|---|---|---|---|---|---|
| SWE1-01 | PASS | none | 1 | 4552 / 2356 | 36.6 s | no |
| SWE1-02 | **FAIL** | "SWR-003 in workproducts/SWE.1/software_requirements.md is not consistently verifiable as written: the requirement says the driver shall not write any register, but its verification only checks that no register write to any CRC register occurs before the first explicit function call." | 1 | 4542 / 18587 | 347.8 s | **no**: it is about the startup requirement SWR-003 (any register vs. CRC registers), not polling, error codes or preservation |
| SWE1-03 | PASS | none | 1 | 4616 / 4216 | 83.6 s | no |
| SWE1-04 | PASS | none | 1 | 4548 / 3518 | 68.3 s | no |
| SWE1-05 | PASS | none | 1 | 4548 / 4090 | 72.0 s | no |
| SWE1-06 | PASS | none | 1 | 4536 / 1773 | 35.2 s | no |
| SWE1-07 | PASS (deterministic; EVENT 4, STATE 1, UBIQUITOUS 3) | none | — | — | — | no |
| SWE1-08 | PASS (deterministic; 16 spec objects) | none | — | — | — | no |

Total: 6 calls, 643.4 s of call wall. INS-SWE.1-001 verdict FAIL, with severity major for SWE1-02. The record's
`detail` field truncates the finding text; the full text above is from the item checkpoint. The runner reply was
`REWORK`, issues `["SWE1-02:major"]`.

Inspect gate: **REWORK**, with reason INS-SWE.1-001, failed_inspections 1, max_rework_cycles 3 and exit code 11. Its
stdout begins with the line `gate execution bi`, which is `inspection.gate`'s deliberate digit-free failure marker.
No author rework was run, because it is outside this test.

The commands were the same in both runs: `builder.gate_cmd('SWE.1','inspect')` piped from `inspect-reply.json`, run in
each copy after its server had stopped (see `work-<run>/gate.cmd`).

## Interpretation (observations, not a qualification)

- **Nothing was flagged.** On this baseline, neither effort produced a finding that names any of the three missing
  obligations. The inspector judges what is written against item-shaped criteria, and no criterion asks for
  obligation coverage against the scope or the contract.
- **Preservation could not be judged.** It is absent from every inspector source, so an inspector could only have
  raised it from general driver knowledge.
- **No polling and no error code were visible but not raised.** They appear in the scope sentence, which the
  document copied into its header. A model may read the header sentence as coverage, and SWE1-03 accepts "explicitly
  specified absence".
- **xhigh did look harder,** and found a real verifiability inconsistency (SWE1-02), but not the omissions. It took
  5.2× the medium run's wall time and 4.5× its output tokens.
- **Small sample.** One baseline and one inspection per effort.

## Read-only proof

`work/snapshot.py` recorded path, type, size, mtime_ns, mode and sha256 before the copies were made (16:27Z) and after
the cleanup (16:42Z). `work/compare.py` reports all 9 roots **identical**: 0 added, 0 removed, 0 changed, root mtime
unchanged (`work/ro-compare.json`).

| Root | Entries |
|---|---|
| trial 06 `…/WO-AFO-7f71565db57f0a76-a1/workspace` | 706 |
| `swe1-ornith-20261031/report-workspaces` (contains the **a02 source tree**) | 1218 |
| `swe1-ornith-20261031/inspect-ws` | 624 |
| `swe1-qwen-20261031/{report-workspaces, inspect-ws, start-ws}` | 1220 / 626 / 705 |
| `swe1-qwen-xhigh-20261031/{report-workspaces, inspect-ws, start-ws}` | 1220 / 626 / 705 |

Both intent files keep their sha256 (`9eff2df3…` STOPPED, `1387fbb2…` PAUSED).

## Preflight and cleanup

- **Preflight (16:26:15Z): PASS.**
  - GPU at 936 MiB with no compute process.
  - Intents STOPPED / PAUSED.
  - gpuq `pending` and `running` empty, no STOP file, and none was created.
  - No own server, gateway or script, ports 18602–18607 free, guard OK.
  - One process was not mine and was left alone: a `tail -F` (PID 2670266) on the Ornith run's progress.log.
- **Guard.** The 1 s watcher in `work/serve.sh <run>` never fired: the last guard was `OK` and there is no `ABORT`
  file.
- **Time.** The limit was 75 minutes (until 17:41:00Z). The run used 16:26–16:44Z.
- **Cleanup (16:42:29Z).**
  - Both servers stopped on SIGTERM with exit 0, and both gateways are gone.
  - No own process remains; my monitor's remote `tail` was stopped too.
  - The GPU is at 936 MiB with 0 compute processes.
  - Ports 18602–18607 are closed.
  - The guard reads `OK`.
  - The runner 2742646 and the conductor 3699940 were untouched. gpuq is empty, and there is no STOP file.
  - The clone is clean.

## Files

- `progress.log`: 27 checkpoint lines at 30 s intervals, plus per-call, pass, server, gate and cleanup lines.
- `inspect-<run>/`:
  - `inspection/SWE.1/INS-SWE.1-001.json` and the deterministic SWE1-07/08 records;
  - the item checkpoints `.forge-run/lrtx/SWE.1/packets/inspect__c566b006b392caf1__*.json`, which hold the full
    finding text;
  - `inspect-reply.json`, `inspections.jsonl` and `inspection-record.json`;
  - `.forge-run/lrtx/SWE.1-inspect/visit-state.json`;
  - the gate log and the rebound `binding.json`.
- `work-<run>/`:
  - `llama.spec.json` (argv), `gateway.env.json`, server argv, log, VRAM samples and stop record;
  - runner stdout/stderr (stderr is empty);
  - `passes.jsonl`;
  - `gate.cmd`, `gate.stdout`, `gate.stderr` and `gate.exit.json`;
  - the isolation record and the moved `durable-binding.json`.
- `state-<run>/llm-gateway/`: the meter and request measurements, with shape and usage only.
- `work/`:
  - the scripts (spec, serve, run, monitor, isolate, guard, snapshot, compare);
  - the deadlines;
  - the read-only snapshots and comparison.

The target baseline's files are already on loop10 in `../swe1-ornith-standalone-20261031/attempts/a02/`.

The server logs have 0 matches for requirement or register text, and the gateway logs are empty. No reasoning text was
kept. The quoted texts are the owner contract sentences and model output. Nothing was committed or pushed.
