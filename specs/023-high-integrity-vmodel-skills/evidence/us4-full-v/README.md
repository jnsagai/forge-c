# T068: the later V-model stages, once each (US4)

## Attempt 1 (`attempt1/`): no stage accepted; distorted by a package defect

| Stage | Outcome | Open findings | Raised by the conductor itself | Blocking open points |
|---|---|---|---|---|
| sys-arch | BLOCKED | 90 | 84 | 5 |
| sw-arch | BLOCKED | 119 | 114 | 3 |
| sw-design | BLOCKED (build and static-analysis FAIL) | 20 | 15 | 4 |
| unit-verif, sw-integ, sw-qual, sys-integ, sys-qual | author harness failed (exit 1); the cause was not recorded | - | - | - |

- **Defect (Claude's, T089):** the coverage matrix ran in every stage. Outside the requirement stages every "covered" row
  became a gap, and the conductor raised bogus SQ-01 findings that went to the author as rework. The coverage matrix is
  now limited to the requirement stages. The earlier accepted runs were requirement stages only and had no such rows.
- **Defect:** build and static-analysis issues were never sent to the author (fixed in d9873f59).
- **Real findings on the accepted run 6 requirements:**
  - `T_DIAG` may run for 20 ms in a 10 ms control cycle whose program flow is checked at its end (CON-SUP-101/103/104);
  - a burst of four fault reports behind an answer line can take 12.9 ms against the 10 ms limit (CON-SUP-143).
  Both come from Claude's fictional decisions, and both passed the requirement inspections of run 6.

A first try at attempt 2 (software design onward) was stopped after a few minutes when the coverage defect was found.

## Attempt 2: no result

Attempt 2 is the stopped try named above. It has no evidence folder.

## Attempt 3 (`attempt3/`): not finished

Generic profile, HI-2. Author: Claude Sonnet. Inspector: GPT-6.1 Terra. One pass is one start of the conductor from
system requirements. A stage that nothing changed keeps its result; a stage that gets changed input or a returned point
gets new rework rounds. A stage accepted after many passes has therefore had many more rounds than one run allows.

### How far each pass got

The stage named is the last one in the pass's `summary.json`. A stage that returned a point upward drops out of that
list when the upstream stage then blocks, so passes 20, 24, 27 and 28 had worked further than shown; row 31 names the
returned integration result as well. Every pass up to 42 ended BLOCKED, except pass 35, which was stopped and has no summary.

| Passes | Last stage in the summary | What stopped it |
|---|---|---|
| 1-6, 9-12, 15, 17, 18, 21, 22, 27, 28 | system requirements | mostly gaps or conflicts in the fictional product decisions |
| 8, 13 | system architecture | deadline bound; counter arithmetic |
| 7, 14, 16, 20, 24, 26 | software architecture | hardware facts, timing, rework limits |
| 19, 23, 25 | software design | architecture conflict; missing drivers; usage limit (25) |
| 29, 30 | unit verification | 29: coverage 99.9/97.1 of 100. 30: tests and coverage PASS, two major findings on kept evidence |
| 31 | software integration, 24 of 25 PASS; then software design BLOCKED | ITC-SIM-002 FAIL, caused by the simulator's timer model |
| 32 | unit verification | the author account's usage limit (not a verdict) |
| 33 | software integration, 35 of 36 PASS (the corrected simulator cases PASS); unit verification ACCEPTED_WITH_GAPS; then software design BLOCKED | ITC-BUD-001: deadline check 511 us of 260, dispatch 25.6 us of 16 (upper bounds with instrumentation). The design stage changed the code but could not run it |
| 34 | software integration BLOCKED: 40 of 43 cases PASS, 3 NOT_RUN. SWE.1 to SWE.4 stages ACCEPTED | one test did not prove that its signal came during an activation; three analyses need a person |
| 35 | software integration ACCEPTED_WITH_GAPS (40 PASS, 3 NOT_RUN); software qualification written and first inspected | stopped by Claude: 46 of 52 cases were declared manual. The package now asks for a program or a reason, and the platform has a monitor for what an outside observer sees |
| 36 | software requirements BLOCKED (OP-SWR-036) | software qualification found that the alive window was never defined; answered by CON-SUP-201 |
| 37 | software architecture BLOCKED (OP-SWC-044); the three stages above ACCEPTED again after CON-SUP-201 | a hardware fact on interrupt re-entry was missing; CON-SUP-202 |
| 38 | software architecture | the author account's usage limit (not a verdict) |
| 39 | software requirements BLOCKED (OP-SWR-039) | CON-SUP-202, Claude's, left the hardware time of an exception entry outside the limits; CON-SUP-203 |
| 40 | system architecture BLOCKED (OP-SYE-011) | the report time had no defined origin (a gap since run 6); CON-SUP-204 |
| 41 | system architecture BLOCKED (OP-SYE-012) | CON-SUP-204, Claude's, gave no tolerance; CON-SUP-205 |
| 42 | software architecture BLOCKED (OP-SWC-051), after two returned points were settled inside the pass | the allowances of a timing chain exceeded its limit once the exception time of CON-SUP-203 was counted; answered with `hi answer` (allowances may be tightened, limits stay) |
| 43 | software architecture and detailed design ACCEPTED; unit verification returned one point (OP-UTC-501) to the design; stopped during the design rework by the author account's usage limit, not a verdict | the answer to OP-SWC-051 was accepted; the inspector found three blocking points in the retained-data unit (latch read for interrupts, latch written with the fault records, order of invalidating the two copies) |
| 44 | detailed design and unit verification ACCEPTED; software integration ACCEPTED_WITH_GAPS; software qualification returned one point (OP-QTC-005) to the design; stopped by the author account's usage limit, not a verdict | first pass with SWE.1 to SWE.5 all accepted on the same code; system integration and qualification not yet reached |
| 45 | software qualification returned test failures to the design three times (OP-QTC-005, -021, -023); each was settled and integration accepted again with gaps; the run then had no returns left, so the design ended BLOCKED with OP-SWU-041 returned to the architecture | a release that arrives while the execution deadline of the earlier release is armed replaced that deadline, so an overrun went unreported (QTC-TIM-004); the architecture must decide how one armed deadline serves both cases |
| 46 | the architecture took OP-SWU-041; its follow-on points went to the system architecture and software requirements, which accepted them; after three returns the architecture ended BLOCKED with OP-SWC-058 returned to software requirements | SWR-SCH-007 asked for more than its parent SYE-SUP-072 (an order for captures made before a return-path mark can take effect); the architecture asks software requirements to follow the parent |
| 47 | the architecture accepted OP-SWU-041 again; the design took OP-QTC-023 and returned OP-SWU-042 to the architecture; stopped at 04:31 during that rework because Claude Code killed the background pass when the host ran out of memory (another build used it), not a verdict | the partial state was committed as found and the pass was restarted as pass 48 once memory was free |
| 48 | the architecture took OP-SWU-042, then ended BLOCKED with OP-SWC-059: a fault record that cannot be saved has no stated reaction | product decision CON-SUP-206 (round 48): such an update is a code 7 fault, not retried; the unrecorded faults are exempt from the 1 ms and 2 ms limits |
| 49 | the left side accepted CON-SUP-206; the architecture ended BLOCKED with OP-SWC-061 | CON-SUP-206, Claude's, covered only the faults of the failed update and not those detected after it; CON-SUP-207 (round 49) |
| 50 | the system requirements accepted CON-SUP-207, then the system architecture returned OP-SYE-014 and the system requirements ended BLOCKED with OP-SYS-025 | CON-SUP-206 required the data of the last completed update after the reset, which a failed start-up write can make impossible; CON-SUP-208 (round 50) defers to the existing reset rule CON-SUP-164 |
| 51 | the system requirements accepted CON-SUP-208; the system architecture ended BLOCKED with OP-SYE-013 | CON-SUP-206 named a refused write or read of the retained memory, which no device fact lets the software detect or a test cause; CON-SUP-209 (round 51) keeps only detectable failures, states the test means and adds a fourth hardware assumption |
| 52 | system requirements to detailed design all ACCEPTED with CON-SUP-209 (OP-SWU-042 and OP-QTC-023 settled); stopped in unit verification by the author account's usage limit, not a verdict | the CON-SUP-206 to 209 chain is settled on the left side |
| 53 | unit verification updated its tests and returned one point (OP-UTC-402) to the design; both stopped by the author account's usage limit, not a verdict | - |

Before pass 39 the Lexar drive with the disk image was remounted (2026-11-26 08:19) and the image gave input/output
errors; it was attached again with the owner's approval, and `git fsck` of the run repository was clean.

System integration and system qualification had no result up to pass 42; software qualification had 7 executed cases.

### Limits a reader must know

- **The product is fictional.** Claude wrote the product decisions, so Claude answered the questions the stages raised.
  Several blocks came from Claude's own earlier decisions: CON-SUP-151 was unsafe and was replaced, and the inspector
  refused the deviation in CON-SUP-165.
- **Eleven decisions relaxed something:** CON-SUP-170, 171, 172, 177, 187, 191, 192, 198, 201, 204 with 205, and 206 with 207, 208 and 209 (196 and 197
  were withdrawn by 198).
- **CON-SUP-195 is a hardware assumption accepted without evidence.** The owner let the work continue with it; that is
  not a confirmation of the hardware.
- **CON-SUP-202 is a second hardware assumption accepted without evidence:** an enabled TIM2 flag that is still set when
  the handler returns enters the handler again. Vendor documents for other Cortex-M cores describe this for
  level-sensitive interrupts; the Cortex-M55 text was not found and no hardware was used.
- **CON-SUP-203 is a third hardware assumption accepted without evidence:** every exception entry and return takes at
  most 1 µs, and every time limit includes it. The simulator counts no such time.
- **CON-SUP-209 is a fourth hardware assumption accepted without evidence:** the retained memory never ends a write or
  a read in a processor fault. No device indication of a refused access is cited, so the supervisor detects only a CRC
  computation that cannot be carried out and a read-back that differs. Tests that cause these failures show the
  supervisor's reaction only.
- **CON-SUP-200 is an observation**, made by Claude on the simulator. It is not a product decision.
- **Coverage is measured on the test build** (`HI_TEST_BUILD`), not on the product build.
- **Simulation is not hardware.** Renode is not cycle accurate (50 MIPS assumed). Timing results say nothing about
  the real device.
- **Simulator defect (Claude's platform):** Renode's stock `STM32_Timer` drops the pending compare match of a channel
  when the interrupt-enable register is written. ITC-SIM-002 failed because of it. `HiTimer` replaces the model, and
  `sim/selftest/test_rearm.c` fails on the stock model. With product and tests unchanged, the four simulator cases
  passed in a scratch run, and in the package run of pass 33.
- **Unit results up to pass 33 come from the instrumented run:** the coverage gate ran after the unit-test gate and
  overwrote its results and logs, so the hash in the unit-test verdict did not match. Fixed after pass 33.
- **Three integration analyses are NOT_RUN** (ITC-BUD-004 to 006: single time allocations, worst-case interference,
  worst-case stack). They need a person and nobody performs them here; exception entry and exit time is not judged by
  any case. Claude answered the stage's question (`hi answer`) so that the run could go on; nothing was relaxed, and
  both stay gaps.
- **A changed input makes every stage be judged again,** and a fresh inspection then finds older gaps (pass 40 found
  one present since run 6). Each decision costs a pass over the left side.
- **The package changed between passes.** Defects found by one pass were fixed in the package before the next, so the
  passes do not measure one fixed version.
- No certification is claimed. READY would mean ready for human review.
