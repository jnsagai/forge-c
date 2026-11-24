# Owner decisions: feature 023

| Date | Decision | Source |
|---|---|---|
| 2026-11-22 | Bring Forge-C to the Capgemini Global Agentic Engineering Hackathon 2026 as an APM package (skills first) | owner chat |
| 2026-11-22 | Forge-C is led by generic high-integrity standards; ISO 26262 is one profile among others; keep every existing Forge-C feature | owner chat |
| 2026-11-22 | Ready for cloud and local models; standard V-model from system requirements; two input classes (natural-language needs; datasheets/reference manuals/models) | owner chat |
| 2026-11-22 | New branch for the work; cloud-based for now: local repo + GitHub + cloud models, **no Omniverse2** | owner chat |
| 2026-11-22 | Models configurable per role; tests use **Claude as author** and **GPT as inspector** | owner chat |
| 2026-11-22 | Constitution amendment to v0.5.0 approved ("I agree. And keep other features already existing for forge-c") | owner chat |
| 2026-11-22 | T077: public GitHub push and tag authorized now. T078: Capgemini repository publication at submission time | owner chat |
| 2026-11-22 | T079: the package licence is **Apache-2.0** | owner chat |
| 2026-11-22 | T080: the local-model run goes last, locally on loop10 | owner chat |

## 2026-11-22: demo project

- **Decision:** the end-to-end demo is the **Safety Supervisor** on STM32N6 (STM32N657X0, Cortex-M55): alive,
  deadline and program-flow supervision; IWDG/WWDG serviced only while healthy; CRC self-test of code and
  configuration; safe state and reset; fault reporting over USART; status pin.
- **Why:** every peripheral it needs already has a Renode platform under `factory/sim/stm32n6/` (WWDG to be checked)
  and prior driver work. It exercises both input classes (natural-language needs for the middleware, the reference
  manual RM0486 by section/page for the drivers) and gives measurable fault-injection evidence.
- **Effect:** the `watchdog-manager` demo is renamed `safety-supervisor` (T040, T052, T068). No task added or removed.

## 2026-11-22: reference test models and floor view

- **Decision:** the reference test configuration uses **Claude Sonnet** (`claude -p --model sonnet`, owner account,
  reported as `claude-sonnet-5-5`) as author and **GPT-6.1 Terra** (`codex exec -m gpt-6.1-terra`, ChatGPT login) as
  inspector. Owner chat: "for claude use sonnet and for gpt use Terra".
- **Effect:** runs 1 and 2 used the account defaults (Claude Opus 5.5, GPT-6.2-Sol); from run 3 on, the example
  configuration pins Sonnet and Terra. Evidence and the impact report name the models per run.
- **Floor:** owner asked to see the runs on the factory floor (:8788). `tools/hi_floor_line.py` serves the conductor
  records read-only as the "Hackathon" line.

## 2026-11-22: demo product decisions, second round (fictional, by Claude)

- **Decision:** `CON-SUP-117..120` answer the four blocking open points left by run 4 (latch count, reading the reset
  cause, fault-report entity for codes 8 and 9, order of fault report and safe-state entry). Like `CON-SUP-101..116`
  they are fictional demo-product decisions written by Claude, labelled as such in the input file; the owner has not
  been asked to make them (question still open in chat).
- **Effect:** run 4 is continued in update mode with the changed input; the conductor re-authors only what the change
  affects.
- **Third round:** `CON-SUP-121..122` answer the two blocking open points that the second round's answers exposed
  (watchdog servicing between detection and safe state; entity of a program-flow fault). Same status: fictional, by
  Claude.
- **Fourth round:** `CON-SUP-123` clarifies `CON-SUP-122` (which task is named when checkpoints arrive swapped). Same
  status: fictional, by Claude.
- **Fifth round:** `CON-SUP-124..128`. After pass 4 no open point blocked, but the inspector raised blocking findings
  against five deferred open points (deferral hides a system-level decision, as the skills now ask it to check). The
  product owner decides them. Same status: fictional, by Claude.
- **Sixth round:** `CON-SUP-129..130` complete the fifth round (CRC-32 parameters; status-state rules). Same status:
  fictional, by Claude.
