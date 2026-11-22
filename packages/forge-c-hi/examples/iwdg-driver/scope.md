# IWDG driver: scope

Input class: reference document (HAL / low-level driver). This file states the task in our own words. All hardware
facts come from the reference manual, cited by section and page; no text from it is reproduced here.

## Reference document

- **RM0486**, STMicroelectronics reference manual for the STM32N647/657xx microcontrollers, revision 4. Chapter
  "Independent watchdog (IWDG)".
- Obtain it from the vendor's web site and place it at `docs/rm0486.pdf` in your project. It is not part of this
  package and must not be redistributed. Then run `hi doc-index docs/rm0486.pdf --doc-id RM0486`.

## Task constraints

| ID | Constraint |
|---|---|
| CON-IWDG-001 | Write the interface requirements of a low-level driver for the IWDG peripheral of the STM32N657X0. |
| CON-IWDG-002 | The driver offers: configuration and start, refresh, optional window configuration, early-wakeup interrupt configuration, status queries for pending register updates, and reading the reset cause flag set by the IWDG. |
| CON-IWDG-003 | The driver never stops a started watchdog (the hardware cannot be stopped by software). |
| CON-IWDG-004 | Every operation that waits for the hardware has a bounded wait and reports a timeout instead of blocking forever. |
| CON-IWDG-005 | Language C11, no dynamic memory, no recursion; the caller supplies a configuration structure. |
| CON-IWDG-006 | The Safety Supervisor middleware (`examples/safety-supervisor`) uses this driver; its software requirements link to these driver requirements. |
