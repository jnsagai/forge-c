# Safety Supervisor: product-owner decisions

**Fictional demo product.** These are the answers a product owner gave after the first run stopped BLOCKED on open
points (the stakeholder needs alone leave these values undecided, and the package refuses to guess them). They are
demo inputs, not recommendations for a real product. Requirements may cite them like constraints.

| ID | Decision |
|---|---|
| CON-SUP-101 | Supervised tasks: three 10 ms tasks, T_IN, T_CTRL and T_OUT, released in that order every 10 ms, and one 100 ms task, T_DIAG, released after T_OUT in every tenth 10 ms period. The 10 ms period is the control cycle. |
| CON-SUP-102 | Alive supervision starts when the start-up integrity checks have passed. A supervised task that has not completed an execution for 2 consecutive periods of its own has stopped. |
| CON-SUP-103 | Timing limits per task are configuration values. Defaults: a task starts at most 2 ms after its release; a 10 ms task executes for at most 3 ms and T_DIAG for at most 20 ms. Times are measured with a 100 µs resolution. A start later than the limit is a late start; an execution longer than the limit is an overrun, detected when the limit expires. |
| CON-SUP-104 | Program flow is checked once per control cycle at its end: the checkpoints of the tasks released in that cycle must arrive in the configured order; a missing or out-of-order checkpoint is a flow fault. |
| CON-SUP-105 | The 50 ms reaction time of STK-SUP-009 counts from the instant the fault becomes detectable by its rule (end of the alive window, expiry of a timing limit, end of the control cycle for flow, completion of the failing integrity computation) to both control outputs being off and the status signal showing "not operational". |
| CON-SUP-106 | Independent watchdog timeout: 100 ms. Window watchdog: one refresh per control cycle at its end; a refresh earlier than 6 ms or later than 12 ms after the previous refresh causes a reset. Register values are derived in the design from the reference manual. |
| CON-SUP-107 | Program code is the application image in flash between the linker symbols `__app_start` and `__app_end` (at most 1 MiB). Configuration data is one block with its own stored CRC-32 (polynomial 0x04C11DB7). Both are checked at start-up before any task is released. |
| CON-SUP-108 | The run-time code check processes one 1 KiB segment per control cycle and must complete a full pass of a 1 MiB image within 11 s. It uses at most 0.5 ms of processor time per control cycle. |
| CON-SUP-109 | Control outputs: two digital outputs; "off" means driven low. Status signal: one digital output, high = operational, low = not operational. From any reset until the start-up checks pass, both control outputs and the status signal are low. |
| CON-SUP-110 | After entering the safe state the supervisor transmits the fault report and then requests a software reset within 20 ms. A fault is "the same" when its fault code is the same. Three consecutive supervisor resets with the same fault code, without 60 s of fault-free operation in between, latch the safe state until a power-on reset. The latch and the fault history are kept in memory that survives software and watchdog resets but not power loss. |
| CON-SUP-111 | Reset causes are classified at start-up from the reset flags as: power-on, independent watchdog, window watchdog, supervisor (software) reset, or other. The cause is sent in a start-up message and is readable by the service tool. |
| CON-SUP-112 | Fault report line: `FLT,<code>,<entity>,<ms since start>` terminated by a line feed, sent within 10 ms of detection. Codes: 1 alive, 2 late start, 3 overrun, 4 flow, 5 code integrity at start-up, 6 configuration integrity, 7 code integrity at run time, 8 watchdog reset, 9 configuration out of range. Entity: the task name or `CODE` / `CONFIG`. |
| CON-SUP-113 | Service requests on the diagnostic line: `GET STATUS` returns `STS,<state>,<fault count>` and `GET FAULTS` returns the last 8 fault reports, each answered within 50 ms. Any other request is answered `ERR`. |
| CON-SUP-114 | Processor time (STK-SUP-014) is the supervisor's execution time over any 1 s window in normal operation (no fault, no service request), measured on the simulator at the configured core clock. |
| CON-SUP-115 | A configuration value outside its allowed range (a timing limit longer than the task period, a zero period, an unknown task) is a configuration fault (code 9) at start-up and latches the safe state. |
| CON-SUP-116 | Each fault class can be injected through test hooks that exist only in test builds; integration and system tests run on the Renode simulator. |

