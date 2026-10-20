# Software Safety Analysis — STM32N6 IWDG LL and HAL drivers

| Field | Value |
|---|---|
| Document | SSA-IWDG-001, version 1.1 |
| Status | **DRAFT v1.1 for owner review — not approved** (v1.0 signed 2026-10-20 stays in force for 0009a/0009b until v1.1 is signed) |
| Safety scope | SC-IWDG-2026-10-20, target ASIL B (owner decision 2026-10-20, OD-2026-10-20-04) |
| Product | IWDG LL driver (example `0009a-iwdg-ll`) and IWDG HAL driver on that LL (example `0009b-iwdg-hal`) |
| Basis | Work order inputs, source requirements hash `bfee8b2ee260d6e114e2cf92b77336da4c8534e11efd53cf3c2a7995910b9286` |
| Analysed work products | LL `WO-0009A-STM32N6-IWDG-LL-i003` (SWE.1–SWE.6, factory commit 83ee4c7); HAL `WO-0009B-STM32N6-IWDG-HAL-h003` (SWE.1–SWE.6, factory commit 55e9532, package READY_FOR_OFFLINE_REVIEW, archive c0073b6b…); context from the HAL runs h001 and h002 (section 12) |
| Drafted by | Claude Opus 5.5 (Claude Code), v1.0 and v1.1 2026-10-20, from the factory records listed in sections 10 and 12 |
| Responsible engineer | Jefferson Nascimento (owner) |

> DRAFT v1.1 for owner review — not approved. Version 1.0 (signed, OD-2026-10-20-05, file
> `../software_safety_analysis.md`) is unchanged and remains the signed document for 0009a/0009b. This draft enters
> no work order until the owner signs it and its register entry is updated (OD-2026-10-20-06, pending). Signing
> would record the reviewer's engineering judgement; it is not a safety approval or certification.

## Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-20 | Signed (OD-2026-10-20-05): analysis of the IWDG LL (i003). The HAL example 0009b was added to the scope at signing without an analysis of its HAL code (open finding recorded in `config/factory/safety-scope.yaml`). |
| 1.1 (draft) | 2026-10-20 | Owner request "adress all" (2026-10-20): the HAL is analysed. New: HAL scope (section 1), ASR-09 to ASR-15 (section 3), FM-16 to FM-27 (section 5.2), DF-06 to DF-08 (section 6), AOU-09 to AOU-12 (section 7), SSA-IWDG-FND-07 to FND-12 and status updates of FND-01, -02, -05 and -06 (section 8), Q-08 to Q-12 (section 9), section 12 (HAL evidence). Sections 1–11 of v1.0 are otherwise unchanged. |

The basis hash is computed exactly as `workorder.prepare` does from the five inputs of `examples/0009a-iwdg-ll`
(DS14791 rev 9 datasheet, RM0486 rev 4 chapter 59, the IWDG memory-map excerpt, the conversion manifest and the HAL
driver guideline). It is identical to the hash of the inputs recorded in the i003 manifest, and (v1.1) to the hash
of the five inputs recorded in the h003 manifest (`examples/0009b-iwdg-hal` uses the same input files).

## 1. Purpose and scope

This document analyses how the IWDG LL driver can fail, what the effect of each failure is at the driver boundary,
which measures in the design and verification already address it, and what is still open. It applies to every IWDG
work order whose inputs match the basis hash above; a change to the inputs invalidates it until it is re-reviewed.

**In scope** (the 9 header-only `static inline` functions of i003, on the register block `ll_iwdg_regs`):

- `LL_IWDG_Enable` (key 0xCCCC), `LL_IWDG_ReloadCounter` (key 0xAAAA), `LL_IWDG_EnableWriteAccess` (key 0x5555),
  `LL_IWDG_DisableWriteAccess` (key 0x0000), all writing IWDG_KR;
- `LL_IWDG_SetPrescaler` (IWDG_PR.PR[3:0]) and `LL_IWDG_SetReloadCounter` (IWDG_RLR.RL[11:0]), masked
  read-modify-write;
- `LL_IWDG_IsActiveFlag_PVU`, `LL_IWDG_IsActiveFlag_RVU`, `LL_IWDG_IsActive` (IWDG_SR.PVU, RVU, ONF), read only.

**In scope (v1.1), the HAL of h003** (`software/hal/stm32n6xx_hal_iwdg.{h,c}`, built only on the PROVIDED i003 LL
header, SHA-256 5996e7e6…, which the HAL work order may not change):

