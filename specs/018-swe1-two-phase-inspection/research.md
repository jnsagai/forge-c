# Research: Two-phase SWE.1 inspection

Sources: code map of tip `de42bc29` (2026-11-09), the pinned guideline, owner-lane evidence L40-L43 and F017 trial 1.

## R1 Where phase 1 runs
- **Decision**: between `swe1_author` and `swe1_author_gate` (before the freeze).
- **Rationale**: the freeze hashes the work products; phase-1 rework after freeze makes the baseline stale, re-runs
  SWE1-01..06 (checkpoints keyed by baseline hash) and each recorded inspection counts against `maximum_rework_cycles`.
- **Alternatives**: inside the inspector node (cannot swap to the author model in one node under managed serving);
  after the freeze (cost above).

## R2 Single-requirement rework
- **Decision**: a one-requirement output schema and a deterministic splice into the task checkpoint, then
  `validate_group` and `assemble` from existing records.
- **Rationale**: today's repair unit is the register group; protection of other keys is a prompt instruction only
  (`structured.py` "keep every element not named"), and changing any register task re-authors the crosscutting task.
  Splicing guarantees byte-identical other requirements and needs no author re-run.
- **Alternatives**: group repair with a post-hoc diff check (wastes calls, still re-triggers crosscutting).

## R3 Batching and swaps
- **Decision**: rounds: inspect all pending (inspector) -> rework all failing (author) -> check; `serve` is a no-op
  when the model is loaded, so a round costs at most two swaps.
- **Rationale**: one GPU; a swap is ~60-90 s (F017 probes: stack serve 70-90 s).

## R4 Per-requirement inspector context
- **Decision**: the requirement, its own task's other requirements (read-only, IQ-09), the cited RM section, the
  scope and out-of-context note, IQ criteria.
- **Rationale**: the current item packet carries the whole set (~241 kB on GPIO) for every item; per-requirement
  packets are small, cheap and focused. Set-level consistency is phase 2's job (SQ-05).

## R5 SQ items and the gate
- **Decision**: SQ-01..10 judged as non-gating items; actionable SQ findings make the reply REWORK while an SQ
  allowance (2 cycles) remains, then are recorded only.
- **Rationale**: owner decision "checklist + SQ as additional set findings that route to rework" and the guideline's
  own note that the versioned checklist stays the gate; the allowance bounds the loop (constitution: bounded loops).

## R6 Request shapes
- **Decision**: reuse roles `swe1-inspector` (json_schema, effort medium, temperature 0, seed 1) and `swe1-author`
  (json_schema, effort medium) so the owner-lane product-role trial declares them already (CAPA-195 lesson).

## R7 Rounds
- **Decision**: 3 per requirement content lineage; stop early on no change.
- **Rationale**: guideline step 7 (repair and re-check affected items); bounded.