**Second round.** Answers to the four blocking open points of run 4 (same fictional demo product owner).

| ID | Decision |
|---|---|
| CON-SUP-117 | The safe state latches at the **third detection** of the same fault code without 60 s of fault-free operation since the first: the first and second detections each lead to the safe state, the fault report and a supervisor reset; the third leads to the safe state and the fault report and requests no reset. The latch holds until a power-on reset. This is how "three consecutive supervisor resets" in CON-SUP-110 is to be read. |
| CON-SUP-118 | The service request `GET RESET` returns `RST,<cause>` with `<cause>` one of `POR`, `IWDG`, `WWDG`, `SW`, `OTHER` (the classes of CON-SUP-111), answered within 50 ms. It is added to the requests of CON-SUP-113. |
| CON-SUP-119 | Fault report entity for code 8 (watchdog reset): `IWDG` or `WWDG`, the watchdog whose reset flag was set. For code 9 (configuration out of range): `CONFIG`. |
| CON-SUP-120 | The fault report and the safe-state entry are independent: the report is transmitted within 10 ms of detection (CON-SUP-112) and the safe state is entered within 50 ms of the detectable instant (CON-SUP-105), in either order. The supervisor reset of CON-SUP-110 is requested within 20 ms after the later of the two has completed. This replaces "after entering the safe state the supervisor transmits the fault report" in CON-SUP-110. |

**Third round.** Answers to the two blocking open points left after the second round.

| ID | Decision |
|---|---|
| CON-SUP-121 | Watchdog servicing stops at fault detection (STK-SUP-005 applies without exception). If a watchdog reset comes before the fault report and safe-state entry have completed, the reset itself puts the outputs in the reset state of CON-SUP-109 (safe), and the fault is reported at the next start-up as code 8 with the watchdog's name as entity (CON-SUP-119). No report is required for the fault that was being handled. |
| CON-SUP-122 | Entity for fault code 4 (program flow): the first task, in the configured release order, whose checkpoint is missing or out of order in that control cycle. One report per control cycle. |

**Fourth round.** Clarifies CON-SUP-122 (open point after the third round).

| ID | Decision |
|---|---|
| CON-SUP-123 | To find the entity of a flow fault (CON-SUP-122), the checkpoints received in the control cycle are compared with the configured release order position by position. The entity is the task expected at the first position where the received checkpoint differs or is missing. Example: expected T_IN, T_CTRL; received T_CTRL, T_IN: the entity is T_IN. |

**Fifth round.** The inspector judged five deferred open points to be needed at system level; the product owner
decides them.

| ID | Decision |
|---|---|
| CON-SUP-124 | Program code integrity uses the same CRC-32 as the configuration block (CON-SUP-107). The reference value is stored in the 4 bytes at linker symbol `__app_crc`, outside the checked range `__app_start`..`__app_end`. |
| CON-SUP-125 | `<state>` in `STS,<state>,<fault count>` is one of `STARTUP`, `OPERATIONAL`, `SAFE`, `LATCHED`. `<fault count>` is the number of fault reports since the last power-on reset; like the fault history it survives software and watchdog resets (CON-SUP-110). |
| CON-SUP-126 | `<ms since start>` counts milliseconds since the latest reset of any kind, as an unsigned 32-bit decimal number that wraps to 0 after 4294967295 ms. |
| CON-SUP-127 | A measured start delay or execution time equal to its limit is within the limit. Because times are measured with 100 µs resolution, a violation may be detected up to 100 µs after the limit expires; verification uses margins of at least 200 µs on either side of a limit. |
| CON-SUP-128 | A supervised task that has not started when its start limit expires has a late start (code 2), detected when the start limit expires. |

**Sixth round.** Completes CON-SUP-124 and CON-SUP-125.

| ID | Decision |
|---|---|
| CON-SUP-129 | The CRC-32 of CON-SUP-107 and CON-SUP-124 is CRC-32/MPEG-2: polynomial 0x04C11DB7, initial value 0xFFFFFFFF, no input or output reflection, no final XOR, computed over the bytes in increasing address order. Each stored reference is a 32-bit little-endian word. |
| CON-SUP-130 | Status states: `STARTUP` from any reset until the start-up checks pass; `OPERATIONAL` while supervising with no fault; `SAFE` from the instant a fault is detected (during start-up or operation) until the next reset; `LATCHED` while the latch of CON-SUP-117 is set (it overrides the others). A code 8 report at start-up is a report only: it counts as a detection of code 8 for CON-SUP-117 but does not by itself enter the safe state, and start-up continues. |

