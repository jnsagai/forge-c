# Stage 6 — Comprehension Test (EGM Goldfish)

- Reviewer: `egm:egm-comprehension` (fresh native subagent, `omitClaudeMd`, Read/Grep/Glob only), egm 0.1.0 @403d888
- Target: `docs/designs/forge-c-process-first-ornith-qwen.md`, FeatureRange 1-464, DetailedRange 465-832, 2026-10-31
- Document standard: none (per egm-review Stage 6). Status: completed. Design unchanged since Stage 5.

---

## Comprehension review: forge-c-process-first-ornith-qwen.md (Stage 6, lines 1-832)

**Review status:** Complete. I read the persona, the whole target and all four supplied context files: the constitution, spec.md, the plan PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md and SOURCE-INVENTORY.md. No document standard applies to this stage.

**Verdict:** No Blockers. I could paraphrase every section. There are 11 Major and 10 Nit findings. Most come from text left over after D4 raised the cap to two reworks (five attempts), and from safety-relevant terms that are never defined.

### What this proposes

The design adds an opt-in work-order mode, `QM_PROCESS_LAB`, which stops the workflow graph after SWE.1 (software requirements analysis). Each driver gets one work order with a fixed plan of 2–5 single-model attempts: AUTHOR, INSPECT, REWORK, INSPECT, REWORK. Ornith writes and reworks the requirements, and Qwen inspects them read-only. Between roles, an operator swaps models on the single 48 GB GPU using a runbook script. The scheduler holds back any attempt whose profile does not match the model currently loaded, so all attempts of one role across all drivers run as a batch. Each attempt seals its artifacts immutably. Requirement IDs stay stable through a ledger, and cache keys gain the model digest, profile sha and reasoning setting. The run emits a versioned `process-handoff/1` package. Three deterministic tools then work on that package, outside the workspace:
- a CLI scorer compares it with a hidden, frozen per-driver oracle and gives MEETS, FAILS or NEEDS_HUMAN;
- a corpus "decide" CLI is the only place that can declare SWE.1 USABLE;
- a minimal SWE.2 importer proves the package can be consumed.

### How the existing system works, per this document

AFO is a durable queue. It creates attempts from a work order and launches each as a job pinned to one model. On failure, a recovery planner may retry with a different `model_profile`. Fabro runs a workflow graph built by `builder._build`, which always emits all six phases SWE.1–SWE.6. Model calls go through `lrtx` structured packets and a gateway that shares the model provider's process namespace. The packet cache key uses the model *name* only. The SWE.1 author renumbers requirement IDs on every assembly, SWE.2 reads SWE.1 by regex over markdown, and RM0486 is hard-coded. When the stepwise inspector fails or times out, it routes to rework. Model handoff safety rests on a mission ledger (inference owner, QUIESCENCE records, SENT/UNKNOWN requests), operations intents (RUNNING / DRAINING / STOPPED) and a llama-server stack that serves one model per profile from Ollama `library` manifests.

---

### Findings

**1. Major: the plan size and swap counts disagree with D4 (lines 98, 155–158, 207, 381, 398)**
- D4 allows up to five attempts. But Alternative B (l.381) says "D1 chose one order with **three** planned attempts".
- §2 (l.207) covers only "Attempts 2 and 3"; attempts 4 and 5 are not addressed.
- The data-flow diagram shows only seq 1–3.
- Alternative D (l.398) expects "about 2–3 swaps per corpus". With role batching and a five-entry plan, the sequence is Ornith → Qwen → Ornith → Qwen → Ornith, which is up to 4 swaps per arm. Alternative D's argument for a manual swap rests on that number.

**2. Major: CUJ 1 contradicts D2 about who swaps models (line 117)**
- CUJ 1 says "AFO runs the Ornith author job, proves quiescence, **swaps to Qwen**".
- D2 (l.100) and §3 say AFO never loads or unloads a model; the operator does, by runbook.
- CUJ 1 never says the operator has to act. It also never says that someone must first start the stack with the Ornith profile; per item 20, the order otherwise defers forever with `RESIDENT_PROFILE_UNKNOWN`.
- The runbook step "when to swap" (item 28) is not explained either. Nothing says how the operator learns that a role batch is finished.