- `HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout)`: rejects a NULL pointer, a prescaler above 7, a
  reload above 0xFFF and a timeout of 0 or above `HAL_IWDG_TIMEOUT_VALUE` (1000) with HAL_ERROR before any register
  access; otherwise follows RM0486 59.4 (window option disabled): start key, access key, prescaler, reload, then polls
  PVU and RVU for at most `timeout` iterations; when both are 0 it refreshes (0xAAAA) and returns HAL_OK, otherwise it
  returns HAL_TIMEOUT without a refresh and leaves the watchdog running (it cannot be stopped);
- `HAL_IWDG_Refresh(void)`: writes the refresh key unconditionally and returns HAL_OK.

**Out of scope** (work order scope, not implemented, so not analysed): the window option (IWDG_WINR), the
early wake-up interrupt (IWDG_EWCR, IWDG_ICR), the hardware watchdog option bytes, low-power freeze and debug
freeze, and the RCC/LSI clock configuration. (v1.0 also listed the HAL API as out of scope.)

## 2. Safety context — element developed out of context

No item definition, safety goal, technical safety requirement, HSI or software safety requirement has been provided
for the IWDG driver. `safety/software_safety_requirements.md` in i003 states that no software safety requirement is
allocated and `upstream/upstream-inputs.yaml` is not provided. The owner has set the product target ASIL B
(OD-2026-10-20-04); no system context exists from which to derive a fault tolerant time interval, the refresh
period or the safe state.

Unlike the RCC driver, the IWDG is itself a **safety mechanism**: its job is to reset the device when the software
stops running correctly. A driver fault therefore matters in two ways:

- **loss of the safety mechanism** (watchdog not started, wrong timeout, or refreshed by faulty software), which is a
  latent fault: nothing visible happens until the fault it should catch occurs;
- **spurious resets** (timeout too short), which affect availability.

This analysis treats the driver as a component developed without a known system context: it states the safety
requirements it **assumes** (section 3) and the conditions the integrating system must guarantee (section 7).

## 3. Assumed safety requirements

These are **assumptions made by the drafter** for the reviewer to accept, change or reject (Q-01). SWR ids are those
of i003 (regenerated by each work order).

| ID | Assumed safety requirement | Implemented today by |
|---|---|---|
| ASR-01 | The start function shall write exactly the start key 0xCCCC to IWDG_KR and nothing else. | SWR-001 |
| ASR-02 | The refresh function shall write exactly the refresh key 0xAAAA to IWDG_KR and nothing else. | SWR-002 |
| ASR-03 | The driver shall not write any IWDG register except on an explicit caller request (no writes at startup or on its own). | SWR-013 |
| ASR-04 | The configuration functions shall write only the addressed field, and a requested prescaler or reload value outside the field range shall not silently produce a different timeout. | SWR-005, SWR-006 for in-range values; **not met** for out-of-range values (finding SSA-IWDG-FND-01) |
| ASR-05 | Status queries shall not modify any IWDG register. | SWR-007 to SWR-012 |
| ASR-06 | Write access to IWDG_PR and IWDG_RLR shall be enabled only by the explicit enable function and removed by the disable function. | SWR-003, SWR-004 |
| ASR-07 | Every driver call shall return within a bounded number of CPU instructions. | No loops in any function (code inspection); no SWR states it explicitly |
| ASR-08 | The driver shall use no memory other than the IWDG register block and its own stack. | SWR-015 (0 B static RAM), SWR-016 (≤ 128 B stack; measured max frame 0 B) |

**HAL (v1.1).** SWR ids are those of h003.

| ID | Assumed safety requirement | Implemented today by |
|---|---|---|
| ASR-09 | The HAL initialisation shall reject every invalid parameter with HAL_ERROR before any IWDG access. | SWR-005 (NULL, prescaler > 7, reload > 0xFFF, timeout 0 or > 1000) |
| ASR-10 | The HAL initialisation shall perform the RM0486 sequence in order: start key, access key, prescaler, reload, wait for both update flags, refresh. | SWR-001 to SWR-003; key order verified by the unit tests on the LL test double (call order), not by the register contract |
| ASR-11 | The HAL shall report HAL_OK only when both update flags were observed cleared and the refresh was written. | SWR-001, SWR-006 |
| ASR-12 | Every HAL wait shall be bounded, and the bound shall be long enough for the hardware update to complete (RM0486 table 573: TDPVU/TDRVU up to 6 kernel-clock periods). | SWR-008 bounds the wait in **polling iterations** (≤ 1000); **not met** for the time part (finding SSA-IWDG-FND-07) |
| ASR-13 | After a failed initialisation the HAL shall leave the watchdog in a state that still detects a software hang, and shall not leave the configuration registers writable. | SWR-006/SWR-007: watchdog keeps running, no refresh; the registers stay writable (finding SSA-IWDG-FND-08) |
| ASR-14 | The HAL shall not accept a configuration that RM0486 advises against (reload below 2). | **Not met**: SWR-003 and the contract require HAL_OK for reload 0 and 1 (finding SSA-IWDG-FND-02, now also at the HAL API) |
| ASR-15 | The HAL refresh shall write exactly the refresh key and nothing else. | SWR-004 |

