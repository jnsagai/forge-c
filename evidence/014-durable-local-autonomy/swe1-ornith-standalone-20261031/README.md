# Standalone SWE.1 author test with Ornith on Omniverse2, 31 October 2026

This is a measurement, not a qualification. The owner authorized it on 2026-10-31 ("Yes, author only"). It ran the
unchanged Forge-C SWE.1 structured author (`forge_factory.lrtx.modelcmp` → `lrtx.swe1.visit` → the unchanged author
gate). The author model was Ornith-1.5-35B-A3B Q8_0 on one standalone llama-server. AFO, Fabro, the gateway and every
existing process were not involved. No inspector ran.

**Result:** 2 of 2 attempts gave visit PASS and author gate `FROZEN` (BL-SWE.1-001 in each copy). Attempt 1 has 11
requirements and attempt 2 has 8. modelcmp exit code 0, total wall time 29.8 s, 6 model calls. One hard constraint
was broken by factory code: see deviation 1.

## Preflight (read-only, 2026-10-31T13:35:35Z): PASS

| Check | Observed |
|---|---|
| GPU | RTX 6000 Ada, 936 MiB used of 49140, 0 % utilization, no compute process |
| AFO intent `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json` | STOPPED, epoch 7, sha256 `9eff2df3…f4d545` (unchanged at the end) |
| production-local-014 intent `/home/omniverse2/.local/state/forge-c-production-014/operations.json` | PAUSED, epoch 111, sha256 `1387fbb2…947e63c` (unchanged at the end) |
| gpuq `/mnt/data/forge-c/inspector-014-b309039/gpuq` | `pending/` and `running/` empty. No STOP file, and none was created. |
| Own llama-server | none |
| Idle processes left alone | conductor 3699940 (heartbeat OBSERVE_ONLY / operations_wait), gpuq runner 2742646, idle ollama/llm_gateway |

## Code and start workspace

- Code: a new clone at `/mnt/data/forge-c/operations/swe1-ornith-20261031/repo`, HEAD
  `31231e0c081084e7c78b54ec7f66e211000717f2`, contained in `origin/feat/014-durable-local-autonomy`. No factory file
  was changed. The clone is kept.
- Start workspace (trial 06, order `afo-7f71565db57f0a76`, native `01M67ZJWDYS7H33828MPTK6E6D`):
  `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/state/workorders/WO-AFO-7f71565db57f0a76-a1/workspace`
  - `.forge-run/manifest.json` sha256 `d90e53715711dcd9a4a944782f4dd95f2ffe7b41378ae74adc9fe87d8afca6be`. It was the
    same before and after the run.
  - The manifest gives layer LL, peripheral crc, and `local_profile.id` `local-rtx-v2-omniverse2-q38-delivery-first`
    (config sha `82394277…58e7`, the same as in the checkout).
  - It holds a completed native SWE.1 (11 SWRs) and the RM0486 input sections, including
    `inputs/sections/RM0486/26.4.2_CRC_independent_data_register_CRC_IDR.md`.
  - It contains no symlinks.
- modelcmp's `_fresh_copy` put the attempt copies in
  `/mnt/data/forge-c/operations/swe1-ornith-20261031/report-workspaces/ornith-1.5-35b-a3b-q8-0{1,2}/workspace`.

## Server

```
/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3 --alias ornith-1.5-35b-a3b-q8 --host 127.0.0.1 --port 18592 --no-webui --offline -c 65536 -np 1 --jinja --reasoning off --cache-type-k f16 --cache-type-v f16 --flash-attn on --gpu-layers all -b 2048 -ub 2048 --spec-type none --fit off --metrics
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/ollama-0.34.0/lib/ollama)
```

| Item | Value |
|---|---|
| PID | 2550827 |
| Started | 2026-10-31T13:42:55.05Z |
| Stopped | 13:43:43Z (SIGTERM, exit 0, 1.06 s) |
| Model loaded (server log) | 5.49 s |
| `/health` OK | 6.32 s |
| n_ctx_slot | 65536, 1 slot |
| VRAM peak | **38152 MiB** (baseline 936, so about 37.2 GB above baseline; the 32K protocol run peaked at 37384) |
| Decode | 150.7–155.1 tok/s (server `print_timing`) |
| Prompt eval | 4.7k–6.7k tok/s |

