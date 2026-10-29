# Trusted retained-maintenance task metadata

External controller implementation: `0da4616a4084b98899af63b6e494b0b2343bedc1`.
Canonical integration fixture correction / tested revision:
`c1f1378733af388b50ba1d6e5de37c16f3c0a9ee`.

The existing maintainer launch derives changed/new candidate paths and hashes
from Git, checks existing protected paths and source bounds, and persists an
immutable work-unit record. A fixed controller instruction tells the agent to
rework retained files and resolve independently recorded findings. Incident and
source prose cannot become trusted instructions or expand tool permissions.
This uses the existing Conductor/Fabro/Maintainer path, with no new scheduler or
memory store. It does not edit or approve the Qwen-authored repair.

Local affected cohort: **85 PASS**, zero failures/errors/skips after supplying
the real Fabro binary. Exact clean native Omniverse2 source: **9 PASS**, including
actual MCP schema/call checks and launch-to-generated-workflow integration.
Native tests use bubblewrap, one CPU, 1 GiB address space, 45 CPU/60 wall seconds,
no GPU devices or network, and no model requests. Initial 8 PASS/1 FAIL native
result is preserved: an invalid integration-test job identity was rejected by
the correct production guard. The test was corrected; the guard was unchanged.
The initial local missing-binary environment failure is also retained.

**NOT_DEPLOYED** at this checkpoint; runtime remains92c49a6. This is a bootstrap
change authored externally, not Qwen self-healing. Its effect on real Qwen repair
quality is **NOT_RUN**. A new source-bound trial needs a fresh finite authority
window: the previous22:25:58UTC window has expired. No old grant was renewed,
mission reset, candidate accepted or formal task completed here.
