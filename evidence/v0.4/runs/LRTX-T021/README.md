# LRTX-T021 — seeded semantic defects on independent frozen holdouts (qwen3-coder:30b)

Run: 2026-10-21 19:01–19:48 UTC, factory 88802e0 (run worktree `forge-c-run-t021`), inside the profile namespace.
- Command: `python -m forge_factory.lrtx.seeded --holdout <rc1 IWDG LL> --holdout <rc1 RCC LL> --model qwen3-coder:30b`.
- Record: `20261021T190139.json` (evidence_run PASS).
- Catalogue: `lrtx-seeded-1`, sha256 `03bdc7c7…`, frozen before the run.
- Holdouts: WO-0009A-STM32N6-IWDG-LL-rc1 and WO-0002A-STM32N6-RCC-LL-rc1.
  - Both are READY_FOR_OFFLINE_REVIEW work orders of the Codex/Claude line, with 0 gaps.
  - They were copied, never written: the tree hashes before and after the run are identical
    (`holdouts-before.sha256`, `holdouts-after.sha256`).

## Result (MEASURED, `seeded-report.json`)

| Case | Class | IWDG-LL | RCC-LL |
|---|---|---|---|
| BASELINE | none (unmutated holdout) | **false rejection** by the inspection | **false rejection** by the inspection |
| S1-OMIT | omitted requirement | inspection FAIL, off target | inspection FAIL, off target |
| S1-QM | safety-scope contradiction | deterministic gate | deterministic gate |
| S3-INVERT | inverted behaviour | **missed** (inspection PASS) | **missed** |
| S3-COMMENT | commented-out code | inspection, **on target** | NOT_APPLICABLE (no register-array assignment to comment out) |
| S4-VACUOUS | wrong test property | inspection FAIL, off target | inspection FAIL, off target |

- **Totals:** 9 seeded cases applied. 2 were caught by the deterministic gate and 1 by the inspection on target.
  4 inspection FAILs were off target, 2 defects were missed, and both clean baselines were falsely rejected.
- **Unchanged gates:** they caught every defect in their scope: the QM claim inside an ASIL B scope (CAPA-044 check).
  - The other classes (an omitted requirement, inverted key, vacuous test) pass every deterministic gate. They are
    left to the inspection by design.
- **Clean holdouts rejected:** the Claude inspector had passed these exact work products. The local inspector failed
  SWE.1 for the recorded PENDING safety allocation, missing failure handling and safe states, and unverifiable
  requirements "without a safety allocation". These are the same findings as in lrtx7–lrtx10.
- **Off-target FAILs:** they would block a defective baseline, but for unrelated reasons that are often false:
  - S1-OMIT: the safety allocation and atomicity again.
  - S4-VACUOUS: SWE4-03 mock fidelity, never the always-true CHECK.
  They are not counted as detections.
- **Missed defects:** the inverted IWDG key (start written instead of refresh, or HSI enable inverted) passed the
  local SWE.3 inspection on both holdouts.

## Conclusion

On this pilot catalogue, the structured qwen3-coder:30b inspector is not a usable independent inspector:
- semantic detection 1 of 7 inspection-relevant cases;
- false rejection of 2 of 2 clean holdouts.

The profile keeps it NOT_QUALIFIED. This is pilot evidence on two holdouts and a small frozen catalogue, not a
reliability or safety qualification.
