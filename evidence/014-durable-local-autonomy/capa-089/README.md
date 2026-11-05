# CAPA-089 — a brownfield SWE.2 call contract was first compiled at SWE.3

- Observed: Fabro runs WO-F014-SWE2-CRCK-20261101-01 -> WO-F014-SWE3-CRCK-20261101-01 (Omniverse2, CRC IDR on ST code).
  SWE.2 froze workproducts/SWE.2/api_calls.json, passing the undeclared identifier CRC_Instance. The CRC LL order's
  contract passed no arguments at all. Only the SWE.3 gate compiled the contract. SWE.3 may not edit SWE.2 files and
  filed no upstream defect, so three author cycles (about 4.3 h) ended STUCK.
- Owner 2026-11-01: "Fix first, rerun fresh".
- Fix b9ff12cc:
  - For orders with delivered code, the SWE.2 freeze gate compiles the call contract against the delivered headers.
  - At SWE.3, the compile finding tells the author to report an ARCHITECTURE defect for the carried contract instead of
    editing it.
  - Greenfield orders are unchanged: they have no header before SWE.3.
- Reproducer RPR-089: the real SWE.2 author gate on a brownfield CRC IDR workspace built from the pinned ST/CMSIS
  sources (register facts only for CRC_IDR). Runs: rr-765f301bb2aa0f1da7bc:20ca687a:BASELINE:SYMPTOM_PRESENT rr-25eaab50b5ee8e36598a:b9ff12cc:CANDIDATE:SYMPTOM_ABSENT rr-06d0a991c6a8b848ee9e:20ca687a:BASELINE:SYMPTOM_PRESENT rr-8c07e39b287694d52d28:b9ff12cc:CANDIDATE:SYMPTOM_ABSENT rr-cb3f366a77427819f680:b9ff12cc:PREVENTION:SYMPTOM_ABSENT rr-eb23143e2a8af4ccb6ea:09f03cb3:PREVENTION:SYMPTOM_ABSENT rr-530a6fb660e52dee8dbd:815c52c8:PREVENTION:SYMPTOM_ABSENT rr-3ef4b7e749905e48d422:e1292cb3:PREVENTION:SYMPTOM_ABSENT rr-65a8a143d4b359d19620:fc6848bb:PREVENTION:SYMPTOM_ABSENT rr-d349002b33e7d6f09c33:103a938e:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-1134bf28d3e98d8879ee ELIGIBLE (FIX, 7/7); CAPA-089 in ../../cre/capa/capa-089.json.
