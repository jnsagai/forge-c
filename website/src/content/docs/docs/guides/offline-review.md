---
title: "Review a sealed package"
description: "## What the statuses mean"
---

## What the statuses mean

`READY_FOR_OFFLINE_REVIEW` means the run satisfied its **configured** gates. It is an invitation to review the evidence, not a release approval. `BLOCKED` means required evidence or checks are missing or failed; the package preserves available work and findings.

A zero-gap pilot result is scoped to that run's configuration and recorded owner decisions. It does not establish suitability for another target, safety allocation, or production use.

## Verify integrity

Obtain the archive and expected checksum through the project's agreed handover procedure. Verify the archive's outer checksum, then its embedded member hashes.

After loading the factory environment:

```python
from pathlib import Path
from forge_factory.release.finalize import verify_archive

result = verify_archive(Path("review-package.zip"))
print(result)
```

This is an example invocation; replace the archive name with the package you received. A hash match is an integrity check, not an engineering judgment.

## Read the package

1. Start with `REVIEW_SUMMARY.md` for the status, scope, and findings.
2. Inspect `missing_artifacts.json` and `evidence/quality/final-gates.json`.
3. Read `evidence/safety/known_limitations.md` and the applicable safety scope and owner dispositions.
4. Follow traceability from approved inputs through requirements, design, code, tests, and inspections.
5. Examine raw tool evidence, versions, target assumptions, exclusions, and any deviations.
6. Record independent engineering and safety review through your organization's release process.

The exact package members depend on the work-order profile and available evidence. The landing-page archive view is illustrative.

## Resolve blocked work explicitly

A missing document, failed test, unresolved conformance finding, unavailable tool, or exhausted budget must remain visible. Correct the actual issue and follow the documented rework or new-run procedure. Protected release and safety policies are outside automatic repair authority.

Source: [release finalizer](https://github.com/jnsagai/forge-c/blob/main/factory/python/forge_factory/release/finalize.py) and [operations review procedure](https://github.com/jnsagai/forge-c/blob/main/docs/OPERATIONS-v0.4.md).
