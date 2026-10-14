# Compliance mapping — ASPICE 4.0 + ISO 26262 ASIL B

**Important:** In ASPICE PAM 4.0 the listed *information items* are assessment indicators, not necessarily one document per item. Their sufficiency is assessed against outcomes and base practices. This map is a **proposed evidence architecture**, not a normative transcription of ISO text or a guarantee of capability level.

Official primary source: https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf (sections 4.4.1–4.4.6, pages printed 45–57).

## SWE.1–SWE.6 evidence register

| Process | Work products / information items (PAM IDs) | Factory content | Quality gate |
|---|---|---|---|
| **SWE.1 Software Requirements Analysis** | `17-00` Requirement, `17-54` Requirement Attribute, `15-51` Analysis Results, `13-51` Consistency Evidence, `13-52` Communication Evidence | Software requirements, allocated safety IDs, interface + timing + ROM/RAM constraints, feasibility/operating context analysis, review and communication logs | Upstream linkage, unambiguous acceptance, completeness, agreement |
| **SWE.2 Software Architectural Design** | `04-04` Software Architecture, `15-51`, `13-51`, `13-52` | Components/modules, external interfaces, deployment, state/modes/ISR interaction, rationale for size/timing/safety trade-offs | Reviewed architecture; design-to-SWR trace; dynamic model |
| **SWE.3 Software Detailed Design and Unit Construction** | `04-05` Software Detailed Design, `11-05` Software Unit, `13-51`, `13-52` | Unit contracts, register operations/side effects, data values/ranges, state and timing, code C/H, static/dynamic detail, trace | Compiles with locked target toolchain, design/units/code links |
| **SWE.4 Software Unit Verification** | `08-60` Verification Measure, `03-50` Verification Measure Data, `08-58` Verification Measure Selection Set, `15-52` Verification Results, `13-51`, `13-52` | Unit test specs, mock register map, boundary/fault/mode tests, code reviews, static analysis, coverage results | Selected tests pass, anomalies resolved/approved, linked raw results |
| **SWE.5 Software Component Verification and Integration Verification** | `08-60`, `06-50` Integration Sequence Instruction, `03-50`, `08-58`, `15-52`, `13-51`, `13-52`, `01-03` Software Component, `01-50` Integrated Software | Component/driver-level checks, MMIO integration with clocks/resets/ISR, integration sequence, fake bus + Renode/HwSim + HIL | Verification of component behavior AND integration behavior; interface consistency |
| **SWE.6 Software Verification** | `08-60`, `03-50`, `08-58`, `15-52`, `13-51`, `13-52` | Requirements-based software-level verification, functional/safety/non-functional test cases, target footprint/timing evidence, summary | Software requirements covered; integrated driver passes selected software verification |

Definitions in SWE.5 and SWE.6 differ from older ASPICE 3.1 terminology. Separate unit, component, integration and integrated-software results; do not collapse all results under one generic unit-test report.

### Common ASPICE activities to retain

- Review/communication evidence, bidirectional traceability with **consistency analysis**, tool/configuration IDs, baselines, impacted interfaces and closed anomalies.
- Supporting processes outside SWE are likely applicable: **SUP.1 Quality Assurance**, **SUP.8 Configuration Management**, **SUP.9 Problem Resolution Management**, **SUP.10 Change Request Management**, **MAN.3 Project Management**, and other system/safety processes as scoped.
- Do not claim SWE.1–6 evidence alone satisfies all process capability assessments. A CL2/CL3 target adds requirements regarding managed and established processes, resources, responsibilities and deployment.

## ISO 26262:2018 work product / evidence strategy

The actual mandatory content depends on the item's lifecycle, allocated safety requirements, safety plan and ASIL tailoring decisions. **Use the licensed standard and responsible safety manager to confirm the final normative checklist.** The factory targets the following evidence families:

