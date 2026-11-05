"""Public provider serialization must choose a prerequisite; CPU-only, no model or grants.

The witness supplies its own primary text/graph and inspects the actual provider
message. It neither calls a new selection helper nor imports candidate tests.
"""
import json
import os
import tempfile
from pathlib import Path

from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo.durable import Refused, canonical
from forge_factory.afo.durable_agent import request_material

SIG = "diagnosis serializes a dependent objective before its unresolved prerequisite"


def symptom(reason):
    print("CONTROL_PATH:" + reason)
    print("SYMPTOM_PRESENT:" + SIG)
    return 1


def main():
    with tempfile.TemporaryDirectory(prefix="rpr176-") as directory:
        root = Path(directory)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "events")
        ws = root / "workspace"
        source = ws / "workproducts/SWE.3/contract.md"
        source.parent.mkdir(parents=True)
        source.write_text("Keep both counterexamples covered. Prerequisite counterexample must be resolved first.\n")
        bundle = dict(bundle_id="rpr176-b", order_id="rpr176-o", attempt_id="rpr176-a",
                      phase="SWE.3", fingerprint="rpr176-f")
        graph = {"AAA-DEPENDENT": ["ZZZ-PREREQUISITE"], "ZZZ-PREREQUISITE": []}

        def case_for(dependencies):
            ref = P.seal(ws, bundle,
                         [dict(id=k, obligation_id=k, detail="Observed counterexample for " + k) for k in dependencies],
                         [dict(path="workproducts/SWE.3/contract.md")], dependencies=dependencies,
                         required_obligations=[*dependencies, "REQ-GLOBAL"])
            path = root / (ref["sha256"] + ".json")
            path.write_text(json.dumps(dict(bundle=bundle, workspace=str(ws), packet_ref=ref)))
            return dict(case=str(path), role="afo-recovery-planner", model="qwen3.6:35b-a3b",
                        profile="local-rtx-v2-omniverse2"), P.load(ref)

        job, packet = case_for(graph)
        original = canonical(packet)
        body, _ = request_material(job)
        doc = json.loads(body["messages"][1]["content"])
        if doc["diagnosis_context"]["selected_incident_unit_ids"] != ["ZZZ-PREREQUISITE"]:
            return symptom("unconfigured-provider-scope")
        assert doc["diagnosis_context"]["global_unit_dependencies"] == graph
        assert set(doc["diagnosis_context"]["required_requirement_ids"]) == {*graph, "REQ-GLOBAL"}
        assert doc["packet"]["remaining_obligations"] == ["AAA-DEPENDENT"]
        assert doc["primary_sources"][0]["text"] == source.read_text()
        assert original == canonical(P.load(json.loads(Path(job["case"]).read_text())["packet_ref"]))
        try:
            request_material({**job, "selected_obligations": ["AAA-DEPENDENT"],
                              "completed_obligations": {"ZZZ-PREREQUISITE": {"result": "PASS"}}})
        except Refused as error:
            assert error.code == "OBLIGATION_DEPENDENCY_UNSATISFIED"
        else:
            return symptom("explicit-unready-scope")
        broken, _ = case_for({"READY": [], "CYCLE-A": ["CYCLE-B"], "CYCLE-B": ["CYCLE-A"]})
        try:
            request_material({**broken, "selected_obligations": ["READY"]})
        except Refused as error:
            assert error.code == "OBLIGATION_DEPENDENCY_MISSING_OR_CYCLIC"
        else:
            return symptom("disconnected-cycle-hidden")
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
