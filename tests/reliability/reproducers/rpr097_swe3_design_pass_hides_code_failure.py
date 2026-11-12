"""RPR-097 (Fabro run WO-F014-SWE3-IWDG-20261101-L1, Omniverse2, 2026-11-01): IWDG LL greenfield SWE.3 resumed from
WO-F014-SWE2-IWDG-20261101-02. The structured code visit ended FAILED (cppcheck MISRA-10.6/12.1 left after the tool
repair round); the next workflow node, the deterministic design visit, replaced that reply with PASS and the author gate
froze the code with the open findings. SWE.4 then failed SWE4-04 on them.

Scenario: a SWE.3 workspace whose last code visit recorded open cppcheck findings and whose cppcheck measures FAIL,
through the real swe3.visit_design (unit list, checkpoints, tool calls and file writes are stubbed: not part of the
symptom). Symptom: the design visit answers PASS."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.3 design visit answers PASS while the code visit left cppcheck findings open"
CPP = {"status": "FAIL", "summary": "2 rules violated", "issues": ["MISRA-10.6:stm32n6xx_ll_iwdg.h:135"], "metrics": {}}


def main() -> int:
    from forge_factory.assurance import register_contract
    from forge_factory.inspection import swtrace
    from forge_factory.lrtx import swe3, tools
    unit = {"id": "SWU-LL-01", "n": 1, "swrs": ["SWR-001"],
            "function": {"name": "LL_IWDG_SetPrescaler", "operation": "sets PR", "fields": ["IWDG_PR.PR"], "params": [],
                         "returns": "void"}}
    swe3.units = lambda _ws: [unit]
    swe3._ident = lambda _ws: {"header": "stm32n6xx_ll_iwdg.h", "block": "ll_iwdg_regs", "pfx": "IWDG"}
    swtrace.component_constraints = lambda _ws: []
    register_contract._requirements = lambda _ws: {"SWR-001": "The driver shall set IWDG_PR.PR."}
    tools.call = lambda _ws, _srv, op, *_a, **_k: CPP if op == "cppcheck" else {"status": "PASS", "summary": "ok",
                                                                                  "issues": [], "metrics": {}}
    swe3.V.write_scoped = lambda *_a, **_k: None
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        lr = ws / ".forge-run/lrtx/SWE.3"
        (lr / "packets").mkdir(parents=True)
        ck = swe3.V._ckpt(ws, "SWE.3", "code:SWU-LL-01")
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text(json.dumps({"task": "code:SWU-LL-01", "status": "VALID", "doc": {"code": "x" * 40, "spec_items": [
            {"id": "USPEC-LL-01-01", "behaviour": "The unit sets the prescaler field.", "traces": ["SWR-001"]}]}}))
        (lr / "code-assembly.json").write_text(json.dumps({"units": ["SWU-LL-01"],
                                                          "issues": ["cppcheck: MISRA-10.6:stm32n6xx_ll_iwdg.h:135"]}))
        rep = swe3.visit_design(ws)
    if rep.get("status") == "PASS":
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if rep.get("status") == "FAILED" and any("MISRA-10.6" in str(i) for i in rep.get("issues") or []):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{str(rep)[:140]}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