A 1 s watcher ran next to the server. On each tick it checked:
- gpuq `pending` and `running`;
- foreign GPU compute processes;
- the conductor heartbeat;
- the sha256 of both intent files;
- the 15:00:00Z wall deadline.

It never fired. The last guard result was `OK`, and there are no ABORT records.

## Run

From `repo/factory/python`:

```
python -m forge_factory.lrtx.modelcmp --workspace <start ws> --model ornith-1.5-35b-a3b-q8 --repeat 2 --phase SWE.1 --out /mnt/data/forge-c/operations/swe1-ornith-20261031/report.json
```

The environment was:

| Variable | Value |
|---|---|
| `FORGE_LRTX_GATEWAY_URL` | `http://127.0.0.1:18592/v1` (direct, no gateway) |
| `FORGE_STATE_DIR` | `/mnt/data/forge-c/operations/swe1-ornith-20261031/state` (fresh) |
| `FORGE_DATA_ROOT` | `/mnt/data/forge-c` |
| `PYTHONPATH` | the checkout's `factory/python` |
| `FORGE_LRTX_PROFILE` | `local-rtx-v2-omniverse2-q38-delivery-first` |
| `PYTHONDONTWRITEBYTECODE` | `1` |
| proxy variables | unset |

Python was the venv at `/mnt/data/forge-c/venv/bin/python`. Default `--max-calls 35`.

The profile sets `structured.semantic_phases: []`, so `author_module` picked `lrtx.swe1`. Every call was made with
schema mode `json_schema` (basis `UNPROBED (default)`) and ended with `finish_reason: stop`.

### Per-attempt results

| Attempt | Visit | Author gate | Calls | Prompt / output tokens | Wall | SWRs (model + deterministic) |
|---|---|---|---|---|---|---|
| a01 | PASS | FROZEN (13:43:21.97Z) | 3 | 5588 / 2004 | 15.1 s | 11 (2 CRC_IDR + 4 crosscutting + 5 budget) |
| a02 | PASS | FROZEN (13:43:31.77Z) | 3 | 5266 / 1275 | 9.7 s | 8 (2 CRC_IDR + 1 crosscutting + 5 budget) |

### Per-task results

| Attempt | Task | First call valid | Calls | Prompt / output | Call wall | Status |
|---|---|---|---|---|---|---|
| a01 | requirements:CRC_IDR | yes | 1 | 1839 / 513 | 3748 ms | VALID |
| a01 | requirements:crosscutting | no | 2 | 3749 / 1491 | 10443 ms | VALID after 1 repair |
| a02 | requirements:CRC_IDR | yes | 1 | 1839 / 471 | 3318 ms | VALID |
| a02 | requirements:crosscutting | no | 2 | 3427 / 804 | 6014 ms | VALID after 1 repair |

The first-call findings in crosscutting came from the deterministic `validate_group`, not from the schema:
- a01 had 3 findings. Each was "acts on CRC_IDR, which the CRC_IDR task covers".
- a02 had 4 findings. Two were the same overlap finding. Two were effect-value format errors: a non-numeric value,
  and a value that is not `""` for `no_write`.

The 5 budget SWRs (flash, static RAM, stack, simulation instructions, simulation time) are rendered deterministically
from the work-order budgets. They are not model output.

`model_loads` is empty and `load_ms_median` is `UNKNOWN`, because no gateway meter exists with a direct server. The load
time above comes from the server log.

### Scope of these results

- The scope is small. The inventory has 1 register (CRC_IDR, 1 field, RM pages 1172–1173), so SWE.1 had 2 model
  tasks. This is the two-function CRC IDR slice, not a full LL peripheral.
- `FROZEN` is the unchanged author gate, i.e. presence, format and traceability checks. No SWE.1 inspection ran. The
  semantic correctness of the requirements has not been independently verified.

## Cleanup proof (13:43:59Z, after the watcher's own stop record)

- PID 2550827 is gone from /proc, and no llama-server of ours is running.
- No `swe1-ornith-20261031/work` script is still running.
- The GPU is at 936 MiB with 0 compute processes, which equals the baseline.
- Port 18592 is closed.
- The guard reads `OK`.
- The runner 2742646 and the conductor 3699940 were still running and were never signalled. gpuq is empty, and no STOP
  file exists.