**Seventh round.** Software-level questions raised while deriving the software requirements.

| ID | Decision |
|---|---|
| CON-SUP-131 | `<ms since start>` in a fault report is the time of **detection** of the fault (the instant its rule fires, CON-SUP-105), not of transmission. |
| CON-SUP-132 | From any reset until software configures them, the two control outputs and the status signal are held low by external pull-down resistors on the board; the microcontroller pins are inputs in that interval. Software configures them as outputs driven low before any other start-up step. |
| CON-SUP-133 | Of the 50 ms reaction time (CON-SUP-105), the output stage on the board takes at most 1 ms from the pin change to the output level; software must have changed the pins within 49 ms of the detectable instant. |
| CON-SUP-134 | `GET FAULTS` returns the fault reports held, oldest first, at most 8, one per line, followed by a line `END`; with none held it returns only `END`. |
| CON-SUP-135 | The 60 s of fault-free operation in CON-SUP-110 and CON-SUP-117 count only time in the `OPERATIONAL` state; time in reset, start-up or the safe state does not count. |

**Eighth round.**

| ID | Decision |
|---|---|
| CON-SUP-136 | The fault-free operating time of CON-SUP-135 may **under-count** by at most 10 ms per reset (time since its last update may be lost at an unannounced reset) and by at most 100 µs per update from measurement resolution; it must never over-count. An under-count only makes the latch of CON-SUP-117 more conservative and is accepted. |

**Ninth round.** Raised by the clean run 5.

| ID | Decision |
|---|---|
| CON-SUP-137 | A code 8 report at start-up (CON-SUP-130) records a reset that already happened; it is **not** a fault detection in the sense of CON-SUP-121. Watchdog servicing during start-up continues as for any start-up, and the report counts only toward the latch rule of CON-SUP-117. |
| CON-SUP-138 | A service request is a line of at most 32 ASCII characters ended by a line feed. It counts as received when its line feed is received. The 50 ms answer time of CON-SUP-113 runs from that instant to the end of the answer's last character on the line. A line longer than 32 characters is answered `ERR`. |

**Tenth round.**

| ID | Decision |
|---|---|
| CON-SUP-139 | The service tool sends a request only after it has received the complete answer to its previous one. A request received while an answer is still being transmitted is ignored (no answer). Fault reports have priority over answers: the 50 ms answer time of CON-SUP-138 is extended by the transmission time of the fault reports sent between the request and its answer. |
| CON-SUP-140 | Each fault code keeps its own count for the latch of CON-SUP-117: a detection of a different code neither resets nor advances it (codes 1, 2, 1, 1 latch at the third detection of code 1). A count returns to zero only after 60 s of fault-free operation (CON-SUP-135). This replaces "consecutive" in CON-SUP-110. |

**Eleventh round.**

| ID | Decision |
|---|---|
| CON-SUP-141 | The `<ms since start>` of a code 8 report is the time, since the latest reset, at which start-up classified the reset cause (CON-SUP-111). |

**Twelfth round.** Raised by run 6, the first run with the governance step.

| ID | Decision |
|---|---|
| CON-SUP-142 | The configuration data block lies between the linker symbols `__cfg_start` and `__cfg_end`. Its stored CRC-32 reference is the 4 bytes at linker symbol `__cfg_crc`, outside the checked range `__cfg_start`..`__cfg_end`: the same treatment as for program code (CON-SUP-124). |
| CON-SUP-143 | A fault report raised while an answer is being transmitted waits only for the end of the answer line in transmission (its line feed); it is sent before any further line of that answer. Answer lines are at most 40 characters including the line feed (at most 3.5 ms at 115200 baud), so the 10 ms of CON-SUP-112 still holds. A fault report never interrupts a line in the middle. |
| CON-SUP-144 | The code 8 report at start-up (CON-SUP-130) is transmitted within 10 ms of the instant start-up classified the reset cause (CON-SUP-141). |

**Thirteenth round.** Raised by run 6 pass 2.

