# Implementation Plan: Preserve validated artifacts across runs

**Branch**: `feat/021-preserve-validated-artifacts` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

## Summary

Generalise the SWE.1 functional carry (`lrtx/swe1_carry.py`, D36/D39) into a factory mechanism: a validated-item store
with run-identity-free keys, per-phase preservation units with dependency sets and an impact walk, partial phase carry,
hash-bound tool evidence and a carry manifest in the package. Paths relative to `factory/python/forge_factory/`.

## Technical Context

**Language/Version**: Python 3.13 (factory), unchanged toolchain
**Primary Dependencies**: existing lrtx visit/structured/review, inspection engine, assurance ImpactGraph, release packager
**Storage**: per-order `.forge-run/` records (unchanged) + a validated-item index (sqlite, one per line state dir)
**Testing**: pytest, scripted answers only (never a real model); CRE reproducer per behaviour change
**Target Platform**: Omniverse2 owner lane + cloud bridge (same code)
**Constraints**: pinned adapters untouched (`llm_gateway.py`, `afo/product_job.py`, `afo/execution_lifecycle.py`,
`fabro/client.py`, `lrtx/stack.py`); register-level ladder packets byte-identical (FR-010/SC-004); CRE gate before deploy
**Scale/Scope**: SWE.1..SWE.6, one component lineage per carry

## Constitution Check

- Deterministic gates stay authoritative: carried items are re-validated by the current validators (FR-003) - PASS.
- No certification/release claims; carried verdicts are labelled (FR-008) - PASS.
- Evidence linkage: provenance per carried item (FR-008/US2) - PASS.
- Baseline tests keep passing (FR-010) - PASS by design (no carry sources = today's path).

## Design (per FR)

| FR | Change | Where |
|---|---|---|
| FR-001 | `validated_items` index: (phase, item_key, content_sha, dep_sha) -> record ref, verdicts, provenance | new `lrtx/carry_store.py` |
| FR-004 | split `input_hash` into `semantic_key` (prompt/skill/criteria/schema/sources shas) and run context; QM scope without work_order_id in the key; lessons pinned per key | `lrtx/structured.py`, `release/qm.py` (key only; packets unchanged for orders without carry) |
| FR-002/003 | lookup + re-validate + release on finding, generalising `swe1_carry.seed_task/merge_kept/verdict_carrier` | `lrtx/carry.py` (from `swe1_carry.py`) |
| FR-005 | per-phase unit declarations and dependency sets; wire `assurance/impact.ImpactGraph` into rerun planning | `inspection/engine.py`, `assurance/impact.py`, phase modules |
| FR-006 | partial phase carry instead of all-or-nothing `--resume-from` | `workorder.py` resume, `lrtx/visit.py` |
| FR-007 | tool evidence keyed by code/test/tool-image shas per test id | `inspection/engine.py` tool PASS freshness |
| FR-008/009 | carry manifest in the package; refusal reasons | `release/` packager, `lrtx/carry.py` |

## Phases

1. Store + semantic key (FR-001, FR-004) - SWE.1 functional migrates onto it (no behaviour change, D36 tests green).
2. Partial phase carry (FR-006) + carry manifest (FR-008/009).
3. Per-phase units + impact walk (FR-005): SWE.2, SWE.3, SWE.4, SWE.5, SWE.6 in that order.
4. Hash-bound tool evidence (FR-007).