| Reference | Proposed evidence | Gate / responsibility |
|---|---|---|
| **Part 2 — Management** | software safety activity plan, responsibilities, verification/confirmation plan, independence and release responsibilities | Safety Manager owns and signs; upstream organizational work remains external |
| **Part 4 — System product development** | allocated technical safety requirements, assumptions, HSI/hardware constraints, interface safety contracts | Upstream system/hardware owners approve; software factory cannot invent SG/TSR |
| **Part 6, clause 6** | software safety requirements specification, non-safety functional and non-functional requirements, consistency and verification | Safety allocated IDs and acceptance criteria linked |
| **Part 6, clause 7** | safety-informed software architectural design, interface/partition/freedom-from-interference assumptions, failure-handling modes, resource analysis | Architecture safety review plus approved assumptions |
| **Part 6, clause 8** | software unit design and C implementation consistent with coding guidelines and design principles | Coding standard report, detailed design, controlled deviations |
| **Part 6, clause 9** | software unit verification plan, measures, executed results, structural coverage / static analysis as justified | Independent assessment of method and coverage evidence |
| **Part 6, clause 10** | integration and verification plan/results, error handling and inter-component interactions | Integration results including negative tests and hardware interfaces |
| **Part 6, clause 11** | embedded software test plan/results on representative target and environment | Hardware confirmation and realistic time/footprint measurement |
| **Part 8 — Supporting processes** | verification and documentation control, change/config control, tool confidence assessment (TI/TD/TCL), qualification where needed, reuse/COTS assessment | Approve use-cases and documented tool confidence; not tool-wide blanket qualification |
| **Part 9** | ASIL-oriented/decomposition/dependent failure aspects if allocated to this software element | Safety organization decides applicability |
| **Other relevant parts** | safety case/confirmation evidence, hardware safety interface, supplier documentation and release integration assumptions | Ownership and acceptance defined per project |

**ASIL B is an allocation**, not a property conferred by a static-analysis pass. Not every tool requires qualification, and qualification is specific to **tool + usage + detection/impact measures + project ASIL**. Test/coverage method selection (including MC/DC, where justified) must follow the actual applicability and rationale; no universal '100% MC/DC mandatory at ASIL B' assertion.

## Minimum traceability shape

```text
Safety Goal / TSC / TSR / SYS requirement (external, immutable references)
    --> Software Requirement (SR)
    --> Architecture element (SA)
    --> Detailed design item (DD)
    --> C software unit (UNIT)
    --> Unit verification measure (TC-UNIT) --> verification result (VR-UNIT)

Software Requirement (SR) --> Software verification measure (TC-SW) --> VR-SW
Architecture (SA) --> Component/integration measure (TC-INT) --> VR-INT
```

Each link has `source_id`, `target_id`, `relation`, `reason`, `reviewer`, `baseline_id`. Views are generated in both directions from a **single canonical link database**, with consistency review independent of link existence. Upstream items outside the factory remain externally controlled and referenced by immutable IDs/baselines.

## Work product package layout (per driver release)

```text
release/<driver>/<version>/
  source/                       # C/H, ELF, map, disassembly, binary digest
  config/                       # exact MCU, variants, toolchain and scripts
  SWE.1/requirements-analysis.md
  SWE.2/software-architecture.md
  SWE.3/detailed-design.md
  SWE.4/unit-verification-plan.md
  SWE.4/unit-verification-report.md
  SWE.5/integration-verification-plan.md
  SWE.5/integration-verification-report.md
  SWE.6/software-verification-plan.md
  SWE.6/software-verification-report.md
  SAFETY/software-safety-requirements.md
  SAFETY/safety-analysis.md
  SAFETY/tool-confidence-assessment.md
  QUALITY/misra-compliance-report.md
  QUALITY/optimization-report.md
  QUALITY/anomalies-and-deviations.md
  TRACE/traceability.json
  TRACE/consistency-review.md
  REVIEWS/design-review.md
  REVIEWS/independent-code-review.md
  REVIEWS/release-approval.md
  manifest.json
```

**Release policy:** filenames are an implementation convention. Completeness is tested against ASPICE outcomes and the project's applicable ISO 26262 requirements. Release report MUST distinguish `satisfied`, `open` and `not_applicable_with_rationale` for every applicable evidence obligation.

## Acceptance for this factory's own process

- The process map above is independently reviewed against the licensed standards (gap analysis).
- Evidence is generated from versioned original results, never retrospectively invented.
- A single failed mandatory gate causes `RELEASE_BLOCKED`.
- A human Safety Manager and owner of the software item approve the release; confirmation measures/independence as determined by safety plan.
