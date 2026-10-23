# Validation ledger — Feature 011

**Status as of 2026-10-22 (authoring): SPECIFICATION_ONLY.** At authoring there was **no** completed implementation, local model trial, SafeC Linux run, safety qualification or live full regression evidence from Feature 011. That provenance is kept below unchanged; the measured results that followed are in the sections after it, newest last.

## Verified GitHub provenance (metadata, not host deployment)

| Item | Result |
|---|---|
| Forge-C source selected | Main `2f4b9cf44fd9cc56648fa26b6da6c2e29248338d`, merge commit of PR #34, recorded through connected GitHub |
| New branch | `feat/011-safec-semantic-first` created at that commit |
| Existing baseline | `baseline/codex-claude-2026-10-21` pinned to `86f1f40c030bc721e7e5125a572d69647c4ac041` in ADR-0013 |
| SafeC discovery ref | Private main `556dca8df4d2fccd9cb59fd8fb0432aafdd05835`; executable binary/runtime hash NOT_VERIFIED (at authoring; see M0) |
| T024 baseline | 13/30 run, 0 READY, 8.41 h / 640 calls / 204 Wh GPU-board only; NOT_PASS, not a 30-case result |
| T021 baseline | 1/7 on-target inspections, 2/2 false clean rejections; limited catalogue, not a qualification |

## Checklist of required engineering evidence

| Check | Status | Required evidence path/pointer when implementation occurs |
|---|---|---|
| New schemas/Spec Kit content readable in GitHub | PASS (M0 local validator) | `F011-T005` (schemas 2020-12, 14 example messages, 41 references resolved, 3 planned files) |
| Existing ACP/default/Feature 010 compatibility | PASS (M0, before any runtime change) | `F011-T003` (default/ACP fixture 86f1f40 + new local-rtx-v1 fixture 2f4b9cf, ACP/provider tests, v0.1, v0.3, design check) |
| SafeC Linux build/probe and license inventory | MEASURED, NOT_PASS (M0) | `F011-T004` public summary: 263 passed / 2 failed (baseline defects, see M0); Kind 2 and Z3 absent; `F011-T002`: no licence file declared |
| Python/Rust bridge conformance and adversarial tests | PASS (M1, protocol only; every SafeC operation UNSUPPORTED) | `F011-T010` (Forge-C), `F011-T008` (real pinned engine, network denied); SafeC crate tests in the SafeC ledger |
| Register-io authoritative semantic fixtures | PASS except reset contradiction, which is not expressible in register-io-0.1 (M2) | `F011-M2-SAFEC`, `F011-M2-ENGINE`; F011-AT-011..015 covered, AT-016 without the startup invariant |
| Local SWE.1 RCC/IWDG runs | AUTHOR-ONLY PASS (M3): 6/6 frozen by the unchanged gate on 2847678; inspection NOT_RUN | `evidence/v0.4/runs/F011-T024/README.md` (F011-AT-017/018; AT-025 needs the inspector, M4) |
| Independent inspector qualified on holdouts | NOT_RUN | F011-AT-019..023,030 |
| SWE.2 and SWE.3..SWE.6 integration | NOT_RUN | F011-AT-024,026..029 |
| Offline 30-case v2 campaign | NOT_RUN | F011-AT-032 |
| Actual machine isolation, archive verification and rollback | PARTIAL: deployment/archives/namespace PASS in M0 (`F011-T001`); rollback NOT_RUN | F011-AT-001..005,033 |
| Assurance/release/ASIL acceptance | NOT_GRANTED | External offline authority and mandatory evidence |

**Rule:** No checklist may be ticked based on proposal text, model narrative or unsupported simulation. Refresh this ledger with exact hashes, tests, failures and limitations after each implementation milestone.

## M0 results — 2026-10-22 (Claude Code; Forge-C branch `feat/011-safec-semantic-first`, SafeC (private) branch feat/013-register-io-semantic-core)

No runtime behaviour of the default, ACP or local-rtx-v1 lines changed. The models stayed unloaded; no work order ran.

