"""RPR-133 (lineage invalidation after oracle commit a88b61a5, 2026-11-03): a88b61a5 changed only the wording of
checklist item SWE2-08 (its new clause concerns a HAL with a bounded wait). Each inspection's assessment context bound
the sha of the WHOLE checklist file, so on a88b61a5+ code the SWE.2 gate of every earlier order recomputed REINSPECT
(INSPECTION_ASSESSMENT_CONTEXT_CHANGED), LL orders included, and provided_ll refused the fully verified ST CRC LL lineage
WO-F014-SWE6-CRCL-20261103-L24: PROVIDED_LL_NOT_VERIFIED:...:SWE.2.

Scenario: a scratch ASPICE_ONLY LL work order (real assessment-context binding) with frozen SWE.1/SWE.2 baselines is
inspected PASS under a synthetic SWE.2 checklist A (served through the engine's checklist loader), then re-gated under
* B1: A with only the criterion of a HAL-only item (`applies_to: {layer: [HAL, LL+HAL]}`) changed;
* B2: A with only the HAL clause of a mixed item changed, plus the owner's hash-bound revision record declaring the
  edit unchanged for LL orders (the shape of SWE2-08).
Controls, each a fresh order inspected under A, must still re-inspect: an LL-applicable criterion change, a severity
change, an evidence change, an added required item, reordered items, a revision record left on a later edit, and a HAL
order under B1 and under B2.
Symptom: the LL order's verdict is not kept under B1 or B2."""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "an edit to a checklist item that does not apply to the order invalidates the order's inspection verdict"
POLICY = {"maximum_rework_cycles": 3, "require_independent_inspector": True}
EV = ["workproduct_reference", "recorded_verdict"]
VIEWS = {"id": "SWE2-T01", "required": True, "severity_if_failed": "major", "evidence": EV,
         "criterion": "The architecture provides a static and a dynamic PlantUML view naming the driver components."}
HAL = {"id": "SWE2-T02", "required": True, "severity_if_failed": "major", "evidence": EV,
       "applies_to": {"layer": ["HAL", "LL+HAL"]}, "criterion": "The dynamic view shows the HAL timeout path."}
MIXED = {"id": "SWE2-T03", "required": True, "severity_if_failed": "major", "evidence": EV,
         "criterion": "The dynamic view shows, for a HAL work order, a timeout path (an LL-only work order shows the "
                      "caller-bounded ready poll)."}
MIXED_NEW = ("The dynamic view shows, for a HAL work order whose HAL has a bounded wait, a timeout path (an LL-only work "
             "order shows the caller-bounded ready poll; a HAL that never waits shows none).")
CHECKLIST = {"A": [VIEWS, HAL, MIXED]}


def _ask(item):
    from forge_factory.afo.durable import digest

    return digest({k: v for k, v in item.items() if k not in ("source", "revisions")})


def _variants():
    a = CHECKLIST["A"]
    b1 = copy.deepcopy(a)
    b1[1]["criterion"] = "The dynamic view shows the HAL timeout path where the HAL has a bounded wait."
    b2 = copy.deepcopy(a)
    b2[2]["criterion"] = MIXED_NEW
    b2[2]["revisions"] = [{"previous_item_sha256": _ask(a[2]), "item_sha256": _ask(b2[2]),
                           "unchanged_for": {"layer": ["LL"]}, "decision": "synthetic owner record"}]
    crit = copy.deepcopy(a)
    crit[0]["criterion"] += " Each view also names the allocated driver APIs."
    sev = copy.deepcopy(a)
    sev[0]["severity_if_failed"] = "minor"
    evid = copy.deepcopy(a)
    evid[0]["evidence"] = EV + ["views_report_reference"]
    added = copy.deepcopy(a) + [{"id": "SWE2-T04", "required": True, "severity_if_failed": "major", "evidence": EV,
                                 "criterion": "Every register offset matches the reference manual."}]
    order = [copy.deepcopy(a[2]), copy.deepcopy(a[0]), copy.deepcopy(a[1])]
    stale = copy.deepcopy(b2)
    stale[2]["criterion"] = MIXED_NEW.replace("caller-bounded ready poll", "ready poll")  # LL ask changed, record kept
    return {"B1": b1, "B2": b2, "LL_CRITERION": crit, "SEVERITY": sev, "EVIDENCE": evid, "ADDED_REQUIRED": added,
            "REORDERED": order, "STALE_REVISION": stale}


