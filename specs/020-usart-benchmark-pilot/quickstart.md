# Quickstart / validation guide: USART benchmark pilot - SWE.1

Run everything on Omniverse2 over ssh, in the feature worktree `/mnt/data/forge-c/repos/forge-c-020-usart`
(Python: `/mnt/data/forge-c/repos/forge-c-capa195/.venv/bin/python`, from `factory/python`,
`FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONDONTWRITEBYTECODE=1`). Never run git over the sshfs mount. After any
test run restore `docs/IMPLEMENTATION-STATUS-v0.4.md` and `evidence/v0.4/implementation-status.json`.

## 1. Register-level orders are unchanged (SC-007)

- Run the identity guards listed in research.md R1/R2 (structured golden, RCC equivalence, lrtx compat, stop-after,
  018 suites, swe1 suites, reqif, f019 derived campaign, WWDG lineage, owner-supervised suites).
- Expected: identical results to the base commit (same failures, none new); no frozen fingerprint re-recorded.

## 2. Governance inventory and coverage (US1, SC-001)

- Prepare the UART order from `examples/0012u-st-cube-uart-module` with no model run.
- Expected: `inputs/governance-inventory.json` exists, validates against
  `contracts/governance-inventory.schema.json`, lists every input with its role (delivered files only as
  `implementation_under_analysis`) and classifies every delivered public function `in`/`out`.
- Negative: remove one function from every scope group in a test copy → prepare refuses with INPUT_GAP naming it.
- With a fake model answer for the governance step: coverage `COVERAGE_PASS`; drop one in-scope function from all
  use cases → `COVERAGE_FAIL` naming it, SWE.1 author not started.

## 3. Functional SWE.1 (US2, SC-002..SC-006)

- Unit level: `test_f020_*` - schema, validators (level rule, links, groups, code-source refusal, design constraints
  by inspection), assembly lines after `Verification:`, `requirement_attributes.json`, ReqIF attributes and relations,
  gate rejection texts, two-phase packets for functional orders, register-level packets byte-identical.
- On the line (pilot launch): the `uart-module` lineage runs SWE.1 only; expected gate PASS within the normal rework
  budget, no owner input; then check SC-002..SC-005 with `benchmark/compare.py --pilot-only`.

## 4. Comparison, privacy, proposal (US3, SC-008..SC-010)

- Private (outside the repo): extract benchmark metrics into
  `/mnt/data/forge-c/model-service/private-benchmark/metrics.json` (validates against
  `contracts/benchmark-metrics.schema.json`).
- `python -m forge_factory.benchmark.compare --pilot <workspace> --benchmark <private metrics.json> --out <dir>`:
  every FR-024 metric for both sides.
- Privacy test: the repository scan with hashed forbidden tokens finds nothing.
- `python -m forge_factory.benchmark.proposal --log specs/020-usart-benchmark-pilot/decision-log.md --metrics <dir>`:
  every rule cites its log entry.
- Second module (SC-009): the synthetic test module is prepared and passes the governance and SWE.1 validators with
  only its own data.

## 5. Commands actually used (T038, rounds 2-3, 2026-11-12/13) and their results

- Comparison with the guarded metrics of the previous round (D34):
  `python -m forge_factory.benchmark.compare --pilot <workspace> --benchmark <private metrics.json> --out <private dir>
  --preserve <previous comparison.json>` -> `{"status": "OK", "requirements": N, "regressed": [...]}`. Outputs stay
  in the private directories (Omniverse2 `model-service/f020-compare-<run>`, loop10 `ops/scratch/f020/private/cmp-<run>`).
  Results: L49 241 reqs; L50 137 (traced share and IQ first pass REGRESSED vs L49, set inspection lost to the
  CAPA-249 guardian crash); C03 273 (set packet refused, CAPA-248); C04 257, every guarded metric PRESERVED vs C03.
- Cloud control run (account-only bridge, loop10): inside `lrtx.stack exec` with `FORGE_LRTX_PROFILE=
  cloud-bridge-claude-author-codex-inspector`: `python -m forge_factory.workorder --example
  ../../examples/0012u-st-cube-uart-module --wo <WO> --profile cloud-bridge-claude-author-codex-inspector --model
  claude-opus-5-5 --purpose ASPICE_ONLY --stop-after SWE.1 --detach`; each run from its own worktree.
- Carry between rounds (D36/D39): `examples/0012u-st-cube-uart-module/workorder.json` `swe1.carry_from` lists the
  predecessor runs (first existing workspace wins); only requirements a new rule names are reworked.
- Round 3 (D40) unit evidence: `pytest tests/test_f020_round3_references.py tests/test_f020_carry.py
  tests/test_f020_template_v2.py` -> 24 passed; reproducer RPR-256 (stale reference) 4/4 roles via
  `model-service/checkrpr.sh 256`.
- Regression scope (T024/T040): `bash /mnt/data/forge-c/model-service/f020reg2.sh` (feature vs base, prints NEW/GONE).
