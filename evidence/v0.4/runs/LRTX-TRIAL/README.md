# Feature 010 local RTX trials (profile local-rtx-v1)

Host: RTX 4070 Laptop 8 GB, i9-14900HX, 32 GB RAM. Every agent node runs on qwen3-coder:30b
(digest 06c1097e…, Q4_K_M) through the profile's own Ollama, admission gateway and Fabro server. These run inside
a user+network namespace with no external interface. No ACP and no cloud model were used.

## lrtx1 — baseline on the existing (monolithic agent) graph, factory cb89135, 2026-10-21 11:31–12:31 UTC

`WO-0009A-STM32N6-IWDG-LL-lrtx1`, `--profile local-rtx-v1 --model qwen3-coder:30b`, timeout scale 4 (profile).
Result: **BLOCKED at SWE.1** after 5 failed cycles (rework budget 3 + 2 progress extensions), 49 gaps.

| SWE.1 attempt | Deterministic rejection |
| --- | --- |
| 1 | SAFETY_SCOPE: QM claim in the ASIL B scope (safety statement) |
| 2 | CONTRACT_CASE_ID: duplicate effect case QUERY_WATCHDOG_STATUS |
| 3 | STARTUP_INVARIANT_ON_HOST_TEST: SWR-010 mapped to a host unit test |
| 4 | SAFETY_SCOPE: QM claim again |
| 5 | CONTRACT_CASE_ID again |

The QWEN-TRIAL GPU runs recorded the same failure classes; they are triaged in `../LRTX-T016-REPLAY/replay.json`.

Run verification (`lrtx1/verify.json`, `python -m forge_factory.lrtx.verify_run`): PASS on all eight checks:
- the profile is recorded;
- ACP was rejected and no ACP node exists;
- the network denial was observed (`DENIED_VERIFIED`, interfaces `lo` only);
- the model digest matches the profile;
- the roots are isolated;
- the Fabro providers are local loopback;
- admission metrics are present;
- the package is sealed.

Measurements: 93 model calls with a median prompt of 14,585 tokens (p95 20,754, max 22,568), 1,275,108 input and
18,357 output tokens, one model load of 76 s. Stage records show 3,486 s of inference and 54 s of tool time.
Two limitations of these measurements:
- **Single-chunk answers:** this run used the gateway of cb89135, which recorded the first-delta time as "prefill"
  even when the answer (a tool call) arrived in one chunk (69 of 93 calls). Later gateway code labels those
  UNKNOWN.
- **Queue waits:** these (max 220 s) include three capability-probe calls of the operator interleaved with the run.

## Fabro 0.362 probes (throwaway server in the profile namespace)

1. A command node's stdout is **not** available as `context.response.<node>`. The error was "stdin_source
   'context.response.a' was not found in workflow context". Structured runners therefore persist their reply and
   the gates read it by pipe (ADR-0014).
2. A command node with no activity for 1800 s is ended by the **stall watchdog**: "Stall watchdog timeout node=c
   idle_seconds=1800", then the run failed. Structured runners print one progress line per model call. Whether
   output counts as activity is probed separately (`fabro-probes.md` once complete).

## Host observation

With qwen3-coder:30b loaded (the `llama-server` resident set was 13 GB) and other owner workloads running, swap was
exhausted. The CRE promotion sandbox then failed to compile its reproducers (decision pd-7f4521cc52c2676c4638,
REJECTED, RESOLVED_FAILURE_REAPPEARED with build failures). The same candidate line was ELIGIBLE after the local
model was unloaded (pd-b6853328caf1e2190ecf). Local inference and factory verification compete for host memory on
this 32 GB machine; scheduling must keep them apart.
