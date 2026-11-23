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

## Product decisions

**Fictional demo product.** Like the Safety Supervisor decisions, these answer the blocking open points a driver run
stopped on. They were written by Claude for the demo and are not recommendations for a real product.

| ID | Decision |
|---|---|
| CON-IWDG-007 | The product selects the software watchdog mode in its option bytes; the hardware watchdog mode (watchdog running from power-on) is out of scope. If the start service is called while the watchdog is already running, it changes nothing and returns an "already running" status. |
| CON-IWDG-008 | The driver does not detect a refresh that the hardware ignored. The refresh service issues the request and returns; a refresh that never takes effect is caught by the caller's own supervision (in the Safety Supervisor: the window watchdog and the deadline monitoring). The driver offers no separate status for it. |
| CON-IWDG-009 | Every bounded wait takes a timeout in milliseconds from the caller (1 to 1000 ms), measured with the platform's 1 ms tick. A wait still unfinished when the timeout has elapsed returns a timeout status. |