- Server time used: 48 s. Whole test: about 13:35–13:50Z, inside the 90-minute limit.

## Deviations

1. **The factory wrote into the read-only start workspace (byte-identical content).** In the original,
   `.forge-run/lrtx/SWE.1/development-execution.json` and its directory got a new mtime at 13:43:31.57Z, inside
   attempt 2 just before its gate. The file's 106 bytes are unchanged. The sha256 over all non-`build/` files is
   `3906af4f…bb6d5` before and after. A full listing before and after (`work/source-tree-{before,after}.txt`) differs
   only in these two mtime lines. No file was added or removed. Attempt 1 most likely rewrote the file the same way,
   but only the last mtime can be seen.
   - Cause (code at 31231e0c):
     1. `_fresh_copy` copies `.forge-run/binding.json` unchanged. That file holds the original's absolute `workspace`
        path.
     2. `swe1.write_scoped` → `visit.write_scoped` builds `Authorizer(Binding.load(<copy>/.forge-run/binding.json))`.
        That sets `self.workspace = realpath(binding.workspace)`, i.e. the original.
     3. `Authorizer.decide` → `development_execution.mutation_allowed(self.workspace, …)` →
        `phase_state(<original>, "SWE.1")`. That function rewrites `development-execution.json` with a temp file and
        `os.replace`, and opens the lock file with `a+`.
   - The products themselves were written to the copy (`Path(ws)/rel`).
   - modelcmp's isolation of the start workspace is therefore incomplete whenever a manifest has
     `development_execution`. Nothing was reverted, because resetting the mtime would be one more write.
2. **Model name.** `--model ornith-1.5-35b-a3b-q8` (the server alias) was accepted without any workaround. The
   profile allows only `qwen3.8:27b-q8_0`, but this path never checks it. `packet()` computes the packet identity, the
   lesson lookup and the development call reservation only when `RECOVERY_WORKSPACE` is set, and modelcmp calls
   `visit()` directly without setting it. So the attempts ran with no packet identity, no lessons and no per-task call
   allowance. This is different from a native work order.
3. **Fresh state.** The fresh state folder has no capability probe record, so the schema mode is
   `UNPROBED (default)` json_schema. It also has no gateway meter, so the load is `UNKNOWN` in `report.json`.
4. **progress.log.** This was added at the coordinator's request after the run started. The preflight and checkout
   lines were back-filled at 13:39:15Z (preflight measured at 13:35:35Z). The 30 s checkpoint loop wrote only 2 lines,
   because the whole run took 30 s.
5. **Port and deadline.** The port was 18592, not the protocol's 18591. The hard deadline was set at 15:00:00Z and
   was not reached.
6. **Files left out here.** `inventory.json` was not copied, because it contains register description text from the
   RM. It stays on Omniverse2 in the attempt copies.

## Files

- `report.json`: the modelcmp report.
- `progress.log`: the live progress log.
- `attempts/a0{1,2}/` (attempt copies renamed `ornith-1.5-35b-a3b-q8-0{1,2}/workspace` → `a0{1,2}`):
  - `workproducts/SWE.1/{software_requirements.md,.reqif,register_effects.json}`;
  - `traceability/{requirements_to_tests.csv,upstream_gaps.md}`;
  - `safety/software_safety_requirements.md`;
  - the gate records `.forge-run/gates/gate-log.jsonl` and `configuration/baselines/SWE.1/BL-SWE.1-001.json`;
  - the task checkpoints and visit records under `.forge-run/lrtx/SWE.1/`.
- `work/`:
  - the scripts (guard, server, run, monitor);
  - the server argv, log, VRAM samples and stop record;
  - modelcmp stdout and stderr (stderr is empty);
  - the source-tree listings.

The server log contains no prompt or generated text.

No reasoning text was produced (`--reasoning off`) or kept. Nothing was committed or pushed.

On Omniverse2, these remain:
- `/mnt/data/forge-c/operations/swe1-ornith-20261031/`: the clone `repo/`, `report-workspaces/`, `state/`, `work/`,
  `report.json` and `progress.log`.

---

# Step 2: Qwen inspection of the attempt-1 baseline (owner, 2026-10-31: "now run the Qwen inspection on the produced baseline")

