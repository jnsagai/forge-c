# Quickstart: Brownfield Work Orders

Validation guide for feature 008. Contracts: `contracts/`. Data model: `data-model.md`.

## Prerequisites

```bash
cd /home/jefferson/forge-c && . scripts/forge-env.sh
eval "$(scripts/forge_cloud_bench.sh env)"   # live runs only (Codex authors, Claude inspectors)
export PYTHONPATH=$PWD/factory/python:$PWD/factory/python/tests
```

## 1. Deterministic checks (no models)

```bash
python -m pytest -q -p no:cacheprovider factory/python/tests/test_brownfield_*.py
```

Expected: all pass. The suite covers:
- intake refusals: missing function, missing licence, build failure, FIX_ALLOWED with a licence that forbids
  modification;
- read and write protection;
- the trace map;
- the five seeded mismatch kinds;
- FROZEN escalation;
- the FIX_ALLOWED change report;
- packaging.

## 2. Intake only

```bash
python -m forge_factory.workorder --example examples/0008a-rcc-ll-delivered --wo WO-0008A-INTAKE --intake-only
```

Expected: `.forge-run/delivery/intake.json` with status `ACCEPTED`, 16 resolved functions and one fingerprint per
file. The workspace contains **no** `software/` files yet (FR-007).

## 3. FROZEN run on the factory's own LL code (SC-001, SC-004, SC-007)

```bash
python -m forge_factory.workorder --example examples/0008a-rcc-ll-delivered --wo WO-0008A-RCC-LL-b001 \
  --model deepseek-flash --provider deepseek --acp-authors codex --acp-inspectors claude --detach
```

Expected:
- `.forge-run/delivery/injection.json` names the SWE.1 baseline frozen before injection;
- every phase produces its work products, and the packaged `software/ll/*` matches the delivered fingerprints;
- `conformance.json` has no findings, or each finding is named;
- the package is READY_FOR_OFFLINE_REVIEW or BLOCKED with named gaps;
- the run takes under 60 minutes.

## 4. FIX_ALLOWED run on the HAL with a seeded defect (SC-003)

```bash
python -m forge_factory.workorder --example examples/0008b-rcc-hal-delivered --wo WO-0008B-RCC-HAL-b001 \
  --provided-from WO-0002A-STM32N6-RCC-LL-r170 --model deepseek-flash --provider deepseek \
  --acp-authors codex --acp-inspectors claude --detach
```

Expected:
- a CODE defect for the seeded rollback fault;
- `change_report.json` links each changed file to that defect, with its diff;
- untouched delivered files stay byte-identical.

## 5. ST pilot (SC-006)

```bash
python -m forge_factory.workorder --example examples/0008c-st-cube-rcc --wo WO-0008C-ST-RCC-LL-b001 ...
```

Expected:
- the package states ST, BSD-3-Clause and the download fingerprints, and lists 11 scope functions and the excluded
  ones;
- it ends READY or BLOCKED, with every gap named.

## 6. Greenfield unchanged (SC-008)

Run the full regression (`python -m forge_factory.assurance.regress --full`) and the CRE promotion gate. Both must
pass, with the existing checklists, release policies and greenfield tests unchanged.
