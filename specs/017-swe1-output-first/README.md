# Feature 017 — SWE.1 output-first requirements pipeline

Status: implementation handoff; no runtime changes or model qualification claimed.
Created: 2026-11-08.
Feature branch: `feat/017-swe1-output-first`.

Deliver correct, complete software requirements with substantially less model generation. Optimize SWE.1 only, using generic driver contracts, deterministic rendering and validation, and bounded repair. First establish whether the models actually deployed on Omniverse support an effective thinking-off mode through the installed serving path. Support in upstream documentation is not deployment evidence or evidence of SWE.1 competence.

## Read in order

1. [Claude implementation handoff](CLAUDE_START.md)
2. [Specification](spec.md)
3. [Implementation plan](plan.md)
4. [Data model](data-model.md)
5. [Validation and experiment protocol](validation.md)
6. [Incremental tasks](tasks.md)
7. [Evidence and integration notes](research.md)

The first delivery is **M0–M1: trustworthy measurement and a role-specific capability experiment**. Do not enable thinking-off for both roles or launch an unattended campaign merely because the settings serialize successfully. Later milestones introduce a minimal contract, coverage obligations, semantic inspection and targeted recovery.

This is a documentation-only feature package based on remote `main` at `f6d6e526b7cdde1f9766409362918c552cec0c88`. The active Omniverse checkout can be newer or divergent. Reconcile its actual revision before implementing. Do not replace that checkout with this older documentation base; transplant this feature directory into an isolated worktree of the appropriate implementation base when necessary.

Only synthetic examples and public documentation belong in this directory. Private run archives, vendor excerpts, full prompts and raw responses remain outside git.