| ID | Decision |
|---|---|
| CON-SUP-145 | The start-up message of CON-SUP-111 is the line `RST,<cause>` (the form and causes of CON-SUP-118) terminated by a line feed. It is transmitted within 10 ms of the instant start-up classified the reset cause, and before the code 8 report of CON-SUP-144 when there is one. |

**Fourteenth round.** Raised by run 6 pass 3.

| ID | Decision |
|---|---|
| CON-SUP-146 | The end symbols `__app_end` and `__cfg_end` are the address **after** the last byte: the checked ranges are `__app_start` up to and excluding `__app_end`, and `__cfg_start` up to and excluding `__cfg_end`. |

**Fifteenth round.** Raised by run 6 pass 4.

| ID | Decision |
|---|---|
| CON-SUP-147 | Behaviour at exact equality with a timing limit (CON-SUP-127: equal is within the limit) is verified by **analysis** of the measurement and the comparison (100 µs resolution, a fault only when the measured value is greater than the limit). Tests keep the margins of CON-SUP-127. A requirement that states the equality rule therefore names analysis as its verification method. |

**Sixteenth round.** Raised by the architecture stages of the full-V run. CON-SUP-149 and CON-SUP-150 correct two
contradictions between earlier decisions.

| ID | Decision |
|---|---|
| CON-SUP-149 | **Replaces the part of CON-SUP-104 that concerns T_DIAG.** The end-of-cycle program flow check covers T_IN, T_CTRL and T_OUT only. T_DIAG is preemptible by the 10 ms tasks, may span control cycles, and is supervised by the alive, late-start and overrun rules. Its execution limit is elapsed time from its start, preemption included. The end-of-cycle watchdog servicing does not wait for T_DIAG to finish. |
| CON-SUP-150 | **Replaces the 10 ms claim of CON-SUP-143 for several reports, and limits CON-SUP-112 and CON-SUP-120 accordingly.** The 10 ms apply to a fault report that has no other fault report pending. Reports detected while others are pending are sent in detection order, each within 10 ms after the previous one completes. Up to 16 reports can be pending; a further one is dropped and still counted in the fault count. A fault history entry is kept for every report, dropped or not. |
| CON-SUP-151 | The safe-state latch, the detection counts, the fault count and the fault history are kept in a RAM region that start-up code does not initialise, protected by its own CRC-32 (CON-SUP-129). At start-up after a power-on reset, or when that CRC is wrong, the region is set to its power-on values. The design confirms from the reference manual, by section and page, that the chosen region keeps its content across software and watchdog resets. |
| CON-SUP-152 | The configured core clock is 200 MHz. |
| CON-SUP-153 | The board's electrical design is outside this product: supply range, power-on reset timing, pin and output-stage voltage levels, drive capability and pull-down values belong to the board project and its review. This product specifies and verifies these interfaces at logical level (low, high) and in time only. |
| CON-SUP-154 | On a framing, noise or overrun error on the diagnostic line, the characters received since the last line feed are discarded up to and including the next line feed, without an answer and without a fault report. |
| CON-SUP-155 | The window watchdog is enabled at the end of the first control cycle after the start-up integrity checks have passed, and refreshed once per control cycle from then on. During the start-up checks only the independent watchdog runs; it is serviced after every 64 KiB checked. |
| CON-SUP-156 | There is no memory protection between the supervisor and the application tasks on the shared core. The application tasks are developed to the same integrity level as the supervisor, and freedom from interference is not claimed. |
| CON-SUP-157 | Withdrawn; replaced by CON-SUP-166: the missing models were built. |
| CON-SUP-158 | **Measurement (fact).** A table-driven CRC-32/MPEG-2 loop compiled with arm-none-eabi-gcc 10.3.1 (`-mcpu=cortex-m55 -O2`) has 6 instructions per byte, about 6150 for a 1 KiB segment. The 0.5 ms limit at 200 MHz is 100 000 core cycles. Cycles per instruction and memory wait states were not measured. Execution-time evidence on the target is not available in this project; see CON-SUP-167. |

**Seventeenth round.**

| ID | Decision |
|---|---|
| CON-SUP-159 | A fault is entered in the fault history and counted in the fault count when it is detected, not when its report is sent. Fault reports still pending or partly sent when a reset occurs are lost and are not sent again after the reset; CON-SUP-112 and CON-SUP-150 do not apply to them. Their faults stay in the history and the count as CON-SUP-125 and CON-SUP-151 say. |

