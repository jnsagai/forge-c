"""RPR-113 (Omniverse2 local runs WO-F014-SWE1-IWDG-20261101-03 and WO-F014-SWE1-CRCL-20261102-L12, cloud
cross-inspection 2026-11-02): the local SWE.1 inspector correctly failed SWE1-04 because the work order allocates no
CPU or timing constraint (packets inspect__240507b5...__SWE1-04, inspect__7d0adec2...__SWE1-04). The refuter
lrtx/review.py:fact_conflicts answered "judges an input the owner recorded as NOT_PROVIDED as a failure" because
traceability/upstream_gaps.md records NOT_PROVIDED, the inspector withdrew both findings and the baseline PASSED.
The bound inspection assessment view of the same order says missing_required_constraint: OPEN_INPUT_GAP_NOT_SATISFIED
and lists "explicit measurable flash/RAM/stack/CPU/timing constraints" as required engineering evidence.

Scenario: a synthetic ASPICE-only SWE.1 workspace in scratch (manifest with the real bound assessment context of the
revision under test, a recorded NOT_PROVIDED budgets row) and the real fact_conflicts on the two recorded qwen
findings plus a control finding about the recorded HSI gap (which the context does not require and which stays
refuted). Symptom: a finding about the missing CPU/timing constraint is refuted by the recorded gap."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "a missing required CPU/timing constraint finding is refuted because the owner recorded the input as NOT_PROVIDED"

CPU = ("No CPU constraint (e.g., maximum cycle count or instruction count per public API call) is stated in "
       "workproducts/SWE.1/software_requirements.md; the manifest records budgets.api_cycle_limits and "
       "budgets.max_wait_polling_iterations as PLACEHOLDER (not provided upstream), and no SWR captures a measurable "
       "CPU limit for the driver.")
TIMING = ("Timing constraint missing: No measurable timing constraint (e.g. maximum execution time, deadline, or "
          "bounded polling iterations) is stated for the driver. SWR-011 in workproducts/SWE.1/software_requirements.md "
          "delegates wait-bounding to the caller but does not establish a measurable timing bound. The manifest "
          "upstream.issues contains 'PLACEHOLDER:budgets.max_wait_polling_iterations' confirming a timing constraint "
          "was anticipated but its value is NOT_PROVIDED.")
HSI = ("The HSI contract is NOT_PROVIDED upstream and no requirement states the approved interface contract of the "
       "peripheral.")
REQS = """# Software requirements

- **SWR-011** The driver shall not wait on a status flag; the caller bounds its polling.
  - Source: RM section 4
  - Verification: Pass when the function returns without reading the status flag in a loop.
- **SWR-013** The driver shall occupy at most 4096 bytes of flash.
  - Source: WO-BUDGET
  - Verification: Pass when the linked size is at most 4096 bytes.
"""
GAPS = """# Upstream coverage

| Input | Status as stated in the manifest | Affected SWR IDs |
| --- | --- | --- |
| HSI contract | register interface excerpt; upstream.status: NOT_PROVIDED | SWR-011 |
| Budgets | development targets set by the work-order owner; flash_bytes: 4096; upstream.status: NOT_PROVIDED | SWR-013 |
"""


def main() -> int:
    from forge_factory.inspection import assessment_context
    from forge_factory.lrtx import review
    from forge_factory.release import aspice

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        m = {"work_order": "WO-RPR-113", "purpose": aspice.PURPOSE, "aspice_development": aspice.binding(),
             "scope": "register access driver", "layer": "LL", "target": {"safety_allocation": "NOT_ASSESSED"},
             "budgets": {"flash_bytes": 4096, "stack_bytes": 128, "static_ram_bytes": 64},
             "upstream": {"status": "NOT_PROVIDED"}}
        m[assessment_context.FIELD] = assessment_context.binding(m)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
        (ws / "traceability").mkdir()
        (ws / "traceability/upstream_gaps.md").write_text(GAPS)
        view = assessment_context.view(m) or {}
        if view.get("missing_required_constraint") != "OPEN_INPUT_GAP_NOT_SATISFIED":
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no bound assessment view with the open-input-gap rule")
            return 2
        got = {name: review.fact_conflicts(ws, "SWE.1", "SWE1-04", [f]) for name, f in
               (("cpu", CPU), ("timing", TIMING), ("hsi", HSI))}
    refuted = {k for k, v in got.items() if any("recorded as NOT_PROVIDED" in x for x in v)}
    if "hsi" not in refuted:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the recorded HSI gap is no longer refuted (control)")
        return 2
    if refuted & {"cpu", "timing"}:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