## 4. Method

1. **Fault-mode analysis per function and interface** (section 5), with the guide words *omission*, *commission*,
   *wrong value*, *too early / too late*, *stuck* and *corruption by another writer*.
2. **Dependent-failure analysis** (section 6).
3. **Evidence used**: the i003 work products and tool records (section 10). No hardware or HIL evidence exists; all
   target evidence comes from the factory's Renode IWDG behavioural model and is `silicon_verified: false`.

## 5. Fault-mode analysis

### 5.1 LL fault modes (v1.0)

| ID | Element | Fault mode | Cause | Effect at driver boundary | ASR | Measure / V | Open |
|---|---|---|---|---|---|---|---|
| FM-01 | `LL_IWDG_Enable` | Watchdog not running after the call | Wrong register addressed, key write lost, start key ignored in hardware watchdog mode (RM0486 59.7.1: 0xCCCC enables the watchdog "except if the hardware watchdog option is selected") | Latent loss of the safety mechanism | ASR-01 | SWR-001; unit and Renode tests check the key write and ONF | The driver does not check ONF after the start; the caller must (AOU-04). |
| FM-02 | `LL_IWDG_ReloadCounter` | Refresh by faulty software | A runaway loop or a wrong task calls the refresh function | A software hang is masked; the watchdog never fires | — (use) | None in the driver; the window option that would catch too-early refreshes is out of scope | AOU-02 and Q-03 (window option for ASIL B). |
| FM-03 | `LL_IWDG_ReloadCounter` | Refresh not taken | A refresh sent while the previous one is still being processed is ignored (RM0486 59.4, note after figure 775); refresh too late (the counter must be refreshed before it reaches 1) | Unwanted reset | ASR-02 (availability) | None in the driver | AOU-03 (refresh period with margin for TDRefresh). |
| FM-04 | `LL_IWDG_SetPrescaler`, `LL_IWDG_SetReloadCounter` | Wrong timeout from an out-of-range value | The value is masked to the field width without a report: reload 0x1000 becomes 0x000, prescaler 0x10 becomes 0x0 (/4) | Much shorter (reset loop) or different timeout; caller is not told | ASR-04 | Masking keeps reserved bits clear; V: unit tests with in-range values | **SSA-IWDG-FND-01**: reject or report out-of-range values (a range-checked wrapper or a HAL layer). |
| FM-05 | `LL_IWDG_SetReloadCounter` | Reload below 2 accepted | RM0486 59.7.3: "It is not recommended to set RL[11:0] to a value lower than 2"; the driver accepts 0 and 1 | Immediate or near-immediate reset | ASR-04 | None | **SSA-IWDG-FND-02**. |
| FM-06 | Configuration functions | New value silently not applied | Written while PVU/RVU is set (RM0486 59.7.2/59.7.3: the flag must be reset to change the value) | Old timeout stays in force; nothing reported | ASR-04 | Flag queries are provided; the driver does not wait (scope: "the caller bounds its polling") | AOU-04. The Renode model accepts the write even while the flag is set, so no test can detect this fault (**SSA-IWDG-FND-03**). |
| FM-07 | Write-access sequence | Protected write ignored | Any other key written to IWDG_KR between 0x5555 and the PR/RLR write re-protects the registers (RM0486 59.4.6), for example a refresh from an interrupt | New prescaler or reload silently not applied | ASR-04, ASR-06 | None in the driver | AOU-01 (serialise every IWDG_KR writer for the whole sequence) and AOU-04 (read back after PVU/RVU clear). |
| FM-08 | Write-access disable | Registers left writable | Caller omits `LL_IWDG_DisableWriteAccess` | A stray write can change the timeout | ASR-06 | Disable function; a refresh (0xAAAA) also re-protects (RM0486 59.4.6) | AOU-05. |
| FM-09 | Read-modify-write of PR/RLR | Stale read used | RM0486: the PR/RLR read value is valid only when PVU/RVU is reset | Only reserved bits (0) and the masked field are written, so the read value has no effect on the written field | ASR-04 | Masking | None identified; a plain write would remove the dependency (Q-04). |
| FM-10 | LL register definitions (offsets, masks, keys) | Wrong register, field or key | Error in the RM0486 conversion or in the generated header | Watchdog not started, wrong timeout, or other IWDG register changed | ASR-01–ASR-06 | `inspection.regmap` generates and checks the offsets and masks (multi-bit fields, feature 009) against the RM0486 section files; register contract with the `write` op checked by the independent oracle; Renode model; SWE.3 inspector | Common cause: all derive from the same converted RM0486 text (DF-02). |
| FM-11 | Register block placement `ll_iwdg_regs` | Driver accesses the wrong memory, or the block is initialised at startup | Linker places the array somewhere other than the IWDG base 0x56004800, or in a zero-initialised section | Writes corrupt RAM or another peripheral; startup zero writes reach IWDG registers | ASR-03, ASR-08 | Integration assumption; target images use the factory linker script | **SSA-IWDG-FND-04**: link-time check of the symbol address and section. AOU-06. |
| FM-12 | Status queries | Flag stuck | Hardware fault, or the clock domain not running | A caller polling PVU/RVU waits for ever | ASR-07 (caller) | The driver does not loop; Renode `never_ready` scenario verifies that the flag stays set and the caller's bounded poll gives up | AOU-04. |
| FM-13 | Timeout value (caller) | Timeout differs from intent | The timeout depends on the LSI frequency and its tolerance (DS14791), the prescaler and the reload | Late detection of a hang or spurious resets | — (use) | None in the driver | AOU-03; LSI accuracy NOT_VERIFIED from the supplied inputs (Q-05). |
| FM-14 | Low-power modes | Reset during Stop or Standby | The IWDG keeps running in Stop and Standby (RM0486 table 572); freeze options are out of scope | Unwanted reset on wake-up | — (use) | None | AOU-07. |
| FM-15 | All functions | Stack overflow or excessive time | Deeper call chain | Memory corruption, missed deadline | ASR-07, ASR-08 | Max frame 0 B, text 160 B (`-fstack-usage`, `size`, target build) | Object-level figures only (same limit as SSA-RCC FND-05). |

