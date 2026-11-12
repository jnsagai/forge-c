# Bounded same-order maintenance rework qualification

Exact tested implementation **8f215118168515db97346b49dcb8d648ca80625a**
(parent e528734d61cdcf4adc2448f1d1f4d795c0ec6fba). External Codex implementation,
not Qwen-authored engineering repair. **Not deployed** at this checkpoint.

The existing independent review worker seals a bounded retained child after a safe
receipted REJECTED maintenance candidate. Existing Conductor admits it under the
same order, mission, cumulative counters and deadline. Child artifacts are exact
Git blob bytes, with immutable intent, full bounded independent feedback, registered
symptom signature, case/seed/reference hashes and atomic case publication.
Partial seeding resumes; ready children are never reseeded over new model edits.
No new scheduler, memory store, authority or autonomous deployment is introduced.
Opt-in maintenance.max_retained_reworks defaults0, accepts0..8.

Current operator intent, grant, source, policy, parent quiescence, independent
decision, receipt, protected paths, verification lease and remaining capacity are
checked. Exhaustion/oversize/unsafe results remain explicitly blocked. Publication
transport failure is recorded separately while retaining independent eligibility;
it cannot trigger an engineering retry. Existing deployment gates remain.

## Executed results

- Exact revision local **151PASS/0FAIL/0ERROR/0SKIP**,32.664seconds.
- Exact revision Omniverse2 native bubblewrap **34PASS/0FAIL/0ERROR/0SKIP**,
 223.847seconds; source clean before/after, zero model calls, no GPU/network.
- Native bounded verifier:4CPU affinity20..23, nice5,1.5GiB address space,
 240CPU seconds and360wall seconds. Production source/services unchanged.
- Ruff and static specification/contracts/design checks PASS. Static validation
 is **SPEC_CONTRACTS_ONLY_NOT_RUNTIME**, not operational/model qualification.

Local cohort: pytest -q -p no:cacheprovider on test_afo_maintenance_rework.py,
test_afo_review_disposition.py,test_afo_retained_work_unit.py,
test_afo_local_autonomy.py,test_da014_maintenance.py,test_da014_launch_boundary.py,
test_afo_m5_maintainer.py,test_mcp_input_schema_metadata.py,test_da014_integration.py,
under the existing offline environment. Exact log/XML retained here.

The executable native helper and provenance preserve exact command, bundle hash,
environment, bounds and revision. Native tests cover MCP schema, retained task,
review disposition and19new retained-rework cases, including real worker-to-child
dispatch with a synthetic correct patch, partial seed restart, CRLF preservation,
signature feedback, receipt tamper, pause, capacity/iteration exhaustion and
publication failure. Synthetic fixtures are not live Qwen capability evidence.

## Earlier failures retained

The first native attempt exceeded180wall seconds before producing final XML.
Its error is retained; process termination was confirmed before the bounded retry.
The retry showed successful progress, with observed journal-commit disk waits.
Local initial failures were fixture bugs: isolation availability patched too
broadly; global Popen stub intercepting Git; operator intent parent permissions.
Fixtures were corrected; initial failing XML is retained. One incorrectly named
test path caused collection exit4/no tests; corrected cohort148PASS, then final
151PASS after additional cases. No failing test was reclassified as runtime success.

Actual Qwen V7 separately passed scoped causal/frozen checks. This software
qualification is not proof of live automatic rework, full LL/HAL success, broad
self-healing, learning benefit or24/72/168-hour operation. Formal tasks30/58
unchanged. Activate only with exact scoped authority and test a natural rejected
candidate through this loop. Remaining RCC product capacity must be reconciled
without resetting its historical mission.
