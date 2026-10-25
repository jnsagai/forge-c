# Feature 015: STM32N6 driver benchmark set (Codex authors, Claude inspectors)

Owner request 2026-10-25: "in the meantime I want to have the current forge-c + safeC running to implement more sw
drivers for ST examples to be used as benchmark later for the new version of Forge-C, use the codex + claude inspector
workflow, create a queue of drivers to be implemented, use the same microcontroller as before".

Owner choices (2026-10-25):
- Peripherals: GPIO, SPI, USART, TIM, CRC (STM32N6, RM0486 Rev 4, same target as the RCC/IWDG pilots).
- Use case (owner 2026-10-25): "not to generate code, but use the existing ST code and create all the ASPICE artifacts
  for SWE Process". Every work order delivers ST's STM32CubeN6 v1.4.0 code FROZEN (feature 008 brownfield, like
  0008c), and the factory produces the SWE.1-SWE.6 work products for it.
- ST code per peripheral: the LL driver first; the HAL driver later, once delivery handles ST's HAL dependencies
  (hal_def, hal_conf template).
- Runs execute on loop10 (Codex and Claude are logged in only there), one work order at a time.

## Goal

A frozen set of benchmark work orders with reference outcomes of the current production line (Codex authors, Claude
inspectors, deterministic gates, release packaging), so that a later Forge-C version can be measured against it on the
same inputs.

## Requirements

- **FR-001** Each peripheral is onboarded through the feature 009 mechanism, not by new peripheral-specific code paths
  where a profile suffices. Onboarding consists of:
  - a validated peripheral profile `config/factory/peripherals/<id>.yaml`;
  - the RM0486 chapter and memory-map excerpts converted with `forge_factory.docs.pdf2md`, with a tracked hash
    manifest (the ST text stays local, git-ignored, like the RCC inputs);
  - a behavioural Renode model and platform under `factory/sim/stm32n6/`;
  - the example `00NNc-st-cube-<id>` (ST LL code FROZEN); later `00NNd-st-cube-<id>-hal` (ST HAL code FROZEN).
- **FR-002** One instance per peripheral, at the secure alias of RM0486 Table 3:

  | Peripheral | Instance | Base address | RM page |
  |---|---|---|---|
  | GPIO | GPIOA | 0x56020000 | 176 |
  | SPI | SPI1 | 0x52003000 | 180 |
  | USART | USART1 | 0x52001000 | 180 |
  | TIM | TIM2 | 0x50000000 | 181 |
  | CRC | CRC | 0x56024C00 | 176 |

  The scope of each work order is a stated subset of the peripheral. Everything else is "Out of scope".
- **FR-003** The register-map parser accepts RM headings with an instance placeholder and qualifier, e.g.
  "(GPIOx_MODER) (x = A to H, N to Q)" and "(TIMx_CR1)(x = 2 to 5)", and per-pin generic fields (e.g. MODEy[1:0]).
  The RCC and IWDG outputs stay byte-identical.
- **FR-004** A queue file (`config/factory/benchmark/st-driver-queue.yaml`) lists the work orders in order. An item
  whose example does not exist yet (peripheral not onboarded) is skipped.
- **FR-005** A queue runner on loop10 launches one work order at a time on the main Fabro server with
  `--acp-authors codex --acp-inspectors claude`. It waits for the package and records the outcome. It skips work
  orders that are not onboarded yet and never retries silently: each retry is a new work order id recorded in the
  queue state.
- **FR-006** Each finished work order becomes a benchmark record with its id, commit, inputs hashes, package status,
  gaps, phase results, duration and model usage. The deterministic gates and inspectors decide; nothing is marked
  READY by hand.
- **FR-007** Existing behaviour is unchanged. This covers the RCC and IWDG work orders, the frozen compatibility
  fixtures, the local-rtx profiles and the factory gates. Every factory change goes through CRE.

- **FR-008** (owner 2026-10-25: "the factory should be self-managed"; "AFO on main can't run this yet - solve it! I
  want it running with codex and claude as inspector, forget about deepseek now") The queue runs as AFO work orders
  on the production line:
  - AFO's only pre-approved model profile is `codex-claude` (Codex authors, Claude inspectors);
  - the policy requests PILOT, which takes effect only with the owner's SSH-signed authorization (scope: the benchmark
    driver classes, `codex-claude`; actions: submit, launch, recover);
  - a recovery attempt of a delivered-code order is a fresh work order, because main refuses `--resume-from` for
    delivered code (validated brownfield resume is feature 012);
  - the Conductor launches on the cloud-stack Fabro through an optional environment file.

## Non-goals

- No change to gates, inspector policy or release policy.
- No compliance or safety claim. Packages remain offline review candidates or BLOCKED gap packages.
- No local-model runs on loop10.

## Success criteria

- **SC-001** Every queued work order has a recorded outcome (READY_FOR_OFFLINE_REVIEW or BLOCKED with its gaps).
- **SC-002** The benchmark set (inputs hashes, work orders, outcomes) is frozen in `evidence/v0.4/benchmark/st-drivers/`
  and reproducible from the queue file.
