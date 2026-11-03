"""RPR-123 (Fabro run WO-F014-CMP-SWE3-IWDGHAL-20261102-10, cloud comparison line, loop10, 2026-11-03): native HAL
SWE.3, Claude inspector through the bridge's account tool emulation. Its grep returned nothing and the role policy
reserved its last calls; it recorded INS-SWE.3-001 PASS, then INS-SWE.3-002 FAIL with SWE3-01 "SWE.2
software_architecture.md interface section not examined (grep empty, budget reserved)" and SWE3-06
"matrix_3_code_to_unitspec and SWU-HAL-02.puml not examined (call budget reserved)". The factory recorded them as major
product findings and sent the author to rework; the next three inspector sessions failed before any call and each time
the inspect gate re-used INS-SWE.3-002 as a new failed inspection: "rework budget exhausted (5 failed cycles)".

Scenario: a scratch SWE.3 work order with a frozen baseline; the deterministic checklist items are stubbed PASS (as in
the incident); the inspector's two submissions go through the real verdict-string parser and Store.record_inspection
(the path of check_inspection), then the real inspect and route gates. A second scratch work order has a real FAIL
finding and then an inspector visit that records nothing. A real defect finding must still go to the author.
Symptom: findings stating unexamined evidence are routed to the author as product findings, or an inspector visit that
recorded nothing re-uses the earlier verdict as a new failed cycle."""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "an inspection whose findings say the evidence was not examined is routed to the author as a product finding"
ITEMS = [f"SWE3-{i:02d}" for i in range(1, 11)]
DET = {"SWE3-07", "SWE3-08", "SWE3-09", "SWE3-10"}
NOT_EXAMINED = {"SWE3-01": "SWE.2 software_architecture.md interface section not examined (grep empty, budget reserved); "
                           "API match vs api_calls.json only",
                "SWE3-06": "matrix_3_code_to_unitspec and SWU-HAL-02.puml not examined (call budget reserved); trace "
                           "provenance unverified by inspector"}
REAL = {"SWE3-02": "HAL_IWDG_Refresh writes 0xAAAA to IWDG_KR without the 0xCCCC start key the design requires"}


def _verdicts(fails: dict) -> str:
    return "; ".join(f"{i}=FAIL:{fails[i]}" if i in fails else f"{i}=PASS" for i in ITEMS)


def _workspace(ws: Path, tag: str):
    from forge_factory.inspection import gate
    from forge_factory.inspection.engine import Store

    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": f"WO-RPR-123-{tag}", "layer": "HAL",
                                                             "created_at": "2026-11-03T00:00:00Z", "scope": [],
                                                             "target": {}, "budgets": {}}))
    for rel, text in {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** The HAL shall refresh IWDG.\n",
                      "workproducts/SWE.2/software_architecture.md": "# Software architecture\nSWC_HAL\n",
                      "workproducts/SWE.3/detailed_design.md": "# Detailed design\nSWU-HAL-01 HAL_IWDG_Init\n",
                      "software/hal/stm32n6xx_hal_iwdg.c": "#include \"stm32n6xx_hal_iwdg.h\"\n",
                      "software/hal/stm32n6xx_hal_iwdg.h": "void HAL_IWDG_Refresh(void);\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    st = Store(ws)
    st.deterministic_items = lambda phase, checklist: {i: {"verdict": "PASS", "evidence_refs": ["det.json"],
                                                           "findings": [], "source": "deterministic"} for i in DET}
    for ph in ("SWE.1", "SWE.2"):
        st.freeze(ph, f"swe{ph[-1]}-author")
    bl = st.freeze("SWE.3", "swe3-author")
    gate._state(ws, "SWE.3", {"step": "author", "result": "FROZEN", "baseline_id": bl["baseline_id"]})
    gate._state(ws, "SWE.3", {"step": "verify", "check": "hal_guideline", "verdict": "PASS"})
    return st, bl


def _inspect(st, bl, *submissions) -> tuple[dict, dict, int]:
    from forge_factory.inspection import gate
    from forge_factory.mcp.servers.evidence import parse_verdict_string

    for s in submissions:  # as check_inspection: a verdict without evidence refs cites the inspected baseline record
        verdicts = parse_verdict_string(s)
        for v in verdicts.values():
            v["evidence_refs"] = v["evidence_refs"] or [f"configuration/baselines/SWE.3/{bl['baseline_id']}.json"]
        st.record_inspection("SWE.3", "swe3-inspector", bl["baseline_id"], verdicts)
    reply = json.dumps({"status": "REWORK", "artifacts": [], "issues": [], "next_action": "rework"}) if submissions \
        else ""
    with contextlib.redirect_stdout(io.StringIO()):
        gate.step_inspect(st, "SWE.3", reply)
        rc = gate.step_route(st, "SWE.3")
    rows = [json.loads(x) for x in (st.workspace / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    last = {r.get("step"): r for r in rows}
    return last["inspect"]["gate"], last["route"]["gate"], rc


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ.update(FORGE_STATE_DIR=str(root / "state"), FORGE_EVENTS_DIR=str(root / "events"))
        try:
            st, bl = _workspace(root / "a", "a")
            ga, ra, _rc = _inspect(st, bl, _verdicts({}), _verdicts(NOT_EXAMINED))  # the incident's two submissions
            ins = st.inspections("SWE.3")
            routed = [f["id"] for f in (ins[-1]["findings"] if ins and ins[-1]["verdict"] == "FAIL" else [])]
            st, bl = _workspace(root / "b", "b")
            _inspect(st, bl, _verdicts(REAL))
            from forge_factory.inspection import gate

            gate._state(st.workspace, "SWE.3", {"step": "author", "result": "FROZEN_BY_EVIDENCE",
                                                "baseline_id": bl["baseline_id"]})
            gb, rb, _ = _inspect(st, bl)  # the next inspector session failed before any call: nothing recorded
            st, bl = _workspace(root / "c", "c")
            gc, rc_, _ = _inspect(st, bl, _verdicts({**REAL, **NOT_EXAMINED}))  # real defect beside unexamined items
            real = [f["id"] for f in st.inspections("SWE.3")[-1]["findings"]]
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
    if gc.get("decision") != "REWORK" or "SWE3-02" not in real or rc_.get("decision") != "REWORK":
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:a real defect finding did not reach the author {json.dumps(gc)[:100]}")
        return 2
    if any(i in routed for i in NOT_EXAMINED) or ga.get("decision") in ("REWORK", "PASS") or \
            gb.get("decision") == "REWORK" or rb.get("decision") == "REWORK" or \
            any(i in real for i in NOT_EXAMINED):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if ga.get("decision") == ra.get("decision") == "REINSPECT" and gb.get("decision") == "REINSPECT":
        print("SYMPTOM_ABSENT")
        return 0
    print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:unexpected gates {json.dumps([ga, gb])[:140]}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