### 5.2 HAL fault modes (v1.1, h003)

| ID | Element | Fault mode | Cause | Effect at HAL boundary | ASR | Measure / V | Open |
|---|---|---|---|---|---|---|---|
| FM-16 | `HAL_IWDG_Init` parameter check | Invalid configuration accepted | Check missing or wrong bound | Wrong or immediate-reset timeout | ASR-09 | SWR-005; contract cases INIT_INVALID_* (no_write, HAL_ERROR) checked by the independent oracle; unit tests with no LL call | None for the listed values. |
| FM-17 | `HAL_IWDG_Init` parameter check | Valid-range value that RM0486 advises against accepted (reload 0 or 1) | SWR-003 range 0..0xFFF | Immediate or near-immediate reset after the start | ASR-14 | None; the contract requires HAL_OK for INIT_RELOAD_ZERO/ONE | **SSA-IWDG-FND-02** (open, now also at the HAL). |
| FM-18 | `HAL_IWDG_Init` key sequence | Keys or writes out of order (e.g. PR before 0x5555, refresh before the wait) | Coding error | PR/RLR write ignored (protected) or update not completed; old timeout stays | ASR-10 | Unit tests on the LL test double check the call order (`ll_fake_index_of`); Renode target test reads PR/RLR back on the IWDG model | The register contract sees only final values (by design); the Renode model accepts PR/RLR writes while an update is pending (FND-03). |
| FM-19 | `HAL_IWDG_Init` wait | Spurious HAL_TIMEOUT on silicon | The wait is bounded by ≤ 1000 **iterations**; the update takes up to 6 LSI periods (RM0486 table 573, about 190 µs at a nominal 32 kHz — LSI accuracy NOT_VERIFIED); at a high CPU clock 1000 iterations of two register reads may be shorter | Init reports HAL_TIMEOUT although the hardware is correct; no refresh; reset follows unless the caller recovers | ASR-12 | None: simulator and host tests have no time base | **SSA-IWDG-FND-07** (High). |
| FM-20 | `HAL_IWDG_Init` wait | Wait not bounded | Loop without counter | Software hangs until the watchdog resets | ASR-12 | SWR-008; contract `busy` cases (flag held set) checked by the oracle with an access bound; unit tests with the flag scripted set until timeout exhaustion (h002 DEF-003 corrected a test that passed after one poll) | None for boundedness. |
| FM-21 | `HAL_IWDG_Init` timeout path | Configuration registers left writable | No refresh (0xAAAA) on HAL_TIMEOUT, so the access key 0x5555 stays in force (RM0486 59.4.6) | A stray IWDG_PR/IWDG_RLR write by other software changes the timeout | ASR-13 | None | **SSA-IWDG-FND-08**: write 0x0000 (or another non-5555 key) before returning HAL_TIMEOUT, or document a caller obligation. |
| FM-22 | `HAL_IWDG_Init` timeout path | Unknown effective timeout after HAL_TIMEOUT | The watchdog was started with the previous PR/RLR (reset values or an earlier configuration) and the new values are still pending | The reset may come earlier or later than the caller expects | ASR-13 | SWR-006/SWR-007 state the fallback (watchdog running, no stop attempt); SWR-007 is reported REQ_NOT_TESTABLE / REQ_UNBOUNDED_TIME by the observe-only SWE.1 verifier | **SSA-IWDG-FND-09**: requirement and caller reaction (AOU-09). |
| FM-23 | `HAL_IWDG_Init` | Watchdog not running after HAL_OK | Hardware watchdog mode, start key ignored, or ONF not set | Latent loss of the safety mechanism | ASR-11 | Renode target test checks ONF on the model; the HAL does not read ONF | AOU-04 (caller checks ONF); Q-08 (should Init check ONF). |
| FM-24 | `HAL_IWDG_Refresh` | Refresh by faulty software | Called from a runaway loop or a periodic interrupt | A hang is masked | — (use) | None (unconditional refresh by design) | AOU-02; Q-03 (window option). |
| FM-25 | `HAL_IWDG_Refresh` / Init concurrency | Refresh from an interrupt during Init | 0xAAAA between 0x5555 and the PR/RLR writes re-protects the registers | New configuration silently not applied; Init may still report HAL_OK once the flags are clear | ASR-10, ASR-11 | None in the HAL (no lock) | AOU-01 extended to the HAL (AOU-10); Q-09 (read-back of PR/RLR after the wait). |
| FM-26 | HAL on the provided LL | HAL uses LL functions differently from their verified use | LL changed, or the HAL bypasses the LL | Unverified register access | ASR-10 | The provided LL is hash-pinned and read-only (implementation check `PROVIDED_COMPONENT_CHANGED`); unit tests run on the generated LL test double, which has no register array, so a HAL that bypasses the LL does not compile; HAL calls only LL functions (`LL_CALL_UNDEFINED` check) | None identified. |
| FM-27 | HAL resource use | Stack or time overrun | Deeper frame, longer loop | Memory corruption, missed deadline | ASR-07, ASR-08, ASR-12 | Max frame 8 B (`HAL_IWDG_Init`), text 140 B, static RAM 0 B (h003, target gcc); worst-case loop 1000 iterations | Object-level figures only; worst-case execution time NOT_VERIFIED (Q-10). |

