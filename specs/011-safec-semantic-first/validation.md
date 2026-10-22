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
