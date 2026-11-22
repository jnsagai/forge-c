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