**3. Major: the mapping from attempt outcome to order terminal state to verdict is not connected (lines 203–204, 565–566, 651–656)**
- §2 says a failed or stopped attempt makes the order terminal with `LAB_ATTEMPT_FAILED` / `LAB_ATTEMPT_STOPPED`.
- Item 18 instead sends FAILED, CANCELLED and STOPPED attempts to VALIDATING, after which `process_lab.verdict` returns `BLOCKED/<specific reason>`.
- A *successful* lab order is reported as `BLOCKED/PROCESS_LAB_SEALED`, and this is never explained (presumably it ensures no READY verdict).
- "Final planned seal exists" is ambiguous when an early REWORK skip ends the order after two attempts. If "planned" means the plan's last entry, a clean early finish would be reported as a failure reason.
- A reader cannot name the full set of terminal states that G1 promises, or say how one reads a good lab result.

**4. Major: the planned-attempt creation and swap intents may not fit together (lines 642–645, 651–654, 231–234)**
- `planned_attempt` refuses unless the operations intent is RUNNING.
- The swap puts the intent into DRAINING. An attempt that succeeds during the drain would therefore hit the refusal.
- Item 18 says "Otherwise transition to VALIDATING", which reads as if the order would end early.
- The design should say what happens to the next planned attempt when the intent is not RUNNING: retried at the next reconcile, or terminal.

**5. Major: "actionable finding" is undefined but decides control flow (lines 184, 209, 652–653)**
- Whether a REWORK runs depends on "actionable findings" in `inspection-<seq>.json`.
- No criterion is given: severity, category, or any FINDINGS outcome at all.
- This choice decides how many attempts and swaps occur, so it affects cost.

**6. Major: the four scoring criteria cannot all be computed from what is defined (lines 309–311, 522–525)**
- "≥ 90% judgeable verification criteria" must be computed by a deterministic scorer with no model call. Neither the method nor the needed oracle field exists; the oracle schema has no element for judgeability.
- It is unclear whether assumption-marked refs count toward "100% resolvable refs".
- Keyword "matching hints" are vague about how a match is decided.

**7. Major: the corpus decision depends on undefined inputs (lines 317–326, 604–609)**
- `decide` takes a `preregistration.json`, but no schema or field list is given for it, and it is not among the five new schemas (item 8).
- "Trial", "order" and "driver" are used interchangeably. If a driver has several trials, it is unclear whether "every driver MEETS" requires every trial to be MEETS.

**8. Major: the core terms of the safety handoff are undefined (lines 21, 55, 232, 247, 615–616)**
- These terms are central to the safety argument, yet none is defined or linked: "the existing quiescence proof", "inference owner", "QUIESCENCE record", "SENT/UNKNOWN request", "held lease", "settle_shutdown", "provider retire, kernel-proven exit" and "epoch+1".
- The swap state machine also mixes operations intents (RUNNING, DRAINING, STOPPED) with swap-only states (QUIESCENT, UNLOADED, LOADING, READY). It never says which are real stored states and which are labels used only by the script.

**9. Major: project-specific systems and modes are used without definition or link (throughout)**
- **AFO** is never expanded or described, even though it carries the queue, dispatch and policy. Spec.md does not define it either.
- **Fabro** is only implied by the diagram.
- `QM_DELIVERY_FIRST_DEMO` / Delivery-First is the pattern §1 says to follow, but nothing links to DELIVERY-FIRST-E2E.md.
- "strict graphs / strict release", "brownfield resume" (l.207), "owner execution window", "grant / revoke" and "signed per-experiment AFO policy" are also used without definition.

