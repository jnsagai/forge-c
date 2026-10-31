# Standalone SWE.1 test with Qwen3-Coder-Next as author and inspector on Omniverse2, 31 October 2026

This is a measurement, not a qualification. The owner authorized it on 2026-10-31 ("lets try also qwen3-coder-next
q4_K_M, both as author and inspector"). It is the fourth arm after:
- [swe1-ornith-standalone-20261031](../swe1-ornith-standalone-20261031/README.md) (Ornith author, thinking off);
- [swe1-qwen-standalone-20261031](../swe1-qwen-standalone-20261031/README.md) (Qwen author, medium);
- [swe1-qwen-xhigh-standalone-20261031](../swe1-qwen-xhigh-standalone-20261031/README.md) (Qwen author, xhigh).

The inspection of the Ornith attempt-2 baseline repeats the
[inspector omission test](../swe1-inspector-omission-20261031/README.md) with this model.

The model was `qwen3-coder-next:q4_K_M` (Qwen3-Next architecture, 79.7B parameters, Q4_K_M, 512 experts with 10
active). It ran on one standalone llama-server with partial MoE expert offload, called directly with no gateway. AFO,
Fabro and every existing process were not involved.

**Result:**
- **Protocol: PASS.**
  - Strict `json_schema`: 20 of 20 answers were exact and schema-valid.
  - Truncation: 4 of 4 reported `finish_reason: length`.
  - Streaming: usage was correct.
  - The factory's `structured.call()` worked, including `OUTPUT_TRUNCATED_AT_RESERVE`.
- **Author: 1 of 2 attempts FROZEN.**
  - a01: visit **FAILED**, and the author gate did not run. The crosscutting task was still INVALID after 3 calls (see
    "Author failure, exact cause").
  - a02: visit PASS and gate `FROZEN`, with 8 requirements (BL-SWE.1-001, hash `528a461d…`).
  - modelcmp exited with code 0, after 53.9 s of wall time and 9 model calls.
  - **No first call was valid** in either attempt (0 of 4 tasks).
- **Inspection (a), its own attempt-1 baseline: NOT RUN.** Attempt 1 has no frozen baseline, and the brief only allows
  inspection (a) on a FROZEN attempt 1. Attempt 2 was not inspected in its place.
- **Inspection (b), the Ornith attempt-2 baseline (omission target):**
  - Record: INS-SWE.1-001 **FAIL**. SWE1-06 FAILED with severity major and 3 findings; the other 7 items PASSED.
  - Inspect gate: **REWORK** (rc 11, failed_inspections 1).
  - Cost: 1 runner pass, 8 calls, 34.8 s.
  - **No finding names any of the three missing obligations** (no polling, no error code on a valid call, changing only
    the IDR field).
- **Read-only proof:** trial 06 and all five earlier run directories are unchanged, with one exception. The `.git`
  directory mtime of the clone changed, caused by my own `git status` after the run (deviation 7).

## Preflight (read-only, 2026-10-31T16:45:47Z): PASS

| Check | Observed |
|---|---|
| GPU | RTX 6000 Ada, 936 MiB used of 49140, 0 % utilization, no compute process |
| AFO intent `/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/control/operations.json` | STOPPED, epoch 7, sha256 `9eff2df3…f4d545` (unchanged at the end) |
| production-local-014 intent `/home/omniverse2/.local/state/forge-c-production-014/operations.json` | PAUSED, epoch 111, sha256 `1387fbb2…947e63c` (unchanged at the end) |
| gpuq `/mnt/data/forge-c/inspector-014-b309039/gpuq` | `pending/` and `running/` empty. No STOP file, and none was created. |
| Own processes | no own llama-server or script. Port 18610 was free. |
| Guard (`work/guard.sh`, byte-identical to the earlier arms') | `OK` |
| Host memory | 125 GiB total, 117 GiB available, 24 CPUs |
| Not mine, left alone | gpuq runner 2742646, conductor 3699940, the idle `llm_gateway` processes 212513, 781321, 1969873, 1978292 and 2624654, and a `tail -F progress.log` (PID 2772065) whose cwd is the xhigh arm's folder |

The time limit was 150 minutes, from 16:45:47Z to 19:16:20Z. The server watcher had a hard deadline at 19:05:00Z, and
no inspector pass could start after 18:45:00Z. The run used 16:45–17:03Z. The server-load wait took 11 of those 18
minutes.

## Model and chat template

- Manifest: `production-local-014/ollama-models/manifests/registry.ollama.ai/library/qwen3-coder-next/q4_K_M`.
- Model layer: `sha256-30e51a7c…2ffb`, 51741599936 bytes. The size matches the manifest; the sha256 was not recomputed.
- GGUF metadata, read with my own KV reader (`work/ggufmeta.py`, output `work/gguf-meta.json`):

| Key | Value |
|---|---|
| Architecture | `qwen3next` |
| Parameters | 79674391296 |
| File type | 15 (Q4_K_M) |
| Blocks | 48 |
| Full-attention interval | 4 (SSM layers in between) |
| Experts | 512, of which 10 used |
| Training context | 262144 |

**Thinking mode: none.**
- The GGUF chat template (6067 chars) contains no `<think>` tag, no `enable_thinking` and no `reasoning_content`. It does
  contain tool-call handling.
- The served `/props` agrees: `supports_reasoning_effort: false` and `supports_preserve_reasoning: false`, and the
  served template has no `<think>` (`work/protocol-result.json` → `props`).
- In the protocol run, no response carried `reasoning_content` (0 of 20 Q1 answers).
- The template text itself was not copied here (vendor text).

## Server

```
/mnt/data/forge-c/ollama-0.34.0/lib/ollama/llama-server --model /mnt/data/forge-c/production-local-014/ollama-models/blobs/sha256-30e51a7cb1cf1333b9e298b90b4c7790fe2572d8736b002482a0ac96328a2ffb --alias qwen3-coder-next:q4_K_M --host 127.0.0.1 --port 18610 --no-webui --offline -c 65536 -np 1 --jinja --reasoning off --cache-type-k f16 --cache-type-v f16 --flash-attn on --gpu-layers all --n-cpu-moe 10 -b 2048 -ub 2048 --spec-type none --fit off --metrics
env LD_LIBRARY_PATH=<lib>:<lib>/cuda_v13 GGML_BACKEND_PATH=<lib>/cuda_v13/libggml-cuda.so   (lib=/mnt/data/forge-c/ollama-0.34.0/lib/ollama)
```

This is the Ornith direct-server argv with these changes:
- the model, alias and port;
- **`--n-cpu-moe 10`**: this build supports `--n-cpu-moe` (and `--override-tensor`, `--cpu-moe`), so the expert
  weights of the first 10 of 48 layers stay in host RAM, and every other tensor is on the GPU.

The build is `0.3.0-dev (build 1, commit 0f3a71be1)`.

`N=10` was chosen from an estimate:
- The expert tensors are about 97 % of the 49343 MiB of weights, so about 1 GiB per layer.
- The target was VRAM ≤ 46 GB with the 936 MiB baseline, KV and compute buffers.
- No other value was tried.

| Item | Value |
|---|---|
| PID | 2793648 |
| Started | 16:48:45Z |
| Model loaded (server log) | 649.8 s |
| `/health` OK | 650.9 s |
| Context | n_ctx_slot 65536, 1 slot (the preferred 65536 fitted) |
| VRAM after load | 43564 MiB |
| **VRAM peak** | **43632 MiB** of 49140 (baseline 936; about 42.7 GB above it) |
| Host RSS peak | 57909672 kB (55.2 GiB): 6913268 kB anonymous, 50689152 kB file-backed (mmap of the model) |
| Decode | 80.0–90.0 tok/s on the 25 requests with ≥ 100 output tokens. All author and inspector requests ran at 84.8–90.0 tok/s (server `print_timing`). |
| Prompt eval | 1087–1921 tok/s on the author and inspector requests |
| Stopped | 17:02:34Z, SIGTERM, exit 0, 2.08 s. Server time used: 829 s, of which 651 s was loading. |

**Why the load was slow.** At load the server logged `tensor overrides to CPU are used with mmap enabled - consider
using --load-mode none`. RSS grew at about 70–190 MB/s while the file was paged in from disk, and VRAM stayed at
1370 MiB until the end of the load. The default mmap load mode was kept.

**Watcher.** `work/serve.sh` ran next to the server. It is the earlier arms' 1 s watcher without the gateway, plus two
additions: host RSS sampling and a VRAM stop at 46500 MiB. On each tick it checked:
- gpuq `pending` and `running`;
- foreign GPU compute processes;
- the conductor heartbeat;
- the sha256 of both intent files;
- the wall deadline;
- VRAM above 46500 MiB.

It recorded 759 samples (`work/vram.csv`: epoch, VRAM MiB, VmRSS, RssAnon and RssFile in kB) and never fired. The
last guard result was `OK`, and there is no `ABORT` file.

## Step 1: protocol check: PASS (`work/protocol-result.json`)

The check ran 16:59:47Z–17:00:42Z against the direct server (`work/protocol.py`), with synthetic prompts only. The
schemas were the factory's own:
- `structured.PROBE_SCHEMA`;
- a nested enum/array schema;
- `swe1.GROUP_SCHEMA`;
- `review.VERDICT_SCHEMA`.

Every answer was checked with `jsonschema` (Draft 2020-12) and with the factory's `structured.validate`.

| Q | Verdict | Evidence |
|---|---|---|
| Q1: strict `json_schema` answers are exact and schema-valid | **PASS** | 20 requests: 5 schemas × stream on/off × seed 1/2. All 20 ended with `stop`, all 20 are exact JSON (no surrounding whitespace, no fence, `json.loads` of the whole content), and all 20 are schema-valid under both validators. The adversarial prompt asked for a fence, an extra `confidence` field and a trailing sentence; it still gave plain, valid JSON. The no-schema control with the same prompt was not exact JSON and not schema-valid. |
| Q3: `finish_reason` on truncation | **PASS** | `swe1.GROUP_SCHEMA` with `max_tokens` 8 and 64, stream on and off: 4 of 4 gave `finish_reason: length` and unparseable partial JSON. `structured.call()` with reserve 16 reported `NOT_JSON:…` + `OUTPUT_TRUNCATED_AT_RESERVE`. |
| Q5: streaming usage | **PASS** | With `include_usage`, each of the 12 streamed Q1/Q3 requests had exactly one usage chunk, with `choices: []`, before `data: [DONE]`. Without `include_usage` there was no usage chunk. `structured.call()` (reserve 4096) received usage (129 prompt / 420 completion tokens), `finish_reason: stop` and no errors. |

The run went on to the factory only because Q1 was PASS (`run.sh` stops otherwise).

## Step 2: author arm

Scratch start copy `start-ws` = `/mnt/data/forge-c/operations/swe1-codernext-20261031/start-ws`, a fresh `cp -a` of
trial 06 (`…/WO-AFO-7f71565db57f0a76-a1/workspace`). It had the same recorded edits as the Qwen arm
(`work/isolation-edits-start.json`):
- `binding.json`: workspace path → start-ws (1 occurrence);
- `workflow.toml`: the same (2 occurrences);
- `durable-binding.json`: moved to `work/isolated-start/`;
- 57 historical files still name the trial-06 path and were left unchanged.

```
python -m forge_factory.lrtx.modelcmp --workspace <start-ws> --model qwen3-coder-next:q4_K_M --repeat 2 --phase SWE.1 --out /mnt/data/forge-c/operations/swe1-codernext-20261031/report.json
```

The command ran from the clone's `factory/python` with `/mnt/data/forge-c/venv/bin/python` and this environment:
- `FORGE_LRTX_GATEWAY_URL=http://127.0.0.1:18610/v1`: **the server directly, no gateway**;
- `FORGE_STATE_DIR=<run>/state` (fresh);
- `FORGE_DATA_ROOT=/mnt/data/forge-c`;
- `PYTHONPATH=<clone>/factory/python`;
- `FORGE_LRTX_PROFILE=local-rtx-v2-omniverse2-q38-delivery-first`;
- `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`;
- proxy variables unset.

**Why direct.** The model has no thinking mode, so there was nothing for `FORGE_GATEWAY_REASONING` to control. This is
the Ornith arm's method. Every call used json_schema (basis `UNPROBED (default)`) and ended with `finish_reason: stop`.

### Per-attempt results

| Attempt | Visit | Author gate | Calls | Prompt / output tokens | Wall | SWRs |
|---|---|---|---|---|---|---|
| a01 | **FAILED** | NOT_RUN (visit FAILED) | 5 | 8945 / 1449 | 26.1 s | none frozen. The tasks gave 2 CRC_IDR requirements (VALID) and 1 crosscutting requirement (INVALID). |
| a02 | PASS | FROZEN (17:01:38.38Z) | 4 | 7351 / 1364 | 20.9 s | 8 (2 CRC_IDR + 1 crosscutting + 5 budget) |

The a02 baseline hash is `528a461d74183f11…`. The 5 budget SWRs are rendered deterministically and are not model
output.

### Per-task results (all findings come from the deterministic `validate_group`, none from the schema)

| Attempt | Task | First call valid | Calls | Findings per call | Prompt / output | Call wall | Status |
|---|---|---|---|---|---|---|---|
| a01 | requirements:CRC_IDR | no | 2 | 3, 0 | 4134 / 783 | 11.8 s | VALID after 1 repair |
| a01 | requirements:crosscutting | no | 3 | 6, 1, 4 | 4811 / 666 | 10.6 s | **INVALID** |
| a02 | requirements:CRC_IDR | no | 2 | 1, 0 | 4096 / 785 | 11.2 s | VALID after 1 repair |
| a02 | requirements:crosscutting | no | 2 | 3, 0 | 3255 / 579 | 8.5 s | VALID after 1 repair |

The first-call findings were of the same kinds as in the earlier arms, plus one more:
- non-numeric effect values for the 32-bit IDR field (`'0xXXXXXXXX'`, `'input_value'`, `'caller_value'`);
- verifications without a "passes when …" criterion;
- crosscutting requirements that act on CRC_IDR, which the CRC_IDR task covers;
- one CRC_IDR requirement in the crosscutting task. This last kind was not seen in the earlier arms.

### Author failure, exact cause (a01)

1. Crosscutting call 1 had 6 findings. Most were overlap with the CRC_IDR task.
2. The repair (call 2) produced 21 output tokens and dropped the requirements. Its one finding was that the
   crosscutting task must state the reset/startup behaviour.
3. Call 3 re-added a reset requirement `crc_reset_no_write`, with 4 findings:
   - no pass criterion;
   - the effect statement does not name CRC_IDR.IDR;
   - the value is not `""` for `no_write`;
   - it acts on CRC_IDR.
4. Code at `2d91c2fa`:
   - `swe1._visit` runs the crosscutting task through `visit.run_task` with `max_repairs=2`, so the limit is 3 calls.
   - The bounded extension is granted only if the last answer has fewer findings than the one before. Here it had 4
     against 1, so no extension was granted.
   - `_repair_rounds` applies only to register-group tasks.
   - So the visit returned `FAILED` after 5 of 35 calls (`swe1.py` lines 749–756), and nothing was assembled or frozen.

`model_loads` is empty and `load_ms_median` is `UNKNOWN`, because there is no gateway meter. The load time above comes
from the server log.

## Step 3a: inspection of its own attempt-1 baseline: NOT RUN

The `run.sh` decision was `NO_GO visit=FAILED gate=NOT_RUN (visit FAILED)`. The brief allows (a) only if attempt 1 is
FROZEN. Attempt 2 is FROZEN, but it was not inspected instead, because that would have changed the protocol. That
inspection is possible on request. The server would have to load again (about 11 minutes).

## Step 3b: inspection of the Ornith attempt-2 baseline (omission target)

The copy `inspect-omission` = `/mnt/data/forge-c/operations/swe1-codernext-20261031/inspect-omission`, a fresh `cp -a`
of `swe1-ornith-20261031/report-workspaces/ornith-1.5-35b-a3b-q8-02/workspace`:
- BL-SWE.1-001 hash `c566b006b392caf1…`;
- 8 SWRs.

It had the omission test's edits (`work/isolation-edits-omission.json`):
- `binding.json`: trial-06 path → the copy (1 occurrence);
- `workflow.toml`: the same (2 occurrences);
- `durable-binding.json`: moved to `work/isolated-omission/`;
- the copy carried no earlier SWE.1 inspector checkpoints.

```
python -m forge_factory.lrtx.runner inspect --phase SWE.1 --workspace <inspect-omission> --model qwen3-coder-next:q4_K_M --time-budget 1200
```

The environment was as in step 2, with a fresh `FORGE_STATE_DIR=<run>/inspect-state-omission` and the same direct
server.
- The inspector module was `lrtx.review`, because the profile has `semantic_inspect_phases: []`.
- The output reserve was the review packet's 2048. No gateway was present, so no extra reasoning tokens were added.
- Pass 1 returned `REWORK`, not `CONTINUE`, so no `--resume` pass ran.
- All 8 calls used json_schema (`UNPROBED (default)`) and ended with `stop`.

### Per item

| Item | Verdict | Findings | Calls | First call valid | Prompt / output | Call wall | Names a missing obligation |
|---|---|---|---|---|---|---|---|
| SWE1-01 | PASS | 0 | 2 | no: 3 findings rejected because they judged the owner-recorded NOT_PROVIDED inputs (HSI contract, budget baseline) as failures | 9375 / 412 | 9.2 s | no |
| SWE1-02 | PASS | 0 | 1 | yes | 4386 / 106 | 3.4 s | no |
| SWE1-03 | PASS | 0 | 1 | yes | 4460 / 83 | 3.2 s | no |
| SWE1-04 | PASS | 0 | 1 | yes | 4392 / 83 | 3.2 s | no |
| SWE1-05 | PASS | 0 | 1 | yes | 4392 / 83 | 3.2 s | no |
| SWE1-06 | **FAIL** (major) | 3 | 2 | no: the finding "SWR-003 lacks verification" was rejected, because the document gives one | 9240 / 695 | 11.8 s | **no** (see below) |
| SWE1-07 | PASS (deterministic; EVENT 4, STATE 1, UBIQUITOUS 3) | 0 | — | — | — | — | no |
| SWE1-08 | PASS (deterministic; 16 spec objects) | 0 | — | — | — | — | no |
| **Total** | **FAIL** | **3** | **8** | **4 of 6** | **36245 / 1462** | **34.0 s** (pass 34.8 s) | **none** |

The SWE1-06 findings (model output, quoted from the item checkpoint):
1. "SWR-001 verification criterion is incomplete: it states the test passes when CRC_IDR.IDR reads back the supplied
   value, but does not specify how the read-back is performed (…), nor what constitutes a successful match (…)."
2. "SWR-002 verification criterion is incomplete: it states the returned value must equal the current value of
   CRC_IDR.IDR, but does not document how the reference value is obtained (…)."
3. "Unresolved ambiguities are not documented: e.g., whether consecutive writes before a read are allowed, whether IDR
   must retain its value across function calls without side effects, or whether read-after-write must be in the same
   thread context or interrupt context; these ambiguities are not recorded in the work product."

INS-SWE.1-001 keeps only the first finding's text, truncated, in `detail`. The runner reply was `REWORK`, with issues
`["SWE1-06:major"]`.

**Gate.** `builder.gate_cmd('SWE.1','inspect')` was piped from `inspect-reply.json` in the copy (`work/gate-omission.cmd`).
Its decision was **REWORK**: reason INS-SWE.1-001, failed_inspections 1, max_rework_cycles 3, rc 11. Its stdout starts
with the gate's failure marker `gate execution bi`. No author rework was run.

### Omission-test result

| Inspector on Ornith a02 (`c566b006…`) | Verdict | Findings | Names no polling / no error code / IDR-only change? | Gate | Calls / pass wall |
|---|---|---|---|---|---|
| Qwen3.8-27B medium (omission test) | PASS, 8/8 | 0 | no / no / no | PASS | 6 / 123.3 s |
| Qwen3.8-27B xhigh (omission test) | FAIL, SWE1-02 | 1 (SWR-003 verification wording) | no / no / no | REWORK | 6 / 644.1 s |
| **Qwen3-Coder-Next q4_K_M (this run)** | **FAIL, SWE1-06** | **3** (verification criteria detail; undocumented ambiguities) | **no / no / no** | **REWORK** | **8 / 34.8 s** |

- **No finding names any of the three missing obligations.**
- Finding 3's "whether IDR must retain its value across function calls without side effects" is about value
  retention between calls. It is not the missing obligation that a write changes only the IDR field and preserves the
  other fields (Ornith a01 SWR-006), and it does not name polling or error codes.
- The sources were the same as in the omission test. `lrtx.review.evidence()` gives the inspector only the baseline
  files (without `.reqif`) and the two manifest views.
  - `inputs/IDR-CONTRACT.md` and `inputs/provided-requirements.json` are not inspector sources.
  - The preservation obligation appears nowhere in the inspector's evidence.
  - No polling and no error code appear only in the scope sentence. That sentence is in the manifest views and in the
    a02 document's header.
  - Every item's `evidence_checked` lists only baseline files and manifest paths.
- This model's FAIL is a verifiability and ambiguity judgement under SWE1-06. It is not an obligation-coverage finding.
  Like the xhigh run, it shows that an inspector can reject this baseline, but not because of the omissions.
- In two items the validator's repair loop corrected the model's first answer:
  - SWE1-01: judging NOT_PROVIDED inputs as failures;
  - SWE1-06: claiming a missing verification that is present.
- The SWE1-06 findings were not checked for correctness against the baseline. They are reported as the model gave
  them.

## Comparison with the earlier arms

The earlier numbers come from the linked READMEs. Every arm used trial 06 as the start, the same profile, and a
1-register scope (CRC_IDR, 1 field), with n = 2 attempts. "Inspector" is the inspection of that arm's own attempt-1
baseline; the omission inspections are in the table above.

| Arm | Gate (FROZEN of 2) | Requirements a01 / a02 | Author calls a01 / a02 (total) | Prompt / output tokens a01; a02 | Author wall a01 / a02 (total) | First-call validity | Inspector verdict / findings | Inspector calls | Inspector time (runner pass) |
|---|---|---|---|---|---|---|---|---|---|
| Ornith-1.5-35B-A3B Q8_0, thinking off, direct | 2 / 2 | 11 / 8 | 3 / 3 (6) | 5588 / 2004; 5266 / 1275 | 15.1 / 9.7 s (29.8 s) | 2 of 4 | PASS / 0, by Qwen medium | 9 | 205.3 s (206.1 s) |
| Qwen3.8-27B Q8_0, medium, gateway | 2 / 2 | 10 / 9 | 2 / 4 (6) | 3173 / 5369; 4353 / 9916 | 79.7 / 148.5 s (228.8 s) | 2 of 4 | PASS / 0, by Qwen medium | 6 | 129.9 s (130.5 s) |
| Qwen3.8-27B Q8_0, xhigh, gateway | 2 / 2 | 10 / 8 | 4 / 3 (7) | 7874 / 33448; 5232 / 19208 | 589.4 / 339.8 s (929.8 s) | 1 of 4 | PASS / 0, by Qwen xhigh | 6 | 580.2 s (583.2 s) |
| **Qwen3-Coder-Next q4_K_M, no thinking, direct (this run)** | **1 / 2** (a01 visit FAILED) | **— / 8** | **5 / 4 (9)** | **8945 / 1449; 7351 / 1364** | **26.1 / 20.9 s (53.9 s)** | **0 of 4** | **NOT RUN** (no frozen a01). On Ornith a02: FAIL / 3 | **— (8 on Ornith a02)** | **— (34.0 s / 34.8 s on Ornith a02)** |

Notes:
- **Serving differs between arms.** Ornith and Coder-Next ran with no thinking on a direct server. Qwen ran with
  thinking through the gateway, so its output tokens and wall times are mostly thinking. Coder-Next's decode was
  80–90 tok/s with 10 layers' experts on the CPU (Ornith 151–155, Qwen medium 68–83).
- **Speed and compliance.** Coder-Next was the second-fastest author, after Ornith. It was the only one with no
  first-call-valid task and the only one with a failed visit. Its repairs were short (21–392 output tokens).
- **Different inspected baselines.** Coder-Next did not inspect its own baseline, so its inspector row is not
  comparable to the other three. The like-for-like comparison is the omission table above.
- **Load cost.** The 651 s load (mmap page-in) is not in any wall time above. The other arms loaded in 4–6 s.

## Read-only proof

`work/snapshot.py` (the earlier arms' script) recorded path, type, size, mtime_ns, mode and sha256 of every entry:
- before (16:48:18Z), after the preflight and before any copy;
- after the cleanup (17:03:0xZ).

`work/compare.py` wrote the result to `work/ro-compare.json`:

| Root | Entries | Result |
|---|---|---|
| trial 06 `…/WO-AFO-7f71565db57f0a76-a1/workspace` | 706 | identical |
| `/mnt/data/forge-c/operations/ornith-protocol-20261031` | 51 | identical |
| `/mnt/data/forge-c/operations/swe1-ornith-20261031` (incl. the a02 omission target) | 10671 | identical |
| `/mnt/data/forge-c/operations/swe1-qwen-20261031` (incl. the clone `repo/`) | 11576 | **1 change: the `repo/.git` directory mtime** (16:46:20.74Z → 17:03:01.13Z). 0 added, 0 removed, 0 files changed. See deviation 7. |
| `/mnt/data/forge-c/operations/swe1-qwen-xhigh-20261031` | 2626 | identical |
| `/mnt/data/forge-c/operations/swe1-omission-20261031` | 1343 | identical |

A second pair, taken just before and after the omission inspection (`work/ro-omission-compare.json`), covers the same
roots plus this run's `report-workspaces` (1211 entries). Every root is identical, so the inspection wrote nothing into
the source copy or the attempt copies.

**CAPA-075 observation.** `work/start-ws-vs-source.json` compares start-ws after the run with the trial-06 snapshot.
The only differences are this run's isolation edits:
- `binding.json` and `workflow.toml` changed;
- `durable-binding.json` was moved out;
- the `.forge-run` directory mtime changed as a result.

The factory did not write into the start copy.

Both intent files keep their sha256. The clone's `git status` is clean, and its HEAD is still `2d91c2fa`.

## Cleanup (verified 17:03:00Z)

- The server (2793648) stopped on SIGTERM with exit 0 in 2.08 s.
- No own llama-server, monitor or script is still running.
- The GPU is at 936 MiB with 0 compute processes, which equals the baseline.
- Port 18610 is closed.
- The guard reads `OK`.
- The runner 2742646 and the conductor 3699940 were untouched and still running.
- gpuq `pending` and `running` are empty, and no STOP file exists.
- The `tail -F` 2772065 that was not mine was left running.

## Deviations

1. **Inspection (a) did not run**, because attempt 1 was not FROZEN; see step 3a.
2. **Direct server for the inspector too.** The earlier Qwen inspections ran through the gateway, with
   `extra_output_tokens` and `reasoning_stripped`. Here the inspector called the server directly, with the review
   packet's own reserve of 2048, so no gateway meter or request measurements exist. The packets' `accounting` (the
   factory's serialized-request estimate) is present.
3. **Offload settings are my choice.** These are `--n-cpu-moe 10` (estimated, not tuned), the default thread count
   (`-t -1`) and the default mmap load mode. I added the VRAM > 46500 MiB stop to the watcher.
4. **`--reasoning off`** was passed for parity with the Ornith argv. The template has no thinking mode, so it changes
   nothing.
5. **Model alias outside the profile.** `qwen3-coder-next:q4_K_M` is not in the profile's `models.allowed`, and this
   path does not check it.
   - modelcmp set no `RECOVERY_WORKSPACE`, so the author used no packet identity, lessons or per-task allowance, as in
     the Ornith arm.
   - The schema mode was `UNPROBED (default)` json_schema everywhere.
   - The server's prompt cache was active (`cache_prompt` default), so later calls reused cached prompt prefixes.
6. **Gate timing.** The inspect gate ran while the server was still up. The earlier arms ran it after the stop. The
   gate makes no model call.
7. **`.git` directory mtime in the clone.** My `git status` in the clone at 16:46:20Z (preflight) and again at
   17:03:01Z (cleanup check) created and removed `.git/index.lock`. That moved the directory mtime between the two
   snapshots. No file in `.git` changed. This is the only write to an earlier run's tree, and I made it, not the
   factory.
8. **Snapshot scope.** The proof covers all five earlier run directories in full, which is wider than the earlier arms'
   tree lists.
9. **Files left out here:**
   - `inventory.json` (it contains RM register description text);
   - the chat template text (vendor text);
   - the full `start-ws-after.json`; its diff is included.
   - a01's `traceability/` and `safety/` files, which are byte-identical to trial 06 and are not output of this run.

## Files

- `report.json`: the modelcmp report.
- `progress.log`: the live progress log (44 lines, the last one the cleanup record), in the earlier format: preflight, model, checkout, snapshot,
  server, protocol, attempts and calls, 30 s checkpoints, the inspector pass, the gate, stop and done.
- `attempts/a01/`: `.forge-run/lrtx/SWE.1/` (task checkpoints, `reply.json`, visit records) and the gate log, which
  has no SWE.1 entry from this run.
- `attempts/a02/`:
  - `workproducts/SWE.1/{software_requirements.md,.reqif,register_effects.json}`;
  - `traceability/`;
  - `safety/`;
  - `configuration/baselines/SWE.1/BL-SWE.1-001.json`;
  - the gate log;
  - `.forge-run/lrtx/SWE.1/`.
- `inspection/inspect-omission/`:
  - `inspection/SWE.1/INS-SWE.1-001.json` and the deterministic SWE1-07/08 records;
  - the item checkpoints `packets/inspect__c566b006b392caf1__*.json`, which hold the full finding text;
  - `inspect-reply.json`, `inspections.jsonl` and `inspection-record.json`;
  - `SWE.1-inspect/visit-state.json`;
  - the rebound `binding.json` and the gate log.
- `work/`:
  - the scripts: guard, serve, run, protocol, monitor, isolate, snapshot, compare and ggufmeta;
  - the server argv (`server-ncmoe10.argv`), log, VRAM/RSS samples and stop record;
  - `gguf-meta.json` and `protocol-result.json`;
  - modelcmp and runner stdout/stderr (stderr is empty);
  - `passes-omission.jsonl`;
  - the gate command, output and exit code;
  - the isolation records and the moved `durable-binding.json` files;
  - the read-only snapshots and comparisons.

The server log has 0 matches for requirement or register text. No reasoning text was produced (the model has no
thinking mode, and `reasoning_content` was absent) or kept. `protocol-result.json` holds the final JSON content of the
synthetic protocol prompts only. Nothing was committed or pushed.

On Omniverse2, `/mnt/data/forge-c/operations/swe1-codernext-20261031/` keeps:
- `start-ws/`, `report-workspaces/` and `inspect-omission/`;
- `state/`, `inspect-state-omission/` and `protocol-state/`;
- `work/` (including the template text);
- `report.json` and `progress.log`.
