# ADR-DA-016: Preserve typed prelaunch causes

The first local B attempt reached verified source and inputs, then the external
guard refused it before native submission. Its durable non-dispatch receipt
stored `Refused`, losing the actionable `GUARD_FAIL` code available in the launch
transcript. An autonomous diagnostic consumer should not need a log search to
distinguish an input problem from a host guard refusal.

`LaunchNotStarted` retains a canonical code from the existing controller
`Refused` type. Codes contain one leading capital letter and at most 127 further
capital letters, digits or underscores. Other exceptions and malformed codes keep
their previous class-name fallback; details do not enter the durable key. The
exception message, job identity and nonce retain their existing behavior.

This changes diagnostic fidelity, not the proof boundary. Only existing proven
pre-native paths can construct this local refusal. A transport timeout after an
invocation still retains uncertainty and its resource lease. Attempt charges,
immutable receipts and quarantined commands are not reset or replayed. Historical
records are never rewritten. Actual hardware/model capability is not qualified
by these private control cases.
