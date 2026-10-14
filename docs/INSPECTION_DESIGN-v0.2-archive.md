> HISTORICAL: v0.2 design reference only. See active v0.5 architecture and current specs/checklists.

# Forge-C v0.2 — Independent Formal Inspection Design

**Status:** design proposal only, not implemented or validated in the Fabro executor.  
**Editable source:** `Forge-C_Fabro_Inspections_v0.2.drawio`, with six tabs.  
**Baseline:** preserves the current OSS bootstrap tab; replaces candidate workflow schematic with six independent inspection loops.

## Required behavior

1. After every `SWE.1`–`SWE.6` author stage, Fabro snapshots all required workproducts, hashes them, and assigns a different reviewer agent (independent role and isolated context). If reviewers use the same model weights, this remains agent-role separation—not organizational independence under ISO 26262 or SUP.1.
2. The inspection agent reads a versioned checklist (`checklists/SWE.n.yaml`), input/output baselines, upstream requirements, links to evidence, and prior findings. It must classify **every** mandatory question `PASS`, `FAIL`, or `N/A` with justification. N/A must be justified and accepted by the applicable policy.
3. The reviewer emits one immutable **inspection record** and zero or more **finding records**. Each finding has unique ID, severity, workproduct revision/hash, exact source/evidence link, owning phase, proposed action, closure criterion and status.
4. A deterministic gate—not the inspecting LLM—decides whether review may close. Open major/critical issues always block. Minor issues require a documented disposition under human-approved policy; safety-related waivers cannot be autonomous.
5. If rejected, Fabro routes findings back to the **responsible author agent**, which makes changes on a new revision, reruns relevant deterministic tests, and **resubmits for inspection**. Do not mark an issue resolved merely because the author claims a fix: require the reviewer to verify evidence and close the finding.
6. If a finding indicates incorrect upstream requirements, architectural allocations or register assumptions, create a SUP.10-like change request and a change-impact record. Reopen the originating SWE phase, invalidate affected downstream baselines and review records, and rerun affected inspections and deterministic verification.
7. Bound autonomous retries to three cycles (configurable). Exhaustion, conflict, safety-critical ambiguity, or repeated no-progress creates a **HOLD** requiring human triage.
8. A phase's **accepted inspection record** gates progression to the next SWE phase. All six accepted records join the candidate evidence package, alongside traceability and raw tool logs. The separate release process still requires human safety authorization and target/HIL evidence.

## Reviewer/author separation

- Agent identity and execution context must differ; an agent must never inspect its own workproduct.
- Reviewers should start from the frozen workproduct, checklist and authoritative inputs, not the author's unchecked rationale or self-assessment.
- An inspector can open or recommend closure of a finding but **must not edit the authored workproduct**.
- Fabro control code checks identities, completeness, revision/hash freshness, findings state, and reinspection coverage.
- Human review and organizational QA independence remain separate responsibilities.

## Inspection workproducts

| Workproduct | Suggested ID | Content |
|---|---|---|
| Checklist baseline | INS-CHK-SWE.n | Version, mandatory criteria, rationale, evidence types |
| Inspection assignment | INS-ASG-nnnn | Author and inspector IDs, independence check |
| Frozen input snapshot | INS-BASE-nnnn | Revision and SHA-256 of each affected workproduct |
| Inspection record | INS-REC-nnnn | Per-check verdict, cited evidence, summary outcome |
| Finding record | INS-FND-nnnn | Severity, source, owner, change, reproduction/acceptance |
| Corrective action & verification | INS-COR-nnnn | Diff, new revision, rerun results, reviewer confirmation |
| Impact analysis | INS-IMP-nnnn | Reopened SWE phase, invalidated descendants, tests/reviews needed |
| Closure certificate | INS-CLOSE-nnnn | Accepted revision, no blocking open findings, timestamp/identity |

## Gate expression (design pseudocode)

```text
require(author_id != reviewer_id)
require(snapshot_is_frozen && sha256_verified)
require(checklist_version_is_approved)
require(all_required_items_have_evidence_and_verdict)
require(no_open_critical_or_major_findings)
require(all_other_findings_formally_dispositioned)
require(changed_baseline_has_complete_reinspection)
require(no_stale_upstream_or_downstream_dependencies)
if fail:
    emit_findings(); route_to_author_or_upstream_origin()
    if retries >= max_rework_cycles: human_hold()
else:
    emit_inspection_closure(); enable_next_phase()
```

## ASPICE / safety interpretation

This added inspection discipline supports SWE workproduct quality and is compatible with **SUP.1 quality assurance**, **SUP.9 problem resolution**, **SUP.10 change request management**, and **SUP.8 configuration management**. It is a project-defined formal inspection method; Automotive SPICE 4.0 does not make a specific proprietary inspection workflow mandatory. Automated LLM review is not, by itself, independent safety verification or ISO 26262 ASIL B compliance evidence.

## Existing implementation status

`workflows/oss-local-candidate.fabro` in the original Forge-C v0.1 project does **not** implement the loops shown in this v0.2 diagram. The `.drawio` diagram and YAML checklists are a **design update**, not an executable Fabro migration. The OSS host bootstrap tests in the previous package remain unchanged.
