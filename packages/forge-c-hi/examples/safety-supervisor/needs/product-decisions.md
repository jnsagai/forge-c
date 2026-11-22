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
