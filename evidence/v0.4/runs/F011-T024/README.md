# F011-T024 — real semantic-first SWE.1 author trials under local-rtx-v2 (qwen3-coder:30b + pinned SafeC)

All attempts are kept, failed ones included. **Result on the final revision (batch 3): 6 of 6 author visits frozen
by the unchanged SWE.1 author gate** (IWDG-LL 3/3, RCC-LL 3/3), every task valid at its first model call. This is
an author-only measurement. No inspector judged these baselines, and nothing here qualifies a model or the inspector.

## Setup (identical for every batch)

- **Stack:** `local-rtx-v2`, root `/media/…/forge-c-lrtx-v2`. Its own user and network namespace, loopback only.
  Ports: Ollama 11455, gateway 11456, Fabro 32391. The shared model store is read-only. qwen3-coder:30b, digest
  `06c1097e…`.
- **Start work orders:** prepared inside the namespace with
  `python -m forge_factory.workorder --example examples/<0009a-iwdg-ll|0002a-arm_55_rcc_ll> --wo WO-F011-T024-<IWDG|RCC>-START --model qwen3-coder:30b --profile local-rtx-v2 --intake-only`.
  - The profile's pre-launch checks passed: ACP/cloud refusal, isolation, loopback endpoints, network denied in
    the namespace, model digest match.
  - The role binding a run writes was added with `f011_bind.py` (here). It calls the same factory functions as
    `workorder.run`.
- **Trials:** `python -m forge_factory.lrtx.modelcmp --workspace <start> --model qwen3-coder:30b --repeat 3 --phase SWE.1`.
  Each attempt is a fresh copy, one real author visit (the semantic author the profile selects), then a freeze
  through the unchanged SWE.1 author gate.
- **Engine:** the SafeC engine is the one the run worktree's profile pins. Every call is hash-verified and
  handshaked by the bridge client.

## Batches

| Batch | Forge-C revision (run worktree) | SafeC engine | IWDG-LL frozen | RCC-LL frozen | Cause of the failures (each a factory defect, fixed before the next batch) |
|---|---|---|---|---|---|
| 1 | c9a9c38 (`forge-c-run-f011-t024`) | c18dd2d / `5f23606f…` | 0/3 | 0/3 | IWDG: the engine **panicked** on `write_key_sequence` intents that cite the value fact with no value (exit 101, no result); the client reported an engine fault, not a model error. RCC 1: the free-text cross-cutting task kept non-EARS wording. RCC 2–3: intent keys unique per group collided in the joint check. Every RCC register task was valid at the first call. |
| 2 | 7786d60 (`forge-c-run-f011-t024b`) | 813b4e8 / `ecd5cf1c…` | **3/3** | 0/3 | RCC: the rendered `write_only_named_field` catalogue rule was not EARS-conformant for the unchanged checker (a comma in the trigger), and the model cannot repair rendered text. Register tasks were all valid at the first call. |
| 3 | 2847678 (`forge-c-run-f011-t024c`) | 813b4e8 / `ecd5cf1c…` | **3/3** | **3/3** | none |

Records:
- `evidence/v0.4/runs/F011-T024-{IWDG,RCC}/`, `F011-T024B-*/`, `F011-T024C-*/` (evidence_run PASS means the trial
  harness completed; the outcome is in the reports);
- reports in `batch1/`, `batch2/`, `batch3/` (`forge-c/lrtx-modelcmp/1`, copied unchanged).

## Batch 3 measurements (MEASURED; GPU board energy via the v2 gateway meter, `batch3/energy.jsonl`, `f011_energy.py`)

| Work order | Frozen | Calls per visit | Wall per visit (s) | Prompt tokens per visit | Output tokens per visit | GPU board energy, 3 visits |
|---|---|---|---|---|---|---|
| IWDG-LL | 3/3 | 6, 6, 6 | 156.4*, 39.0, 40.5 | 14 443 / 14 459 / 14 444 | 863 / 865 / 860 | 1.33 Wh |
| RCC-LL | 3/3 | 7, 7, 7 | 187.2, 142.8, 143.0 | 19 822 / 19 771 / 19 771 | 3 306 / 3 211 / 3 213 | 3.76 Wh |

\* includes the model cold load, 55.9 s.

**Feature 010 comparison** (same host, same author model; not the same experiment):
- lrtx10 used 63 calls and 61 min for SWE.1, and was BLOCKED.
- In the T024 campaign, 0 of 13 work orders passed SWE.1, and RCC-LL kept failing on mask-as-value.

Here SWE.1 authorship takes 6–7 calls and 40–190 s per visit. Wall-power energy is UNKNOWN (no meter on this host).

## Limits

- This is an author-only freeze. The baselines were not inspected: inspector qualification is M4 (F011-T025..T030).
- The SafeC contract checks register facts and intents only. What it covers and leaves open (errata not baselined,
  preconditions, ordering/timing not modelled) is rendered into the open points of every requirements document.
- A semantically questionable but valid intent passes the author gate. In batch 1, RCC queried `RCC_CR.PLLxON` as
  "ready" and wrote intents for out-of-scope PLLs. Judging that is the inspector's job.
- The sample is 3 visits per work order on one host. It is not a reliability claim.