**10. Major: AT references are unanchored and partly mismatched (for example lines 189, 301, 779, 777)**
- AT02–AT17 are cited as justification but never tied to plan §9.
- Several citations do not match the plan's definitions:
  - **AT16:** the plan defines it as source-control privacy; the design uses it for oracle-path isolation.
  - **AT08:** the plan defines it as GPU-contention cooldown; the design uses it for resident-profile batching.
  - **AT17:** the plan defines it as the learning disposition after a stop; the design never mentions learning disposition.
  - **AT11:** the plan says "exactly one bounded correction", but the design cites it for the two-rework case.
- A reader who follows these citations gets conflicting text. Unlike D3, which explicitly overrides the AtomicChat reference, the design never says that D4 supersedes the plan's "one rework" wording (plan §5.2, §7, AT11).

**11. Major: "model digest" means two different things (lines 101–102, 145, 705–706)**
- D3 gives `de46c4ba…` as the Ornith sha256, and CUJ 5 speaks of the "GGUF digest".
- Item 24 sets the profile `digest` to the sha of the *Ollama manifest file* and puts `de46c4ba…` in `model_blob_sha256`.
- G3 and §4 key the cache on the "model digest". Which value is meant decides whether the cache-invalidation goal holds.

**12. Nit: the builder and process_lab.workflow appear to call each other (lines 563, 636)**
- Item 16 has the builder hand off to `process_lab.workflow(manifest, role)` when the lab block is present.
- Item 9 has `process_lab.workflow` call the builder with `stop_after="SWE.1"`.
- The entry point, how the loop is avoided, and where `role` comes from at line 212 are not stated.

**13. Nit: per-requirement inspector outcome with two inspections (lines 186–189, 287–288, 192–193)**
- `requirements[].inspector outcome` is a single value, but up to two inspections occur. It is unclear which one it reflects.
- "The REWORK seal references the AUTHOR seal" does not cover seq 5. Item 10's "prior seal sha" suggests a chain instead.

**14. Nit: inspector enum mismatch (lines 273, 517)**
- §7 defines three outcomes. Item 4's schema adds `NOT_RUN` without explanation.

**15. Nit: CUJ 3 wording (line 133)**
- "Cannot be MEETS if a critical obligation is uninspected **and** unmatched": an unmatched critical obligation already gives FAILS under §9, whatever the inspection status.
- §9 says inspector verdicts never override the score. The CUJ suggests inspection status affects the result, which it does not.

**16. Nit: "repair budget" vs "never repaired silently" (lines 131, 344)**
- The two phrases read as contradictory. "Repair budget" needs a one-line definition.

**17. Nit: a sealed package cannot be told apart from a scored copy (lines 291, 546)**
- An invalid-example fixture rejects `criteria_result: MEETS` in a "sealed, unscored package".
- No field is given that lets the schema tell a sealed package from a scored copy.

**18. Nit: profile terms are unexplained (lines 198–206, 214–216)**
- `profile` vs `model_profile` in the attempt entries is never explained.
- "Profile sha" (the sha of which file?) and the mapping from short names such as `lab-ornith-q8` to the YAML filenames are also unstated.

**19. Nit: the `tests/` alias conflicts (lines 467–468, 824)**
- `tests/` is defined as `factory/python/tests/`, but the Verification Plan runs `python3 tests/spec/validate_design.py`.

**20. Nit: minor undefined identifiers**
- loop10, MTP, F015 / Feature 015, "DA task ticks", `COUNT=58`, `0014g`, "IDR", PF-SWE1-006, "semantically 3/9" (Q5), "the reply" (item 22).
- "lab terminal node" (§1) vs `lab_end` (item 16).
- "time box `Continue`" vs CONTINUE.
- "release code … reused" in the Overview, although the lab graph has no release nodes.

**21. Nit: document bookkeeping**
- Open Questions start at Q3, with no note on what became of Q1 and Q2.
- Item 29 marks this design as "(Create)", but it already exists.

Reviewed file: /media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-process-first/docs/designs/forge-c-process-first-ornith-qwen.md
