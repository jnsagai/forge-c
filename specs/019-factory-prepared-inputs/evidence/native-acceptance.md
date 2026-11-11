# Feature 019 - native acceptance of the SWE.1 stage (T025)

Recorded 2026-11-10 from the Omniverse2 line queue and work-order records. Ladder: WWDG LL -> WWDG HAL (on L29) ->
SPI LL -> TIM LL, SWE.1 only (owner 2026-11-09).

| Step | Order | Created by the line | Result |
|---|---|---|---|
| WWDG LL SWE.1 | WO-F014-SWE1-WWDGL-20261109-L44F | 2026-11-09 11:49Z | PASS (`PHASE_VERDICT:PASS:SWE.1`) |
| WWDG HAL SWE.1 | WO-F014-SWE1-WWDGH-20261109-L45 | 2026-11-09 14:16Z | PASS; its manifest names the provided LL order WO-F014-SWE6-WWDGL-20261103-L29 (`--provided-from`) |
| SPI LL SWE.1 | WO-F014-SWE1-SPIL-20261107-L41N / L41O / L41P | 14:39Z, then retries | L41N, L41O BLOCKED (CAPA-206..212); L41P PASS 2026-11-10 06:14Z |
| TIM LL SWE.1 | WO-F014-SWE1-TIML-20261107-L43J | 2026-11-10 06:16Z (2 min after the SPI pass) | closed before admission by an owner-approved test window (`CLOSED_FOR_SOURCE_FIX:AUTODEPLOY`); the line re-creates it after the window |

Not yet shown: a TIM LL SWE.1 run (pending the window end); the deploy record field `campaign_source: DERIVED`
(not found in the deployer log; the generator dry run `generator-dry-run-swe1-stage.txt` shows DERIVED).
T025 stays open until the TIM LL order runs.
