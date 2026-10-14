# SWE.2 — Software Architecture

Document ID / version / approved requirement baseline: <...>

1. Scope, target variant, modes, external interfaces, clock/reset domains, safety partitions.
2. Static component diagram (register access, state manager, HAL facade, timer/timebase, safety diagnostics).
3. Dynamic state machine & sequence diagrams (init, clock enable/reset, timeout, recovery, ISR preemption).
4. Data/control dependencies, synchronization, memory barriers, HW preconditions and expected safe state.
5. Alternatives / resource estimates / safety risks and rationale for selection (record ROM/RAM/timing estimates).
6. Bidirectional requirement consistency and design review/communication evidence.