- **Seventh round:** `CON-SUP-131..135` answer the software-level questions of run 4 pass 6 (timestamp event, outputs
  before software start-up, split of the 50 ms, GET FAULTS framing, what counts as fault-free time). Same status:
  fictional, by Claude.
- **Eighth round:** `CON-SUP-136` (allowed error of the fault-free time used for the latch). Same status: fictional,
  by Claude.
- **Ninth round:** `CON-SUP-137..138`, raised by the clean run 5: a contradiction between CON-SUP-121 and CON-SUP-130
  (watchdog servicing after a start-up code 8 report) and when a service request counts as received. Same status:
  fictional, by Claude.
- **Tenth round:** `CON-SUP-139..140` (overlapping service requests; per-code latch counts). Same status: fictional,
  by Claude.
- **Eleventh round:** `CON-SUP-141` (timestamp of a code 8 report). Same status: fictional, by Claude.
- **Twelfth round:** `CON-SUP-142..144` (configuration CRC layout, a fault report during an answer, deadline of the code 8 report), raised by run 6 (governance step). Same status: fictional, by Claude.
- **Thirteenth round:** `CON-SUP-145` (start-up message form and deadline), raised by run 6 pass 2 when the inspector challenged the deferral of OP-SYS-001. Same status: fictional, by Claude.
- **Fourteenth round:** `CON-SUP-146` (CRC range end symbols are exclusive), raised by run 6 pass 3. Same status: fictional, by Claude.
- **Fifteenth round:** `CON-SUP-147` (equality with a timing limit is verified by analysis), raised by run 6 pass 4. Same status: fictional, by Claude.
- **Driver demo, first round:** `CON-IWDG-007..009` in `examples/iwdg-driver/scope.md`: software watchdog mode only and
  the "already running" status, no detection of an ignored refresh, and bounded waits in milliseconds. They were raised by
  driver demo pass 2. Same status as the supervisor decisions: fictional, by Claude.
- **Driver demo, second round:** `CON-IWDG-010..012`. Window and early-wakeup settings are written only at start, after
  the update flags clear. There is no driver guard on configuration-induced reloads; the refresh timing is the caller's
  duty. An out-of-range timeout returns invalid-parameter. Raised by driver demo pass 3. Fictional, by Claude.
- **Driver demo, third round:** `CON-IWDG-013..015`. Early wakeup is part of the start configuration (resolving a
  conflict between two earlier decisions). Argument checks take precedence over "already running". The start sequence
  issues no extra reload and does not confirm one, and refresh timing within the window stays the caller's duty.
  Raised by driver demo pass 4; two of its questions were conflicts that Claude's earlier decisions had created.
  Fictional, by Claude.
- **Driver demo, fourth round:** `CON-IWDG-016..017`. The start service follows the manual's documented sequence, which
  replaces CON-IWDG-015: that decision had forbidden the load step the manual's sequence needs. No early-wakeup value
  is written when the option is off. Raised by driver demo pass 5. Fictional, by Claude.
- **Driver demo, fifth round:** `CON-IWDG-018..019`. They clarify how two earlier decisions apply to the manual's
  register-level sequence (the automatic reload caused by the window write, and the shared early-wakeup register).
  Raised by driver demo pass 6. Fictional, by Claude.
- **2026-11-24, goal:** "move forward autonomously, fixing issues and blocks by yourself, and run until you finish a
  complete v-model cycle".
- **Sixteenth round:** `CON-SUP-149..156`, fictional decisions by Claude; 149 and 150 correct contradictions between
  Claude's earlier decisions. `CON-SUP-157..158` are facts: the simulator models that exist, and a counted compiled loop.
- **Seventeenth round:** `CON-SUP-159` (reports pending at a reset), raised by full-V attempt 3. Fictional, by Claude.
- **Eighteenth round:** `CON-SUP-160..161`. 160 replaces an unsafe rule in CON-SUP-151 (Claude): an update interrupted by a reset would have cleared the safe-state latch. Raised by full-V attempt 3. Fictional, by Claude.
- **Nineteenth round:** `CON-SUP-162..163` (update number and equal copies), raised by full-V attempt 3. Fictional, by Claude.
- **Twentieth round:** withdraws `CON-SUP-160, 162, 163` (design detail that Claude had put at system level and that
  contradicted CON-SUP-150/159) in favour of `CON-SUP-164`. `CON-SUP-165` is a **deviation from the stakeholder need
  STK-SUP-015**, accepted by Claude under the owner's /goal of 2026-11-24 for the fictional demo and not confirmed by the
  owner. Raised by full-V attempt 3.
