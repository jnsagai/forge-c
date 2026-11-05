# CAPA-079 — critical obligation could not be repaired: validator said "remove", coverage only post-assembly

- Observed: Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-03 (01M69V139JKG14HMVVTT8GWNAH): OBL-preserve-other-registers uncovered; the one development repair pass was spent before the coverage finding; SWE.1 BLOCKED (correctly fail-closed).
- Diagnosis (offline, real validators): a cross-cutting preservation requirement naming CRC_IDR got "remove requirement [k]"; the same rule without the register name is valid; the run log shows the coverage repair call was refused (REPAIR_EXHAUSTED); first-attempt errors were overwritten (now kept: checkpoint history).
- Fix 003913e0: rephrase-not-remove instruction for obligation-citing cross-cutting requirements; cross-cutting task checks obligations without register effects; checkpoint history.
- Reproducer RPR-078: rr-14722017cebc3ee4a717 PRESENT at b4b84933, rr-301a71626aa0e53ad724 ABSENT at 003913e0. Failed-before: before-fix.txt.
- CRE: first gate pd-a679a8ce6f44c134f1dd REJECTED (prevention: RPR-076/077 v1 REPRODUCER_ERROR, scenario not reached - promotion-gate-rejected.txt); owner chose to re-freeze v2 reproducers (3436f4c8); second gate pd-526a6b7ea5b2cdf2046b ELIGIBLE, 7/7 (promotion-gate.txt). CAPA-079 EFFECTIVENESS_OBSERVING.
