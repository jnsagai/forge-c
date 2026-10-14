# MISRA C assessment protocol (open-source toolchain)

**Checker:** Cppcheck open-source `misra.py` addon. MISRA rule texts are NOT embedded in this repository. The addon targets MISRA C:2012 and amendments as supported by the installed version; the project must document rule applicability and the exact licensed baseline. This checker does NOT implement all rules.

## Mandatory review dataset

One row per applicable rule: `rule_id`, `edition/amendments`, `applicable`, `checker_supported`, `checker_evidence_path`, `checker_version`, `violation_count`, `classification`, `deviation_record`, `manual_review_evidence`, `reviewer`, `review_date`, `approval_status`.

Allowed classifications: `automatic_pass`, `automatic_findings`, `manual_review_required`, `deviation_proposed`, `deviation_approved`, `not_applicable_with_rationale`, `not_assessed`.

**Fail-closed:** absence of a violation from Cppcheck is not a PASS for unsupported guidelines. A checker cannot mark a required manual review complete; the human reviewer must use the authorized MISRA rules publication. Non-machine-verifiable coding constraints, design-level concerns and hardware-access deviations demand manual assessment.

## Example Cppcheck invocation

`./scripts/run_oss_misra_subset.sh` executes the open-source addon against the generic RCC example. Missing Cppcheck or addon causes an explicit error. To supply the addon location, set `CPPCHECK_MISRA_ADDON=/path/to/addons/misra.py`.

No result from that script may be interpreted as an overall MISRA Compliance summary without the rule matrix, deviation record and required approvals.
