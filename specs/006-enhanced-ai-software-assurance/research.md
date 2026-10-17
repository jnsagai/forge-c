# Feature 006 — Standards and assurance research notes

## Normative authority and copyright

- **ISO 26262-6:2018** (edition 2) remains the published software-level ISO standard: https://www.iso.org/standard/68388.html. ISO/DIS replacement is under development; do not silently upgrade.
- Its ASIL `++` denotes *highly recommended*, not a blanket instruction to perform all alternatives; method applicability, combinations and explicit rationale must be evaluated from the controlled edition.
- Repository's 47-method matrix is a **working reference index of concise original descriptions** from preliminary secondary cross-checks and previous engineering analysis. It is NOT the copyrighted full tables. Before using it for normative compliance statements, a competent authorized reviewer must validate every row, table, ASIL column, footnote, alternative group and exceptions against a legitimately obtained controlled ISO 26262-6:2018 copy. No redistribution of copyrighted text.
- Public secondary cross-checks (do not treat them as normative authority):
  - https://public-docs.ferrocene.dev/main/certification/core/norm-mapping/iso-26262/iso-26262-6-method-tables.html (Tables 5–9, B/D; development preview)
  - https://www.ansys.com/content/dam/amp/2022/april/webpage-requests/2022-ansys-scade-handbook.pdf (architecture Table 4 comparison)
  - https://www.mathworks.com/help/slcheck/ug/assess-standards-compliance-of-simulink-model-testing-artifacts-with-iso-26262.html (requirements test methods)
  - https://www.blackduck.com/resources/white-papers/iso26262-guidelines.html (several method crosswalks)
- **ISO/IEC/IEEE 15026-2:2022** describes the *structure* and terminology of assurance cases, not a guarantee that CAE content is correct: https://www.iso.org/standard/80625.html.
- **Automotive SPICE:** retain current Forge-C approved v4.0 baseline; the VDA QMC 4.1 guideline now exists, but migration would be a separate project decision: https://webshop.vda.de/QMC/en/automotive-spice-guideline-edition_2026.

## Automotive SPICE SWE crosswalk caveats

- ISO26262 Part6 clauses do NOT map to Automotive SPICE names one-to-one; use SWE.1–SWE.6 as *execution stations*, not claim identical process objectives, assessments, rating or deliverables.
- SWE.1 corresponds primarily to Part6 clause6 safety requirements; clause5 general guideline checks apply across several stations.
- No new SUP or MAN processes requested. Existing configuration/incident/metrics infrastructure may be used as tool services only.

## Assurance overmatch engineering policy

The *product* target may remain ASIL B while ENHANCED selects additional risk-based C/D-favored analyses where feasible. This internal profile is not ASIL D, is not normative 'ASIL B + 1', and cannot bypass missing safety lifecycle inputs. A project needs explicit selected methods, applicability and evidential sufficiency; source methods remain the competent-approved safety allocation/requirements.

**Core extra checks:** independent oracle derivation, mutation testing, selected MC/DC, register semantics/errata, concurrency/resource bounding, negative and fault injection, requirements-execution traces, evidence/counterevidence CAE, independent quality gates and genuine target fidelity.

- **Statement/branch coverage**: ASIL B `++` entries Table9; no universal mandated numeric 100% threshold.
- **MC/DC**: ASIL B `+`; chosen for specific risk and toolchain capability, not silently a requirement of ASIL B.
- **Mutation testing**: project-enhanced metric; only meaningful if mutant operators/population, equivalent mutants, harness and actual killed/survivor results recorded. Not a claimed ISO table method.
- **Renode** simulates a target/model with limited peripheral semantics; not by definition HIL or evidence of silicon/PCB electrical behavior.
- **Tool qualification**: clarify tool confidence/evidence and applicability (ISO 26262-8); this feature does not create SUP/MAN workflows or author a false qualification certificate.
- **Assurance case**: evidence links, defeaters and counterarguments require independent technical scrutiny; layout in CAE format doesn't make weak evidence strong.

## Empirical baseline / case study

The user-provided run report (2026-10-17, DeepSeek r80–r107, excluding cancelled r98) states 12/27 runs passed six SWE process gates and 10/27 had only the two owner-deferred safety documents missing. There were 43 inspection checklist entries, with 7 recomputed by deterministic checks; more independent evidence is needed to estimate adequacy. LL runs most often stopped at SWE.3 and HAL at SWE.4. R101 LL and R102 HAL are selected as read-only initial audit cases.

**Do not infer that a passed gate proves product correctness**, or that a failed gate means an assessor rated the entire process poorly. These are execution-level claims. For a competent audit, materialize exact sealed archives, compare hash and tool provenance, and inspect selected source-to-requirement-to-oracle-to-hardware semantics.
