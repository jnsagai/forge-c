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