**Eighteenth round.**

| ID | Decision |
|---|---|
| CON-SUP-160 | Withdrawn; replaced by CON-SUP-164. It prescribed a storage mechanism, which is a design matter. |
| CON-SUP-161 | The history entry, the fault count and the per-code detection count of a fault are updated together, in one update of the retained data, completed within 1 ms of the detection. After a reset during that update the fault is either completely present (entry and both counts) or completely absent; both are acceptable. |

**Nineteenth round.**

| ID | Decision |
|---|---|
| CON-SUP-162 | Withdrawn; replaced by CON-SUP-164. It prescribed a storage mechanism, which is a design matter. |
| CON-SUP-163 | Withdrawn; replaced by CON-SUP-164. It prescribed a storage mechanism, which is a design matter. |

**Twentieth round.** Withdraws CON-SUP-160, 162 and 163.

| ID | Decision |
|---|---|
| CON-SUP-164 | After a reset other than power-on, the retained data of CON-SUP-151 is either the data before or the data after the update the reset interrupted, never a mixture; a reset never clears the safe-state latch by interrupting an update. This replaces the wrong-CRC rule of CON-SUP-151: if no intact retained data is found after a reset other than power-on, the system starts with the safe state latched, the counts and the history empty, and reports no additional fault for it. After a power-on reset the retained data has its power-on values. The storage mechanism is chosen in the design; there is no limit on the number of updates. |
| CON-SUP-165 | Withdrawn; the deviation from STK-SUP-015 is no longer needed (CON-SUP-166). |

**Twenty-first round.** Withdraws CON-SUP-157 and CON-SUP-165.

| ID | Decision |
|---|---|
| CON-SUP-166 | **Verification environment (fact).** Host tests with the hardware interface replaced by fakes, and one combined simulator platform (`sim/`, Renode, Cortex-M55) with time-driven IWDG, WWDG, reset flags, USART1, GPIOA, TIM2, CRC and retained RAM, on which every fault class can be injected and its complete reaction observed. The watchdog reset times measured on it are 100.0 ms (IWDG) and 10.49 ms (WWDG). Its limits are listed in `sim/README.md`; in particular it is not cycle accurate: execution time is verified on it only under the assumption of CON-SUP-167. |

**Twenty-second round.**

| ID | Decision |
|---|---|
| CON-SUP-167 | **Timing assumption.** Processor-time limits (CON-SUP-108, CON-SUP-114) are verified by test on the simulator platform, which executes 50 million instructions per second: an assumed average of 4 clock cycles per instruction at the 200 MHz of CON-SUP-152. A limit is met when the time measured there is within it. The assumption is not confirmed on hardware. Confirming it on the target is an obligation on the integrator of the product, listed in the review package; until then the result holds under this assumption only. |

**Twenty-third round.** Raised by the architecture stages of the full-V run. CON-SUP-170 and CON-SUP-171 relax two bounds that earlier decisions stated without counting concurrent work.

| ID | Decision |
|---|---|
| CON-SUP-168 | **Replaces the wording of CON-SUP-114 on cycles.** The only limit on the supervisor's total processor time in normal operation is 10 % over any 1 s window. There is no limit per control cycle on the total; CON-SUP-108 alone limits the run-time code check per cycle. A per-cycle budget in an architecture is a design allocation; a cycle that also clears the detection counts (CON-SUP-140) may exceed it as long as the 1 s limit holds and the end-of-cycle watchdog service stays inside its window. |
| CON-SUP-169 | **Clarifies CON-SUP-139.** An answer counts as being transmitted from the instant its request is accepted (its line feed is received while no answer is being transmitted) to the end of the last character of the answer. A request received in that time is ignored. |
| CON-SUP-170 | **Replaces the 1 ms of CON-SUP-161 for concurrent faults.** One update of the retained data may record any number of faults that are pending when it starts. A fault detected while no update is running is recorded by an update completed within 1 ms of the detection; a fault detected while an update is running is recorded by the next update, completed within 2 ms of the detection. An update, whatever number of faults it records, uses at most 0.5 ms of processor time, verified under CON-SUP-167. |
| CON-SUP-171 | **Extends CON-SUP-140.** The check that 60 s of fault-free operation have passed is made once per control cycle. The counts return to zero at the latest 20 ms after the end of the 60 s (as extended by the under-count of CON-SUP-136), and never before it. The 60 s start at the instant the supervisor recognises the fault in software; after a reset that follows a detection, time from before that detection does not count. |

