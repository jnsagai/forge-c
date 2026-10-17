# Contracts — EASA Feature 006

This directory contains 13 JSON Schemas and illustrative **synthetic** examples. None is live execution evidence. The `iso26262-6-2018-methods.working.yaml` catalog has exactly 47 ASIL B `++` **provisional** entries and MUST be reconciled against an approved licensed ISO source before normative claims. Tables 1–15 are inventoried, Table 12 contains zero ASIL B `++` in this working index; Clause 6 uses textual requirements rather than a `++` table.

`enhanced-techniques.yaml` has 30 additional Forge-C engineering assurance measures, which are **project-defined** and must never be described as ISO-mandated `++`. `assurance-policy.example.yaml` starts `OBSERVE_ONLY`, does not change ASIL and does not authorize SUP/MAN workflows, autonomous safety signoff, or missing-evidence waivers.

For real runtime: generate signed/profile-hashed method applicability, capture actual tool output with hardware fidelity labels, verify independent oracle origins and holdout access, assemble CAE claims with counterevidence, and let the original independent release finalizer adjudicate readiness.
