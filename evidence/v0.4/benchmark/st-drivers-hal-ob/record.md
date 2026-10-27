# ST HAL onboarding acceptance record

Recorded 2026-10-27T15:55:37.692224Z. The JSON snapshot retains every attempt, all named gaps and raw token counters.

| Peripheral | Current package SHA-256 | Signed approval |
|---|---|---|
| GPIO | `e7eeec3c04d48ad30d4b6ef2d178bee17131299a7e4bff094d8caaab9edb9891` | OA-2026-10-27-05 (APPROVAL_OK) |
| SPI | `dd2e4792a5f04c9302aea1430c23be86c0778a140bf53fef95a8eb9e30078523` | OA-2026-10-27-02 (APPROVAL_OK) |
| USART | `ad9bfa76ac4a23e283aac36714781582faf038c401a6a9bf7b28d2e2be9801c9` | OA-2026-10-27-03 (APPROVAL_OK) |
| TIM | `cefb9802488388480dce855fd8048f58b09b727fde7a1f8860f38bddd98ba804` | OA-2026-10-27-04 (APPROVAL_OK) |

The initial GPIO package was superseded after omitted RM fields were found. Its failed attempt and original archive remain in this record; OA-2026-10-27-05 approves the corrected package. The first SPI attempt also remains visible with its factory probe defect. Terminal package status is not safety acceptance.
Phase ACP token counters are retained per model and role, including separate cache counters. Recovery budget tokens remain the native UNKNOWN; they are not reported as zero or estimated from budget ceilings.

# ST-driver benchmark record (st-hal-onboarding)

Recorded 2026-10-27T15:55:37.692224Z from evidence only (schema forge-c/st-hal-onboarding-acceptance/0.2). Nothing here is a READY or safety claim; BLOCKED outcomes are kept as recorded.

| work order | route | peripheral | revision | phases (final) | package | gaps | duration | author / inspector tokens (in+out) |
|---|---|---|---|---|---|---|---|---|
| WO-AFO-6a6875714405b8ce-a1 | AFO | onboarded:0010e-st-cube-gpio-hal-ob | 9fa4664 | 1:BLOC 2:INCO 3:INCO | BLOCKED | 52 | 13 min | 3373 / 0 |
| WO-AFO-cbde5111bd5eeaf6-a1 | AFO | onboarded:0011e-st-cube-spi-hal-ob | 557e920 | 1:PASS 2:PASS 3:BLOC | BLOCKED | 1495 | 36 min | 5961 / 3405 |
| WO-AFO-3043541c6afd38b1-a1 | AFO | onboarded:0010e-st-cube-gpio-hal-ob | 557e920 | 1:PASS 2:PASS 3:PASS 4:BLOC | BLOCKED | 709 | 38 min | 50333 / 5365 |
| WO-AFO-d5622d4914a0ac9d-a1 | AFO | onboarded:0011e-st-cube-spi-hal-ob | 9dd5b71 | 1:PASS 2:PASS 3:PASS 4:BLOC | BLOCKED | 310 | 38 min | 11588 / 8582 |
| WO-AFO-91b7e28a3bab37e5-a1 | AFO | onboarded:0012e-st-cube-usart-hal-ob | 9dd5b71 | 1:PASS 2:PASS 3:PASS 4:BLOC | BLOCKED | 711 | 27 min | 4287 / 5847 |
| WO-AFO-a06f0cfbf6e556cc-a1 | AFO | onboarded:0013e-st-cube-tim-hal-ob | 9dd5b71 | 1:PASS 2:PASS 3:PASS 4:BLOC | BLOCKED | 230 | 42 min | 11807 / 5106 |

## BENCH-GPIO-ST-HAL-OB

Order `afo-6a6875714405b8ce`: **BLOCKED**.

Terminal reason: `UNKNOWN_NOT_RECOVERABLE_BY_AFO`.

Cited cause review: 1 onboarding-fact causes identified among 52 named gaps. Initial GPIO failed at SWE.1 because derived RM facts were missing; subsequent artifacts and delivery injection were not completed.

Review limitation: This reviews causes of named gaps against the onboarding subject. It is not owner acceptance or independent adjudication of every generated CODE/requirement finding. Earlier unsuccessful attempts remain explicit.