def _serve(current):
    from forge_factory.afo.durable import digest
    from forge_factory.inspection import engine

    def load(phase, root=None, brownfield=False):
        checks = copy.deepcopy(current["checks"])
        return {"phase": phase, "version": "0.4", "policy": dict(POLICY), "checks": checks,
                "sha256": digest({"policy": POLICY, "checks": checks})}

    engine.load_checklist = load


def _order(root: Path, tag: str, layer: str, current):
    from forge_factory.inspection import assessment_context
    from forge_factory.inspection.engine import Store
    from forge_factory.release import aspice

    ws = root / tag
    (ws / ".forge-run").mkdir(parents=True)
    man = {"work_order": f"WO-RPR-133-{tag}", "layer": layer, "purpose": aspice.PURPOSE,
           "aspice_development": aspice.binding(), "created_at": "2026-11-03T00:00:00Z", "scope": ["synthetic"],
           "target": {}, "budgets": {}}
    man[assessment_context.FIELD] = assessment_context.binding(man)
    (ws / ".forge-run/manifest.json").write_text(json.dumps(man))
    for rel, text in {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** The LL shall poll ready.\n",
                      "workproducts/SWE.2/software_architecture.md": "# Software architecture\nSWC_LL\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    st = Store(ws)
    st.deterministic_items = lambda phase, checklist: {}
    st.freeze("SWE.1", "swe1-author")
    bl = st.freeze("SWE.2", "swe2-author")
    current["checks"] = CHECKLIST["A"]
    verdicts = {c["id"]: {"verdict": "PASS", "evidence_refs": ["workproducts/SWE.2/software_architecture.md"],
                          "findings": []} for c in CHECKLIST["A"]}
    with contextlib.redirect_stdout(io.StringIO()):
        rec = st.record_inspection("SWE.2", "swe2-inspector", bl["baseline_id"], verdicts)
    first = st.gate("SWE.2")
    if rec["verdict"] != "PASS" or first["decision"] != "PASS":
        raise RuntimeError(f"not PASS under checklist A: {rec['verdict']} {first}")
    return st


def _regate(root: Path, tag: str, layer: str, checks, current) -> dict:
    st = _order(root, tag, layer, current)
    current["checks"] = checks
    return st.gate("SWE.2")


def main() -> int:
    current: dict = {}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ.update(FORGE_STATE_DIR=str(root / "state"), FORGE_EVENTS_DIR=str(root / "events"))
        try:
            _serve(current)
            v = _variants()
            ll = {k: _regate(root, f"ll-{k.lower()}", "LL", v[k], current) for k in ("B1", "B2")}
            controls = {k: _regate(root, f"ctl-{k.lower()}", "LL", v[k], current)
                        for k in ("LL_CRITERION", "SEVERITY", "EVIDENCE", "ADDED_REQUIRED", "REORDERED",
                                  "STALE_REVISION")}
            controls.update({f"HAL_{k}": _regate(root, f"hal-{k.lower()}", "HAL", v[k], current) for k in ("B1", "B2")})
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
    weak = sorted(k for k, g in controls.items() if g.get("decision") != "REINSPECT")
    if weak:
        print(f"REPRODUCER_ERROR:CONTROL_NOT_REINSPECTED:{','.join(weak)} "
              f"{json.dumps({k: controls[k].get('decision') for k in weak})[:120]}")
        return 2
    if any(g.get("decision") == "REINSPECT" for g in ll.values()):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if all(g.get("decision") == "PASS" for g in ll.values()):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:unexpected gates {json.dumps(ll)[:140]}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
