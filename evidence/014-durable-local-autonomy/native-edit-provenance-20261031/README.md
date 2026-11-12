# Native source edits: verified external provenance, unchanged live runtime

**The external audit confirms the frozen candidate came from a native source
write followed by six accepted edits. The live factory remains on0e342eef;
its internal exact-write reporter retainsUNVERIFIED_EDIT_CHAIN. DF-M1 remains
pending terminal packaging and the complete external audit.**

Native01M67R1HNE9TKPWCYJ2SVKEPJS produced header9aa11db1... and passed its
preregistered independent functional checks at01:15:07UTC. The actual source
author used write_file and then edit_file. The existing reporter compared only
whole-write payloads to final bytes, so legitimate edits made provenance
conservatively unverified. No model or operator correction was needed to the
already passing driver for this metadata issue.

## Implementation and exact tests

**13d734afb64da594d9694b72ba5ce4ac0e906360** reconstructs accepted source writes
and unambiguous literal edits, matching completions by node/visit/stream/call
identity and checking every declared candidate hash. The packet includes the
source anchor and literal edits with before/after hashes for offline inspection.
Wrong roles, incomplete calls, opaque patches, ambiguous replacements, missing
anchors, altered final bytes or incomplete candidate coverage remain unverified.
An unrelated document write does not invalidate a frozen source proof. Existing
pure-write classification remains compatible. This proves source origin only.

**30371da548bad2790a9f3c21dafc8964047ce06d** adds the existing-module CLI step
`source-provenance`. It reads the native events and candidate hashes, checks
candidate stability across the observation, and records separate producer and
auditor revisions. It performs no inference, verification execution or workspace
write. Missing candidates and concurrent changes remain unverified. The CLI
explicitly reports functional verification asNOT_EVALUATED_BY_THIS_AUDIT.

Exact parser cohort: **85PASS**. Exact CLI-inclusive cohort: **88PASS**, with
zero failures/errors/skips. Focused parser/integrated native cases21PASS and
three CLI isolation/missing/race casesPASS. Counts overlap and are not additive.
Ruff and specification validationPASS. The known inherited Feature009 RCC
graph-golden failure remains outside these cohorts; no golden was rewritten.
See [exact revisions, commands and scopes](source-qualification.json).

Failed-before receipts distinguish three observations: the first13failures were
API scaffolding before the helper existed; the meaningful exact-write-only
baseline then had15PASS/2FAIL, reproducing the missing edit-chain support;
one later regression exposed an unrelated pending-document false negative.
Raw failed JUnit is retained as deterministic gzip, with readable whitespace
views and representation hashes. These are synthetic framework tests on loop10,
not local execution of Qwen-generated C or model qualification.

## Real read-only audit on Omniverse

The tested auditor was staged in an [isolated checkout](auditor-stage.json),
without changing the active source or operator intent. At01:45:00UTC it ran
inside the correct native namespace against the actual workspace and native
API. Producer revision0e342eef, auditor revision30371da5 and auditor moduleSHA
8ceca6bd... are separate, recorded facts.

The [audit packet](native-source-audit.json) contains an actual successful whole
source write and six accepted literal edits. Replaying them yields exactly
9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e, matching
the frozen candidate and its independent verification receipt. Candidate hashes
before/after the audit match. The [immutable remote receipt](remote-audit-ref.json)
has SHAca5c850a...; its raw local transfer matches. Compressed original bytes
and a semantically identical readable JSON view are preserved. Source payloads
are workproduct evidence; no hidden reasoning or raw prompts are published.

The separate [source mutation event extract](native-source-mutation-events.json)
preserves both whole writes and all six edits, including the earlier overwritten
source version, with actual completion flags and native event hashes. All eight
completed successfully in df_author_0. It supports offline replay and preserves
the ordinary within-author history separately from numbered correction rounds.

This is external qualification evidence. The active job, source, internal
authorship flag and later archive are not hotpatched or relabeled. The audit
does not establish functional correctness, release eligibility, model-role
competence or factory self-healing. Independent functional proof remains the
separate preregistered compiler/oracle/simulation result.

Reusable command, executed on Omniverse from the isolated auditor checkout with
its PYTHONPATH/FORGE_REPO_ROOT and the workspace's actual native namespace:

```text
python -m forge_factory.delivery_first --workspace <workspace> --step source-provenance
```

The same command can be repeated after terminal packaging; retain each immutable
observation and compare final bytes. It creates no controller, scheduler, memory
store, grant or work order.

## Ongoing pipeline

The same native advanced to SWE.3 author at01:45:20UTC; its header remains frozen.
Actual [SWE.2 tool receipts](swe2-tool-observations.json) show a nonnumeric register
offset FAIL followed by the author's correction to PASS, then valid static and
dynamic diagrams covering both APIs. A first semantic inspectionPASS was followed
by another FAIL with two major findings; both remain recorded. This is ordinary
job-local correction, not a measured learning benefit or accepted SWE.2 phase.
The generated process drafts contain12SWR entries; independent functional claims
remain bound to the preregistered scope, not arbitrary generated additions.

Next: let the unchanged native finish. Audit final-receipt inclusion, archive
integrity, complete source/model/scope provenance, all-six outcomes and observed
interventions before any fresh comparable trial. Keep source0e342eef/profile3
stable if used for repeatability, and pin this external auditor separately.
Original deadline **2026-10-31T07:57:59Z** and mission history remain unchanged.

Supports DF-T005/008/009 evidence and DF-AT-004/009. No original DA checkbox,
DF-M1/DF-M2, full LL/HAL, production, ASPICE assessment, generic-driver, learning
or24/7 claim is made by this increment.
