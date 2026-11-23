# T052: driver demo from a reference manual, and the middleware link (US2)

Reference configuration: Claude Sonnet author, GPT-6.1 Terra inspector, generic profile HI-2. The example is
`PKG/examples/iwdg-driver`, the independent watchdog of an STM32N6 microcontroller.

**Input and privacy:**
- The input is the owner's local copy of the vendor reference manual RM0486 (4669 pages), indexed with `hi doc-index`:
  3513 sections. The index content is local only; its hash is `seal/index.sha256`.
- Neither the manual nor its index is committed. Section titles from the manual are redacted (hashed) in every
  committed `governance.redacted.json`.
- Every committed pass folder passed `quote_check.py`: no run of 8 words is shared with the manual.

## Driver project (`f023-drv-1`): ACCEPTED in 7 passes

| Pass | Result | What it showed |
|---|---|---|
| 1 (`pass1-blocked-by-my-diagnostic/`) | BLOCKED by the operator | A diagnostic import by the operator wrote `.pyc` files, which the scope check charged to the active author (documented in `NOTE.md`). Also showed the defect that use cases naming constraints were "unknown references" (fixed in 3ad63c38). |
| 2 | BLOCKED | All gates PASS, including `doc-sources`: every citation resolves in the index. Three scope decisions were needed: hardware mode, ignored refresh, wait unit. |
| 3–6 | BLOCKED | The inspector went into the watchdog's window-mode and reload semantics. Decision rounds 2–5 (`CON-IWDG-010..019`); two rounds resolved conflicts between Claude's own earlier decisions. Fixes on the way: stale input hashes in the task, coverage-row tracking. |
| 7 (`pass7-accepted/`) | **ACCEPTED** | 51 driver interface requirements with 73 document citations (section and page) and every gate PASS. Sealed READY with 85 files and verified (`seal/`; the archive itself is not committed because it holds vendor headings). |

Totals: 150 model calls, 44 min author and 52 min inspector time.

## Middleware link (`link/`): ACCEPTED in 1 pass

A copy of the accepted run 6 Safety Supervisor project:
- is linked with `hi init --link ../f023-drv-1:driver_interface`;
- has one added fictional decision, `CON-SUP-148` (`link/driver-link.md`): the supervisor drives the independent
  watchdog only through the driver's services.

The conductor copied the driver's items into `.hi/linked/` (`link/linked-snapshot.json`) and updated the software
requirements:
- **107 items**, of which 6 now cite `DRV-IWDG-*` items;
- **11 trace links** of type `interfaces`, all valid, resolved by the trace gate in the driver project;
- **both stages ACCEPTED**, sealed READY with 90 files and verified (`link/verify.txt`).

Not certification or approval: these are engineering inputs for an offline review. The decisions are fictional demo
inputs, recorded in `../owner-decisions.md`.
