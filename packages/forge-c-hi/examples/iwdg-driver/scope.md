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
| CON-IWDG-010 | The window option and the early-wakeup interrupt are configured only by the start service, before the first refresh, and never changed while the watchdog runs. Before it issues the first load request, the start service waits until every register-update flag is clear (bounded by CON-IWDG-009). No other settling delay is required of the driver. |
| CON-IWDG-011 | The driver neither reports nor guards the reloads that a configuration write causes. The caller refreshes only through the refresh service and keeps its refresh timing clear of the window; this caller duty is stated in the driver interface. |
| CON-IWDG-012 | A timeout outside 1 to 1000 ms makes the service return an invalid-parameter status without accessing the hardware. |
| CON-IWDG-013 | The early-wakeup value is a field of the start configuration. There is no separate early-wakeup configuration service; this replaces that part of CON-IWDG-002. |
| CON-IWDG-014 | Every service checks its arguments first. An invalid argument, such as a timeout outside the range of CON-IWDG-012, returns invalid-parameter even when the watchdog is already running. The "already running" status of CON-IWDG-007 applies only to a start call with valid arguments. |
| CON-IWDG-015 | The start service writes the prescaler, reload, window and early-wakeup settings, waits until every register-update flag is clear (CON-IWDG-010) and returns success. It issues no extra load request after writing the window value and does not confirm that a reload took effect. The driver accepts every window value the register allows; keeping the first and later refreshes inside the window is the caller's duty (CON-IWDG-011). |
| CON-IWDG-016 | **Replaces CON-IWDG-015.** The start service follows the configuration sequence the reference manual documents for the watchdog, citing it by section and page: start the watchdog, then write the prescaler, reload, window and early-wakeup settings, and wait until every register-update flag is clear (bounded by CON-IWDG-009). It then loads the counter the way the manual describes for the chosen window option. It does not confirm that the load took effect. Refresh timing within the window stays the caller's duty (CON-IWDG-011). |
| CON-IWDG-017 | When the early-wakeup option is off, the start service writes no comparison value. It only leaves the early-wakeup interrupt disabled. |
| CON-IWDG-018 | The flag wait of CON-IWDG-010 applies only to a load request the driver issues itself. The automatic reload that the window write causes, inside the sequence of CON-IWDG-016, is part of that sequence and not such a request. |
| CON-IWDG-019 | To leave the early-wakeup interrupt disabled (CON-IWDG-017), the driver may write the register that holds both the enable and the comparison field if it keeps the field's current content. CON-IWDG-017 forbids only writing a new comparison value. |
