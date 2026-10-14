# Offline Reviewer Checklist — Not Part of Fabro Execution

The human reviewer conducts an offline review after receiving the package. This checklist is not executed as an interactive stage in the automated workflow.

**Package identification:** Run ID ______  Package SHA-256 ______  Target MCU ______  Reviewer ______  Date ______

- [ ] Independently verify ZIP SHA-256 against separately transferred trusted checksum.
- [ ] Verify SHA256SUMS for every evidence file and inspect the package manifest/gap report.
- [ ] Validate HSI, MCU baseline, allocated software safety requirements and their authenticity.
- [ ] Examine all SWE.1–SWE.6 workproducts, source code and code-generation provenance.
- [ ] Review bidirectional traceability and consistency of requirements, architecture, design, tests and results.
- [ ] Review checklist criteria, independent AI inspection results, closure evidence and process limitations.
- [ ] Investigate all open and previously reopened findings, waived/nonapplicable rules, reasons and tool limitations.
- [ ] Verify MISRA C checking-rule coverage and legitimate deviation approvals; evaluate tool confidence/qualification assumptions.
- [ ] Review static analysis, target verification, coverage (including MC/DC where applicable), fault injection, timing and memory/stack budgets.
- [ ] Independently inspect and, where required, repeat critical software/safety verification on qualified environments.
- [ ] Determine adequacy of the safety case/evidence package for the actual ASIL B item and its hardware/software context.
- [ ] Record approval/rejection/rework findings via the organization's authorized safety and ASPICE processes.

**Disposition:**  [ ] Rejected/return for rework  [ ] Accepted for further assessment  [ ] Additional evidence required

Safety authorization and production release are separate organizational decisions; neither occurs inside the dark factory.
