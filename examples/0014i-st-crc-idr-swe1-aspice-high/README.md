# 0014i - CRC IDR SWE.1 with owner obligations, high-allowance repair policy

Identical to `../0014h-st-crc-idr-swe1-aspice` (same inputs, scope, owner-approved obligations, ASPICE_ONLY,
`--stop-after SWE.1`) except `development_execution_policy: incremental-delivery-high-allowance-v2` (2 phase repair
passes, up to 9 calls per task). Owner 2026-10-31 (approval 4): if a run blocks only through model variance under the
one-repair policy, run one comparison arm with the high-allowance policy. Run -05 blocked one EARS fix short.