**Result:** the factory's SWE.1 inspector `lrtx.review`, with `qwen3.8:27b-q8_0` behind the factory gateway, inspected
attempt 1's frozen baseline BL-SWE.1-001 (hash `b6af5383c8720b97…`).
- Reply: PASS.
- Record: INS-SWE.1-001 PASS, 0 findings, all 8 checklist items PASS.
- Inspect gate: decision **PASS** (reason INS-SWE.1-001, failed_inspections 0, rc 0).
- Cost: 1 runner pass with no CONTINUE, 9 model calls, 206.1 s.
- The read-only proof is identical for the trial-06 source and both attempt workspaces.

Step 2 started at 13:48:45Z with a preflight PASS: 936 MiB, guard OK, no own server, gpuq empty. It ended at about
14:02Z, inside its 90-minute limit. Outputs are in [inspection/](inspection/).

## Target and isolation (scratch copy only)

`inspect-ws` = `/mnt/data/forge-c/operations/swe1-ornith-20261031/inspect-ws`, a `cp -a` of the attempt-1 workspace.
These isolation edits were made in the copy only and are recorded in `inspection/inspect-work/isolation-edits.json`:

| File in copy | Change | sha256 before → after |
|---|---|---|
| `.forge-run/binding.json` | `workspace`: the trial-06 source path → the inspect-ws path (1 occurrence) | `45026c39…` → `199871fc…` |
| `.forge-run/workflow.toml` | the same path replaced (2 occurrences, in node scripts) | `17ea1c8e…` → `b3ecc4f0…` |
| `.forge-run/durable-binding.json` | **moved out** to `inspect-work/isolated/` (sha `4a853d42…`) | — |

`durable-binding.json` binds the workspace to trial 06's AFO product job
(`afo-product-f6dbe535…`, mission `mission-feature014-delivery-first-20261030`). With that file present, the runner's
`structured.call` would send it as `forge_execution`. The gateway would then route every call through
`afo.request_admission.reserve` for a job that does not exist in the scratch state, and refuse every call. This edit
goes beyond a path rewrite and is recorded as a deviation.

25 files in the copy still name the source workspace path, and they were left unchanged:
- historical delivery-first evidence logs, `result.json`/`latest.json` and `evidence/raw/*`;
- 2 `oracle` executables.

The inspector path does not write to them, and the read-only proof below shows that nothing was written to the source.

## Server and gateway

The argv comes from `forge_factory.lrtx.stack.llama_server_spec`, called from the checkout with:
- `settings('local-rtx-v2-omniverse2-q38-delivery-first')`;
- `FORGE_LRTX_ROOT=/mnt/data/forge-c/production-local-014`;
- `ports['llama']=18593`.

The function checked the Ollama manifest digest (`8f5fb6b7…6039`) and the blob size itself. Only the root and the
port were adapted; the blob path follows from the root.

```
/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf --alias qwen3.8:27b-q8_0 --host 127.0.0.1 --port 18593 --no-webui --offline -c 262144 -np 1 --jinja --reasoning on --cache-type-k f16 --cache-type-v f16 --flash-attn on -b 1024 -ub 512 --spec-type draft-mtp --spec-draft-n-max 3 --reasoning-effort medium --reasoning-format deepseek --gpu-layers all
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama)
```

| Item | Value |
|---|---|
| Context | the full profile context fitted: n_ctx_slot 262144 |
| PID | 2565329 |
| Started | 13:54:42.92Z |
| Model loaded (log) | 4.26 s |
| `/health` OK | 4.85 s |
| VRAM after load | 46558 MiB |
| **VRAM peak** | **46590 MiB** of 49140 (baseline 936) |
| Decode | 64–75 tok/s (server `print_timing`) |
| MTP draft acceptance | 0.72–0.77, mean length 3.2–3.3 |

The binary is byte-identical to `/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server`. The argv is the same as
the one the overnight trial recorded in `model-profile.json` (that run used port 11457).

