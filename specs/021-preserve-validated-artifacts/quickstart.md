# Quickstart: preserve validated artifacts (feature 021)

Owner factory rule 2026-11-13 (D36): a rerun keeps everything already inspected and validated unless a dependency
changed. All commands run on Omniverse2 from `factory/python` with
`PY=/mnt/data/forge-c/repos/forge-c-capa195/.venv/bin/python` and `FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONPATH=.`.

## What is carried

| Phase | Unit | Carried when | Code |
|---|---|---|---|
| SWE.1 (functional) | requirement | named or own-series source with the same governance inventory; PASS verdict when the requirement is byte-identical | `lrtx/swe1_carry.py`, `lrtx/carry_store.py` |
| every phase | author task (SWE.3: unit, SWE.4: unit test, SWE.6: scenario topic, SWE.5: file kind, SWE.2: interfaces/design) | resume source (same packet) or an earlier attempt of the order's line series (same semantic key), accepted by the current schema and validator | `lrtx/visit.inherited_task` (T009) |
| SWE.4+ tool evidence | required tool PASS | it ran on exactly the frozen SWE.3 code (`code_sha`) | `mcp/sdk.invoke`, `inspection/engine.missing_outputs` (T014) |

Every carried item is listed in the package's carry manifest with its source order and record sha (FR-008) and is
never presented as a direct verdict of the run.

## Validate

```bash
$PY -m pytest -q tests/test_f021_semantic_key.py tests/test_f021_carry_store.py tests/test_f021_partial_carry.py \
    tests/test_f021_carry_manifest.py tests/test_f021_partial_phase_carry.py tests/test_f021_unit_carry.py \
    tests/test_f021_tool_evidence_binding.py tests/test_f020_carry.py tests/test_f020_carry_retry.py
```

Recorded 2026-11-14: all pass; regression (`/mnt/data/forge-c/model-service/reg021b.sh`, 189 files) 37 = 37 failures
against the campaign tip cd3f1078, NEW none, GONE none; final scope with inspection/gate/MCP tests (`reg021c.sh`, 206 files) 44 = 44, NEW none, GONE none.

## Open

T012 (SWE.2 per-function units), T014 per-test-id result binding and tool-image hash, T015 SWE.5 per-integration-test
tasks, T016 (impact walk instead of whole-phase staleness), T018 (final regression on the deployed commit).
