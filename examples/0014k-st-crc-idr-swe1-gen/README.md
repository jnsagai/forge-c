# 0014k - CRC IDR subset of ST's real stm32n6xx_ll_crc.h (CubeN6 v1.4.0, BSD-3), FROZEN, SWE.1, zero human input. As ../0014f-st-cube-crc-idr-qm without provided_requirements (human-reviewed), plus generate_obligations: true; operation_scope keeps the two IDR functions (selector only). Owner 2026-11-01.

Zero human input (2026-11-01 correction): `operation_scope` keeps only the selectors (the two functions, the IDR field and
RM section 26.4.2). The per-part `prompt_overrides` and the written caller-precondition `dependencies` inherited from
0014f are removed; the CRC peripheral profile's own prompts apply.