- Attempt `afo-6a6875714405b8ce-a1`, Fabro `01M5YK3Z4XR0ANW069WPHZZQ0K`.
- Factory `9fa4664798183218184a6cf1a650ab1985087ea4`; approved package `1b940650471a28ac7980c741bb36d73a113640d752221be66ff83b694933cb2b` (OA-2026-10-27-01).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-6a6875714405b8ce-a1/forge-c-WO-AFO-6a6875714405b8ce-a1-review.zip`.
- Archive SHA-256 `ddea8b4c93b6d0dea365e4ce666e1c6e29655b4037ab23de9c1593761aa437f6`; 52 named gaps (full list in JSON and sealed archive).

Full attempt duration: 768.111237 s (2026-10-27T11:49:40.037136Z to 2026-10-27T12:02:28.148373Z).

## BENCH-SPI-ST-HAL-OB

Order `afo-cbde5111bd5eeaf6`: **BLOCKED**.

Terminal reason: `PLAN_REJECTED:FROZEN_CODE_SCOPE:software/include`.

Cited cause review: 0 onboarding-fact causes identified among 1495 named gaps. Initial SPI passed SWE.1/2 but blocked on the factory contract-probe include context (DEF-008). Named conformance/CODE findings and downstream missing artifacts remain. No package fact or delivered dependency needed changing for the include-context correction.

Review limitation: This reviews causes of named gaps against the onboarding subject. It is not owner acceptance or independent adjudication of every generated CODE/requirement finding. Earlier unsuccessful attempts remain explicit.

- Attempt `afo-cbde5111bd5eeaf6-a1`, Fabro `01M5YN8RVQVAK9SZM8G5FBE1RP`.
- Factory `557e920daa540a47461958c1e62842ac6bb709fd`; approved package `dd2e4792a5f04c9302aea1430c23be86c0778a140bf53fef95a8eb9e30078523` (OA-2026-10-27-02).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-cbde5111bd5eeaf6-a1/forge-c-WO-AFO-cbde5111bd5eeaf6-a1-review.zip`.
- Archive SHA-256 `49fb2d523a83c84e5e08c2fc00a5bfd5824da4e1d399618990bb92e641f77574`; 1495 named gaps (full list in JSON and sealed archive).

Full attempt duration: 2151.64835 s (2026-10-27T12:27:12.048351Z to 2026-10-27T13:03:03.696701Z).

Recovery `afo-plan-7d3e9a41c2b85f06`: PLANNER / REWORK_LOCAL / REJECTED. Token budget observation: UNKNOWN (ACP/Codex usage is not reported to the factory; never read as zero).

## BENCH-GPIO-ST-HAL-OB-R1

Order `afo-3043541c6afd38b1`: **BLOCKED**.

Terminal reason: `PLAN_REJECTED:FROZEN_DEFECTS_NEED_OWNER:DEF-006,DEF-007,DEF-008,DEF-009,DE`.

Cited cause review: 0 onboarding-fact causes identified among 709 named gaps. Corrected GPIO passed SWE.1/2/3 inspection, then blocked on runtime unit failures and unverified USPEC coverage. Gaps cover conformance/guideline/CODE findings, remaining verification and safety artifacts. No missing onboarding fact was identified; CODE diagnoses and requirement adequacy remain for owner adjudication.

Review limitation: This reviews causes of named gaps against the onboarding subject. It is not owner acceptance or independent adjudication of every generated CODE/requirement finding. Earlier unsuccessful attempts remain explicit.

- Attempt `afo-3043541c6afd38b1-a1`, Fabro `01M5YQSKZ5CQSEDWHQQE8X3A0J`.
- Factory `557e920daa540a47461958c1e62842ac6bb709fd`; approved package `e7eeec3c04d48ad30d4b6ef2d178bee17131299a7e4bff094d8caaab9edb9891` (OA-2026-10-27-05).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-3043541c6afd38b1-a1/forge-c-WO-AFO-3043541c6afd38b1-a1-review.zip`.
- Archive SHA-256 `9a08206c37163b72e7dcb03d44b6f128d035fdbdea6e91686baec2c4f632f36b`; 709 named gaps (full list in JSON and sealed archive).

Full attempt duration: 2304.444248 s (2026-10-27T13:11:24.291518Z to 2026-10-27T13:49:48.735766Z).

Recovery `afo-plan-4c7e1a9b3d52f08e`: PLANNER / REWORK_LOCAL / REJECTED. Token budget observation: UNKNOWN (ACP/Codex usage is not reported to the factory; never read as zero).

## BENCH-SPI-ST-HAL-OB-R1

Order `afo-d5622d4914a0ac9d`: **BLOCKED**.

Terminal reason: `PLAN_REJECTED:FROZEN_DEFECTS_NEED_OWNER:DEF-005,DEF-006`.

Cited cause review: 0 onboarding-fact causes identified among 310 named gaps. SPI R1 passed SWE.1/2/3 inspection, including the corrected contract-call compilation context. SWE.4 stopped on failed runtime unit checks and unverified USPEC coverage. Named gaps include conformance/guideline findings and escalated CODE reports, remaining verification and safety artifacts. No missing or wrong onboarding fact was identified in these blockers.

Review limitation: CODE reports compare delivered behavior with generated requirements. Owner review must adjudicate requirements, preconditions, diagnostic behavior and code findings; this is not safety acceptance or a blanket assertion that every generated CODE diagnosis is correct.

- Attempt `afo-d5622d4914a0ac9d-a1`, Fabro `01M5YTDC70DYH2CMJSMQ45CD2F`.
- Factory `9dd5b713dd5e8fc92b86b1055cb3d52295f578cc`; approved package `dd2e4792a5f04c9302aea1430c23be86c0778a140bf53fef95a8eb9e30078523` (OA-2026-10-27-02).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-d5622d4914a0ac9d-a1/forge-c-WO-AFO-d5622d4914a0ac9d-a1-review.zip`.
- Archive SHA-256 `858d0fc2a98880ec8c29a75c913b78c577ea500b6e2bbd20ba265639a3fe5458`; 310 named gaps (full list in JSON and sealed archive).