## 6. Dependent-failure analysis

| ID | Shared resource or common cause | Analysis | Conclusion |
|---|---|---|---|
| DF-01 | IWDG_KR shared with other software (tasks, interrupts, boot code, other cores) | Any writer of 0xAAAA or 0x5555 interferes with the write-access sequence and with refresh supervision. | Freedom from interference cannot be claimed by the driver; it relies on AOU-01 and AOU-02. |
| DF-02 | Single source document | Requirements, register header, register contract, oracle and the Renode IWDG model all derive from the same converted RM0486 chapter 59. | Residual common cause. Mitigation: independent review against the original PDF, and tests on silicon (Q-06). |
| DF-03 | AI development and verification | Authors on Codex Sol 6.1, inspectors on Claude Opus 5.5. **In i003 the SWE.4 unit-test author (`swe4_test_author`) ran on DeepSeek**, because of factory defect CAPA-051 (fixed after i003; DeepSeek suspended by OD-2026-10-20-03). The EASA gate does not count AI inspection PASS as independent evidence. | Diversity reduces but does not remove common cause; the i003 unit tests are from a model outside the owner's model decision (SSA-IWDG-FND-05). Human review remains required. |
| DF-04 | Simulator instead of hardware | The Renode IWDG model has no down-counter, no LSI clock, no reset generation, no refresh-ignored behaviour and accepts PR/RLR writes while an update is pending. | The timeout and reset behaviour of the watchdog is **not verified at all**, not even in simulation (SSA-IWDG-FND-03, Q-06). |
| DF-05 | Supervised CPU | The driver runs on the CPU the watchdog supervises; independence comes only from the IWDG's own clock and counter. | Inherent; the refresh strategy (AOU-02) carries the independence argument. |
| DF-06 | HAL and LL from the same factory and the same source text (v1.1) | The HAL requirements, the provided LL, the register contract, the oracle, the LL test double and the Renode model all derive from the converted RM0486 chapter 59 and from factory code; the HAL was authored (Codex) and inspected (Claude) by the same model families as the LL. | Residual common cause, as DF-02/DF-03. The LL test double is generated from the provided LL header (no hand-written behaviour), which limits but does not remove it. |
| DF-07 | HAL unit tests on the LL test double (v1.1) | The double records calls and returns scripted flag values; it does not model the hardware (no update latency, no protection). A HAL fault that depends on hardware timing or protection is invisible to the unit tests. | Covered only by the Renode model (same limits, DF-04) and silicon tests (Q-06). |
| DF-08 | Shared IWDG_KR between HAL Init, HAL Refresh and other writers (v1.1) | Init and Refresh both write IWDG_KR; neither serialises. | As DF-01; AOU-10. |

