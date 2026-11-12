# Future worker promotion — proposal only

**Status:** NOT_AUTHORIZED / NOT_IMPLEMENTED. This document grants no authority and does not change AFO-FR-053, the constitution, maintainer grants or deployment policy. Core Feature 014 implementation and qualification do not depend on approving this proposal.

Current runtime automation can detect defects, run approved operational recipes and prepare/evaluate candidate patches only within the existing maintainer allowlist. Protected AFO/CRE, skills, registries, oracles and policy require externally authorized engineering. Even an eligible CRE result is not deployment permission.

## Possible future boundary

A separately reviewed policy revision could permit automatic activation of specific non-protected worker modules and already qualified adapter configurations, mediated by an independent deployment broker and verifier. The mutable worker would have no write authority over authorization, accounting, inspection gates, holdouts, evidence retention, deployment credentials or the bootstrap recovery kernel.

Required design obligations before any such revision:

1. Enumerate exact mutable paths, interfaces, maximum change scope and prohibited transitive dependencies; no broad AFO/CRE allowance.
2. Require a reproducer failing on baseline and passing on candidate, independent regression/negative/golden/holdout checks and policy/oracle integrity.
3. Bind evaluation to immutable source/build/runtime identities and an explicit signed promotion envelope; qualification alone grants nothing.
4. Use shadow evaluation and an isolated canary with explicit useful-work and defect-detection criteria. No candidate may modify its own acceptance criteria.
5. Use compatible A/B worker versions and stable persistent schemas. Database migrations, safety authority and trusted-kernel changes remain external.
6. Authorize exact activation and rollback transitions in advance; confirm rollback and reconcile in-flight effects. Ambiguity blocks promotion.
7. Rate-limit evolution, retain negative outcomes and versions, and evaluate unseen cases to detect benchmark overfitting.

Feature 014 may produce this review package and candidate architecture. It MUST NOT add a dormant auto-promote flag, silently broaden runtime grants, or activate this lane. The external implementation engineer may fix protected source through normal reviewed development; that is a different authority from runtime self-modification.