- **Twenty-first round:** the independent inspector did not accept the deviation `CON-SUP-165`, so the missing
  simulator models were built (`examples/safety-supervisor/sim`). `CON-SUP-157` and `CON-SUP-165` are withdrawn;
  `CON-SUP-166` states the environment and its limits as facts.
- **Twenty-second round:** `CON-SUP-167`, a timing assumption (4 clock cycles per instruction) made by Claude so that processor-time limits have a verifiable basis. It is **not confirmed on hardware** and is an obligation on the integrator. Raised by full-V attempt 3.
- **Twenty-third round:** `CON-SUP-168..171`, raised by full-V attempt 3 pass 7 (software architecture). 170 and 171
  **relax** two time bounds (retained-data update of concurrent faults 2 ms; counts cleared up to 20 ms late) that
  Claude's earlier decisions had stated without counting concurrent work. Fictional, by Claude.
- **Twenty-fourth round:** `CON-SUP-172` **relaxes** the late-start and overrun detection bound from 100 µs to 200 µs and
  accepts either verdict inside the first 100 µs. Raised by full-V attempt 3 pass 8 (system architecture): CON-SUP-127
  counted the measurement resolution but not the supervisor's reaction time. Fictional, by Claude.
- **Twenty-fifth round:** `CON-SUP-173` states one rule for faults not yet recorded at a reset (present or absent, both
  accepted, as CON-SUP-161 already allowed during an update; it now also covers a reset before the update begins).
  Raised by full-V attempt 3 pass 9 (system requirements). Fictional, by Claude.
- **Twenty-sixth round:** `CON-SUP-174` (history size 8, saturating fault and detection counts). Raised by full-V
  attempt 3 pass 10 (system requirements, OP-SYS-014). Fictional, by Claude.
- **Twenty-seventh round:** `CON-SUP-175` (controlled shutdown out of scope). Raised by full-V attempt 3 pass 12 (system
  requirements, OP-SYS-015). Fictional, by Claude.
- **Full-V attempt 3, pass 14:** software architecture blocked on missing USART facts (OP-SWC-016). No decision: the
  reference manual RM0486 is declared as a local reference document of the project (as in the driver demo). It is never
  committed or redistributed; architecture and design cite section and page only.
- **Twenty-eighth round:** `CON-SUP-176` (permitted task configurations). Raised by full-V attempt 3 pass 15 (system
  requirements, OP-SYS-016). Fictional, by Claude.
- **Twenty-ninth round:** `CON-SUP-177` (a request at the very end of an answer: either outcome, a **relaxation** of
  CON-SUP-139 in a 1 ms window), raised by full-V attempt 3 pass 16; `CON-SUP-178..180` (platform allocation, dispatch,
  memory limits, task table) answer open points deferred to the design. Fictional, by Claude.
- **Thirtieth round:** `CON-SUP-181` (release instants 0, 3, 6 and 9 ms). Claude's CON-SUP-101, 103 and 179 were not
  feasible together; raised by full-V attempt 3 pass 17 (system requirements, OP-SYS-017). Fictional, by Claude.
- **Thirty-first round:** `CON-SUP-182..183` (release tolerance, independence of the limits, application workload). Raised by full-V attempt 3 pass 18
  (system requirements, OP-SYS-018). Fictional, by Claude.
- **Full-V attempt 3, pass 19:** first pass to reach software design. It blocked on a conflict inside the accepted
  architecture (OP-SWU-006: an interface limited to thread context cannot meet the 50 ms answer limit). No decision and
  no relaxation: the point goes back to the software architecture through `returned_to`, added to the package for this.
- **Full-V attempt 3, pass 20:** sw-design returned OP-SWU-006 and OP-SWU-007 to sw-arch, which reached its rework limit
  with four findings the author can fix. No decision. The next pass gives the stage a new set of rework rounds.