The gateway is the factory's own process, `forge_factory.llm_gateway --port 18594 --upstream http://127.0.0.1:18595
--meter <inspect-state>/llm-gateway/usage.jsonl`, PID 2565552. Its env was taken from `stack._start`:

| Variable | Value |
|---|---|
| `FORGE_GATEWAY_REASONING` | `{"qwen3.8:27b-q8_0": {"effort": "medium", "extra_output_tokens": 8192, "role_efforts": {}, "system_message_order": "merge_first"}}`, from `stack.gateway_reasoning` |
| `FORGE_GATEWAY_ROUTES` | `{"qwen3.8:27b-q8_0": "http://127.0.0.1:18593"}` |
| `FORGE_GATEWAY_MAX_INFLIGHT` / `FORGE_GATEWAY_MAX_QUEUE` / `FORGE_GATEWAY_MAX_WAIT_S` | 1 / 8 / 21600 |
| `FORGE_GATEWAY_SAMPLE_S` | 10 |
| `FORGE_GATEWAY_REQUEST_MEASUREMENT` | `{"qwen3.8:27b-q8_0": "native_template_plus_serialized"}` |
| `FORGE_GATEWAY_MEASURE_UNBOUND` | 1 |
| `FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT` | 262144 |
| `FORGE_GATEWAY_REQUEST_TIMEOUT_S` | 21600 |
| `FORGE_GATEWAY_DROP_RETRIES` | 0 |
| `FORGE_STATE_DIR` | `/mnt/data/forge-c/operations/swe1-ornith-20261031/inspect-state` (fresh) |
| `FORGE_DATA_ROOT` | `/mnt/data/forge-c` |

The profile's `role_efforts` is `{}`, so `swe1-inspector` gets the model effort `medium`. The gateway therefore sets
`enable_thinking: true` and raises `max_tokens` from 2048 to 10240. Evidence that this happened:
- all 9 request measurements record `output_reserve_tokens: 10240`;
- all 9 meter rows record `reasoning_stripped: true`.

## Inspection run

```
python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace <inspect-ws> --model qwen3.8:27b-q8_0 --time-budget 1200
```

The command ran from `repo/factory/python` with `/mnt/data/forge-c/venv/bin/python` and this environment:

| Variable | Value |
|---|---|
| `FORGE_LRTX_GATEWAY_URL` | `http://127.0.0.1:18594/v1` |
| `FORGE_STATE_DIR` | `<inspect-state>` |
| `FORGE_DATA_ROOT` | `/mnt/data/forge-c` |
| `PYTHONPATH` | the checkout |
| `FORGE_LRTX_PROFILE` | `local-rtx-v2-omniverse2-q38-delivery-first` |
| `PYTHONDONTWRITEBYTECODE` | `1` |
| proxy variables | unset |

The 1200 s time box is the builder's default `visit_time_s`. The inspector module was **`lrtx.review`**, because the
profile sets `semantic_inspect_phases: []`. Pass 1 returned PASS, so no `--resume` was needed: 9 calls, 206.1 s,
0 continuations.

### Verdicts and findings per checklist item

| Item | Criterion (factory checklist, short form) | Source | Verdict | Findings | Calls | First call valid |
|---|---|---|---|---|---|---|
| SWE1-01 | HSI and allocated functional requirements baselined and traceable | model | PASS | 0 | 2 | no: PASS with findings |
| SWE1-02 | atomic, consistent, feasible, objectively verifiable | model | PASS | 0 | 1 | yes |
| SWE1-03 | failure/error, reset/startup, caller responsibilities source-supported | model | PASS | 0 | 2 | no: PASS with findings |
| SWE1-04 | flash/RAM/stack/CPU/timing explicit and measurable | model | PASS | 0 | 2 | no: 2 non-source paths in evidence_checked |
| SWE1-05 | bidirectional upstream trace and coverage gaps recorded | model | PASS | 0 | 1 | yes |
| SWE1-06 | verification criteria and unresolved ambiguities documented | model | PASS | 0 | 1 | yes |
| SWE1-07 | EARS conformance | deterministic | PASS | 0 major / 0 minor | — | — |
| SWE1-08 | ReqIF 1.2 export validates | deterministic | PASS | 0 | — | — |

SWE1-07 classified the 11 requirements as EVENT 6, STATE 2 and UBIQUITOUS 3. SWE1-08 counted 22 spec objects.

For SWE1-01 and SWE1-03, the first answer was a PASS verdict that carried findings. `validate_verdict` rejects that
combination ("a PASS verdict carries no findings"). The repair answer was PASS with no findings. Those first findings
were not retained (only the validator codes were), so whether they had substance cannot be judged from this run.

### Calls, tokens and wall time

