# Shared mission accounting for structured tool execution

This local follow-up addresses DA-FR-011/054 and the bounds portion of IE-T004.
It does not implement or qualify a positive dependency-independent provisional
continuation. M1 remains blocked/unaccepted; the reviewed simulation input still
needs actual Qwen inspection on Omniverse2.

## Demonstrated defect and implementation

Native Fabro hooks charged MissionLedger before admitted tool use. Deterministic
structured runners called the registered operation handler directly, leaving
their tool executions outside that shared mission count. Both standard and
semantic inspection also directly invoked check_inspection. In addition, direct
structured calls skipped the existing development verification-attempt guard.

- bee02a7 shares afo.tool_accounting.charge between the native hook and structured
  runners. The helper reuses the existing ledger/transaction/counter identities;
  it introduces no store, scheduler, authority or new MCP operation.
- c817ae9 uses the existing development_execution.verification guard before and
  after structured verification handlers. Failure/unknown work retains its charge.
  Denied admission returns and journals a normal BLOCKED tool envelope with
  handler_executed=false. It cannot supply tool PASS evidence.
- c8daeb1 routes standard and semantic inspection receipts through the same
  registered tool dispatcher. Inspector adjudication, schemas, full checklist
  criteria and release policy are unchanged.

Successful and failed executions debit once before entering the handler. Native
hook replay uses its existing event identity; structured calls use the existing
ToolContext invocation identity. Concurrent callers cannot both spend the last
mission slot. A handler crash is not refunded and a restart does not refill it.
A terminal task with unresolved native work keeps its held inference lease.

Workspaces without durable mission binding keep their existing accounting
behavior. Invalid/duplicate-key/dangling-symlink bindings refuse before execution.
Inspection budget refusal creates no inspection record. Result journals carry
mission/job/event references when a debit was accepted.

## Historical uncertainty

Previous tool counts can omit these direct structured operations. This source
fix is prospective. No historical journal, inspection or budget was rewritten;
no debit was fabricated or refunded. On host recovery, audit original operation
receipts/journals and the actual ledger before any explicit, deduplicated
historical reconciliation. Keep incomplete historical tool accounting explicit.
The original conservative token charges and UNKNOWN usage remain intact.

## Verification and scope

At clean source **c8daeb18d3b6afba51219d23562448ef17a56855**, **109 checks
passed, 1 explicitly skipped, 0 failures/errors** in 147.421 seconds, with 0 model calls.
[XML](pytest-c8daeb1.xml), [exact command](commands.txt), [status](status.json).
The one skip is the deliberately disabled live Fabro agent test.
Earlier overlapping cohorts are not added to this count.
All seven changed Python files pass Ruff. The C test driver is a synthetic project fixture with an independent
expected return value. Its wrong-value mutant fails the real host test; correction
passes, and both consume the same cap. This is no STM32 hardware qualification.

The standard/semantic inspection tests reuse genuine reviewed input but explicitly
substitute model verdicts. They test admission/receipt integrity, not model
competence. The live Fabro agent test is deliberately NOT_RUN on this workstation;
actual Qwen execution belongs on Omniverse2. Fixture counts are not product
success or operational availability evidence.

## Remaining work

IE-T004 remains partial: no positive dependency-independent continuation has been
qualified. The current M1 has no accepted downstream test/oracle artifact to
justify skipping its unresolved SWE.1 boundary. Adding a broad advisory edge would
not prove independence. Keep dependent work blocked until real input/inspection
evidence permits it.

Omniverse2 remains owner-confirmed offline. Former live grants expired
2026-10-29T05:00:00Z; none was renewed. This candidate is undeployed and its native
role qualification is NOT_RUN. After host recovery: reconcile actual operator
intent/liveness/leases and cumulative costs; audit historical direct tool calls;
prepare current exact-source authority, reprepare the approved input and continue
the same M1 mission through normal serial intake and all quality gates.

Formal progress remains 30/58; scoped completed incremental IDs remain
IE-T001/002/003/005/006/007. IE-T008 is blocked/unaccepted, IE-T009 unrun.
Learning benefit and 24/72/168-hour operational availability remain unqualified.
