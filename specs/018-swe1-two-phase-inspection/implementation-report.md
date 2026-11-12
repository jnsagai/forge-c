# Feature 018 - native acceptance (T014, T015)

Recorded 2026-11-10 from the Omniverse2 owner lane (work-order records, line queue, deployer log, CRE store).

## T014 - CRE gate, merge, deploy

| Commit | What | CRE decision | Deployed |
|---|---|---|---|
| `03d78012` | merge of feature 018 | REJECTED pd-e9adda3e (phase-1 nodes not bound to their roles) | no |
| `26f0bd8c` | fix: quality criteria outside the protected checklist tree | ELIGIBLE pd-cdff829f | 2026-11-09 09:17Z |
| `a58c4018` | fix: phase-1 nodes bound to their roles for the line-product check | ELIGIBLE pd-1ade8fbe | 2026-11-09 10:18Z |

## T015 - WWDG LL SWE.1 (`WO-F014-SWE1-WWDGL-20261109-L44F`)

- Phase 1 (`.forge-run/lrtx/SWE.1/phase1/summary.json`, 2026-11-09 12:23Z): 20 requirements, 20 passed, 0 rework,
  0 carried, 0 pending, 3 rounds recorded.
- Phase 2 (`phase2/set-quality.json`, 12:32Z): baseline BL-SWE.1-001, 10 set findings, 0 routed to items, 0 unjudged.
- Quality report: `.forge-run/lrtx/SWE.1/quality-report.md` present.
- Gate: SWE.1 inspect PASS (INS-SWE.1-001, failed_inspections 0) at 2026-11-09T12:36:36Z; order ended
  `PHASE_VERDICT:PASS:SWE.1` (SWE.1-only ladder stage).
- Swaps per round: not extracted separately (NOT_RUN); phase 1 needed no rework, so no swap took place.

Second native data point (SPI LL, after CAPA-207..211): `WO-F014-SWE1-SPIL-20261107-L41P`, phase 1 45 requirements,
41 passed first time, 4 reworked within 3 rounds; set inspection PASS first time (failed_inspections 0) at
2026-11-10T06:14:37Z; whole SWE.1 about 2 h.
