# Safety Supervisor: platform constraints

These are given facts about the platform, not needs. Requirements may cite them; they must not invent others.

| ID | Constraint |
|---|---|
| CON-SUP-001 | Target microcontroller: STMicroelectronics STM32N657X0 (Arm Cortex-M55). |
| CON-SUP-002 | Reference manual: ST RM0486 (STM32N647/657xx). Cite it by document id, section and page only; never copy its text. Users obtain it from the vendor. |
| CON-SUP-003 | Peripherals available to the supervisor: IWDG, WWDG, CRC, TIM (time base), USART (diagnostic line), GPIO (status signal and control outputs), RCC (clocks and reset flags). |
| CON-SUP-004 | Language: C11, no dynamic memory allocation, no recursion. |
| CON-SUP-005 | Verification platform: host unit tests (gcc, gcovr) and the Renode simulator with STM32N6 platform descriptions. Real hardware is not required. |
| CON-SUP-006 | Cyclic application tasks run at 10 ms and 100 ms periods from a timer-driven scheduler. |
| CON-SUP-007 | Diagnostic serial line: 115200 baud, 8 data bits, no parity, 1 stop bit. |