**Twenty-fourth round.** Raised by the system architecture stage of the full-V run. CON-SUP-127 allowed for the measurement resolution only, not for the time the supervisor needs to notice an expired limit.

| ID | Decision |
|---|---|
| CON-SUP-172 | **Replaces the 100 µs detection bound of CON-SUP-127.** A late start or an overrun is detected no later than 200 µs after the limit expires: 100 µs for the measurement resolution and 100 µs for the supervisor's reaction. A task that starts or completes no more than 100 µs after its limit may be treated as within the limit or as a violation; both are accepted. A task that starts or completes within its limit is never a violation. The verification margins of at least 200 µs on either side of a limit stay as they are; a test may check the 200 µs bound with a violation that lasts longer than 200 µs. |

**Twenty-fifth round.** Raised by the system requirements stage of the full-V run. One rule instead of separate exceptions.

| ID | Decision |
|---|---|
| CON-SUP-173 | **Recorded fault.** A fault is recorded when the update of the retained data that contains it has completed. Every rule that a fault is in the fault count, in the fault history or in its detection count (CON-SUP-125, CON-SUP-140, CON-SUP-150, CON-SUP-159, CON-SUP-161, CON-SUP-170), also for a dropped report, applies to recorded faults and to the retained data as it is until the next power-on reset or the next start-up without intact retained data (CON-SUP-164). A fault that is detected but not yet recorded when a reset occurs, whether or not its update has begun, is after a reset other than power-on either completely present or completely absent; both are accepted. Requirements state this rule once and refer to "a recorded fault" instead of listing the resets as exceptions. |

**Twenty-sixth round.**

| ID | Decision |
|---|---|
| CON-SUP-174 | The fault history holds the entries of the 8 most recently recorded faults (the ones `GET FAULTS` returns, CON-SUP-113); recording a further fault replaces the oldest entry. The fault count is an unsigned 32-bit number, reported in decimal, that stays at 4294967295 when it reaches it. A detection count stays at 3 when it reaches it (the latch value of CON-SUP-117). Replacing an entry and staying at a maximum are part of the update that records the fault and are not a loss of a recorded fault. |

**Twenty-seventh round.**

| ID | Decision |
|---|---|
| CON-SUP-175 | A commanded or controlled shutdown is out of scope: the product has no shutdown command and no low-power mode. Power is removed without notice. The software has no function for it; the output levels while unpowered belong to the board project (CON-SUP-153), the retained data is lost (CON-SUP-110), and the next start is a power-on reset. |

**Twenty-eighth round.**

| ID | Decision |
|---|---|
| CON-SUP-176 | **Permitted configurations (STK-SUP-004).** The application tasks are the four tasks of CON-SUP-101: T_IN, T_CTRL and T_OUT with a period of 10 ms and T_DIAG with a period of 100 ms. A configuration sets, for each of them, whether it is supervised and its timing limits, and it sets the release order of the 10 ms tasks. At least one 10 ms task is supervised. The periods are 10 ms and 100 ms as given (CON-SUP-006); any other period, an unknown task, a task listed twice, a missing task or no supervised 10 ms task is a configuration fault (code 9, CON-SUP-115). All four tasks are released whether supervised or not. Program flow supervision (CON-SUP-104, CON-SUP-149) covers the supervised 10 ms tasks in their configured order; checkpoints of an unsupervised task are ignored and it raises no fault. |

**Twenty-ninth round.** CON-SUP-177 answers the software architecture stage of the full-V run. CON-SUP-178..180 answer open points that the architecture stages had deferred to the design.

