# EASA pilot validation, rc-v1 HAL packages r161-r164 (measured 2026-10-19)

- **Tool:** `forge_factory.assurance.pilot_validation worksheet`, at the CAPA-047 candidate revision `f1782d4`
  (oracle no_write semantics fixed). The archives were read-only; each sha256 is in `worksheet-unsigned.json`.
- **False negatives:** 24 seeded defects applied (6 per package; 2 of the 8 seed classes do not apply), 0 missed.
  The observed rate is 0/24, with a one-sided 95% upper bound of about 12% (exact). This is a small sample.
- **False positives:** 32 blocking EASA findings to review (8 per package). `review-data.json` gives the gate
  reasons and verifier findings for each row.
- **Status: NOT a validated pilot record yet.** It becomes one only after the named human reviewer fills every
  disposition (CORRECT/INCORRECT) and signs. Then `pilot_validation record` computes the rates.
- ENFORCING still also needs a READY package, and the ASIL B safety evidence is postponed by the owner.