Full attempt duration: 2325.147116 s (2026-10-27T13:57:06.087350Z to 2026-10-27T14:35:51.234466Z).

Recovery `afo-plan-3f9a2c7d41e8b605`: PLANNER / REWORK_LOCAL / REJECTED. Token budget observation: UNKNOWN (ACP/Codex usage is not reported to the factory; never read as zero).

## BENCH-USART-ST-HAL-OB

Order `afo-91b7e28a3bab37e5`: **BLOCKED**.

Terminal reason: `PLAN_REJECTED:FROZEN_DEFECTS_NEED_OWNER:DEF-005,DEF-006,DEF-007,DEF-008`.

Cited cause review: 0 onboarding-fact causes identified among 711 named gaps. USART passed SWE.1/2/3 inspection with the signed 64 MHz test-clock assumption. SWE.4 stopped on runtime unit checks and unverified USPEC coverage. Named gaps include conformance/guideline findings and escalated CODE reports, unfinished verification and safety artifacts. No missing or wrong onboarding fact was identified in these blockers.

Review limitation: The generated requirements need owner adjudication: DEF-004/007 treat BRR=8 with OVER16 as valid from a representable-nonzero premise, and deadline tests require elapsed <= Timeout. These premises must be reviewed against RM constraints and the declared API/time-base contract before accepting the generated CODE diagnoses. This review is not safety acceptance.

- Attempt `afo-91b7e28a3bab37e5-a1`, Fabro `01M5YWP523TFRK5NR9SH74KTJ6`.
- Factory `9dd5b713dd5e8fc92b86b1055cb3d52295f578cc`; approved package `ad9bfa76ac4a23e283aac36714781582faf038c401a6a9bf7b28d2e2be9801c9` (OA-2026-10-27-03).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-91b7e28a3bab37e5-a1/forge-c-WO-AFO-91b7e28a3bab37e5-a1-review.zip`.
- Archive SHA-256 `c2a19403a1f7705d95c960601c670efdba3b0c122534e00203a6cb8638bee3e8`; 711 named gaps (full list in JSON and sealed archive).

Full attempt duration: 1616.646431 s (2026-10-27T14:36:52.172852Z to 2026-10-27T15:03:48.819283Z).

Recovery `afo-plan-7257a29f8732c06e`: PLANNER / RESTART_FROM_LAST_VALID_CHECKPOINT / REJECTED. Token budget observation: UNKNOWN (ACP/Codex usage is not reported to the factory; never read as zero).

## BENCH-TIM-ST-HAL-OB

Order `afo-a06f0cfbf6e556cc`: **BLOCKED**.

Terminal reason: `NO_MATERIALLY_DIFFERENT_STRATEGY`.

Cited cause review: 0 onboarding-fact causes identified among 230 named gaps. TIM passed SWE.1/2/3 inspection. SWE.4 stopped on failed runtime unit checks and two uncovered rejection USPECs. CODE reports concern NULL handles, invalid configuration/event values, and intermediate URS writes. The package also retains FACTORY DEF-008: COV_PARSE, truncated LLVM coverage data, with no coverage metrics. The remaining gaps include conformance findings, uncompleted verification and safety artifacts. No wrong or missing onboarding fact was identified in these blockers.

Review limitation: The owner must adjudicate the generated requirements, especially the demand to preserve URS on every intermediate CR1 write: the delivery temporarily sets URS while generating an update, then restores CR1. Do not infer a silicon defect from the final RAM tests or assume every generated CODE diagnosis is valid. Coverage failure remains unresolved factory work. SWE.4 inspection was not reached; no substitute inspector was used after the owner reported Claude quota exhaustion. This is not safety acceptance.

- Attempt `afo-a06f0cfbf6e556cc-a1`, Fabro `01M5YYKKM29X2MVTXV2EVEA1T8`.
- Factory `9dd5b713dd5e8fc92b86b1055cb3d52295f578cc`; approved package `cefb9802488388480dce855fd8048f58b09b727fde7a1f8860f38bddd98ba804` (OA-2026-10-27-04).
- Archive `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/archives/WO-AFO-a06f0cfbf6e556cc-a1/forge-c-WO-AFO-a06f0cfbf6e556cc-a1-review.zip`.
- Archive SHA-256 `ae6059eaac1475bab029d74918423b61a6cecb591053a13b64328d2e42c75749`; 230 named gaps (full list in JSON and sealed archive).

Full attempt duration: 2550.455304 s (2026-10-27T15:10:23.645933Z to 2026-10-27T15:52:54.101237Z).

## Review status

All packages are for offline review. Cited cause reviews are retained in the JSON snapshot; their coverage and bindings are checked separately from terminal outcomes. Owner dispositions remain pending. Held-out model authoring remains NOT_RUN while the approved Claude inspector is out of quota. No merge or safety approval is implied.