| ID | Decision |
|---|---|
| CON-SUP-177 | When the line feed of a request is received within 1 ms before or after the end of the last character of an answer, the request may be accepted or ignored; both are accepted, and nothing else may happen (no partial answer, no wrong answer). This limits CON-SUP-139 and CON-SUP-169. |
| CON-SUP-178 | **Platform allocation.** The boot code, which is not part of this product, starts the supervisor with these clocks: core, TIM2 and USART1 at 200 MHz, WWDG input clock 50 MHz, IWDG 32 kHz. The time base is TIM2 and its interrupt, the diagnostic line is USART1 and its interrupt. The control outputs are PA0 and PA1, the status signal is PA2. A software reset is requested through the system control block of the processor core. Register details and the retained memory region are taken from RM0486 by section and page in the design. |
| CON-SUP-179 | **Task dispatch.** The supervisor's scheduler dispatches the application tasks: the released 10 ms tasks run to completion one after the other in release order; T_DIAG runs when no 10 ms task is pending and is preempted by them. There is no operating system. The supervisor may use at most 64 KiB of code and 32 KiB of RAM, stacks included. A scheduler activation that comes too late has no fault code of its own: the window watchdog is then not refreshed. |
| CON-SUP-180 | The application supplies the task entry functions and identities in a constant table at linker symbol `__task_table`, part of the program code, that is checked with it (CON-SUP-107). Its format is defined in the design. |

**Thirtieth round.** CON-SUP-101 gave a release order but no release instants; with run-to-completion (CON-SUP-179) the 2 ms start limit could not hold.

| ID | Decision |
|---|---|
| CON-SUP-181 | **Release instants, measured from the start of the control cycle.** The first 10 ms task in the configured release order is released at 0 ms, the second at 3 ms and the third at 6 ms; T_DIAG is released at 9 ms of every tenth control cycle. The defaults of CON-SUP-103 hold with these instants: each 10 ms task may execute for its 3 ms before the next is released. The start limit is measured from the release instant of the task itself. A task that has been released waits while an earlier 10 ms task still runs; the resulting late start is a fault of the waiting task when its start limit expires, in addition to the overrun of the running one. |

**Thirty-first round.**

| ID | Decision |
|---|---|
| CON-SUP-182 | In normal operation each release instant of CON-SUP-181 is at most 100 µs early and at most 500 µs late, measured from the start of its control cycle; the start of a control cycle is at most 500 µs from 10 ms after the previous one. While a fault or a service request is handled these tolerances do not apply. Start and execution limits are measured from the actual release and the actual start. The limits of CON-SUP-103 and the end-of-cycle flow check of CON-SUP-104 apply independently: a 10 ms task that is within its start and execution limits but has not completed at the end of its control cycle is a flow fault. |
| CON-SUP-183 | **Workload of the application (assumption for budgets, not a requirement on the supervisor).** In normal operation each 10 ms task needs at most 1 ms of processor time per cycle and T_DIAG at most 5 ms per 100 ms. The limits of CON-SUP-103 stay as they are. |

**Thirty-second round.**

| ID | Decision |
|---|---|
| CON-SUP-184 | **Integrity check that cannot be completed.** An integrity check whose memory cannot be read inside its stated range, or whose CRC computation cannot be carried out, counts as a failed check: code 5 or 6 at start-up, code 7 at run time, with the reaction of that code. The instant the fault becomes detectable (CON-SUP-105) is when the read or the computation is refused. The CRC unit is used by the supervisor only, and its uses never overlap. |

**Thirty-third round.**

| ID | Decision |
|---|---|
| CON-SUP-185 | **Replaces the last sentence of CON-SUP-184.** From the instant the boot code starts the supervisor (CON-SUP-178) only the supervisor uses the CRC unit, and its uses never overlap; that the application tasks and test software leave the unit alone is an assumption on the integrator. What the boot code does with the unit before that instant is outside this product; the supervisor sets the unit up itself before its first use. |

**Thirty-fourth round.**

| ID | Decision |
|---|---|
| CON-SUP-186 | **Limits CON-SUP-170.** One update of the retained data has to record at most 16 pending faults. The 0.5 ms of processor time and the 1 ms and 2 ms of CON-SUP-170 hold for up to 16 and are verified with 16. With four tasks, at most one fault of each of the codes 1, 2 and 3 per task, one flow fault and one code 7 fault in a control cycle, more cannot be pending at once; what happens with more is not specified. |
| CON-SUP-187 | **Content of an answer, relaxes the exact instant of reception.** The fault history of a `GET FAULTS` answer, and the state and fault count of a `GET STATUS` answer, are those held at one instant not more than 1 ms before and not more than 1 ms after the request's line feed is received. A fault recorded, or a state entered, inside that interval may be in the answer or not; both are accepted. The content is never a mixture of two instants. |

**Thirty-fifth round.** Answers the design stage (OP-SWU-008): the boundary between the supervisor and what is not part of it.

