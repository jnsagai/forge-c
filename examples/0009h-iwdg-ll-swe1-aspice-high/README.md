# 0009h - IWDG LL SWE.1, ASPICE_ONLY, high-allowance (second example of the Ornith/Qwen configuration)

Owner 2026-11-01 ("go with your recommendation"): the CRC IDR configuration (runs -10/-12) on a larger part.
Identical to `../0009a-iwdg-ll` (same inputs, scope, budgets, upstream record) except
`development_execution_policy: incremental-delivery-high-allowance-v2` (owner: production default). Launched with
`--purpose ASPICE_ONLY --stop-after SWE.1` and profile `local-rtx-v2-omniverse2-ornith-think-author-q38-inspector`.
No owner obligations are declared (assembly records NOT_DECLARED); generated obligations come later.

Owner 2026-11-01 ("yes, add the simulation_performance budget to IWDG"): `simulation_performance` added, the same
targets as the CRC and RCC LL orders (64 executed instructions and 100 us of virtual time per call at 100 MIPS,
Renode simulation only, not a hardware timing claim), so SWE1-04's CPU/timing constraint comes from an input.