## 7. Assumptions of use (to be met by the integrating system)

| ID | Assumption |
|---|---|
| AOU-01 | All writers of IWDG_KR are serialised, and the sequence 0x5555 → PR/RLR write → wait for PVU/RVU clear → 0xAAAA is not interrupted by another IWDG_KR write. |
| AOU-02 | The refresh is placed only at a program-flow checkpoint that proves the supervised software is running correctly (not in a timer interrupt or an idle loop), or another mechanism (window option, program-flow monitoring) catches refreshes by faulty software. |
| AOU-03 | The caller computes the timeout from the LSI frequency and its tolerance (DS14791), the prescaler and the reload, refreshes with margin before the counter reaches 1, and allows for TDRefresh. |
| AOU-04 | After starting the watchdog the caller checks ONF; after a configuration write it polls PVU/RVU with its own bound and verifies the value took effect; it reacts to a failure with its own safe state. |
| AOU-05 | Write access is disabled (or a refresh is issued) after every configuration sequence. |
| AOU-06 | `ll_iwdg_regs` is linked at the IWDG base 0x56004800 in a section that is not initialised at startup. |
| AOU-07 | The system handles the IWDG in low-power modes (refresh before Stop/Standby or the freeze options, which are out of this scope). |
| AOU-08 | The software/hardware watchdog mode (option bytes) of the product is known and consistent with the start sequence; the silicon revision is checked against the errata. |
| AOU-09 | (v1.1) On HAL_TIMEOUT from `HAL_IWDG_Init` the caller treats the watchdog configuration as unknown: it either reaches its safe state before the running watchdog resets the device, or retries the configuration within the remaining time; it does not assume the requested timeout is in force. |
| AOU-10 | (v1.1) No IWDG_KR writer (including `HAL_IWDG_Refresh` from an interrupt) runs while `HAL_IWDG_Init` is executing. |
| AOU-11 | (v1.1) The caller passes a `timeout` that covers at least 6 LSI periods at the worst-case LSI frequency and the fastest CPU/bus clock of the product, until SSA-IWDG-FND-07 is resolved. |
| AOU-12 | (v1.1) The caller passes a reload of at least 2 (RM0486 59.7.3), until SSA-IWDG-FND-02 is resolved. |

## 8. Findings and proposed measures

| ID | Finding | Proposed measure | Priority (reviewer to confirm) |
|---|---|---|---|
| SSA-IWDG-FND-01 | Out-of-range prescaler or reload values are masked silently (FM-04). | Range-checked API (return an error or assert) in a HAL layer or wrapper; add a requirement and tests. | High |
| SSA-IWDG-FND-02 | Reload values 0 and 1 are accepted against the RM0486 recommendation (FM-05). | Reject RL < 2 or document it as a caller obligation; add a requirement. | High |
| SSA-IWDG-FND-03 | The Renode IWDG model does not model the counter, the reset, refresh-ignored or write-ignored-while-pending (FM-06, DF-04). | Extend the model, and test timeout and reset on silicon. | High |
| SSA-IWDG-FND-04 | Nothing checks that `ll_iwdg_regs` is at the IWDG base and not zero-initialised (FM-11). | Link-time or map-file check in the SWE.5 target build. | Medium |
| SSA-IWDG-FND-05 | The i003 unit tests were written by DeepSeek (CAPA-051), outside the owner's model decisions. | Re-run the work order on a factory revision with CAPA-051 (Codex test author) before relying on SWE.4. | Medium |
| SSA-IWDG-FND-06 | i003 reports MC/DC as not measured; the EASA observe-only gate did not accept the SWE.4 oracle and mutation evidence and reports FAIL/UNKNOWN items at SWE.1, SWE.2 and SWE.5. Some of the observe-only helpers still assume RCC (feature 009 known limit), so the cause of each item is NOT_VERIFIED. | Make the observe-only helpers peripheral-generic, then re-assess the items. | Medium |