| Task | Result | Evidence | Notes |
|---|---|---|---|
| F011-T001 | PASS | `evidence/v0.4/runs/F011-T001/`, `evidence/v0.4/runs/F011-T001/hostcheck.json` | Branch head descends from 2f4b9cf. Remote refs:<br>- `main` 2f4b9cf<br>- `baseline/codex-claude-2026-10-21` 86f1f40<br>- `feat/011-safec-semantic-first` 74e6e0d<br><br>The deployment checkout (the owner's home forge-c checkout) is clean at 86f1f40. Against the T003 preservation snapshot: services UNCHANGED, 208/208 archives preserved, configuration hashes unchanged, profile namespace network DENIED_VERIFIED. |
| F011-T002 | PASS | `evidence/v0.4/runs/F011-T002/` | SafeC remote `main` = discovery ref 556dca8. The SafeC feature branch feat/013-register-io-semantic-core (597335c, draft PR #1) descends from it. Access: owner admin, repository private. Licence: none declared (no LICENSE/COPYING/NOTICE, GitHub licence null); redistribution terms NOT_DECLARED. |
| F011-T003 | PASS | `evidence/v0.4/runs/F011-T003/` | Every compatibility step PASS:<br>- default/ACP fixture (86f1f40);<br>- new `tests/compat/lrtx/local-rtx-v1-2f4b9cf.json.gz` (generated from a clean 2f4b9cf checkout);<br>- ACP/provider tests;<br>- v0.1 and v0.3 suites;<br>- design check.<br><br>Hashes of protected policy and configuration are in the log. The v1 fixture freezes, as observed, that local-rtx-v1 refuses the brownfield LL cases (`STRUCTURED_NODE_MISSING:swe3_ll_author`). |
| F011-T004 | MEASURED, NOT_PASS (not ticked) | `evidence/v0.4/runs/F011-T004/` (public summary only; raw log private, sha256 recorded) | SafeC at 597335c on this host (Linux 6.8, cargo 1.98.1 pinned): 93 test binaries, **263 passed, 2 failed**. The first record (empty crate cache, 0 binaries) is kept as FAIL.<br><br>Root causes (both pre-existing in SafeC; neither fixed by changing evidence or goldens):<br>1. The retained guest evidence replay fails on any fresh clone: SafeC's `.gitignore` excludes `*.log`, so two raw logs listed in each retained manifest were never committed.<br>2. A Linux-only watchdog test: killing `/bin/sh` leaves its `sleep` child holding the stdin pipe, so the request writer does not unblock. That is a process-group handling gap on Linux. |
| F011-T005 | PASS | `evidence/v0.4/runs/F011-T005/`, `evidence/v0.4/runs/F011-T005/static-check.json`, `evidence/v0.4/runs/F011-T005/boundary-scan.json` | Both bridge schemas valid 2020-12. 14 frozen example messages behave as stated. 41 document references resolve and 3 are planned new files. The boundary scan of all lines added since 2f4b9cf against the private checkout (hashes only) found nothing. `public_summary` refuses private paths, private lines, credentials and multi-line values (F011-AT-005). |

**Formal backends on this host** (versions and digests in the F011-T004 summary):
- Available from the Forge-C user-space toolchain: CBMC 6.11.0, Frama-C 33.0, Why3 1.8.2, Alt-Ergo 2.4.3-free, cvc5 1.2.1.
- **Kind 2 and Z3 are absent.** SafeC's temporal (Kind 2 3.0.0 / Z3 4.15.3) analyses are therefore UNSUPPORTED on this host.
- SafeC's recorded Frama-C stack uses Alt-Ergo 2.6.2. Forge-C removed that version for its non-commercial licence, so it is a licence risk for productization (research risk 6). The CBMC 6.11.0 binary here is a different build from SafeC's recorded one (different sha256).

**Found and fixed during M0 (CRE):** `lrtx.hostsnap` accepted a backup directory under a repository when the directory did not exist yet. In a fresh worktree a feature 010 test therefore wrote a deployment snapshot into the ignored `build/`. It was removed and never committed. The fix (`git_root(..., nearest=True)`) has a regression test.

**CRE decisions** (CHANGE, all hard gates PASS, offline review only):

| Decision | Covers |
|---|---|
| `pd-b30ffdc52388ee3d85d2` | ac7ec8d: v1 fixture, static check, boundary guard, hostsnap fix |
| `pd-8bb9f2deec555bdba611` | 21d881a: Linux probe |
| `pd-0eecab2c46856e6511fa` | 4d8fdcd: probe `--cargo-home` |
| `pd-142ff583ea5a169fb3cb` | aa56e74: credential rule needs a varied secret (the b751b7c scan flagged the T005 pytest log's placeholder token); T005 re-recorded |

**M0 exit:** the baseline is safe and source digests are recorded, with no production changes. Linux compatibility is observed: the Rust core builds and 263/265 tests pass. The temporal formal backend stays UNSUPPORTED (Kind 2/Z3 absent). T004 stays open on the two SafeC baseline failures.

## M1 results — 2026-10-22 (bridge protocol; Forge-C 69c89ad, SafeC 6b3934b)

| Task | Result | Evidence | Notes |
|---|---|---|---|
| F011-T006 | PASS | `evidence/v0.4/runs/F011-T010/` | `safec_bridge/contracts.py`. Refused before interpretation: oversize, invalid UTF-8, duplicate keys, non-finite numbers, non-objects, schema violations, duplicate finding/artifact ids, and a PASS carrying a major/critical finding. Requests are written as canonical bytes. |
| F011-T007 | PASS | `evidence/v0.4/runs/F011-T010/`, `evidence/v0.4/runs/F011-T008/` | `safec_bridge/client.py`. The engine file digest is checked before anything executes. The handshake must name the pinned commit, its own digest, the profile and the frozen protocols. The run uses argv only, an empty environment (PATH/LANG/LC_ALL), its own session with a process-group kill on timeout or cancellation (a test shows the grandchild dies too), CPU/AS/FSIZE/NOFILE limits, and streams kept out of the record. |
| F011-T008 | PASS | `evidence/v0.4/runs/F011-T008/` | The real pinned SafeC engine (commit 6b3934b, sha256 `cea1840f…`, reproducible build) ran **inside the local profile's network namespace**: external connect refused, errno 101 (F011-AT-003 for the bridge). Handshake matched; every operation was UNSUPPORTED; a wrong digest or commit was refused; identical requests gave byte-identical result and evidence. The first record (20261022T091119) is kept as FAIL: the SafeC cargo step inside the namespace printed nothing; those crate tests run outside the namespace and are recorded in the SafeC ledger (10/10). |
| F011-T009 | PASS | `evidence/v0.4/runs/F011-T010/` | The result must echo the request id, the exact request digest and the pin. The evidence file must hash to `evidence_sha256` and restate request, input, engine, operation, status, findings and artifacts. Every artifact must exist with its digest. A non-zero exit is ERROR whatever the result says. `ResultCache` is keyed by pin plus exact request bytes and misses on any evidence change (F011-AT-010). |
| F011-T010 | PASS | `evidence/v0.4/runs/F011-T010/` | 55 passed, 2 skipped (the real-engine tests, which run in F011-T008). Compatibility check PASS in the same record: default/ACP and local-rtx-v1 fixtures, ACP/provider tests, v0.1, v0.3, design check. SafeC side: 7 protocol + 3 CLI tests (SafeC ledger). |
| F011-T011 | PASS (scope: no agent is granted the bridge) | `evidence/v0.4/runs/F011-T011/` | In M1 only deterministic orchestration calls the bridge, so no MCP wrapper exists. The test shows the MCP registry has no SafeC operation, and every production role is denied every way to reach it (MCP names, native shell, bare tool). Granting an AI role access later needs a narrow, owner-reviewed registry operation with explicit grants. |

CRE decisions (CHANGE, all hard gates PASS, offline review only):

| Decision | Covers |
|---|---|
| `pd-93721b130876540bbc00` | 69c89ad: the M1 client |
| `pd-252d626238f0445c2ecc` | e23bc39: the boundary scan counts a private-source match only as a distinctive line or a block. The M1 tree had matched one standard idiom, `setrlimit(RLIMIT_CORE, (0, 0))`, that a SafeC script also contains; T005 was re-recorded. |

**M1 exit:** F011-AT-006..010 PASS for the protocol, with no ACP/default/v1 behavioural difference (F011-T010 compatibility steps). No semantic capability is claimed: the engine evaluates nothing, so it cannot yet support any SWE.1 decision.

## M2 results — 2026-10-22 (register-io-0.1; Forge-C 74bfb67, SafeC 9d543b2)

| Task | Result | Evidence | Notes |
|---|---|---|---|
| F011-T012 | PASS | `evidence/v0.4/runs/F011-M2-SAFEC/`, `evidence/v0.4/runs/F011-M2-ENGINE/` | New profile register-io-0.1 in private SafeC (crate safec-register-io, own workspace and lock). It does not touch the sampled-latch CSRI: of the 3157 files tracked at 556dca8, only SafeC's `Cargo.toml` changed (workspace exclusion). Public-safe wire types published here: `contracts/register-io-domain.schema.json` and `contracts/register-io-contract.schema.json`. |
| F011-T013 | PASS | same | `safec_bridge/domain.py` extracts the domain from the work order's key RM sections with the SWE.1 inventory's parser. It adds the reset bits the manual leaves undefined (`IWDG_SR` ONF), the documented values (bulleted `0x…`) and per-section file digests. Unknown stays visible: access `unknown`, defined mask 0 without a reset value, `errata.status NOT_PROVIDED`. SafeC re-validates every invariant. The domain is bound to a request by its SHA-256 (`source_manifest_sha256`); the client refuses a mismatch before execution. |
| F011-T014 | PASS | same | Checked `u64` arithmetic in SafeC, re-derived independently in Forge-C. On real RM0486 facts, `RCC_AHB1ENR.ADC12EN` logical 1 gives mask and encoding `0x00000020`, read-modify-write, preserved `0xffffffdf`. Logical value `0x20` or `32` gives **RIO-MASK-AS-VALUE**, with the logical value 1 named as the repair. Width boundaries, overflow and invalid literals are refused. |
| F011-T015 | PASS | same | RO, WO and RW are modelled. IWDG keys `0xAAAA`/`0x5555`/`0xCCCC` are whole-register writes, and each must cite its own value fact (inverted key gives RIO-KEY-FACT-MISMATCH). Fail checks: RO write, WO read, undocumented key, key written via `write_field`. UNSUPPORTED, never guessed: W1C/RC/mixed/unknown access, read-modify-write next to side-effect fields, and whole-register writes with other fields or undefined reserved reset. |
| F011-T016 | **OPEN** | same (partial) | Covered: RCC ADC12EN, IWDG KEY/PR/RLR/SR, 0x20 mask-vs-value, inverted keys, RO writes, out-of-scope register, unknown field/register/fact, unmodelled access. Not covered: a **reset contradiction**, because the wire contract has no reset/startup intent. Reset and startup remain explicit Forge-C requirements (S013-FR-007). |
| F011-T017 | **OPEN** | same (partial) | Covered: duplicate ids/effects, same-precondition conflicts, unknown preconditions, and a per-field coverage inventory in every contract. Not covered: missing owner decisions as source-linked findings, which belongs with the M3 SWE.1 assembly. |
| F011-T018 | PASS | same | `safec_bridge/contract.py` accepts a contract only if all of these hold:<br>- strict parse and schema;<br>- canonical semantic digest;<br>- the pin, request binding and domain digest;<br>- exactly the requested intents;<br>- every number equal to Forge-C's own `reference_operation`. A disagreement is ENGINES_DISAGREE and blocks. |
| F011-T019 | PASS | same | **SafeC:** register-io 15 and bridge 15 tests (goldens and mutants, e.g. ADC12EN moved to bit 6 changes the mask and the digest), clippy clean. Root workspace: 263 passed / 2 failed, exactly the M0 baseline failures (failure-name digest asserted); root lock unchanged.<br>**Forge-C:** 73/73 against the pinned engine `9d543b2` (sha256 `5955f793…`, reproducible) inside the network-denied namespace, synthetic and real-RM cases. Unsupported obligations recorded in every contract: errata not baselined, preconditions not verified, ordering/timing/locking not modelled. |

CRE decision `pd-46287fcfe3205f989f47` (74bfb67, CHANGE, all hard gates PASS, offline review only).

**M2 exit:** F011-AT-011..015 PASS. F011-AT-016 PASS without the startup invariant (not expressible). No existing gate was changed. Nothing here claims that Kind 2 or existing ACSL verify an RCC or IWDG driver.

## M3 results — 2026-10-22 (local-rtx-v2 semantic-first SWE.1; final Forge-C 2847678, SafeC 813b4e8)

| Task | Result | Evidence | Notes |
|---|---|---|---|
| F011-T020 | PASS | `evidence/v0.4/runs/F011-M3-TESTS/` | `config/factory/profiles/local-rtx-v2.yaml`: explicit opt-in.<br>- Own root (the forge-c-lrtx-v2 directory on the data volume) and ports 11455/11456/32391. v1's ports are forbidden and v1's root counts as an existing deployment.<br>- Same refusals as v1: ACP, cloud, unlisted models. Only the measured qwen3-coder:30b is allowed.<br>- Pinned SafeC engine `813b4e8`, sha256 `ecd5cf1c…`.<br>- The workflow graph is identical to v1; the runner picks the semantic author and inspector from the profile.<br>- The real v2 stack runs in its own namespace. Work orders were prepared under `--profile local-rtx-v2` with every pre-launch check passing.<br>- v1 and default/ACP fixtures unchanged (same record). |
| F011-T021 | PASS | `F011-M3-TESTS`, `F011-T024C-IWDG`, `F011-T024C-RCC` | Register packets ask only for intents. Fields and facts are enums of the task's own domain facts, plus a lowercase request phrase; no statement, mask, bit position or page. The role SKILL, mandatory context, call budget and checkpoint identity are those of feature 010. |
| F011-T022 | PASS | same | EARS statement, verification, effect and source page are rendered from the operations SafeC accepted and Forge-C re-derived. Cross-cutting requirements come from a closed catalogue: the startup invariant always, plus status queries without waiting and writes changing only the named field. Contract obligations (errata not baselined) become open points. The existing assembly, consistency and self-check produce the existing SWE.1 work products. |
| F011-T023 | PASS | same | An identical rejected answer stops its task as STUCK, tested. Joint-check findings go back to their groups for one localized repair round. Engine faults are infrastructure, not model answers. Every attempt is kept in the checkpoints and visit logs. |
| F011-T024 | PASS (author-only) | `evidence/v0.4/runs/F011-T024/README.md`, `F011-T024C-IWDG`, `F011-T024C-RCC` | Batch 3, on 2847678:<br>- IWDG-LL 3/3 frozen, 6 calls per visit;<br>- RCC-LL 3/3 frozen, 7 calls per visit;<br>- every task valid at its first call;<br>- 40–190 s per visit;<br>- 1.33 Wh / 3.76 Wh GPU board energy per 3 visits.<br><br>**Batches 1 and 2 are kept as recorded failures, each a factory defect fixed before the next:**<br>- the SafeC panic (fixed in SafeC 813b4e8);<br>- the free-text cross-cutting task;<br>- group-key collision in the joint check;<br>- a non-EARS rendered rule. |

**CRE decisions:**

| Decision | Covers |
|---|---|
| `pd-e07c152808a83cc7bd40` | c9a9c38, M3 |
| `pd-07085cc44d4423c2dc38` | **REJECTED**: the gate was run without `scripts/forge-env.sh`, so the reproducers could not import `robot` (environment error, kept as a record) |
| `pd-00d2198687927710ccfa` | 7786d60, rerun in the proper environment: ELIGIBLE |
| `pd-ddacbb83402a7b7a1af9` | 2847678 |

**M3 exit:** the unchanged deterministic author gate accepts genuine tested results. The inspector and SWE.2 are not
qualified by this.

## M4 results — 2026-10-22 (inspector qualification: no local candidate qualifies)

Runs 2 and 3 use the adjudication rules frozen at 4f9abde (`pd-d0e9a7512e632a2a0f41`); run 1 used the 7786d60 rules. Holdouts: seen = the two T021
holdouts (WO-0009A IWDG-LL rc1, WO-0002A RCC-LL rc1; no longer blind); unseen = five READY work orders (WO-0002B,
WO-0008A, WO-0008B, WO-0008C, WO-0009B). The holdout trees are hashed before and after each run. Reports are kept in
the m4, m4b and m4c directories of the local-rtx-v2 root.

**Qualification rule:** no false rejection on any clean holdout, seen or unseen, and the SWE.1 seeded defects
detected on target. A candidate that fails it stays NOT_QUALIFIED; F011-T030 integrates nothing unqualified.

| Candidate | Run | Result | Notes |
|---|---|---|---|
| qwen3-coder:30b | run 1 (7786d60 rules, partial) | NOT_QUALIFIED | IWDG clean baseline: FALSE_REJECTION_BY_INSPECTION (a recorded REWORK inspection). S1-OMIT: off target. S1-QM: caught by the deterministic gate. The S3-INVERT "MISSED" row predates the harness fix below and is **not counted** (it may come from the stale record). |
| qwen3-coder:30b | run 2 (4f9abde rules) | NOT_QUALIFIED | IWDG clean baseline again a false rejection (a recorded REWORK inspection). Claims left standing after adjudication: SWE1-02 requirements_inconsistent and requirement_infeasible on SWR-013; SWE1-03 failure_handling_missing and safe_state_missing. Stopped after this row: the rule already excludes it. |
| gpt-oss:20b | run 2 | VOID, then NOT_QUALIFIED (incompatible with the gateway setting) | Every item came back empty ("NOT_JSON ... char 0"). Cause measured in F011-T028C: the gateway forces `reasoning_effort="none"`, and gpt-oss returns no content then. Owner decision pending (ADR-0015 addendum 4). The row reported "none" only because of the harness defect below; it is void. |
| glm4:9b | run 3 (rules 4f9abde, harness b627861, run tree 366db72) | NOT_QUALIFIED | Clean baselines: 3 false rejections, 1 no inspection, 3 passes of 7. Seeded: S1-OMIT off target on IWDG, missed on RCC. |
| phi4:14b | run 3 | NOT_QUALIFIED | 6 false rejections and 1 no inspection of 7 (16 k context; RCC prompts are about 20 k). Seeded: both S1-OMIT off target. |
| mistral-small3.2:24b | run 3 (partial) | NOT_QUALIFIED | IWDG-LL clean baseline falsely rejected; stopped at that row (3.4 tok/s with CPU offload: 6.1 of 17.8 GB in VRAM). |
| granite3.3:8b | run 3 | NOT_QUALIFIED | 3 false rejections and 4 no inspections of 7. Seeded: S1-OMIT off target on IWDG, missed on RCC. |

**Finding for the owner: is the IWDG-LL rc1 baseline clean for SWE1-03?** Every local family evaluated on it
(qwen3-coder:30b, glm4:9b, phi4:14b, mistral-small3.2:24b, granite3.3:8b) fails SWE1-03 with `failure_handling_missing` or `safe_state_missing`. The
criterion reads "Failure handling, reset/startup behavior and safe states are specified." The baseline has a startup
requirement (SWR-013), but no failure-handling or safe-state requirement; its scope statement allocates waiting,
timeouts and error codes to the separate HAL work order. The original cloud inspection passed SWE1-03; that verdict is
the only reason the baseline counts as clean, and its reasoning is not recorded. The frozen adjudication rules do not
treat a documented scope allocation as a refutation, and they are **not** changed after seeing these results: a rule
tuned on seen holdouts would bias the qualification. Whether a scope allocation to another work order satisfies
SWE1-03 for an LL register-access driver is an owner decision. Until then these rows count as false rejections
under the rule above.

**Measured on this host (F011-T028, T028B, T028C):** model digests, quantization, context, cold load, VRAM and decode
rate are recorded per candidate in the probe reports. Only about 6–7 GB of each model was resident in VRAM; larger
models ran partly on the CPU (mistral-small3.2:24b decoded at 3.4 tok/s). Every candidate except gpt-oss:20b answers a
schema-constrained request with reasoning off. Evidence: `evidence/v0.4/runs/F011-T029/README.md`, `F011-M4-TESTS`.

**Next (F011-T030 stays open):** the owner provided a host with a 48 GB GPU (omniverse2), where 30–70B candidates fit
entirely in VRAM. The same frozen rules, harness and holdouts are to be rerun there. If none qualifies, the line stays
NOT_QUALIFIED and no live end-to-end run is made.

**Harness defect found and fixed (b627861, `pd-47c70ee683c05937a4f0`).** The seeded harness read the last
inspection record of the holdout's own original run when the local inspector recorded nothing, and reported that old
PASS as "none" (no false rejection). Now only an inspection recorded by the evaluation's own visit counts; otherwise
the row is NO_INSPECTION and counted as such. The qwen rows above are unaffected: each recorded its own inspection.

**Process violation (recorded):** the PR #37 promotion gate (`pd-05f3c205ef973368b442`) was run while T029 run 2
was active, against the rule that no local run is active during a promotion. The decision stands on its own gates;
the run 2 qwen row it overlapped is a false rejection either way.

**CRE decisions:**

| Decision | Covers |
|---|---|
| `pd-d0e9a7512e632a2a0f41` | 4f9abde: adjudication rules aligned; gpt-oss:20b and glm4:9b allowlisted |
| `pd-47c70ee683c05937a4f0` | b627861: T031 function naming; seeded harness counts only its own inspection |
| `pd-b35c2e22680b5e6c616a` | 366db72: phi4:14b, mistral-small3.2:24b, granite3.3:8b allowlisted |

**F011-T037 (checked):** the route-gate fix went through its own candidate and PR (#37, CAPA-068, RPR-072,
`pd-05f3c205ef973368b442`). It was merged into main as 53d4dac with owner approval. Evidence `F011-T037` and its
script: the fixtures are unchanged, the ACP/provider tests pass on the fix and the main baseline, and the route
regressions pass. The reproducer shows the symptom on main and not on the fix. The single excluded test, the hostsnap
backup refusal, fails on main as well and is fixed on this branch by ac7ec8d.

## M5 results — 2026-10-22 (SWE.2 binding and register-image oracle; Forge-C 9f2d657 + 94c1c6c, SafeC b6ce0f7)

| Task | Result | Evidence | Notes |
|---|---|---|---|
| F011-T031 | PASS | `F011-M5-TESTS` | The semantic SWE.1 names the LL function in every requirement ("When LL_IWDG_Enable is called to ..."); the function is an intent field whose prefix the schema enforces. An interface built from the frozen requirements passes the unchanged SWE.2 check. Renaming LL_IWDG_IsActive to LL_IWDG_IsEnabled is rejected, naming the requirement, the exact name to define and the allocation (F011-AT-024). |
| F011-T034 | PARTIAL (Forge-C side, LL, SWE.4) | `F011-M5-TESTS` | SafeC `derive_tests` returns a register-image oracle bound to the contract digest. Forge-C accepts it only if every case equals its own derivation (`safec_bridge/oracle.py`, schema register-io-oracle in the feature contracts). The frozen semantic SWE.1 records it as the SWE.1 work product register_oracle.json.<br>The EASA C oracle (SWE.4 verifier) checks each case on the real register array: the whole register word, every other word unchanged and the query return value. Before use, the domain is rebuilt and every operation and case re-derived; any difference blocks.<br>End-to-end test on a real LL generated from the contract: it passes every case. Inverted key, absent write, wrong-bit read and a read that writes each fail only on their own case. A tampered oracle blocks.<br>**Open:** SWE.5/SWE.6 (Renode/Robot) use, the vacuous-test and false-positive classes in the SWE.4 test review, and HAL. |
| F011-T035 | PASS | `F011-T035` | Formal tool identities on this Linux host (path, version, sha256): CBMC 6.11.0, goto-cc 6.11.0, Frama-C 33.0, Why3 1.8.2, Alt-Ergo 2.4.3-free and cvc5 present; **Z3 and Kind 2 ABSENT**, Kind 2 UNSUPPORTED (Lustre models, not C). No Windows/WSL evidence reused.<br>CBMC register-effect proofs (`assurance/register_proof.py`): each contract operation on the real LL code, every register word unconstrained, one nondeterministic other word unchanged. Correct LL: PROVED for every operation. A mutant wrong for one initial value only (0x123) passes the four-image C oracle and is FAILED by CBMC on its own operation.<br>Model: host C semantics, registers as plain memory, single thread, loops unwound to 8 with unwinding assertions (INCONCLUSIVE otherwise). Not covered: timing, ordering, target compiler and silicon, errata. Not a generalized hardware proof. |
| F011-T033 | PARTIAL (Forge-C side) | `F011-T035` | The register-io contract is lowered to CBMC properties in Forge-C. SafeC's own C11/ACSL lowering for register-io (S013-T018) and Frama-C WP proofs are open. |

**Defect found by the mutants:** with two initial images (all zeros, all defined bits), a read of a neighbouring bit
passed, because both bits hold the same value in both images. Fixed in SafeC b6ce0f7 and in the Forge-C
derivation: four images, the field alone and all but the field added, duplicates dropped. Engine pin b6ce0f7,
sha256 `359bef94…`, reproduced in two clean target directories; `validate_intents` is unchanged since 813b4e8.

**CRE decisions:** `pd-806bcd9cd305ee417638` (94c1c6c, covering 9f2d657) and `pd-92d2bb0be2853495a977` (b429112, T035): ELIGIBLE_FOR_OFFLINE_REVIEW.

## M5 continued — 2026-10-22 (SWE.2 trials, engine corpus, cross-host pin; Forge-C f185e42 + 972f3d3)

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T032 | PASS (measurement; inspector NOT_QUALIFIED) | `evidence/v0.4/runs/F011-T032/` (script, partial report) | Real SWE.2 author (feature 010 structured author, qwen3-coder:30b) on the genuinely accepted rc1 SWE.1 baselines, then the inspector the runner selects. **IWDG-LL 2 of 2 attempts FAILED** at the interfaces task: the model kept LL_IWDG_IsActive for SWR-011/012, which name LL_IWDG_IsEnabled, through every repair with the exact finding (3 calls; 1331 s and 257 s). Nothing was frozen, so nothing was inspected. The owner then froze local runs on this host ("freeze any local run in my pc and wait to have omniverse ready"), so the 4 remaining attempts (IWDG-LL 3, RCC-LL 1–3) did not run. No evidence_run record: the run was stopped. **omniverse2 run 1 (2026-10-23, `20261023T181611`, report `evidence/v0.4/runs/F011-T032/report-unbound-20261023T181611.json`): 0 of 6 frozen, nothing inspected.** The harness copied the rc1 work orders without binding them to the local profile, so the local-rtx-v2 SWE.2 settings did not apply (harness defect, fixed in the script: each copy is bound as `workorder.run --profile` binds it). IWDG-LL 1–2 failed on the same IsActive/IsEnabled rename, IWDG-LL 3 and RCC-LL 3 on 'compliance' echoed from the design instruction, RCC-LL 1–3 on sequence steps written with a parameter list ('LL_RCC_HSI_Enable(void)'). Author fix under local-rtx-v2 (`swe2_constrained_design`, CRE pd-b6a84518fc9a84481508): the design schema enumerates the interface names and the instruction no longer seeds the refused word; the design checks are unchanged. A path error run (`20261023T181433`, exit 2) is kept. **omniverse2 run 2 (`20261023T191405`, profile-bound, report `evidence/v0.4/runs/F011-T032/report-run2-20261023T191405.json`): 0 of 6 frozen.** IWDG-LL now passes the interface task (the named-function fix works) and fails the unchanged design checks by model variance: one answer repeated unchanged after its findings, one wrote 'timing or sequence compliance', one left ISR use out of concurrency_and_reentrancy. RCC-LL failed 3/3 at the interface task with no function at all: its requirements name no LL function, so the named-mode schema left no place for one (author defect; fixed by falling back to the feature 010 function list, CRE pd-552e5f27bf05719e38a1). **omniverse2 run 3 (`20261023T193033`, report `evidence/v0.4/runs/F011-T032/report-run3-20261023T193033.json`): 0 of 6 frozen; 4 of 6 passed the interface and design tasks** (IWDG-LL 2–3, RCC-LL 1–2) and stopped at the views step with `VIEWS:TOOL_MISSING:plantuml`: the pinned PlantUML jar was not on this host (environment gap, not a model result). It was then installed from the PlantUML release and checked against loop10's sha256 (796e464e…). The other two failed the unchanged design check on ISR use in concurrency_and_reentrancy. **omniverse2 run 4 — the T032 measurement (`20261023T193607`, `evidence/v0.4/runs/F011-T032/report.json`, tree 20af919, profile local-rtx-v2-omniverse2, author qwen3-coder:30b, inspector gpt-oss:120b NOT_QUALIFIED): 3 fresh attempts per pilot on the genuinely accepted rc1 SWE.1, design/inspection gates unchanged.** Author: **5 of 6 frozen** by the unchanged SWE.2 gate (IWDG-LL 1, 3; RCC-LL 1–3); IWDG-LL 2 FAILED (the claim check refused 'compliance' written by the model). Inspection of the 5 frozen baselines: **RCC-LL 2 PASS, 1 FAIL** (SWE2-04 safety mechanisms/degraded states, SWE2-05 no time budget); **IWDG-LL 0 PASS, 2 FAIL** (SWE2-02 clock/reset semantics, SWE2-05 no time budget). The inspector is not qualified (F011-T029), so these verdicts are measurements, not acceptance: nothing here is an accepted SWE.2. Author time 25–36 s per frozen visit on the 48 GB host. |
| SWE.2 named functions | Implemented, tested, **not yet measured** | `pd-2fd79d4a286aaeb309c7` | Under local-rtx-v2 (`structured.swe2_named_functions`), each function a frozen requirement names is a required key of the SWE.2 output schema. A rename such as IsActive to IsEnabled is refused by the schema itself. Other profiles keep the feature 010 schema unchanged (tested). T032 is to be rerun with it on the 48 GB host. |
| SafeC engine corpus (S013-T015, Forge-C side) | PASS | `F011-ENGINE-CORPUS` | 17 hostile requests sent straight to the real pinned engine, past the client: each ends within 60 s without a panic and gives a schema-valid ERROR, STALE or FAIL, never PASS; a correctly bound control passes. The first version of the test was vacuous (the engine refuses an existing evidence directory, so every case failed for that one reason); the control exposed it. Recorded finding: control characters in request_id are schema-valid and echoed unchanged; Forge-C builds request ids from fixed tags only. |
| Engine pin across hosts | PASS | SafeC f6d7089 (private) | b6ce0f7 built from a fixed source path (`git archive`, cargo home remapped, locked, offline) gives sha256 `2a54f4a3…` on both loop10 and the new 48 GB host. Built from different checkout paths it does not, because cargo metadata depends on the path dependencies' location. |

**CRE decision:** `pd-2fd79d4a286aaeb309c7` (972f3d3, covering f185e42): ELIGIBLE_FOR_OFFLINE_REVIEW.
**Second host:** `config/factory/profiles/local-rtx-v2-omniverse2.yaml` (6af8286, `pd-81790d8356ca886904e5`). It is
local-rtx-v2 with the omniverse2 paths (data root /mnt/data/forge-c) and the cross-host engine build; a test fails if
the two profiles drift apart in anything else. Not yet started there: the models are still being copied.
**Per-model reasoning exception** (owner decision; ADR-0015 addendum 5): 82c5fe8, `pd-704dec78b9e1f85b1f92`. gpt-oss:20b
may reason at `low` with extra output tokens; reasoning is still stripped before anything is stored. Not yet measured
on the holdouts. Pre-existing and unrelated: test_kpi_003 t012/t020 fail the same way on a clean 209191a checkout
(they read live factory state).
**omniverse2 host tuning** (owner: "go to high directly, on omniverse I dont care about energy, time and resources,
lets use the most of the machine"): b981617, `pd-411645d07a947efdd302`. On local-rtx-v2-omniverse2 only:
- gpt-oss:20b reasons at `high` with 16384 extra output tokens;
- two models stay resident;
- the KV cache is f16;
- the context is 65536 tokens.

The laptop profile is unchanged.

## M5 continued — 2026-10-23 (C11/ACSL obligations and Frama-C WP; Forge-C 2bcf31c, SafeC 7032f48)

Owner, 2026-10-23: the laptop continues the tasks that need no model runs while the 48 GB host is prepared.

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T033 | PASS | `F011-T033` (22 tests, no skip), `F011-T035` | SafeC lowers each validated operation to ACSL obligations of one call, with a C11 reference body and an applicability class per tool measured on this host (S013-T018): WP decides FIELD_VALUE, WHOLE_WORD, RETURN_FIELD, FRAME and NO_WRITE; PRESERVED_BITS is INCONCLUSIVE for WP and left to CBMC (bit-precise, F011-T035); Kind 2 is NOT_APPLICABLE (not temporal). Key-sequence order, hardware side effects, reset/timing and concurrency are UNSUPPORTED and listed per operation. The bridge offers it as `derive_contracts` (artifact `formal_obligations`, schema `contracts/register-io-obligations.schema.json`). Forge-C re-derives every obligation, the applicability class and the not-lowered list independently (`safec_bridge/obligations.py`): a weakened obligation, an over-claimed tool or a hidden gap is ENGINES_DISAGREE and blocks. The semantic SWE.1 freezes the verified obligations (work product SWE.1 register_obligations.json); `assurance/register_wp.py` re-verifies them against the rebuilt domain and runs Frama-C WP on the real LL code through a wrapper per operation (the SWE.2 call, inlined). On the IWDG LL test implementation every operation is PROVED; an inverted key, an absent write, a wrong-bit read, a read that writes and a write to another register each leave their own operation, and only it, NOT_PROVED. A WP goal that is not proved is never reported as a refutation. The Wheel/temporal profile of SafeC is unchanged (S013-T018). |
| Result schema | Additive change | `contracts/bridge-result.schema.json` | Artifact kind `formal_obligations` added (sha256 e323567a…, was abfad52f…). Results of earlier engines are unchanged and still valid; an older client refuses the new kind, so the change fails safe. SafeC's copy is byte-exact. |
| Engine pin | 7032f48 | both local-rtx-v2 profiles | Cross-host build, sha256 `746490271ee091e3a49d4c0266f72fc6d1cb96e7628c0406b53aab5381a9957a`; `validate_intents` and `derive_tests` decide as b6ce0f7. On the 48 GB host it must be built with SafeC `scripts/build-pinned-engine.sh 7032f48 /mnt/data/forge-c/safec/engines` before the profile can start. |
| Consumer/producer | PASS | SafeC validation S013-T015 | The Forge-C real-engine tests pass against SafeC 1866a92 (66) and 7032f48 (bridge, oracle and obligations suites, 128 related tests). |

**CRE decision:** `pd-6b5fb4484e9525325f18` (candidate 2bcf31c, baseline aa9707f): ELIGIBLE_FOR_OFFLINE_REVIEW.
**Provenance scan base:** after the merge of PR #36, the scan's base is the branch's merge base with main (aa9707f).
From the old base 2f4b9cf it flagged the already published F011-T035 tool identities, because SafeC's private S013-T019
probe record repeats the same host tool paths and digests; the lines are Forge-C's public evidence, not SafeC content.

## M5 continued — 2026-10-23 (contract mutants and the oracle on target; Forge-C e4dd999)

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T034 | PARTIAL (SWE.4 and SWE.5 for LL; SWE.6 and HAL open) | `F011-T034-M5B` (43 tests, no skip), `F011-M5-TESTS` | **Contract mutants (AT-027):** register_ops in the assurance mutation module derives requirement-level faults from the verified SafeC contract, never from the code: KEY_SWAP (another documented key of the field), FIELD_BIT_SHIFT (the neighbouring bit), OMIT_WRITE (a register write removed), RO_WRITE (a write to a read-only register added). The SWE.4 mutation campaign carries them (operator set forge-mut-rio/1). On the IWDG LL test implementation: 23 contract mutants, 21 killed by the SafeC register oracle, the remaining 2 (a prescaler and a reload clear mask shifted by one bit, wrong only for initial values no concrete image uses) killed by the CBMC proof; 0 survive. **Vacuous test (AT-028):** a unit test that only calls the functions lets the KEY_SWAP and OMIT_WRITE mutants survive, so the campaign reports them as SURVIVOR findings. **Defect found and fixed:** the C oracle compared other register words starting from a zeroed file, so a stray write of 0 (to a read-only register) was invisible; every other word now starts from a non-zero background (`0xA5A50000 \| index`). **False positive:** the correct implementation passes every case (host oracle, CBMC, WP). **On target (SWE.5):** `assurance/target_oracle.py` runs each oracle case as a Cortex-M55 image on the Renode STM32N6 platform. It first proves the model holds the case's initial image (the image with the field flipped, then the image); otherwise the case is NOT_SETTABLE and never counted. RCC_AHB1ENR (real RM0486 facts): set/clear ADC12EN pass on every image; RCC_SR ready flags are NOT_SETTABLE (driven by the model); a wrong-bit mutant fails on its own cases only. IWDG: all 24 cases NOT_SETTABLE (write-only key register, write-protected configuration registers, model-driven status flags), reported as limitations, none as pass. The SWE.5 raw-outcome verifier includes it for LL work orders with a frozen SafeC oracle; other work orders are unchanged. **Open:** SWE.6 (Robot) use of the oracle, and HAL. |

**CRE decision:** `pd-84002850487ede3163dc` (candidate e4dd999, baseline 319e0f3): ELIGIBLE_FOR_OFFLINE_REVIEW.

## M5 continued — 2026-10-23 (SWE.6 cross-check; Forge-C 1880e0e) — F011-T034 complete for the semantic LL profile

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T034 | PASS (LL, semantic local-rtx-v2) | `F011-T034` (30 tests, no skip), `F011-T034-M5B`, `F011-T033`, `F011-T035` | Requirement-derived oracles and mutations at every phase, from the verified SafeC contract only: **SWE.3** bounded CBMC proofs (F011-T035) and Frama-C WP proofs (F011-T033) of each register effect; **SWE.4** the register-image oracle in the EASA C oracle and the contract-derived mutants (inverted/other key, absent write, neighbouring bit, read-only write: 23 on IWDG, 0 survive) plus the vacuous-test class (a test that observes no register lets them survive and is reported); **SWE.5** the oracle on the Renode target (unsettable cases stated, never passed); **SWE.6** every requirement the Robot suite verified is cross-checked against the oracle on target: Robot PASS with an oracle FAIL is FALSE_POSITIVE_TEST, a requirement with no independent target observation is a stated limitation. False positive in the other direction: the correct implementation passes everything. **Scope:** the register-image oracle models one register effect per call, so it applies to LL work orders with a frozen SafeC contract; HAL calls sequence and poll registers and keep the existing HAL register-contract cases; HAL is not claimed local-structured (F011-T036). |

**CRE decision:** `pd-570bd020fd06d45aa2de` (candidate 1880e0e, baseline 2806492): ELIGIBLE_FOR_OFFLINE_REVIEW.

## M2 follow-up — 2026-10-23 (F011-T017 complete; Forge-C d50e115)

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T017 | PASS | `F011-T017` (two failed runs kept: a wrong test path, then a test that read a single-group contract from another engine call; fixed and rerun), `F011-M2-ENGINE`, `F011-M2-SAFEC` | Cross-intent consistency and the per-field coverage inventory were done in M2. Now the semantic SWE.1 also writes the work product SWE.1 owner_decisions.json, bound to the frozen contract digest: every in-scope field without an intent (UNCOVERED_FIELD, with the author's reason kept but deciding nothing), every obligation SafeC leaves unresolved (ERRATA_NOT_BASELINED, PRECONDITION_NOT_VERIFIED) and every author open point, each with its source fact id, RM section and pages when one exists (`source_linked` says when none does). The factory decides none of them. On the IWDG test: the uncovered fields are exactly those of the contract's coverage inventory, each linked to its fact and pages; the missing errata is a finding. |

**CRE decisions:** `pd-12b8a45f8e0a60d3311c` (84bab68, the implementation) and `pd-82ce6f9e313d9a52ffa9` (d50e115, the test fix): ELIGIBLE_FOR_OFFLINE_REVIEW.

## Owner decisions and follow-up — 2026-10-23 (Forge-C a9d5717, SafeC cf3b01b)

Owner, 2026-10-23: "i approve all" (PR #38 merged as 7c643d5, SafeC PR #2 as b3b6412), then chose:
- F011-T016: add a narrow reset intent;
- S013-T014: seal bridge evidence (option 2);
- F011-T004: fix the Linux watchdog;
- SWE1-03: "Yes, it is clean".

| Item | Result | Evidence | Notes |
|---|---|---|---|
| F011-T016 | PASS | `F011-T016`, `F011-M2-ENGINE`, `F011-M2-SAFEC` | New intent action `check_reset` (request schema, additive): a requirement's claim of a field's reset value. SafeC checks it against the register's reset value in the domain: a wrong claim is RIO-RESET-CONTRADICTION with both values and the repair, a field whose reset the source leaves undefined is RIO-RESET-UNDEFINED (UNSUPPORTED), a missing value is RIO-VALUE-REQUIRED. An accepted claim is no register operation (oracle, proofs and mutants unchanged) and is listed in the contract's `reset_claims` (contract schema, additive; absent when there is none, so earlier contracts are byte-identical). Forge-C re-derives each claim from the domain; a claim changed after the engine wrote it is ENGINES_DISAGREE. Tested on real RM0486 IWDG facts (IWDG_RLR.RL) through the real engine. The author model's schema does not offer `check_reset` yet; the other listed fixtures were done in M2. |
| S013-T014 (Forge-C side) | PASS | `F011-T016` | Engine cf3b01b seals every result as a finalized `safec-evidence` payload (scope: no product acceptance) of the request, evidence, artifacts and result bytes. The client checks a seal when present: finalized, inventory and digests per its manifest, and the same bytes as the files it revalidated; a changed sealed file, an unfinalized seal or other request bytes are refused. An engine without a seal (earlier pins) is checked as before. |
| F011-T004 | NOT_PASS (narrowed) | SafeC `validation.md` | The Linux watchdog defect is fixed in SafeC (512edd5: the transport's process group is killed). SafeC on Linux is now 264 passed / 1 failed; the failure left is the retained-guest-logs test, which needs the original Windows host's files. Kind 2 and Z3 are still absent. |
| SWE1-03 (IWDG-LL rc1) | Owner: clean | — | The holdout stays clean; local rejections there are false rejections, as they were scored in M4. No M4 result changes. |
| Engine pin | cf3b01b | both local-rtx-v2 profiles | sha256 `5a3b4cda16cd101b1f2126f73269a3a52abab80a37dc2484ac8b2d7d1396d36f` (cross-host build). |

**CRE decision:** `pd-5f92f4b1b4c5972f348c` (candidate a9d5717, baseline 7c643d5): ELIGIBLE_FOR_OFFLINE_REVIEW.
