# Bounded hash-bound maintenance edits

Exact implementation/native revision **ab46545c1cfb7ffd90fb09715b6715b7d21ad242**.
Local maintenance cohort61PASS (20.473s); final registry/preflight cohort41PASS
(1.818s). Omniverse2 native66PASS (246.900s), source clean before/after.
Native command/provenance and full XML/logs retained. One pre-existing rootless
Podman-specific nested credential test is explicitly deselected in the outer
bubblewrap verifier; it passed in the local61cohort. The native suite itself runs
with network/GPU off, UID2001,4CPU,1.5GiB address space,240CPU/480wall seconds.
It includes source edits, remaining M5 broker tests, retained work units, rework,
review disposition and MCP schema metadata. No Qwen or model calls occurred.

The existing maintenance MCP adds edit_source: SHA256 compare-and-replace of one
unique exact UTF8 fragment (8192bytes each). It retains the source allowlist,
protected-path/symlink/size checks, serializes with submit, refuses sealed cases,
and atomically fsyncs/renames changed bytes. Stale, ambiguous, concurrent, oversized,
protected and failed-replace cases retain original bytes. Existing write_source
uses the same lock/atomic publication. Registry/skill/render template/hash updated.

The first local61cohort had2FAIL because the changed skill lock was not refreshed;
original result retained, corrected lock gives61PASS. Ruff, specification/contracts
and14static design tests pass separately; static validation is not runtime/model
qualification. This is an external deterministic tool improvement, not a Qwen-
authored engineering fix or proof of self-healing. No feature task completion added.
