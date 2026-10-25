# Tasks: Feature 015 STM32N6 driver benchmark set

Order follows input readiness: the CRC, SPI and USART chapters parse with the current register-map parser; GPIO and TIM
need the FR-003 parser change first. A task is checked only with run evidence (`evidence/v0.4/runs/F015-Txxx/`).

## M0 — Inputs and queue

- [ ] **F015-T001** Convert the five RM0486 chapters and memory-map excerpts (`examples/00NN-<id>-st/inputs/`, tracked
  hash manifests, ST text git-ignored) and record which register sections the current parser finds.
- [ ] **F015-T002** Queue file `config/factory/benchmark/st-driver-queue.yaml` (FR-004) and queue runner
  `forge_factory.benchmark.queue` (FR-005) with tests; outcome records (FR-006).

## M1 — CRC (RM0486 ch. 26)

- [ ] **F015-T010** CRC profile, Renode model and platform, example 0014c (ST LL code FROZEN); intake and register-map tests.
- [ ] **F015-T011** Run 0014c; record the outcome.

## M2 — SPI (RM0486 ch. 67)

- [ ] **F015-T020** SPI1 profile, Renode model and platform, example 0011c (ST LL code FROZEN); intake and register-map tests.
- [ ] **F015-T021** Run 0011c; record the outcome.

## M3 — USART (RM0486 ch. 65)

- [ ] **F015-T030** USART1 profile, Renode model and platform, example 0012c (ST LL code FROZEN); intake and register-map tests.
- [ ] **F015-T031** Run 0012c; record the outcome.

## M4 — Parser (FR-003)

- [ ] **F015-T040** Register headings with an instance placeholder and qualifier, and per-pin generic fields. RCC and
  IWDG generated register maps stay byte-identical. CRE.

## M5 — GPIO (RM0486 ch. 15) and TIM (RM0486 ch. 54)

- [ ] **F015-T050** GPIOA profile, Renode model and platform, example 0010c (ST LL code FROZEN); intake and register-map tests.
- [ ] **F015-T051** Run 0010c; record the outcome.
- [ ] **F015-T060** TIM2 profile, Renode model and platform, example 0013c (ST LL code FROZEN); intake and register-map tests.
- [ ] **F015-T061** Run 0013c; record the outcome.

## M6 — ST HAL code (later, owner 2026-10-25 "LL first, HAL later")

- [ ] **F015-T065** Delivery of ST HAL code with its dependencies (hal_def, hal_conf template); examples `00NNd-st-cube-<id>-hal`; queue items after the LL items.

## M7 — Freeze

- [ ] **F015-T070** Freeze the benchmark set (FR-006, SC-002) and open the PR (no merge without owner approval).