**Status of the v1.0 findings for the HAL (v1.1):**

- FND-01 (out-of-range values masked by the LL): **addressed for HAL callers** — `HAL_IWDG_Init` rejects prescaler > 7 and reload > 0xFFF with HAL_ERROR (SWR-005, oracle cases). Still open for software that calls the LL directly.
- FND-02 (reload 0 and 1): **still open**, and now required behaviour of the HAL (SWR-003; contract cases INIT_RELOAD_ZERO/ONE expect HAL_OK).
- FND-03 (Renode model limits): **still open**; it also limits the HAL target tests (h003: 11 checks on the model).
- FND-05 (i003 unit tests by DeepSeek): unchanged for the LL. **Not applicable to the HAL**: in h003 every agent node ran on Codex (14 author nodes) or Claude (7 nodes); no agent node ran on DeepSeek (CAPA-051).
- FND-06: for the HAL (h003, factory with the peripheral-generic assurance helpers of feature 009 phase 8): MC/DC 100 % on the host; the SWE.4 independent oracle (24 contract cases, including 4 `busy` timeout cases) and mutation evidence are PASS. Remaining observe-only items: SWE.1 SOURCE_CONTRADICTION_CHECK (REQ_SOURCE_MISMATCH on SWR-001/SWR-006: a known verifier defect when a requirement cites several pages, which affects RCC too — not a HAL fault) and TESTABILITY_CHECK (REQ_NOT_TESTABLE / REQ_UNBOUNDED_TIME on SWR-007, see FND-09); SWE.2 FLOW_SCHEDULING_ANALYSIS UNKNOWN; SWE.4 NEGATIVE_BOUNDARY_CASES UNKNOWN (generic boundary generation exists for the RCC HAL timeout contract only); every phase AI_PASS_NOT_EVIDENCE (by design).

**New findings (v1.1, HAL):**

| ID | Finding | Proposed measure | Priority (reviewer to confirm) |
|---|---|---|---|
| SSA-IWDG-FND-07 | The HAL wait is bounded in polling iterations (≤ 1000), not in time; the update takes up to 6 LSI periods. On silicon at a high CPU clock `HAL_IWDG_Init` may report HAL_TIMEOUT for a correct update (FM-19). | Express the bound in time (LSI periods or a time base), or derive the iteration bound from the worst-case CPU clock; measure on silicon. Until then AOU-11. | High |
| SSA-IWDG-FND-08 | On HAL_TIMEOUT the access key stays in force: IWDG_PR/IWDG_RLR remain writable (FM-21). | Write a non-0x5555 key (e.g. 0x0000) before returning HAL_TIMEOUT; add a requirement and a test. | High |
| SSA-IWDG-FND-09 | The fallback after HAL_TIMEOUT is stated (SWR-007) but not testable as written and leaves the effective timeout unknown (FM-22). | Reformulate SWR-007 with an observable criterion; caller reaction AOU-09. | Medium |
| SSA-IWDG-FND-10 | `HAL_IWDG_Init` does not confirm ONF and does not read back PR/RLR after the wait (FM-23, FM-25). | Decide whether Init should verify (Q-08, Q-09). | Medium |
| SSA-IWDG-FND-11 | No serialisation between `HAL_IWDG_Init` and `HAL_IWDG_Refresh` (FM-25, DF-08). | Caller obligation AOU-10, or a guard in the HAL. | Medium |
| SSA-IWDG-FND-12 | The HAL unit tests run on a generated LL test double without hardware behaviour; HAL faults that depend on timing or protection are seen only by the Renode model (DF-07). | Extend the Renode model (FND-03) and test on silicon. | Medium |

## 9. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept ASR-01 to ASR-08 as the assumed safety requirements, or should they be changed? |
| Q-02 | Should the findings be fixed before signing, or accepted as open items listed in the package limitations? |
| Q-03 | For ASIL B, should the window option be added to the scope to catch refreshes by faulty software (FM-02)? |
| Q-04 | Should PR/RLR be written with a plain write instead of read-modify-write (FM-09)? |
| Q-05 | Which LSI accuracy and which timeout/refresh period apply to the product (FM-13)? |
| Q-06 | When will the register header be reviewed against the original RM0486 PDF, and when will the timeout and reset be tested on silicon (DF-02, DF-04)? |
| Q-07 | Is the product used in software or hardware watchdog mode (AOU-08)? |
| Q-08 | (v1.1) Should `HAL_IWDG_Init` check ONF after the start key and report a failure (FM-23)? |
| Q-09 | (v1.1) Should `HAL_IWDG_Init` read back IWDG_PR and IWDG_RLR after the update flags clear (FM-25)? |
| Q-10 | (v1.1) What is the worst-case CPU/bus clock and the required worst-case execution time of `HAL_IWDG_Init` (FM-19, FM-27)? |
| Q-11 | (v1.1) Do you accept one analysis for the LL and the HAL on it, with the LL findings carried over? |
| Q-12 | (v1.1) Should FND-07 and FND-08 be fixed (a new HAL work order) before v1.1 is signed, or accepted as open findings? |