| Item / call | Prompt tokens | Output tokens (incl. thinking) | Call wall |
|---|---|---|---|
| SWE1-01 #0 | 5006 | 1449 | 23.4 s |
| SWE1-01 #1 | 5471 | 256 | 4.6 s |
| SWE1-02 #0 | 4996 | 3631 | 54.7 s |
| SWE1-03 #0 | 5070 | 1831 | 28.2 s |
| SWE1-03 #1 | 5625 | 541 | 8.4 s |
| SWE1-04 #0 | 5002 | 1655 | 29.0 s |
| SWE1-04 #1 | 5222 | 1034 | 15.3 s |
| SWE1-05 #0 | 5002 | 1178 | 19.4 s |
| SWE1-06 #0 | 4990 | 1424 | 22.3 s |
| **Total** | **46384** | **12999** | **205.3 s** (runner pass 206.1 s) |

- All 9 calls ended with `finish_reason: stop`, schema mode json_schema.
- `usage` does not separate thinking from answer tokens. The answer content was 182–2109 chars per call.
- The gateway's native request measurement gave 5346–5994 input tokens; all 9 fitted the 262144 limit.

### Gate

`builder.gate_cmd('SWE.1','inspect')` was run as the graph runs it:
`cat .forge-run/lrtx/SWE.1/inspect-reply.json | PYTHONPATH=<checkout> FORGE_STATE_DIR=<inspect-state> FORGE_DATA_ROOT=/mnt/data/forge-c FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first /mnt/data/forge-c/venv/bin/python -m forge_factory.inspection.gate --workspace . --phase SWE.1 --step inspect`,
in inspect-ws, after the server had stopped.

Its decision was **PASS** (reason INS-SWE.1-001, failed_inspections 0, max_rework_cycles 3, rc 0). The gate-log
record has `agent_status` PASS and `agent_ok` true.

## Read-only proof

`inspect-work/snapshot.py` recorded path, type, size, mtime_ns, mode and sha256 of every entry before (13:53:06Z) and
after (13:58:30Z) the run. It covered:
- the trial-06 source (706 entries);
- attempt 1 (607 entries);
- attempt 2 (607 entries).

`compare.py` reports all three **identical**: 0 added, 0 removed, 0 changed, and root mtime unchanged
(`inspection/inspect-work/ro-compare.json`). Both intent files keep their sha256.

## Cleanup (13:58:27Z)

- The server (2565329) stopped on SIGTERM, exit 0, in 1.06 s. The gateway (2565552) is also gone.
- No own llama-server, gateway or script is still running.
- The GPU is at 936 MiB with 0 compute processes.
- Ports 18593, 18594 and 18595 are closed.
- The guard reads `OK`.
- The runner 2742646 and the conductor 3699940 were untouched. gpuq is empty, and no STOP file exists.
- Server time used: 215 s.

## Step 2 deviations

1. **Isolation edits in the copy**, listed above. Removing `durable-binding.json` is more than the authorized path
   rewrite. Without it the run was standalone, which matches step 1 (no AFO). The gateway took its unbound path,
   with request measurement scoped `STANDALONE_NO_DURABLE_ACCOUNTING`.
2. **Gateway environment.** The stack would give the gateway `envmap()` of the profile root, including
   `FORGE_STATE_DIR=<root>/state`. Instead it ran with the scratch state, `FORGE_DATA_ROOT=/mnt/data/forge-c` and my
   own PATH/HOME.
3. **Gateway upstream.** The Ollama upstream is my own closed port 18595, because no Ollama was started. The routed
   model needs no residency or preload, and the resource samples show residency `UNKNOWN`.
4. **llama-server environment.** It got only `LD_LIBRARY_PATH` and `GGML_BACKEND_PATH`. The stack also passes
   `envmap()`.
5. **Profile root.** The root passed to `llama_server_spec` was production-local-014. The profile's own `default_root`
   is `/mnt/data/forge-c/delivery-first-014-20261030-v1`.
6. **Not a qualification.** The author (Ornith) and the inspector (Qwen) are different models, but this is not an
   independent qualification of the inspector. The verdicts are one Qwen inspection of one small baseline. In 2 items the model's first answer had findings that it dropped under the
   validator's repair (see above).

The logs contain no prompt or generated text: the server log has 0 matches for requirement/register text and the
gateway log is empty. Meter rows are shape and usage only. No reasoning text was kept. Nothing was committed.
