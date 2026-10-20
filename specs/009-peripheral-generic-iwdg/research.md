# Research: Peripheral-generic factory

Source: a read-only survey of the factory (2026-10-20) found RCC hard-coded in about 35 modules, and 144 lines of
`workflow/prompts.py`. Line references are as of `feat/008` at 0219f0d.

## R1. Which second peripheral

- **Decision**: IWDG (RM0486 chapter 59, pages 2979–2994; secure base 0x56004800, 1 KB).
- **Rationale**:
  - single instance, one base: the "one register block per driver" design holds;
  - 7 registers (KR, PR, RLR, SR, WINR, EWCR, ICR);
  - it exercises exactly the missing capabilities: multi-bit fields (KEY[15:0], PR[3:0], RL[11:0], WIN[11:0]), value
    writes (key sequence 0xCCCC/0x5555/0xAAAA), and a status-flag wait (SR.PVU/RVU/WVU).
- **Alternatives**: GPIO (12 ports, pin-indexed fields `MODEy[1:0]`, register names with an `x` placeholder, needs
  RCC clocking); a later step.

## R2. Where the peripheral identity lives

- **Decision**: a validated profile file per peripheral (`config/factory/peripherals/<id>.yaml`), named by the work
  order (`"peripheral"`, default `rcc`). `layer.py` exposes the identity API (file names, prefixes, register block,
  components, key sections, base address); every module asks it instead of using literals.
- **Rationale**: `layer.py` already centralises part of this (`LL_HEADER`, `api_prefix`, `components`), but about 30
  sites duplicate the literals. A profile is data, so adding a peripheral needs no code change. The RCC profile
  equals today's constants, so RCC does not change.

## R3. Multi-bit fields

- **Decision**: the field regex in `inspection/regmap.py:23` and `assurance/hardware.py:34` accepts
  `Bits m:n NAME[m:n]:`. Fields keep `lsb`/`msb`; masks are computed from the width.
- **Rationale**: the current regex drops `KEY[15:0]` (and RCC's own `SYSSWS[1:0]`), which was verified by sample.
  RCC's single-bit fields are unaffected.

## R4. Value writes in the register contract

- **Decision**: a new op `write` with `"value"` (an integer, or an RM-named constant), checked by the oracle as
  "the field holds value V after the call". Set/clear/no_write stay.
- **Rationale**: the IWDG key register is written with values, never set or cleared bit by bit.

## R5. Simulator

- **Decision**: the profile names the Renode model file and window size; `sim.py` and the platform template read it.
  The IWDG model emulates:
  - KR keys: 0xCCCC start, 0xAAAA reload, 0x5555 enable register access;
  - PR/RLR/WINR writes accepted only after 0x5555;
  - SR update flags clearing after a write;
  - the counter running down after start.
