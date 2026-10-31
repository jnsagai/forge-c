# Standalone SWE.1 author test with Qwen on Omniverse2, 31 October 2026 (Qwen author arm)

This is a measurement, not a qualification. The owner authorized it on 2026-10-31 ("Qwen author arm"). It is the
comparison arm of [swe1-ornith-standalone-20261031](../swe1-ornith-standalone-20261031/README.md).
- The author was the unchanged Forge-C SWE.1 structured author (`forge_factory.lrtx.modelcmp` → `lrtx.swe1.visit` →
  the unchanged author gate), with Qwen3.8-27B Q8_0 (`qwen3.8:27b-q8_0`) behind the factory's own gateway.
- Qwen then inspected attempt 1's frozen baseline.
- AFO, Fabro and every existing process were not involved.

**Result:**
- Author: 2 of 2 attempts gave visit PASS and author gate `FROZEN` (BL-SWE.1-001 in each copy). Attempt 1 has 10
  requirements and attempt 2 has 9. modelcmp exited with code 0, after 228.8 s of wall time and 6 model calls.
- Inspection: the inspector `lrtx.review` (Qwen, effort medium) inspected attempt 1's BL-SWE.1-001 (hash
  `413e7103f3d08975…`).
  - Record: INS-SWE.1-001 PASS, 0 findings, all 8 checklist items PASS.
  - Every model item's first call was valid.
  - Cost: 1 runner pass, 6 calls, 130.5 s.
- Inspect gate: decision **PASS** (reason INS-SWE.1-001, failed_inspections 0, rc 0).
- Read-only proof: identical for trial 06 and for both of the Ornith run's workspace trees.
- Isolation: the factory did not write into the start copy, so CAPA-075 held here; see "Read-only proof".

## Preflight (read-only, 2026-10-31T15:27:11Z): PASS