| ID | Decision |
|---|---|
| CON-SUP-188 | **Boundary of the product, extends CON-SUP-178.** The boot code starts the supervisor by calling its one start entry function in privileged thread mode, in the secure state; it has enabled the clocks of the peripherals of CON-SUP-003 and routed the two USART1 signals to their pins. Everything else is set up by the supervisor, through the secure addresses of the peripherals (RM0486), the modes of PA0, PA1 and PA2 and the interrupt priorities included. The drivers are part of the product. The integrator's vector table calls these handlers, which the supervisor defines as far as it needs them: `TIM2_IRQHandler`, `USART1_IRQHandler`, `SysTick_Handler`, `PendSV_Handler`, `SVC_Handler`, and, for the interrupts 117 and 118, which only the supervisor's software pends, `SPARE0_IRQHandler` and `SPARE1_IRQHandler`. The integrator's linker script provides the symbols of CON-SUP-107, 124, 142 and 180 and a section `.noinit`, which start-up code leaves as it is, for the retained data. |

**Thirty-sixth round.** Answers the design stage (OP-SWU-014, OP-SWU-017, OP-SWU-020).

| ID | Decision |
|---|---|
| CON-SUP-189 | **Processor core facts, completes CON-SUP-188 (the interrupt priorities are set in the core registers below, not in a register of RM0486).** Cortex-M55, Armv8.1-M Mainline. Exception numbers: SVCall 11, PendSV 14, SysTick 15; interrupt n (RM0486 section 24.1.2) is exception 16 + n. Each interrupt has one 8-bit priority field of which the upper 4 bits are implemented; a lower value is a higher priority. Registers, 32-bit unless stated: interrupt set-enable from 0xE000E100, set-pending from 0xE000E200, clear-pending from 0xE000E280 (one bit per interrupt, 32 per word); priority from 0xE000E400 (one byte per interrupt); interrupt control and state 0xE000ED04 (bit 28 sets, bit 27 clears PendSV pending); reset control 0xE000ED0C (key 0x05FA in bits 31:16, bits 10:8 priority grouping, bit 2 requests the system reset); SVCall priority in bits 31:24 of 0xE000ED1C; PendSV priority in bits 23:16 and SysTick priority in bits 31:24 of 0xE000ED20. When the boot code starts the supervisor, every interrupt is disabled and not pending, the priority grouping, PRIMASK, FAULTMASK and BASEPRI are 0, and the main stack is in use. The order of the priorities is a design matter within the requirements. |
| CON-SUP-190 | **Dispatch is supervisor code, clarifies CON-SUP-179.** The supervisor itself makes a released task run and preempts T_DIAG; the application supplies nothing for it but the table of CON-SUP-180. Interrupts 117 and 118 (CON-SUP-188) and PendSV may be used for it; which context runs what is a design matter. |
| CON-SUP-191 | **Deviation from CON-SUP-004, relaxes it.** The compiler's `__asm__` form is permitted for single core instructions that C11 cannot express (special register access, barriers, wait for interrupt, exception return), only in target-only code under `#if defined(__arm__)` of the driver that gives access to the core. Everything else stays C11. |
| CON-SUP-192 | **Independent watchdog, accepted limits; relaxes the exact 100 ms of CON-SUP-166 and of the timeout setting.** With its 32 kHz clock taken as exact, the reset comes 100 ms after the last service, accepted from 99.5 ms to 100.5 ms. Where a service interval must be shorter than the 100 ms timeout, it shall be shorter than 99.5 ms. The tolerance of the 32 kHz oscillator is an assumption on the integrator and is not part of the verification. Neither watchdog is running when the boot code starts the supervisor. |

**Thirty-seventh round.** Answers the design stage (OP-SWU-024) and the deferred OP-SWC-035.

| ID | Decision |
|---|---|
| CON-SUP-193 | **Retained data in `.noinit`, completes CON-SUP-188.** The integrator's linker script reserves in the section `.noinit` 4096 bytes for the supervisor, aligned to 8 bytes, between the symbols `__noinit_start` and `__noinit_end`. The supervisor reaches its retained data through these symbols, as it reaches the configuration data through `__cfg_start`; no compiler extension is needed. When the boot code starts the supervisor this memory is clocked, readable and writable. |
