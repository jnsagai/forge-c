"""An upstream route carries failed findings as bound data, without carrying acceptance or changing ownership."""
import json
from types import SimpleNamespace as S

import pytest
from forge_factory import rework_context as R
from forge_factory.afo import line_cloud as C
from forge_factory.afo import line_orders as LO
from forge_factory.common import canonical_json, pretty_json, sha256_bytes, sha256_file
from forge_factory.inspection import defects as D
from forge_factory.inspection.engine import Store
from test_bound_rework_context import attempt, inspection, write  # noqa: F401 - shared fixture
from test_cloud_line_scheduler import cloud, env  # noqa: F401 - shared fixture


@pytest.fixture
def upstream(attempt, monkeypatch):  # noqa: F811 - shared fixture
    src, dst, manifest, req, run = attempt
    old = json.loads((src / ".forge-run/manifest.json").read_text())
    old["phase_scope"] = {"stop_after": "SWE.4"}
    write(src, ".forge-run/manifest.json", old)
    inspection(src)
    D.report(src, detected_phase="SWE.3", reported_by="swe3-inspector", kind="ARCHITECTURE",
             summary="The architecture has not established the required state preservation.",
             requirement_ids=["SWR-001"], test_files=[],
             evidence_refs=["workproducts/SWE.2/software_architecture.md:1"],
             requirement_quote="The driver shall preserve state.")
    gates = src / ".forge-run/gates/gate-log.jsonl"
    gates.write_text(gates.read_text() + json.dumps({"ts": "2026-11-04T10:01:00Z", "phase": "SWE.4",
        "step": "author", "result": "REJECTED", "status": "BLOCKED", "issues": ["Upstream architecture unresolved."]}) + "\n")
    manifest["resumed_from"] = {"source_work_order": "WO-SOURCE", "stable_phases": {"SWE.1": "I1"}}
    write(dst, ".forge-run/manifest.json", manifest)
    first = Store(src).current_hash("SWE.1")
    third = Store(src).current_hash("SWE.3")
    ins_path = src / "inspection/SWE.3/INS-SWE.3-001.json"
    ins_doc = json.loads(ins_path.read_text())
    ins_doc.update(baseline_hash=third, baseline_id="BL-SWE.3-001")
    ins_path.write_text(pretty_json(ins_doc))
    class AcceptedPrefix(Store):
        def gate(self, phase):
            if phase == "SWE.3" and self.workspace == src:
                return {"decision": "REWORK", "reason": "INS-SWE.3-001"}
            return {"decision": "PASS" if phase == "SWE.1" or self.workspace == src and phase == "SWE.2" else "BLOCKED"}

        def latest_baseline(self, phase):
            if phase == "SWE.3" and self.workspace == src:
                return {"baseline_hash": third, "baseline_id": "BL-SWE.3-001"}
            return {"baseline_hash": first} if phase == "SWE.1" else None
    monkeypatch.setattr(R, "Store", AcceptedPrefix)
    routing = R.upstream_snapshot(src, "SWE.2", "SWE.4")
    req.update(phase="SWE.2", source_phase="SWE.4", upstream_sha256=sha256_bytes(canonical_json(routing)),
               gate_log_sha256=sha256_file(gates))
    return src, dst, manifest, req, run


def test_actual_normal_defect_route_and_failed_inspection_are_bound_without_inherited_acceptance(upstream):
    src, dst, manifest, req, _ = upstream
    before = {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}
    doc = R.prepare(dst, manifest, req, "SWE.2")
    assert doc["schema"] == "forge-c/rework-context/2" and doc["source_phase"] == "SWE.4"
    assert doc["carried_upstream_baselines"].keys() == {"SWE.1"}
    routing = doc["upstream_routing"]
    assert routing["defects"][0]["record"]["kind"] == "ARCHITECTURE"
    assert routing["failed_reviews"]["SWE.3"]["inspection"]["failed_items"]["SWE3-01"]["findings"]
    assert doc["acceptance"] == "NEW_NATIVE_GATES_AND_INDEPENDENT_INSPECTION_REQUIRED"
    R.install(dst, manifest, req, "SWE.2")
    receipt = json.loads((dst / R.RECEIPT).read_text())
    assert receipt["inherited_verdict"] is False
    assert not (dst / ".forge-run/defects").exists()  # findings are not imported defect state
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("mutation,code", [
    ("defect", "UPSTREAM_HASH_MISMATCH"), ("inspection", "UPSTREAM_HASH_MISMATCH"),
    ("closed", "UPSTREAM_OPEN_DEFECT_MISSING"), ("route", "UPSTREAM_DEFECT_ROUTE_INVALID"),
    ("live", "SOURCE_NOT_KNOWN_TERMINAL"), ("prefix", "UPSTREAM_CONTENT_MISMATCH"),
    ("other_resume", "UPSTREAM_RESUME_SOURCE_MISMATCH"), ("unbound_fields", "REQUEST_INVALID"),
])
def test_upstream_mutation_cannot_rebind_findings_or_expand_the_accepted_prefix(upstream, mutation, code):
    src, dst, manifest, req, run = upstream
    defect = next((src / D.DIR).glob("DEF-*.json"))
    if mutation in ("defect", "closed", "route"):
        doc = json.loads(defect.read_text())
        if mutation == "defect":
            doc["summary"] += " changed"
        elif mutation == "closed":
            doc["status"] = "REJECTED"
        else:
            doc["kind"] = "CODE"
        defect.write_text(pretty_json(doc))
    elif mutation == "inspection":
        path = src / "inspection/SWE.3/INS-SWE.3-001.json"
        doc = json.loads(path.read_text())
        doc["items"]["SWE3-01"]["findings"].append("another finding")
        path.write_text(pretty_json(doc))
    elif mutation == "live":
        run["lifecycle"] = {"status": {"kind": "running"}}
    elif mutation == "prefix":
        (dst / "workproducts/SWE.1/software_requirements.md").write_text("changed")
    elif mutation == "other_resume":
        manifest["resumed_from"]["source_work_order"] = "WO-OTHER"
    else:
        req.pop("upstream_sha256")
    with pytest.raises(R.ReworkRefused, match=code):
        R.install(dst, manifest, req, "SWE.2")
    assert not (dst / R.PATH).exists() and not (dst / R.RECEIPT).exists()


