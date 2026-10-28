---
title: "SWE.1\u2013SWE.6 workflow"
description: "## Intake first"
---

## Intake first

Approved requirements, target reference documents, scope, and applicable safety inputs enter an isolated work-order workspace. Hashes connect each input to the run. Preflight checks the available roles, tools, permissions, and dependencies.

A failure is visible as a blocked outcome. The factory does not fabricate an input or substitute an unapproved MCU register definition.

## Six software engineering phases

| Phase | Workproduct focus |
| --- | --- |
| SWE.1 — Requirements analysis | Traceable software requirements and requirement cases. |
| SWE.2 — Architectural design | Interfaces, responsibilities, allocation, and architecture. |
| SWE.3 — Detailed design and construction | Unit specifications, detailed design, and C implementation. |
| SWE.4 — Unit verification | Tests against unit specifications and associated coverage evidence. |
| SWE.5 — Integration and verification | Integration behavior and evidence for component interactions. |
| SWE.6 — Software qualification testing | Verification of software behavior against software requirements. |

Within a phase, an author writes the workproduct, deterministic tools check it, a separate inspector reviews it against a versioned checklist, and the gate routes the result. Rework is bounded. A finding against an earlier baseline can require downstream revalidation.

## Freeze and inspect

The inspector examines a defined revision. Identity separation, frozen workproducts, checklists, and recorded verdicts support independent inspection. An inspector's prose does not override a failed tool result.

The checks themselves depend on the layer, delivery mode, peripheral profile, target setup, and applicable assurance scope. Read the [source checklists](https://github.com/jnsagai/forge-c/blob/main/docs/SWE-CHECKLISTS.md) for their actual criteria.

## Finish with evidence

The Release Manager collects the workproducts. The deterministic finalizer evaluates the available gate evidence and seals a review candidate or blocked package. The external supervisor also handles runs that terminate without packaging.

[Review the package](/docs/guides/offline-review/) outside the factory. The workflow implements engineering process structure; it does not confer an Automotive SPICE assessment result.

## Watch the recorded workflow

The [interactive workflow replay](/#workflow-demo) follows the actual 21 October 2026 IWDG HAL rc4 gate events, including two rework decisions. The same sequence is available as a captioned video. It is a time-compressed visualization of recorded evidence, not a live run or a screen recording.

[Open the workflow video](/media/workflow-replay.mp4) · [Read the source gate log](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/runs/RC1/WO-0009B-STM32N6-IWDG-HAL-rc4/gate-log.jsonl).
