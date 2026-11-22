# Safety Supervisor: stakeholder needs

Input class: natural language (middleware and application). Each need has a stable ID so that system requirements can
trace to it. The needs are written the way a product owner would state them: they are not yet requirements, and some
are deliberately loose. Making them precise, and raising open points where they cannot be made precise, is the job of
the system-requirements author and inspector.

## Context

A small controller runs a few cyclic application tasks on one microcontroller. A failure of any task, of the program
flow or of the memory content must never go unnoticed: the controller must reach a safe state and recover by a reset,
and must tell the outside world what happened. The Safety Supervisor is the software that provides this protection.

## Needs

### Supervision of the application

- **STK-SUP-001** The supervisor must notice when any supervised application task stops running.
- **STK-SUP-002** The supervisor must notice when a supervised task runs too late or takes too long, compared with
  the timing configured for that task.
- **STK-SUP-003** The supervisor must notice when the tasks of one control cycle run in the wrong order or one of them
  is skipped.
- **STK-SUP-004** Which tasks are supervised, and their timing and order, must be set by configuration, not by changing
  the supervisor code.

### Watchdogs

- **STK-SUP-005** The hardware watchdogs must be serviced only while every supervised task is healthy, so that a
  failure the software does not handle still ends in a hardware reset.
- **STK-SUP-006** Both an independent watchdog (own clock) and a window watchdog (detects servicing too early as well
  as too late) must be used.

### Memory integrity

- **STK-SUP-007** At start-up, before the application runs, the controller must check that its program code and its
  configuration data are intact.
- **STK-SUP-008** While running, the controller must repeat the program-code check in the background, completing a full
  pass in a bounded time, without disturbing the application timing.

### Reaction to faults

- **STK-SUP-009** When any fault above is detected, the controller must enter a safe state quickly: the control
  outputs are switched off and a status signal shows that the controller is not operational. The whole reaction, from
  the fault to the safe state, must fit in 50 ms.
- **STK-SUP-010** After entering the safe state the controller must recover by a reset, unless the same fault has
  repeated several times in a row, in which case it must stay in the safe state until it is power-cycled.
- **STK-SUP-011** After any reset, the controller must be able to tell whether the reset was caused by a watchdog, by
  the supervisor, or was a normal power-on.

### Diagnostics

- **STK-SUP-012** Every detected fault must be reported on the diagnostic serial line with a fault code, the affected
  task or memory area, and a time stamp.
- **STK-SUP-013** A service tool must be able to read the current supervision status and the last faults over the same
  serial line.

### Constraints from the product owner

- **STK-SUP-014** The supervisor must not use more than 10 % of the processor time in normal operation.
- **STK-SUP-015** The supervisor must be testable without the real board, on a simulator, including the injection of
  each fault above.
