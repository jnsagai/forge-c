# 0014h — CRC IDR, SWE.1 with owner obligations (ASPICE_ONLY, Fabro)

Owner 2026-10-31: "I want a fabro run by now just for SWE.1"; "safety is on hold by now, go with just ASPICE QM";
profile choice `local-rtx-v2-omniverse2-q38-aspice-stepwise-medium` (Qwen3.8 medium, structured SWE.1 author and
inspector, purpose ASPICE_ONLY, safety assurance excluded).

- Same inputs, scope, operation scope, budgets and simulation-performance contract as
  `../0014g-st-crc-idr-qwen-delivery` (unchanged), referenced from there.
- No `delivery_first` block: the run starts at SWE.1 in the normal ASPICE order.
- `development_execution_policy: incremental-delivery-v1` (the 0014g QM demonstration policy is QM-only).
- Adds the owner obligations input (`role: owner_obligations`,
  `../../docs/designs/owner-obligations/crc-idr-owner-obligations.json`, DRAFT_FOR_OWNER_REVIEW, used as-is by owner
  choice 2026-10-31), declared before preparation so the scope binding includes it.
- Launched with `--purpose ASPICE_ONLY --stop-after SWE.1`: the run ends after the SWE.1 inspection gate and the
  finalizer reports SWE.2–SWE.6 as gaps (no READY package).
