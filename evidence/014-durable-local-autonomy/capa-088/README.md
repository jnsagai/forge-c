# CAPA-088 — the thinking profile's inspector refused large frozen sources

- Observed: Fabro SWE.1 run WO-F014-SWE1-RCC-20261101-03 (01M6AX62VKEJ0RY4S57NED425T, Omniverse2, RCC LL 0002h, 61
  register groups). The baseline froze after about 3 h 50 min of authoring. The inspector then refused it before any
  model call: SOURCE_TOO_LARGE:workproducts/SWE.1/register_effects.json:107046>40000. CAPA-085 stopped the run after
  three identical refusals. The Ornith thinking profile kept the inherited 40 000-character per-source bound; the other
  Omniverse2 profiles set inspection_max_source_chars 1048576.
- Fix 8ee683b7: think profile v4 sets inspection_max_source_chars 1048576. The gateway still refuses a request over the
  model context. The RCC request measures about 500 k characters (about 156 k tokens) against a 262 k context.
- Owner 2026-11-01: rerun RCC from scratch (queued as WO-F014-SWE1-RCC-20261101-04).
- Reproducer RPR-088 runs: rr-7fde66f367b48959cd26:7eb50799:BASELINE:SYMPTOM_PRESENT rr-8fdbad37122efccdcbc9:8ee683b7:CANDIDATE:SYMPTOM_ABSENT rr-7021970631dde62980a8:7eb50799:BASELINE:SYMPTOM_PRESENT rr-ace74a2322b535618664:8ee683b7:CANDIDATE:SYMPTOM_ABSENT rr-57e0f7760795e7da5c67:8ee683b7:PREVENTION:SYMPTOM_ABSENT rr-288402925b14d56c9f4b:f262931d:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-96606a3ab7a863fca783 ELIGIBLE (FIX, 7/7, promotion-gate.txt); CAPA-088 in ../../cre/capa/capa-088.json.
- Regression (swap set plus the new tests) at 8ee683b7..f262931d and at baseline 7eb50799: 1693 passed / 7 failed and
  1687 passed / 7 failed. The same 7 tests fail on both sides.