## 10. Sources

- Work order scope: `examples/0009a-iwdg-ll/workorder.json`; profile `config/factory/peripherals/iwdg.yaml`.
- Inputs: `examples/0009-iwdg-st/inputs/` (RM0486 rev 4 chapter 59, pp. 2979–2994, memory-map excerpt, manifest).
- Safety scope: `config/factory/safety-scope.yaml` (SC-IWDG-2026-10-20).
- i003 evidence: `evidence/v0.4/runs/PG-T012/latest.json` and `i003/` (gate log, package, generated LL header,
  software requirements); the i003 workspace's `evidence/tool-results.jsonl`, `.forge-run/model-profile.json`,
  `.forge-run/assurance/gate-log.jsonl` and `safety/software_safety_requirements.md`.
- Renode model: `factory/sim/stm32n6/iwdg_model.py`, `factory/sim/stm32n6/stm32n6_iwdg.repl`.
- CAPA-051: `evidence/cre/capa/i003-capas.json`; OD-2026-10-20-03 (DeepSeek suspended).
- (v1.1) HAL: `examples/0009b-iwdg-hal/workorder.json`; `evidence/v0.4/runs/PG-T019/` (h001, h002, h003: gate logs,
  packages, HAL code, requirements, defects); the h003 workspace's `workproducts/SWE.1/register_effects.json`,
  `software/hal/`, `software/tests/`, `evidence/tool-results.jsonl`, `.forge-run/model-profile.json`,
  `.forge-run/manifest.json` and `.forge-run/assurance/gate-log.jsonl` (read 2026-10-20); RM0486 table 573 (p.2980)
  and 59.4.6 (pp. 2985–2986) in the converted chapter 59.

## 11. Review and signature (v1.0, as signed)

| Field | Value |
|---|---|
| Reviewed by (name, role) | Jefferson Nascimento, owner and responsible engineer |
| Reviewer's statement | "I approve all" (2026-10-20), in reply to "Sign the drafts in PR #16 when you're satisfied with them" |
| Answers to Q-01 to Q-07 | Q-01: ASR-01 to ASR-08 accepted as drafted. Q-02: the findings are not fixed before signing; they stay open and are listed with the package. Q-03 to Q-07: not answered at signing; they remain open. |
| Changes made during review | None to the analysis; status, version and this section completed on signing |
| Decision | ☐ Approved ☒ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | 2026-10-20 |

Signing records the reviewer's engineering judgement on this analysis for the stated basis. It is not a safety
approval of an item, a release decision or a certification.

## 12. HAL evidence summary (v1.1)

| Run | Factory commit | Result | Factory defects found |
|---|---|---|---|
| h001 (`WO-0009B-STM32N6-IWDG-HAL-h001`) | 856c3fb | SWE.1, SWE.2 PASS; BLOCKED at SWE.3 | CAPA-053 (HAL allocation read with the RCC prefix), CAPA-052 (Fabro run-title generation reached the suspended DeepSeek once, 06:53:12Z, failed, no tokens) |
| h002 (`…-h002`) | 029fd6e | SWE.1–SWE.6 PASS; package BLOCKED on DEF-001 | CAPA-054 (author skill named a packager-generated file) |
| h003 (`…-h003`) | 55e9532 | SWE.1–SWE.6 PASS; READY_FOR_OFFLINE_REVIEW, 0 gaps | none |

h003 measurements: unit tests PASS on the LL test double; host coverage line, branch and MC/DC 100 %; integration
PASS (host, real LL on a RAM register array); Renode 11 checks, 0 failed (behavioural IWDG model); Robot 12/12 tests,
12/12 requirements verified; cppcheck 0 findings (MISRA subset, no compliance claimed); clang analyzer 0
diagnostics; text 140 B, data 0, bss 0, max frame 8 B; 2 test defects declared and corrected by the authors (check
id, unit-spec annotations). All target evidence is simulation (`silicon_verified: false`).

## 13. Review and signature (v1.1)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-12 | (v1.0 answers: Q-01 accepted; Q-02 findings open; Q-03 to Q-07 open) |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on this analysis for the stated basis. It is not a safety
approval of an item, a release decision or a certification.