| Check | Observed |
|---|---|
| GPU | RTX 6000 Ada, 936 MiB used of 49140, 0 % utilization, no compute process |
| AFO intent `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json` | STOPPED, epoch 7, sha256 `9eff2df3…f4d545` (unchanged at the end) |
| production-local-014 intent `/home/omniverse2/.local/state/forge-c-production-014/operations.json` | PAUSED, epoch 111, sha256 `1387fbb2…947e63c` (unchanged at the end) |
| gpuq `/mnt/data/forge-c/inspector-014-b309039/gpuq` | `pending/` and `running/` empty. No STOP file, and none was created. |
| Own llama-server / gateway | none. Ports 18596, 18597 and 18598 were free. |
| Guard (`work/guard.sh`, byte-identical to the Ornith run's) | `OK` |
| Idle processes left alone | conductor 3699940 (heartbeat OBSERVE_ONLY / operations_wait), gpuq runner 2742646, and the existing idle `llm_gateway` processes of other roots (212513, 781321, 1969873, 1978292, 2624654) |

The time limit was 100 minutes, from 15:27Z to 17:07:00Z. The server watcher had a hard deadline at 17:00:00Z, and no
inspector pass could start after 16:35:00Z. The run used 15:27–15:50Z and reached neither limit.

## Code and start workspace

- Code: a new clone from GitHub at `/mnt/data/forge-c/operations/swe1-qwen-20261031/repo`, detached at
  `2d91c2fa6f7cc7f7983e98259bd4ddb20fba6733` (= `origin/feat/014-durable-local-autonomy`). It contains CAPA-075
  (`2f2aefa0`). No factory file was changed: `git status` is clean after the run.
- Source (read-only), trial 06:
  `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/state/workorders/WO-AFO-7f71565db57f0a76-a1/workspace`.
  - Its manifest sha256 is `d90e5371…afca6be` before and after the run.
  - The manifest gives layer LL, peripheral crc and `local_profile.id`
    `local-rtx-v2-omniverse2-q38-delivery-first`.
- Scratch start copy `start-ws` = `/mnt/data/forge-c/operations/swe1-qwen-20261031/start-ws`, a `cp -a` of trial 06.
  The edits below were made in the copy only and are recorded in `work/isolation-edits-start.json`:

| File in start-ws | Change | sha256 before → after |
|---|---|---|
| `.forge-run/binding.json` | `workspace`: trial-06 path → start-ws path (1 occurrence) | `45026c39…` → `0cb197de…` |
| `.forge-run/workflow.toml` | the same path replaced (2 occurrences, in node scripts) | `17ea1c8e…` → `04891076…` |
| `.forge-run/durable-binding.json` | **moved out** to `work/isolated-start/` (sha `4a853d42…`) | — |

  57 files in start-ws still name the trial-06 path: historical delivery-first logs, results, `evidence/raw/*` and the
  oracle scripts. They are listed in the json and were left unchanged.
- modelcmp's `_fresh_copy` put the attempt copies in
  `/mnt/data/forge-c/operations/swe1-qwen-20261031/report-workspaces/qwen3.8_27b-q8_0-0{1,2}/workspace`.

## Server and gateway (shared by the author arm and the inspection)

The argv comes from `forge_factory.lrtx.stack.llama_server_spec`, called from the clone (`work/spec.py`) with:
- `settings('local-rtx-v2-omniverse2-q38-delivery-first')`;
- root `/mnt/data/forge-c/production-local-014`;
- `ports['llama']=18596`.

The function itself checked the Ollama manifest digest (`8f5fb6b7…6039`) and the blob size.

```
/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf --alias qwen3.8:27b-q8_0 --host 127.0.0.1 --port 18596 --no-webui --offline -c 262144 -np 1 --jinja --reasoning on --cache-type-k f16 --cache-type-v f16 --flash-attn on -b 1024 -ub 512 --spec-type draft-mtp --spec-draft-n-max 3 --reasoning-effort medium --reasoning-format deepseek --gpu-layers all
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama)
```

This is the Ornith run's step-2 argv with only the port changed. The binary is byte-identical to
`/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server`.

| Item | Value |
|---|---|
| PID | 2661907 |
| Started | 15:31:58.49Z |
| Model loaded (server log) | 4.26 s |
| `/health` OK | 4.86 s |
| Context | n_ctx_slot 262144, 1 slot (the full profile context fitted) |
| VRAM after load | 46558 MiB |
| **VRAM peak** | **46590 MiB** of 49140 (baseline 936) |
| Decode | 68.2–83.3 tok/s (server `print_timing`) |
| MTP draft acceptance | 0.72–0.97, mean length 3.17–3.91 |
| Stopped | 15:38:17Z, SIGTERM, exit 0, 1.05 s. Server time used: 379 s. |

The gateway is the factory's own process: `forge_factory.llm_gateway --port 18597 --upstream http://127.0.0.1:18598
--meter <scratch>/state/llm-gateway/usage.jsonl`, PID 2662162. It was up at 15:32:04Z and gone at 15:38:17Z.
`work/spec.py` derived its env the same way `stack._start` builds it (`work/gateway.env.json`):

| Variable | Value |
|---|---|
| `FORGE_GATEWAY_REASONING` | `{"qwen3.8:27b-q8_0": {"effort": "medium", "extra_output_tokens": 8192, "role_efforts": {}, "system_message_order": "merge_first"}}` |
| `FORGE_GATEWAY_ROUTES` | `{"qwen3.8:27b-q8_0": "http://127.0.0.1:18596"}` |
| `FORGE_GATEWAY_MAX_INFLIGHT` / `_MAX_QUEUE` / `_MAX_WAIT_S` / `_SAMPLE_S` | 1 / 8 / 21600 / 10 |
| `FORGE_GATEWAY_REQUEST_MEASUREMENT` | `{"qwen3.8:27b-q8_0": "native_template_plus_serialized"}` |
| `FORGE_GATEWAY_MEASURE_UNBOUND` / `_NATIVE_CONTEXT_LIMIT` | 1 / 262144 |
| `FORGE_GATEWAY_REQUEST_TIMEOUT_S` / `_DROP_RETRIES` | 21600 / 0 |
| `FORGE_STATE_DIR` | `/mnt/data/forge-c/operations/swe1-qwen-20261031/state` (fresh) |
| `FORGE_DATA_ROOT` | `/mnt/data/forge-c` |

Evidence that the reasoning settings were applied:
- All 12 requests have `reasoning_stripped: true` in the meter.
- The output reserve was 12288 tokens on the 6 author calls (4096 + 8192) and 10240 on the 6 inspector calls
  (2048 + 8192).
- Every request measurement has scope `STANDALONE_NO_DURABLE_ACCOUNTING` and `fits: true`.
- Native input tokens were 1873–3099 for the author calls and 5035–5115 for the inspector calls.

A 1 s watcher (`work/serve.sh`) ran next to the server. On each tick it checked:
- gpuq `pending` and `running`;
- foreign GPU compute processes;
- the conductor heartbeat;
- the sha256 of both intent files;
- the wall deadline.

It wrote VRAM samples (`work/vram.csv`, 352 samples) and never fired. The last guard result was `OK`, and there is no
`ABORT` file.

## Author arm (step 2)

From `repo/factory/python`, with `/mnt/data/forge-c/venv/bin/python`:

```
python -m forge_factory.lrtx.modelcmp --workspace <start-ws> --model qwen3.8:27b-q8_0 --repeat 2 --phase SWE.1 --out /mnt/data/forge-c/operations/swe1-qwen-20261031/report.json
```

The environment was:

| Variable | Value |
|---|---|
| `FORGE_LRTX_GATEWAY_URL` | `http://127.0.0.1:18597/v1` (the gateway) |
| `FORGE_STATE_DIR` | `/mnt/data/forge-c/operations/swe1-qwen-20261031/state` (fresh; the same folder as the gateway's) |
| `FORGE_DATA_ROOT` | `/mnt/data/forge-c` |
| `PYTHONPATH` | the clone's `factory/python` |
| `FORGE_LRTX_PROFILE` | `local-rtx-v2-omniverse2-q38-delivery-first` |
| `PYTHONDONTWRITEBYTECODE` / `PYTHONUNBUFFERED` | 1 / 1 |
| proxy variables | unset |

The default `--max-calls 35` applied. `author_module` picked `lrtx.swe1`. Every call used schema mode `json_schema`
and ended with `finish_reason: stop`.

### Per-attempt results

| Attempt | Visit | Author gate | Calls | Prompt / output tokens | Wall | SWRs (model + deterministic) |
|---|---|---|---|---|---|---|
| a01 | PASS | FROZEN (15:33:25.56Z) | 2 | 3173 / 5369 | 79.7 s | 10 (2 CRC_IDR + 3 crosscutting + 5 budget) |
| a02 | PASS | FROZEN (15:35:54.21Z) | 4 | 4353 / 9916 | 148.5 s | 9 (2 CRC_IDR + 2 crosscutting + 5 budget) |

Baseline hashes: a01 `413e7103…203b2`, a02 `8e53459e…ccbecb`. The 5 budget SWRs are rendered deterministically from
the work-order budgets and are not model output.

### Per-task results

| Attempt | Task | First call valid | Calls | Prompt / output | Call wall | Status |
|---|---|---|---|---|---|---|
| a01 | requirements:CRC_IDR | yes | 1 | 1837 / 1865 | 26.9 s | VALID |
| a01 | requirements:crosscutting | yes | 1 | 1336 / 3504 | 52.3 s | VALID |
| a02 | requirements:CRC_IDR | no | 2 | 4353 / 5988 | 88.5 s | VALID after 1 repair |
| a02 | requirements:crosscutting | no | 2 | 3266 / 3928 | 59.3 s | VALID after 1 repair |

The a02 first-call findings came from the deterministic `validate_group`, not from the schema:
- CRC_IDR had 1 finding: a reset/startup requirement placed in the register task, which belongs to the crosscutting
  task.
- crosscutting had 2 findings, both on one requirement:
  - an effect value that is not a number fitting the 32-bit field;
  - the requirement acts on CRC_IDR, which the CRC_IDR task covers.

The repair calls were short (536 and 396 output tokens, 8.4 s and 6.2 s).

Output tokens include thinking, because `usage` does not separate the two. The gateway meter shows that:
- the answer content was 1055–2127 chars per author call;
- the first content delta arrived 21.2–72.5 s into each first call, and 3.0 s into each repair call.

So most of the author wall time was thinking.

`model_loads` is empty and `load_ms_median` is `UNKNOWN`. The gateway meter exists in this arm, but every row has
`model_loaded_before: true`, because the server had loaded the model before the first call. The load time above comes
from the server log.

## Inspection (step 3)

Step 3 started because attempt 1 had visit PASS and gate FROZEN.

`inspect-ws` = `/mnt/data/forge-c/operations/swe1-qwen-20261031/inspect-ws`, a `cp -a` of the attempt-1 workspace.
The edits below were made in the copy only and are recorded in `work/isolation-edits-inspect.json`:
- `binding.json`: the start-ws path → the inspect-ws path (1 occurrence);
- `workflow.toml`: the same (2 occurrences);
- `durable-binding.json`: already absent, because start-ws had none.

25 historical files still name the trial-06 path and were left unchanged.

```
python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace <inspect-ws> --model qwen3.8:27b-q8_0 --time-budget 1200
```

The env was the same as the author arm's, except `FORGE_STATE_DIR=/mnt/data/forge-c/operations/swe1-qwen-20261031/inspect-state`
(fresh). The same server and gateway stayed up. The inspector module was `lrtx.review`, because the profile sets
`semantic_inspect_phases: []`. The role `swe1-inspector` got the model effort `medium`, because `role_efforts` is `{}`.

Pass 1 returned PASS, so no `--resume` was needed: 6 calls, 130.5 s (15:35:59–15:38:10Z), 0 continuations.

### Verdicts per checklist item

| Item | Criterion (factory checklist, short form) | Source | Verdict | Findings | Calls | First call valid | Prompt / output | Call wall |
|---|---|---|---|---|---|---|---|---|
| SWE1-01 | HSI and allocated functional requirements baselined and traceable | model | PASS | 0 | 1 | yes | 4695 / 1277 | 20.9 s |
| SWE1-02 | atomic, consistent, feasible, objectively verifiable | model | PASS | 0 | 1 | yes | 4685 / 2675 | 41.8 s |
| SWE1-03 | failure/error, reset/startup, caller responsibilities source-supported | model | PASS | 0 | 1 | yes | 4759 / 934 | 16.4 s |
| SWE1-04 | flash/RAM/stack/CPU/timing explicit and measurable | model | PASS | 0 | 1 | yes | 4691 / 951 | 16.9 s |
| SWE1-05 | bidirectional upstream trace and coverage gaps recorded | model | PASS | 0 | 1 | yes | 4691 / 1195 | 18.8 s |
| SWE1-06 | verification criteria and unresolved ambiguities documented | model | PASS | 0 | 1 | yes | 4679 / 839 | 15.1 s |
| SWE1-07 | EARS conformance | deterministic | PASS | 0 major / 0 minor | — | — | — | — |
| SWE1-08 | ReqIF 1.2 export validates | deterministic | PASS | 0 | — | — | — | — |
| **Total** | | | **PASS** | **0** | **6** | **6 of 6** | **28200 / 7871** | **129.9 s** |

- SWE1-07 classified the 10 requirements as EVENT 6, STATE 1 and UBIQUITOUS 3.
- SWE1-08 counted 20 spec objects.
- All 6 calls ended with `finish_reason: stop` in schema mode json_schema.
- The answer content was 220–361 chars per call.

### Gate

`builder.gate_cmd('SWE.1','inspect')` was run as the graph runs it, in inspect-ws after the server had stopped (see
`work/gate.cmd`):
`cat .forge-run/lrtx/SWE.1/inspect-reply.json | PYTHONPATH=<clone> FORGE_STATE_DIR=<inspect-state> FORGE_DATA_ROOT=/mnt/data/forge-c FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first /mnt/data/forge-c/venv/bin/python -m forge_factory.inspection.gate --workspace . --phase SWE.1 --step inspect`

Its decision was **PASS**: reason INS-SWE.1-001, failed_inspections 0, max_rework_cycles 3, rc 0. The gate-log record
has `agent_status` PASS and `agent_ok` true.

## Comparison with the Ornith arm

The Ornith numbers are from [that run's README](../swe1-ornith-standalone-20261031/README.md). Both arms used the same
start workspace (trial 06) and the same profile.

| Measure | Ornith-1.5-35B-A3B author | Qwen3.8-27B author (this run) |
|---|---|---|
| Server for the author | standalone, `--reasoning off`, 64K, direct (no gateway) | factory argv, reasoning on (medium), 256K, through the gateway |
| Code | `31231e0c` | `2d91c2fa` (adds CAPA-075) |
| Visit PASS / gate FROZEN | 2 / 2 | 2 / 2 |
| Requirements a01 / a02 | 11 / 8 | 10 / 9 |
| Model-authored part (CRC_IDR + crosscutting) a01 / a02 | 2+4 / 2+1 | 2+3 / 2+2 |
| Author calls a01 / a02 (total) | 3 / 3 (6) | 2 / 4 (6) |
| Prompt / output tokens a01 | 5588 / 2004 | 3173 / 5369 |
| Prompt / output tokens a02 | 5266 / 1275 | 4353 / 9916 |
| Author wall a01 / a02 (modelcmp total) | 15.1 s / 9.7 s (29.8 s) | 79.7 s / 148.5 s (228.8 s) |
| First call valid, CRC_IDR (a01, a02) | yes, yes | yes, no |
| First call valid, crosscutting (a01, a02) | no, no | yes, no |
| First-call validity, all tasks | 2 of 4 | 2 of 4 |
| Author VRAM peak | 38152 MiB | 46590 MiB (shared server) |
| Inspector | Qwen3.8-27B, medium | Qwen3.8-27B, medium (same model as the author) |
| Inspected baseline | Ornith a01, 11 SWRs, `b6af5383…` | Qwen a01, 10 SWRs, `413e7103…` |
| Inspector verdict | PASS, 0 findings, 8/8 items PASS | PASS, 0 findings, 8/8 items PASS |
| Inspector calls / first call valid | 9 / 3 of 6 items | 6 / 6 of 6 items |
| Inspector prompt / output tokens | 46384 / 12999 | 28200 / 7871 |
| Inspector call wall (runner pass) | 205.3 s (206.1 s) | 129.9 s (130.5 s) |
| Inspect gate | PASS | PASS |

Notes on this comparison:
- **Different serving.** The author arms differ in more than the model. Ornith ran with thinking off on a direct
  server; Qwen ran with the profile's thinking (medium, +8192 output tokens) through the gateway. Qwen's higher
  output tokens and wall times are mostly thinking. They are not a like-for-like speed comparison.
- **Different baselines.** Each inspection inspected a different baseline. In the Ornith arm, 3 items needed a repair:
  2 of them were "PASS with findings" (see that run's FINDINGS item 2) and 1 cited evidence paths that are not
  sources. Here no item needed a repair. This run cannot say whether that comes from the baseline or from variance.
- **Weaker independence.** Here the author and the inspector are the same model, so the inspection is less independent
  than in the Ornith arm.
- **Scope.** One register (CRC_IDR, 1 field), so 2 model tasks per attempt, and n = 2 attempts per arm. Neither arm
  measures capability on a full peripheral.

## Read-only proof

`work/snapshot.py` (the Ornith run's script) recorded path, type, size, mtime_ns, mode and sha256 of every entry:
- before the start-ws copy (15:28:21Z);
- after the cleanup (15:38:44Z).

`work/compare.py` reports every root **identical**: 0 added, 0 removed, 0 changed, root mtime unchanged
(`work/ro-compare.json`).

| Root | Entries | Result |
|---|---|---|
| trial 06 `…/WO-AFO-7f71565db57f0a76-a1/workspace` | 706 | identical |
| `/mnt/data/forge-c/operations/swe1-ornith-20261031/report-workspaces` (Ornith a01 + a02) | 1218 | identical |
| `/mnt/data/forge-c/operations/swe1-ornith-20261031/inspect-ws` | 624 | identical |

A second pair, taken just before and after the inspection (`work/ro-inspect-compare.json`), covers the same roots plus
this run's `report-workspaces` (1220 entries). It is identical too, so the inspection wrote nothing into the attempt
copies.

**CAPA-075 observation.** `work/start-ws-vs-source.json` compares start-ws after the run with the trial-06 snapshot.
The only differences are this run's isolation edits:
- `binding.json` and `workflow.toml` changed;
- `durable-binding.json` was moved out;
- the `.forge-run` directory mtime changed as a result.

In particular, `.forge-run/lrtx/SWE.1/development-execution.json` in start-ws keeps the source's mtime (13:43:31.57Z, the time of the Ornith-arm rewrite). The Ornith arm
(code `31231e0c`) had rewritten exactly that file in its start workspace (its deviation 1). That rewrite did not
happen here. This is one observation, not a CAPA effectiveness verdict.

Both intent files keep their sha256. The trial-06 manifest sha256 is unchanged.

## Cleanup (verified 15:38:44Z)

- The server (2661907) stopped on SIGTERM, exit 0, in 1.05 s. The gateway (2662162) is gone too.
- No own llama-server, gateway, monitor or script is still running.
- The GPU is at 936 MiB with 0 compute processes, which equals the baseline.
- Ports 18596, 18597 and 18598 are closed.
- The guard reads `OK`.
- The runner 2742646 and the conductor 3699940 were untouched and still running. gpuq is empty, and no STOP file
  exists.
- The clone's `git status` is clean.

## Deviations

1. **Isolation edits in the scratch copies.** These are the authorized ones, listed above.
   - The `durable-binding.json` move in start-ws had no effect on the author arm: modelcmp never sets
     `RECOVERY_WORKSPACE`, so `structured.call` would not have sent `forge_execution` anyway.
   - It matters for the inspector runner.
2. **Gateway environment.** The gateway ran with the scratch state, `FORGE_DATA_ROOT=/mnt/data/forge-c` and my own
   PATH/HOME, not with the stack's `envmap()` of the profile root. Its Ollama upstream is my own closed port 18598,
   because no Ollama was started. The llama-server got only `LD_LIBRARY_PATH` and `GGML_BACKEND_PATH`.
3. **Profile root.** The root passed to `llama_server_spec` was production-local-014. The profile's `default_root` is
   `/mnt/data/forge-c/delivery-first-014-20261030-v1`.
4. **One gateway state for both steps.** The gateway's `FORGE_STATE_DIR` was `state/`, so its meter and request
   measurements for the author and the inspection are in one folder, `gateway-state/`. The rows can be split by time:
   author 15:32:32–15:35:53Z, inspection 15:36:20–15:38:09Z. The inspector runner and the gate used a fresh
   `inspect-state/`, as in the Ornith arm.
5. **`PYTHONUNBUFFERED=1`** was added to the modelcmp and runner env, so that the per-call progress lines reach
   `progress.log` live. No factory code changed.
6. **Prompt caching across attempts.** a02's first CRC_IDR call had the same prompt as a01's, so the server reused
   1833 of its 1837 prompt tokens from cache (prompt eval 4 tokens). The output was different (a02's first answer was
   rejected), but the attempts are not fully cold.
7. **modelcmp is not a work order.** As in the Ornith arm, `packet()` computes no packet identity, lesson lookup or
   per-task call allowance, because `RECOVERY_WORKSPACE` is unset. Unlike the Ornith arm, the model name is the one
   the profile allows.
8. **Same model as author and inspector.** See the comparison notes. This is not an independent qualification.
9. **Files left out here.** `inventory.json` was not copied, because it contains register description text from the
   RM. It stays on Omniverse2 in the attempt copies. The full start-ws snapshot `start-ws-after.json` was not copied
   either; its diff against the source is.

## Files

- `report.json`: the modelcmp report.
- `progress.log`: the live progress log. It has 13 checkpoint lines at 30 s intervals plus a line for each call,
  attempt, runner pass, the gate and cleanup.
- `attempts/a0{1,2}/` (attempt copies renamed `qwen3.8_27b-q8_0-0{1,2}/workspace` → `a0{1,2}`):
  - `workproducts/SWE.1/{software_requirements.md,.reqif,register_effects.json}`;
  - `traceability/{requirements_to_tests.csv,upstream_gaps.md}`;
  - `safety/software_safety_requirements.md`;
  - the gate records `.forge-run/gates/gate-log.jsonl` and `configuration/baselines/SWE.1/BL-SWE.1-001.json`;
  - the task checkpoints, visit records and `development-execution.json` under `.forge-run/lrtx/SWE.1/`.
- `inspection/inspect-ws/`:
  - `inspection/SWE.1/INS-SWE.1-001.json` and the deterministic SWE1-07/08 records;
  - the item checkpoints, `inspect-reply.json`, `inspections.jsonl` and `inspection-record.json`;
  - the rebound `binding.json` and the gate log.
- `gateway-state/llm-gateway/{usage,request-measurements}.jsonl`: the gateway meter, with shape and usage only.
- `work/`:
  - the scripts (guard, serve, run, monitor, spec, isolate, snapshot, compare);
  - the server argv, log, VRAM samples and stop record;
  - `llama.spec.json` and `gateway.env.json`;
  - the isolation records and the moved `isolated-start/durable-binding.json`;
  - modelcmp and runner stdout/stderr (stderr is empty);
  - the gate command, output and exit code;
  - the read-only snapshots and comparisons.

The server log has 0 matches for requirement or register text. The gateway log is empty. No reasoning text was kept:
the gateway stripped it from every response (`reasoning_stripped: true`), and the checkpoints hold no reasoning or
prompt messages. Nothing was committed or pushed.

On Omniverse2, `/mnt/data/forge-c/operations/swe1-qwen-20261031/` keeps:
- `repo/`, `start-ws/`, `report-workspaces/` and `inspect-ws/`;
- `state/`, `inspect-state/` and `work/`;
- `report.json` and `progress.log`.
