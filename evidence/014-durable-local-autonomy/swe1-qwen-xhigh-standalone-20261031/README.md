# Standalone SWE.1 author test with Qwen at xhigh on Omniverse2, 31 October 2026 (Qwen xhigh arm)

This is a measurement, not a qualification. The owner queued it on 2026-10-31 ("yes, queue the xhigh arm after this
one"). It is the third arm, after:
- [swe1-ornith-standalone-20261031](../swe1-ornith-standalone-20261031/README.md) (Ornith author, thinking off);
- [swe1-qwen-standalone-20261031](../swe1-qwen-standalone-20261031/README.md) (Qwen author, medium).

Everything is the same as the medium arm except the reasoning effort. Qwen3.8-27B Q8_0 ran at **xhigh for every role**,
with the reasoning settings of the existing profile `local-rtx-v2-omniverse2-q38-aspice-max-mtp`. AFO, Fabro and
every existing process were not involved.

**Result:**
- Author: 2 of 2 attempts gave visit PASS and author gate `FROZEN` (BL-SWE.1-001 in each copy). Attempt 1 has 10
  requirements and attempt 2 has 8. modelcmp exited with code 0, after 929.8 s of wall time and 7 model calls.
- Inspection: Qwen at xhigh inspected attempt 1's BL-SWE.1-001 (hash `148e03cf2670f126…`).
  - Record: INS-SWE.1-001 PASS, 0 findings, all 8 checklist items PASS.
  - Every model item's first call was valid.
  - Cost: 1 runner pass, 6 calls, 583.2 s.
- Inspect gate: decision **PASS** (reason INS-SWE.1-001, failed_inspections 0, rc 0).
- Findings at xhigh: none. The inspector raised no finding that medium did not raise; neither raised any.
- Read-only proof: identical for trial 06, both Ornith workspace trees and all three medium-arm trees.

## Preflight (read-only, 2026-10-31T15:44:20Z): PASS

| Check | Observed |
|---|---|
| GPU | 936 MiB used of 49140, 0 % utilization, no compute process |
| AFO intent | STOPPED, epoch 7, sha256 `9eff2df3…` (unchanged at the end) |
| production-local-014 intent | PAUSED, epoch 111, sha256 `1387fbb2…` (unchanged at the end) |
| gpuq `/mnt/data/forge-c/inspector-014-b309039/gpuq` | `pending/` and `running/` empty. No STOP file, and none was created. |
| Own processes | no own llama-server, gateway or script. Ports 18599, 18600 and 18601 were free. |
| Guard (`work/guard.sh`, the same file as both earlier arms) | `OK` |

The time limit was 120 minutes, from 15:44Z to 17:44:00Z. The server watcher had a hard deadline at 17:35:00Z, and no
inspector pass could start after 17:10:00Z. The run used 15:44–16:15Z and reached neither limit.

## Code, profiles and start workspace

- **Code:** the same clone as the medium arm, `/mnt/data/forge-c/operations/swe1-qwen-20261031/repo`, at
  `2d91c2fa6f7cc7f7983e98259bd4ddb20fba6733`. `git status` is clean after the run.
- **Start copy:** start-ws = `/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031/start-ws`, a **fresh** `cp -a` of
  trial 06. It has the same recorded edits as the medium arm (`work/isolation-edits-start.json`):
  - `binding.json`: the workspace path → start-ws (1 occurrence);
  - `workflow.toml`: the same (2 occurrences);
  - `durable-binding.json`: moved out to `work/isolated-start/`;
  - 57 historical files still name the trial-06 path and were left unchanged.
- **The workspace manifest's `local_profile.id` stays `local-rtx-v2-omniverse2-q38-delivery-first`**, the trial-06
  profile.
  - `FORGE_LRTX_PROFILE` was that same profile for modelcmp, the runner and the gate.
  - So module selection was the same as in the medium arm: author `lrtx.swe1`, because `semantic_phases: []`;
    inspector `lrtx.review`, because `semantic_inspect_phases: []`.
  - The inspector sampling and checklist come from that profile too.
  - Only the server argv and the gateway's reasoning policy came from the max profile.

## Server and gateway

The argv comes from `stack.llama_server_spec` for **`local-rtx-v2-omniverse2-q38-aspice-max-mtp`**, called from the
clone (`work/spec.py`), with:
- root `/mnt/data/forge-c/production-local-014`;
- own port `ports['llama']=18599`.

The function checked the manifest digest (`8f5fb6b7…6039`) and the blob size.

```
/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf --alias qwen3.8:27b-q8_0 --host 127.0.0.1 --port 18599 --no-webui --offline -c 262144 -np 1 --jinja --reasoning on --cache-type-k f16 --cache-type-v f16 --flash-attn on -b 1024 -ub 512 --spec-type draft-mtp --spec-draft-n-max 3 --reasoning-effort xhigh --reasoning-format deepseek --gpu-layers all
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/production-local-014/ollama-0.34.0/lib/ollama)
```

**Difference from the medium arm's argv** (`work/llama.spec.json`, computed by `spec.py` with the same port): one
token, `--reasoning-effort medium` → `--reasoning-effort xhigh`. Both argvs have 38 tokens. The blob, context
(262144), KV type, batch sizes (1024/512), MTP draft 3, `--reasoning on` and `--reasoning-format deepseek` are equal,
as are the two profiles' `runtime.llama_server` blocks except `reasoning_effort` (`work/reasoning-sources.json`).

| Item | Value |
|---|---|
| PID | 2683526 |
| Started | 15:45:00.86Z |
| Model loaded (log) | 4.23 s |
| `/health` OK | 4.82 s |
| Context | n_ctx_slot 262144, 1 slot |
| VRAM after load | 46558 MiB |
| **VRAM peak** | **46590 MiB** of 49140 (baseline 936) |
| Decode | 52.6–70.7 tok/s (13 requests, server `print_timing`) |
| MTP draft acceptance | 0.50–0.78, mean length 2.49–3.35 (medium arm: 0.72–0.97) |
| Stopped | 16:10:32Z, SIGTERM, exit 0, 1.06 s. Server time used: 1531 s. |

The gateway is the factory's own `forge_factory.llm_gateway --port 18600 --upstream http://127.0.0.1:18601 --meter
<scratch>/state/llm-gateway/usage.jsonl`, PID 2683773. Its env (`work/gateway.env.json`) is the medium arm's env with
two changes: the new route port, and `FORGE_GATEWAY_REASONING` replaced by the max profile's `gateway.reasoning`
block. That block was copied from the file through `stack.gateway_reasoning(<max profile>)`:

```
FORGE_GATEWAY_REASONING={"qwen3.8:27b-q8_0": {"effort": "xhigh", "extra_output_tokens": 32768}}
```

The medium block was `{"effort": "medium", "extra_output_tokens": 8192, "role_efforts": {}, "system_message_order":
"merge_first"}`. Copying the max block exactly changes three things in what the gateway sends (`llm_gateway.sanitize_request`):
1. **Effort.** The request carries `reasoning_effort: xhigh` for every role (medium arm: medium).
2. **Output reserve.** It is raised by 32768: author calls 4096 → **36864** and inspector calls 2048 → **34816**
   (medium arm: 12288 / 10240). All 13 request measurements confirm this.
3. **No `chat_template_kwargs.enable_thinking`.** The max block has no `role_efforts` key, so the gateway does not
   set it (the medium arm sent `enable_thinking: true`). Thinking still happened, with the server at
   `--reasoning on`:
   - all 13 meter rows have `reasoning_stripped: true`;
   - the first content delta came 102–271 s into each author first call.

The missing `system_message_order` has no effect here, because every structured packet has one leading system message
(`structured.py`).

Other gateway values: max inflight / queue / wait 1 / 8 / 21600; sample 10 s; request measurement
`native_template_plus_serialized`; measure unbound 1; native context limit 262144; request timeout 21600; drop retries
0; `FORGE_STATE_DIR` = this arm's `state/` (fresh); `FORGE_DATA_ROOT=/mnt/data/forge-c`.

The 1 s watcher (`work/serve.sh`) never fired. It checked gpuq, foreign GPU processes, the conductor heartbeat, both
intent sha256 values and the deadline, and recorded 1419 VRAM samples. The last guard result was `OK`, and there is no
`ABORT` file.

## Author arm (step 1)

```
python -m forge_factory.lrtx.modelcmp --workspace <start-ws> --model qwen3.8:27b-q8_0 --repeat 2 --phase SWE.1 --out /mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031/report.json
```

The environment was:
- `FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18600/v1`;
- `FORGE_STATE_DIR=<xhigh>/state`;
- `FORGE_DATA_ROOT=/mnt/data/forge-c`;
- `PYTHONPATH=<clone>/factory/python`;
- `FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first`;
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`;
- proxy variables unset.

Every call used json_schema and ended with `finish_reason: stop`.

### Per-attempt results

| Attempt | Visit | Author gate | Calls | Prompt / output tokens | Wall | SWRs (model + deterministic) |
|---|---|---|---|---|---|---|
| a01 | PASS | FROZEN (15:54:56.63Z) | 4 | 7874 / 33448 | 589.4 s | 10 (2 CRC_IDR + 3 crosscutting + 5 budget) |
| a02 | PASS | FROZEN (16:00:36.62Z) | 3 | 5232 / 19208 | 339.8 s | 8 (2 CRC_IDR + 1 crosscutting + 5 budget) |

Baseline hashes: a01 `148e03cf…`, a02 `8d858205…`.

### Per-task results

| Attempt | Task | First call valid | Calls | Prompt / output | Call wall | Status |
|---|---|---|---|---|---|---|
| a01 | requirements:CRC_IDR | no (3 findings) | 2 | 4469 / 16322 | 287.9 s | VALID after 1 repair |
| a01 | requirements:crosscutting | no (2 findings) | 2 | 3405 / 17126 | 300.8 s | VALID after 1 repair |
| a02 | requirements:CRC_IDR | yes | 1 | 1875 / 6342 | 107.8 s | VALID |
| a02 | requirements:crosscutting | no (2 findings) | 2 | 3357 / 12866 | 227.5 s | VALID after 1 repair |

All first-call findings came from the deterministic `validate_group`, not from the schema:
- a01 CRC_IDR:
  - 2 requirements did not follow the EARS pattern (`EARS_PATTERN_NONCONFORMANT`);
  - 1 reset/startup requirement was placed in the register task.
- a01 crosscutting: one requirement had an effect value that is not a number fitting the 32-bit field, and it acts on
  CRC_IDR, which the register task covers.
- a02 crosscutting: 2 requirements act on CRC_IDR, which the register task covers.

The first calls produced 6342–15736 output tokens each, mostly thinking: the answer content was only 1488–2109 chars.
The repair calls produced 827–3992 tokens.

There was almost no prompt cache reuse between attempts: a02's first CRC_IDR call reused 279 cached tokens, against
1833 in the medium arm. `model_loads` is empty and `load_ms` is `UNKNOWN`, because every meter row has
`model_loaded_before: true`.

## Inspection (step 2)

Step 2 started because attempt 1 had visit PASS and gate FROZEN.

`inspect-ws` = `/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031/inspect-ws`, a `cp -a` of the attempt-1
workspace. The edits below were made in the copy only (`work/isolation-edits-inspect.json`):
- `binding.json`: the start-ws path → inspect-ws (1 occurrence);
- `workflow.toml`: the same (2 occurrences);
- `durable-binding.json`: already absent.

25 historical files still name the trial-06 path and were left unchanged.

```
python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace <inspect-ws> --model qwen3.8:27b-q8_0 --time-budget 1200
```

The env was the same as the author arm's, except `FORGE_STATE_DIR=<xhigh>/inspect-state` (fresh). Pass 1 returned
PASS, so no `--resume` was needed: 6 calls, 583.2 s (16:00:42–16:10:25Z).

| Item | Source | Verdict | Findings | Calls | First call valid | Prompt / output | Call wall |
|---|---|---|---|---|---|---|---|
| SWE1-01 | model | PASS | 0 | 1 | yes | 4561 / 6029 | 112.7 s |
| SWE1-02 | model | PASS | 0 | 1 | yes | 4551 / 10289 | 194.8 s |
| SWE1-03 | model | PASS | 0 | 1 | yes | 4625 / 2171 | 34.3 s |
| SWE1-04 | model | PASS | 0 | 1 | yes | 4557 / 3748 | 74.3 s |
| SWE1-05 | model | PASS | 0 | 1 | yes | 4557 / 6080 | 109.7 s |
| SWE1-06 | model | PASS | 0 | 1 | yes | 4545 / 2715 | 54.4 s |
| SWE1-07 (EARS) | deterministic | PASS | 0 major / 0 minor | — | — | — | — |
| SWE1-08 (ReqIF) | deterministic | PASS | 0 | — | — | — | — |
| **Total** | | **PASS** | **0** | **6** | **6 of 6** | **27396 / 31032** | **580.2 s** |

- SWE1-07 counted 10 requirements: EVENT 6, STATE 1, UBIQUITOUS 3.
- SWE1-08 counted 20 spec objects.
- The answer content was 304–412 chars per call.

### Gate

`builder.gate_cmd('SWE.1','inspect')` was run in inspect-ws after the server stopped (see `work/gate.cmd`). Its
decision was **PASS**: reason INS-SWE.1-001, failed_inspections 0, max_rework_cycles 3, rc 0.

## Three-way comparison

The Ornith and Qwen-medium numbers are from those runs' READMEs. All three arms started from trial 06 under the
workspace profile `local-rtx-v2-omniverse2-q38-delivery-first`. Each inspection inspected its own arm's a01 baseline.
The inspector was Qwen in all three, at medium for the first two arms and at xhigh here.

| Measure | Ornith author (thinking off) | Qwen author, medium | Qwen author, xhigh |
|---|---|---|---|
| Visit PASS / gate FROZEN | 2 / 2 | 2 / 2 | 2 / 2 |
| Requirements a01 / a02 | 11 / 8 | 10 / 9 | 10 / 8 |
| Model-authored (CRC_IDR + crosscutting) a01 / a02 | 2+4 / 2+1 | 2+3 / 2+2 | 2+3 / 2+1 |
| Author calls a01 / a02 (total) | 3 / 3 (6) | 2 / 4 (6) | 4 / 3 (7) |
| Prompt / output tokens a01 | 5588 / 2004 | 3173 / 5369 | 7874 / 33448 |
| Prompt / output tokens a02 | 5266 / 1275 | 4353 / 9916 | 5232 / 19208 |
| Author wall a01 / a02 (modelcmp total) | 15.1 / 9.7 s (29.8 s) | 79.7 / 148.5 s (228.8 s) | 589.4 / 339.8 s (929.8 s) |
| First call valid, CRC_IDR (a01, a02) | yes, yes | yes, no | no, yes |
| First call valid, crosscutting (a01, a02) | no, no | yes, no | no, no |
| First-call validity, all tasks | 2 of 4 | 2 of 4 | 1 of 4 |
| Inspected baseline | Ornith a01 `b6af5383…` (11 SWRs) | Qwen-medium a01 `413e7103…` (10 SWRs) | Qwen-xhigh a01 `148e03cf…` (10 SWRs) |
| Inspector effort | medium | medium | xhigh |
| SWE1-01 verdict / findings / calls | PASS / 0 / 2 (1st: PASS with findings) | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-02 | PASS / 0 / 1 | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-03 | PASS / 0 / 2 (1st: PASS with findings) | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-04 | PASS / 0 / 2 (1st: non-source evidence paths) | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-05 | PASS / 0 / 1 | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-06 | PASS / 0 / 1 | PASS / 0 / 1 | PASS / 0 / 1 |
| SWE1-07 EARS (deterministic) | PASS (E6 S2 U3) | PASS (E6 S1 U3) | PASS (E6 S1 U3) |
| SWE1-08 ReqIF (deterministic) | PASS (22 objects) | PASS (20 objects) | PASS (20 objects) |
| Inspection verdict / findings | PASS / 0 | PASS / 0 | PASS / 0 |
| Inspector calls | 9 | 6 | 6 |
| Inspector prompt / output tokens | 46384 / 12999 | 28200 / 7871 | 27396 / 31032 |
| Inspector call wall (runner pass) | 205.3 s (206.1 s) | 129.9 s (130.5 s) | 580.2 s (583.2 s) |
| Inspect gate | PASS | PASS | PASS |
| VRAM peak (inspector server) | 46590 MiB | 46590 MiB | 46590 MiB |

**New findings at xhigh compared with medium: none.** The xhigh inspector returned 0 findings on every item, and
every first answer was already valid, so there is no rejected first answer whose findings could have been dropped
either. No finding text exists to quote.

Notes on this comparison:
- **Costly, not more selective.** On this one-register slice, xhigh used about 3.4× (a01 6.2×) the author output
  tokens and about 4× the author wall time of medium. Its first-call validity was not better (1 of 4 against 2 of 4).
  It found the same kinds of task-split errors medium had, and in a01 also EARS phrasing errors. The xhigh inspector
  cost about 4.5× the medium inspector's time and raised nothing more. This is n = 2 authors and 1 inspection per arm
  on different baselines, so it is no evidence for or against xhigh on larger drivers.
- **Different wire shape.** Besides the effort, the xhigh arm sent no `enable_thinking` kwarg (see "Server and
  gateway"). The CRC_IDR first prompt measured 1875 tokens, against 1837 in the medium arm, with the same workspace
  content. The cause of the 38-token difference was not determined; a template-level effect of the request kwargs is
  plausible but not verified.
- **Same model.** The author and the inspector are the same model in both Qwen arms. Not an independent
  qualification.

## Read-only proof

`work/snapshot.py` recorded path, type, size, mtime_ns, mode and sha256 before the start-ws copy (15:44Z) and after
the cleanup (16:10:50Z). `work/compare.py` reports every root **identical**, with 0 added, 0 removed, 0 changed and
root mtime unchanged (`work/ro-compare.json`):

| Root | Entries | Result |
|---|---|---|
| trial 06 `…/WO-AFO-7f71565db57f0a76-a1/workspace` | 706 | identical |
| `swe1-ornith-20261031/report-workspaces` | 1218 | identical |
| `swe1-ornith-20261031/inspect-ws` | 624 | identical |
| `swe1-qwen-20261031/report-workspaces` (medium arm) | 1220 | identical |
| `swe1-qwen-20261031/inspect-ws` (medium arm) | 626 | identical |
| `swe1-qwen-20261031/start-ws` (medium arm) | 705 | identical |

A second pair, taken around the inspection (`work/ro-inspect-compare.json`), covers the same roots plus this arm's
`report-workspaces` (1220 entries). It is identical too.

This arm's start-ws differs from trial 06 only by the isolation edits (`work/start-ws-vs-source.json`): the factory did
not write into the start copy.

Both intent files and the trial-06 manifest sha256 (`d90e5371…`) are unchanged.

## Cleanup (verified 16:10:50Z)

- The server (2683526) stopped on SIGTERM, exit 0, in 1.06 s. The gateway (2683773) is gone too.
- No own llama-server, gateway, monitor or script is still running.
- The GPU is at 936 MiB with 0 compute processes, which equals the baseline.
- Ports 18599, 18600 and 18601 are closed.
- The guard reads `OK`.
- The runner 2742646 and the conductor 3699940 were untouched and still running. gpuq is empty, and no STOP file
  exists.
- The clone's `git status` is clean.

## Deviations

1. **Mixed profile on purpose.** The server argv and the gateway reasoning come from the max profile. Everything else
   comes from the workspace profile, as briefed: the gateway admission and measurement env, module selection, the
   inspector sampling and the checklist. Copying the max reasoning block exactly also dropped `enable_thinking` and
   `merge_first` from the wire; see "Server and gateway".
2. **Same isolation and environment deviations as the medium arm** (its deviations 1–5):
   - the copy edits;
   - the gateway with scratch state, own PATH/HOME and a closed dummy Ollama upstream (18601);
   - the llama-server env limited to `LD_LIBRARY_PATH` and `GGML_BACKEND_PATH`;
   - the production-local-014 root (the max profile's `default_root` is `/mnt/data/forge-c/lrtx-v2-q38-aspice-max`);
   - one gateway state for both steps: author rows 15:48:43–16:00:31Z, inspection rows 16:02:34–16:10:24Z;
   - `PYTHONUNBUFFERED=1`.
3. **Clone reused.** As briefed, this arm used the medium arm's clone, which was unchanged and clean.
4. **modelcmp is not a work order.** There is no packet identity, lesson lookup or per-task call allowance.
5. **Files left out here.** `inventory.json` was not copied, because it contains RM register text. The full start-ws
   snapshot was not copied either; its diff against the source is.

## Files

- `report.json`, `progress.log` (52 checkpoint lines at 30 s intervals, plus a line for each call, attempt, runner
  pass, the gate and cleanup).
- `attempts/a0{1,2}/`: the same file set as the medium arm. That is the SWE.1 work products, traceability and safety
  files, the baseline and gate log, and the task checkpoints and visit records.
- `inspection/inspect-ws/`: INS-SWE.1-001, the deterministic SWE1-07/08 records, the item checkpoints, the reply,
  `inspections.jsonl`, the rebound `binding.json` and the gate log.
- `gateway-state/llm-gateway/{usage,request-measurements}.jsonl`: shape and usage only.
- `work/`:
  - the scripts;
  - `llama.spec.json`, which includes the argv diff against medium;
  - `gateway.env.json` and `reasoning-sources.json`, which hold both profiles' reasoning blocks;
  - the server argv, log, VRAM samples and stop record;
  - the isolation records;
  - modelcmp and runner stdout/stderr (stderr is empty);
  - the gate files and the read-only snapshots and comparisons.

The server log has 0 matches for requirement or register text, and the gateway log is empty. No reasoning text was
kept (`reasoning_stripped: true` on every row). Nothing was committed or pushed.

On Omniverse2, `/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031/` keeps `start-ws/`, `report-workspaces/`,
`inspect-ws/`, `state/`, `inspect-state/`, `work/`, `report.json` and `progress.log`.
