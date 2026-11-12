# Development SSA/TAA signature deferral

Owner decision **OD-2026-10-27-02**, 2026-10-27, Jefferson Nascimento:

> about the safety signature, I want it to be ignored during the development of forge-c

This instruction supersedes earlier handover requests to sign SSA/TAA before
development work. The signed-document register and the drafts are unchanged.
It is approval of this development policy, not a signature of either document.

New work orders default to `DEVELOPMENT`. Preparation binds the owner policy,
its source/hash and the unchanged formal package-policy hashes into the manifest.
The existing finalizer derives a development package policy which defers only
`safety/software_safety_analysis.md` and `safety/tool_assurance_assessment.md`.
It adds mandatory policy and deferral records to the sealed archive. It does not
generate signed documents, stamp drafts as approved, change ASIL B or claim a
safety approval. Its purpose remains visible in the finalizer result and quality
report. ASIL scopes never acquire a QM/N/A disposition from this exception.

All phase inspections, code/static checks, tests, coverage, traceability, resource
budgets, target verification, completed-run and no-open-findings requirements stay
in force. Development READY still needs their evidence. In enforcing assurance,
HSI/allocation and other issues remain blocking; only the two document deferrals
are omitted from blocking findings.

`workorder --purpose FORMAL_REVIEW` selects the strict existing package policy.
Historical work orders without the bound development policy keep their original
rules. Sealed archives remain write-once. A bare purpose flag cannot activate the
exception; altered, revoked or stale bindings cause a blocking finding and strict
packaging. Purpose and policy are part of validated brownfield-resume identity.
Changing this policy does not reset a mission, historical attempts or expenditure.

The controlling file is `config/factory/development-safety-policy.yaml`. Its
current owner decision applies globally to new Forge-C development work orders.
The ordinary run/campaign authority, release/disposition and patch-bundle signing
paths retain their existing requirements. No persistent runtime is activated by
committing this change.

Job 050 remains 0/3 READY at its original revision. Its SWE.1 semantic/output
failures need engineering fixes; this signature deferral does not repair them.
New genuine runs need recorded configuration identities including purpose and
the policy hash. Comparing a strict historical package to a development package
cannot establish model improvement from a changed documentation requirement.
Fresh inspector baselines still need genuine independent engineering evidence.
