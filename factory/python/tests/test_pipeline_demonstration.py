"""QM demonstration traverses real phases without accepting failed quality evidence."""
import json
import re

import pytest
from forge_factory import development_demonstration as demo
from forge_factory import development_execution as D
from forge_factory import provided_requirements as P
from forge_factory import workorder as W
from forge_factory.brownfield.inject import inject
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import profile
from forge_factory.release import finalize
from forge_factory.workflow.builder import build
from incremental_idr_anchor import Anchor
from test_simulation_performance import TEST

EXAMPLE = W.REPO_ROOT / "examples/0014f-st-cube-crc-idr-qm"
PROFILE = "local-rtx-v2-omniverse2-q38-qm-demo-mtp"


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for name in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + name + "_DIR", str(tmp_path / name))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    return W.prepare(EXAMPLE, "WO-QM-DEMONSTRATION-FIXTURE", purpose="QM", execution_policy=D.DEMO)


def test_every_phase_and_real_check_is_attempted_without_quality_branching(prepared):
    ws, man = prepared
    prof = profile.load(PROFILE)
    settings = W.local_profile_structured(prof, man, prof["models"]["default"])
    assert settings["demonstration"] and not settings["reinspect"]
    graph, nodes = build(man["work_order"], layer="LL", trace=True, brownfield="FROZEN", peripheral="crc",
                         delivery_style="cmsis", operation_scope=man["operation_scope"],
                         execution_policy=man["development_execution"], assessment_manifest=man, structured=settings)
    edges = re.findall(r"^  (\w+) -> (\w+)(.*)$", graph, re.M)
    assert edges and all(not attrs for _, _, attrs in edges)
    outgoing = {a: b for a, b, _ in edges}
    assert len(outgoing) == len(edges)
    path, node = [], "start"
    while node != "exit":
        assert node not in path
        path.append(node)
        node = outgoing[node]
    for n in range(1, 7):
        expected = [f"swe{n}_author", f"swe{n}_author_gate", f"swe{n}_demo_snapshot",
                    f"swe{n}_inspector", f"swe{n}_inspect_gate"]
        assert all(x in path for x in expected)
        assert [path.index(x) for x in expected] == sorted(path.index(x) for x in expected)
    assert all(x in path for x in ("delivery_inject", "swe3_delivery_check", "swe3_verify", "swe4_scaffold",
                                  "swe4_test_author", "swe5_target_author", "swe6_test_author", "release_manager", "finalize"))
    assert set(nodes) <= set(path) and not any("triage" in x or x.endswith("_route") for x in path)
    assert demo.selected(ws) and D.reserve_phase_rework(ws, "SWE.2") is False
    with pytest.raises(ValueError):
        D.binding(D.DEMO, "ASPICE_ONLY")


def failed_requirements(ws, monkeypatch):
    anchor = Anchor(ws, monkeypatch)
    assert P.materialize(ws)["status"] == "PASS"
    assert gate.step_author(Store(ws), "SWE.1", json.dumps({"status": "PASS", "artifacts": [], "issues": [],
                                                          "next_action": "next"})) == 0
    store = Store(ws)
    base = store.latest_baseline("SWE.1")
    judgments = {c["id"]: {"verdict": "PASS", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"]}
                 for c in store.checklist("SWE.1")["checks"]}
    judgments["SWE1-03"] = {"verdict": "FAIL", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"],
                            "findings": ["Synthetic unresolved functional quality finding; preserve for later improvement."]}
    result = store.record_inspection("SWE.1", "swe1-inspector", base["baseline_id"], judgments)
    assert result["verdict"] == "FAIL" and store.gate("SWE.1")["decision"] != "PASS"
    return anchor, result


def test_intact_failed_requirements_are_provisional_not_accepted_and_tamper_refuses(prepared, monkeypatch):
    ws, man = prepared
    _anchor, failed = failed_requirements(ws, monkeypatch)
    snap = demo.snapshot(Store(ws), "SWE.1")
    assert snap["status"] == "SNAPSHOT_UNQUALIFIED" and not snap["quality_accepted"]
    primary = ws / next(i["path"] for i in man["inputs"] if i["role"].startswith("reference_manual"))
    raw = primary.read_bytes()
    primary.chmod(0o600)
    primary.write_bytes(raw + b"\nchanged input\n")
    with pytest.raises(ValueError, match="DEMONSTRATION_INPUT_CHANGED"):
        inject(ws)
    primary.write_bytes(raw)
    result = inject(ws)
    assert result["status"] == "INJECTED" and result["provisional"] and result["demonstration_only"]
    assert result["swe1_quality_gate"] != "PASS" and Store(ws).inspections("SWE.1")[-1] == failed


def test_full_six_phase_tools_can_finish_with_failed_quality_and_never_release(prepared, monkeypatch):
    ws, _ = prepared
    anchor, failed = failed_requirements(ws, monkeypatch)
    assert inject(ws)["status"] == "INJECTED"
    anchor.architecture()
    anchor.implementation()
    anchor.unit()
    anchor.write("SWE.5", {"software/tests/target/test_performance.c": TEST})
    anchor.integration()
    anchor.validation()
    result = finalize.finalize(ws, "qm-pipeline-demonstration-fixture")
    assert all(Store(ws).latest_baseline("SWE." + str(n)) for n in range(1, 7))
    assert Store(ws).inspections("SWE.1")[-1] == failed
    assert result["package_status"] == "BLOCKED" and any("QM_PIPELINE_DEMONSTRATION_ONLY" in x for x in result["gaps"])
    assert finalize.verify_archive(__import__("pathlib").Path(result["archive"]))["integrity"] == "PASS"