def test_cloud_upstream_placement_attaches_the_same_bound_request_and_cli_arguments(upstream, monkeypatch):
    src, _, _, expected, _ = upstream
    plan = S(current=S(phase="SWE.4", rid="RUN-SOURCE", wo="WO-SOURCE"),
             lineage=S(profile=C.PROFILE), action="PLACE", sweep=False,
             order={"wo": "WO-TARGET", "phase": "SWE.2", "stop_after": "SWE.2", "kind": "UPSTREAM",
                    "resume_from": "WO-SOURCE", "run_model": "gpt-6.1-terra"})
    line = S(workspace=lambda _: src, ended_run=lambda wo, rid: wo == "WO-SOURCE" and rid == "RUN-SOURCE")
    placer = C.CloudPlacer(line, policy_path="unused")
    monkeypatch.setattr(LO.Placer, "_execute", lambda self, plan, *args, **kw: plan.order)
    order = placer._execute(plan, None, None, [], 0, execute=False)
    assert order["rework_context"] == expected
    args = C.context_arguments(order)
    assert args[-4:] == ["--rework-source-phase", "SWE.4", "--rework-upstream-sha256", expected["upstream_sha256"]]
    assert order["resume_from"] == "WO-SOURCE"


@pytest.mark.parametrize("stale", [False, True])
def test_order_ending_in_current_failed_detecting_phase_before_its_stop_phase(upstream, monkeypatch, stale):
    src, dst, manifest, req, _ = upstream
    gates = src / ".forge-run/gates/gate-log.jsonl"
    rows = [json.loads(row) for row in gates.read_text().splitlines()]
    gates.write_text("".join(json.dumps(row) + "\n" for row in rows if row["phase"] == "SWE.3"))
    path = src / "inspection/SWE.3/INS-SWE.3-001.json"
    doc = json.loads(path.read_text())
    current = Store(src).current_hash("SWE.3")
    doc.update(baseline_hash=current, baseline_id="BL-SWE.3-001")
    path.write_text(pretty_json(doc))
    prefix_store = R.Store
    class CurrentDetecting(prefix_store):
        def gate(self, phase):
            return ({"decision": "REWORK", "reason": "INS-SWE.3-001"} if phase == "SWE.3"
                    else super().gate(phase))

        def latest_baseline(self, phase):
            return ({"baseline_hash": current, "baseline_id": "BL-SWE.3-001"} if phase == "SWE.3"
                    else super().latest_baseline(phase))
    monkeypatch.setattr(R, "Store", CurrentDetecting)
    req.update(gate_log_sha256=sha256_file(gates),
               upstream_sha256=sha256_bytes(canonical_json(R.upstream_snapshot(src, "SWE.2", "SWE.4"))))
    if stale:
        (src / "software/hal/current.c").write_text("changed after inspection")
        with pytest.raises(R.ReworkRefused, match="CURRENT_FAILED_DETECTING_PHASE_MISSING"):
            R.prepare(dst, manifest, req, "SWE.2")
    else:
        result = R.prepare(dst, manifest, req, "SWE.2")
        assert result["source_phase"] == "SWE.4" and result["failed_phase"] == "SWE.3"
        assert result["gate_records"] and all(r["phase"] == "SWE.3" for r in result["gate_records"])



def test_signed_cloud_placer_routes_actual_upstream_kind_with_findings_and_preserved_history(env):  # noqa: F811
    placer = cloud(env)
    line = env["line"]
    for _ in range(3):
        placer.cycle()
        placer.cycle()
        for order in list(line.launched):
            rid = (line.workspace(order["wo"]) / ".forge-run/fabro_run_id").read_text()
            if line.fabro[rid] == "running":
                line.finish(order["wo"])
    placer.cycle()
    placer.cycle()
    wo = "WO-F014-CMP-SWE4-CRCHAL-20261104-T1"
    source = line.workspace(wo)
    write(source, "workproducts/SWE.1/software_requirements.md", "- **SWR-001** The driver shall preserve state.\n")
    D.report(source, detected_phase="SWE.4", reported_by="swe4-author", kind="ARCHITECTURE",
             summary="The existing architecture does not support required state preservation.",
             requirement_ids=["SWR-001"], test_files=[], evidence_refs=["workproducts/SWE.2/software_architecture.md:1"],
             requirement_quote="The driver shall preserve state.")
    line.finish(wo, ["REQUIRED_TOOL_NOT_PASS:run_unit:FAIL"])
    count = len(line.launched)
    placer.cycle()
    assert len(line.launched) == count + 1
    resumed = line.launched[-1]
    assert resumed["--stop-after"] == "SWE.2" and resumed["--resume-from"] == wo
    spec = LO._load(LO.supervisor_dir() / "line-orders" / (resumed["wo"] + ".json"))
    assert spec["kind"] == "UPSTREAM" and spec["rework_context"]["source_work_order"] == wo
    assert spec["rework_context"]["phase"] == "SWE.2"
    assert C.context_arguments(spec)[-4:-2] == ["--rework-source-phase", "SWE.4"]
    assert spec["digest"] == LO._digest(spec)
    assert (source / ".forge-run/defects/DEF-001.json").is_file()
