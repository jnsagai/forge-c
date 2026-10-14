# KPI Acceptance Scenarios — deterministic test requirements

| Scenario | Stimulus | Expected |
|---|---|---|
| AC-K01 | 6 phases, all first inspections pass, READY package | RTY=100%, quality=100% (denominator 1), marked low sample; no claim of ASIL approval |
| AC-K02 | SWE.3 fails first inspection; fixes, passes third review | SWE.3 FPY=0% for that first-inspection sample; rework cycles=2; READY possible later, but order RTY=0% |
| AC-K03 | 2 attempts for same work order | Throughput counts one unique order, no fake second unit |
| AC-K04 | Complete BLOCKED archive, no READY | Valid archive exists; throughput=0; tokens per READY=N/A not infinity or zero |
| AC-K05 | Missing safety/tool evidence | Evidence completeness falls; may be BLOCKED; no KPI formula can override gate |
| AC-K06 | Unsupported MISRA checkers | Report rules not checked; do not call package MISRA-compliant |
| AC-K07 | MCU A vs MCU B, different reference footprint | Per-target dashboard separation; memory baseline not silently shared |
| AC-K08 | Missing calibrated time baseline | SFOEE=NOT_COMPUTABLE with explanation, not 0 nor fabricated percentage |
| AC-K09 | No planned run window or queued driver | Availability=N/A, not artificially zero |
| AC-K10 | Event stream replayed twice | Same snapshot values/hash as single replay, including first inspection |
| AC-K11 | Tool claims pass in AI free-text only | Quality gate remains UNKNOWN/BLOCKED; no agent text trusted |
| AC-K12 | Token provider lacks usage counter | `UNKNOWN` or explicitly `ESTIMATED`, no silent zero |
| AC-K13 | UI filter disables AI/tool logs | Underlying events and mandatory audit preserved; metrics unchanged |
| AC-K14 | Repair repeats fault next day | Recurrence ratio reflects actual fingerprint/window; lesson claim still unproven |
| AC-K15 | High SFOEE but safety gate fails | `BLOCKED`, no auto release; OEE does not mask red gate |
| AC-K16 | Adversarial model tries to edit KPI formula/baseline via MCP | Denied by least-privilege policy; audited |
| AC-K17 | Historical formula version upgraded | Historical snapshots retain hashes; versions labelled and metrics recomputed only as explicitly migrated |
| AC-K18 | Release ZIP built | Includes catalog, hashes, numerator/denominator, window, data flags, evidence links and no AI-generated signoff |
