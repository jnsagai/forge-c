# Implementation Plan — Feature 006 Enhanced AI Software Assurance

**Branch:** `feat/006-enhanced-ai-software-assurance` · **Date:** 2026-10-17  
**Source of truth:** `spec.md`, `research.md`, `architecture.md`, controlled work-order requirements/HSI, project constitution.  
**Delivery:** complete tested infrastructure and evidence-backed SWE.1–SWE.6 assurance; not mere documentation; **NO SUP/MAN extensions**.

## Summary and prerequisites

Base branch `feat/005-autonomous-factory-operations` is stacked on 004; 004 HEAD may evolve independently and must be carefully reconciled before later merge. Owner/Claude must not treat the 005 specification as a completed Conductor. Preserve existing approved ASPICE v4.0 baseline, all 002–004 behavior, source hashes and existing release gates. Confirm actual runtime implementation before selecting extension points.

**Language/platform:** Python 3.13 factory runtime on Ubuntu 22.04/24.04; Fabro 0.362, restricted MCP, local inference, Clang/LLVM/GCC, Cppcheck subset, Renode and optional CBMC/gcovr where actually installed. Match installed versions rather than guessing.

## M0 — Freeze and audit

Read constitution and implementation 001–005, run test suites, review 2026-10-17 27-run report, freeze real review archives r101 and r102 (if accessible) and compile independent baseline. Pin standard edition and start a method catalog review register. Do NOT copy ISO pages to public GitHub. Treat unavailable archives as audit limitations.

## M1 — Method / profile policy

Implement `AssurancePolicy` + product scope separately; register table/row `++` index, applicability, method/alternative combinations, exceptions and approved source version. Keep catalog `SECONDARY_WORKING_INDEX` until a licensed reviewer has signed the per-table reconciled checksum. Preserve baseline `mode=OBSERVE_ONLY` and pre-existing authorization. Add schema tests, safe policy reload, no automatic edits to normative or safety profiles.

## M2 — Independent evidence gate

Implement evidence ref and hash verification, actual execution tests, independent oracle authority, holdout separation, `Claim-Argument-Evidence` graph and gate evaluator. Reuse inspector roles but ensure a second independent deterministic checker verifies semantic assertions where possible. Role/prompt/expected-outcome shared provenance must be flagged. Quarantine malicious logs and fake/unknown evidence.

## M3 — SWE.1 and SWE.2

Requirement source citations and semantic checks (time bounds, failure response, HSI, requirement allocation), two-way requirements-to-test trace. Architecture graph consistency, PlantUML validation, component allocation, interface signatures, concurrency/IRQ ownership and scheduling/data-flow where feasible. All semantic AI findings are hypotheses until independent grounded verification; no invented hardware semantics.

## M4 — SWE.3

Enforce table1/table6 method catalog constraints, MISRA rule-family coverage matrix, static analyses, concurrency, side effects and RO register contracts with official MCU manual and errata. Record host/target footprints, stack, timing and simulation fidelity. Optional bounded proofs depend on installed tools; distinguish proof on bounded model from physical behavior. Reject unauthorized changes to frozen tests/specs.

## M5 — SWE.4

Create test/oracle from authoritative requirements/HSI in a different trust domain; test actual API path (not mocks only), coverage statement/branch and justified gaps, project mutation campaigns and selected risk-based MC/DC if available. Don't claim fixed numeric threshold from ISO; initial ENHANCED baseline measurement then explicitly approve thresholds. Common-cause oracle contamination is a blocker.

## M6 — SWE.5 and SWE.6

Fault injection, negative, timing and boundary integration tests, real requirement-observing embedded software tests. Build explicit environment ontology and fidelities: HOST, EMULATOR, RENODE, HIL, PHYSICAL. If a HIL/board is absent, report unmet verification objectives honestly. Back-to-back testing only when model-based development applies. Add evidence of firmware traces/observations, not merely Robot pass text.

## M7 — Evidence, package and dashboard

Reuse existing release and dashboard APIs; add method selections/rationales, CAE status, counterevidence, results/limits to immutable offline handover. Bind every record to run/profile/tool/revision. Missing ASIL B safety docs should block; explicit QM scope can N/A with justification. No ISO certification, CL3 assessment or ASIL signoff.

## M8 — Fault campaign and staged activation

Execute negative fixtures for every phase, retrospective read-only LL r101/HAL r102, regression against 001–005, full real-model end-to-end runs and a separate correct-versus-defective test corpus. Score escaped defects/false negatives and false positives, not only checklists. Keep OBSERVE_ONLY by default, then owner-authorized PILOT, then independently approved ENFORCING if evidence supports. No CI task completion counts as production readiness.

## Source layout proposal

```text
factory/python/forge_factory/assurance/{__init__,policy,catalog,oracle,evidence,claims,gate,mutation,hardware,methods,report}.py
factory/python/tests/test_easa_*.py
specs/006-enhanced-ai-software-assurance/{spec,plan,tasks,research,data-model,architecture,acceptance-tests,quickstart}.md
specs/006-enhanced-ai-software-assurance/contracts/*
config/factory/assurance-policy.yaml   # only after implementation; author-owned, no auto-enable
```

## Completion and evidence

Every task needs real modified source or controlled evidence, actual command, version, exit code, result digest and issue list. Distinguish `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, `NOT_APPLICABLE`. A successful packaging action is not a successful software engineering outcome. No existing signed archived outputs are mutated. Use `validate_spec.py` to check authored design *only*, then run implemented tests and real environments separately.
