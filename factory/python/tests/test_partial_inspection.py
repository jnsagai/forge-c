"""Deterministic policy, exact evidence, and operator ingress tests for the SWE.1 pilot."""
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest
from forge_factory.inspection import gate, partial
from forge_factory.lrtx import progress_api, swe1_quality
from forge_factory.workflow.builder import build


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("FORGE_FLOOR_LINES", raising=False)
    wo = "WO-F014-QM-PILOT"
    ws = tmp_path / "workorders" / wo / "workspace"
    manifest = {"work_order": wo, "purpose": "DEVELOPMENT", "target": {"safety_allocation": "OUT_OF_CONTEXT:"},
                "upstream": {"status": "OUT_OF_CONTEXT"}, partial.MARKER: 1}
    write(ws / ".forge-run/manifest.json", manifest)
    stmt = "The timer shall  report its configured state."
    swrs = {f"SWR-{i:03}": stmt if i == 1 else f"The timer shall report status {i}."
            for i in range(1, 9)}
    artifact = ws / partial.ARTIFACT
    artifact.parent.mkdir(parents=True)
    artifact.write_text("\n".join(f"- **{swr}** {text}" for swr, text in swrs.items()))
    opts = {"revision": 0, "enabled": True, "automatic": False, "threshold": 85}
    partial.configure(ws, opts, "operator")
    finding = {"quality_id": "IQ-11", "severity": "EDITORIAL", "evidence": "two spaces after shall",
               "required_action": "Use one space.", "input_uncertainty": False}
    refs = [{"swr": swr, "task": "task", "key": swr, "obj": {"statement": text},
             "generated": False, "sha": partial.digest(text)} for swr, text in swrs.items()]
    verdicts = {("task|" + ref["key"], ref["sha"]):
                {"swr": ref["swr"], "findings": [finding] if ref["swr"] == "SWR-001" else [], "passed": True}
                for ref in refs}
    monkeypatch.setattr(swe1_quality, "requirements", lambda _ws: refs)
    monkeypatch.setattr(swe1_quality, "verdicts", lambda _ws: verdicts)
    bl = {"baseline_id": "BL-SWE.1-001", "baseline_hash": partial.digest(swrs), "files": {partial.ARTIFACT: "exists"}}
    det = "inspection/SWE.1/deterministic/SWE1-07-20261125T000000.000000Z.json"
    write(ws / det, {"verdict": "PASS"})
    last = {"inspection_id": "INS-SWE.1-001", **bl, "checklist_sha256": "pinned", "verdict": "PASS",
            "inspector_role": "swe1-inspector", "findings": [],
            "items": {"SWE1-07": {"verdict": "PASS", "source": "deterministic", "evidence_refs": [det]}}}
    st = partial.Store(ws)
    monkeypatch.setattr(partial.Store, "latest_baseline", lambda *_: bl)
    monkeypatch.setattr(partial.Store, "stale_reason", lambda *_: None)
    monkeypatch.setattr(partial.Store, "inspections", lambda *_: [last])
    monkeypatch.setattr(partial.Store, "checklist", lambda *_: {
        "sha256": "pinned", "checks": [{"id": "SWE1-07", "deterministic_check": "ears_conformance"}]})
    monkeypatch.setattr(partial.Store, "gate", lambda *_: {
        "decision": "PASS", "reason": last["inspection_id"], "failed_inspections": 0, "max_rework_cycles": 3})
    quality = swe1_quality.quality_checklist()
    sq = {"baseline_id": bl["baseline_id"], "guideline_sha256": quality["guideline"]["sha256"],
          "findings": {item["id"]: [] for item in quality["set"]}}
    write(ws / ".forge-run/lrtx/SWE.1/phase2/set-quality.json", sq)
    partial.pin_scope(st)
    evidence, candidates = partial.basis(st)
    assert evidence["passed"] == 18 and evidence["total"] == 19 and not evidence["holds"]
    key, = candidates
    proposal = {key: {"disposition": "defer", "requirement_id": "SWR-001", "artifact": partial.ARTIFACT,
                      "downstream_impact": "editorial_only", "source": stmt, "replacement": stmt.replace("  ", " "),
                      "rationale": "Only ordinary redundant spacing changes."}}
    write(partial.assessment_file(ws), {"basis_sha256": partial.digest(evidence), "findings": proposal})
    return SimpleNamespace(ws=ws, st=st, wo=wo, manifest=manifest, refs=refs, verdicts=verdicts, finding=finding,
                           last=last, evidence=evidence, proposal=proposal)


def test_exact_evidence_owner_review_and_continuation(campaign, monkeypatch):
    c = campaign
    assert partial.assess(c.st)["status"] == "REVIEW_REQUIRED"
    gate._state(c.ws, "SWE.1", {"step": "inspect", "agent_status": "PASS", "agent_ok": True,
                                "gate": {"reason": "PARTIAL_INSPECTION_GAPS"}})
    assert gate.partial_route(c.st, {"reason": "exhausted"})["decision"] == "PARTIAL_INSPECTION_REVIEW"
    token = partial.assess(c.st)["evidence_sha256"]
    with pytest.raises(partial.Conflict):
        partial.approve(c.ws, token, "operator")
    monkeypatch.setattr(gate.time, "sleep", lambda _: partial.approve(c.ws, token, "operator"))
    assert gate._step_partial_advisory(c.st, "SWE.1", c.st.gate("SWE.1")) == 0
    out, = partial.records(c.ws)
    assert out["evidence_sha256"] == token
    assert out["review"]["operator"] == "operator"
    assert partial.snapshot(c.ws)["continued"]["evidence_sha256"] == token
    assert c.last["verdict"] == "PASS"
    assert c.finding["severity"] == "EDITORIAL"


def test_missing_scope_cannot_increase_percentage(campaign):
    campaign.refs.pop()
    r = partial.assess(campaign.st)
    assert r["status"] == "HOLD"
    assert r["evidence"]["total"] == 19
    assert r["evidence"]["passed"] == 17
    assert "FROZEN_INSPECTION_SCOPE_CHANGED" in r["evidence"]["holds"]


@pytest.mark.parametrize("failure", ["unsafe_finding", "required_check", "missing_requirement", "proposal"])
def test_noneditorial_missing_or_unverified_evidence_holds_above_threshold(campaign, failure):
    c = campaign
    if failure == "unsafe_finding":
        c.finding["input_uncertainty"] = True
    elif failure == "required_check":
        c.last["items"]["SWE1-07"]["verdict"] = "FAIL"
    elif failure == "missing_requirement":
        c.verdicts.popitem()
    else:
        next(iter(c.proposal.values()))["replacement"] = "The timer shall reset."
        write(partial.assessment_file(c.ws), {"basis_sha256": partial.digest(c.evidence), "findings": c.proposal})
    r = partial.assess(c.st)
    assert r["percentage"] > 85
    assert r["status"] == "HOLD"


def test_threshold_and_stale_review(campaign, monkeypatch):
    c = campaign
    monkeypatch.setattr(partial, "active_review", lambda _ws: {"expires_at": "2999-01-01T00:00:00Z"})
    token = partial.assess(c.st)["evidence_sha256"]
    body = {"revision": 1, "enabled": True, "automatic": False, "threshold": 84}
    for bad in [84, 101, 85.0, "85", True]:
        with pytest.raises(ValueError, match="whole number"):
            partial.configure(c.ws, {**body, "threshold": bad}, "operator")
    with pytest.raises(partial.Conflict, match="pilot"):
        partial.configure(c.ws, {**body, "threshold": 90, "automatic": True}, "operator")
    partial.configure(c.ws, {**body, "threshold": 95}, "operator")
    assert partial.assess(c.st)["status"] == "HOLD"
    with pytest.raises(partial.Conflict):
        partial.approve(c.ws, token, "operator")
    with pytest.raises(partial.Conflict):
        partial.configure(c.ws, {**body, "threshold": 85}, "operator")


def test_operator_post_checks_origin_and_saved_threshold(campaign):
    server = ThreadingHTTPServer(("127.0.0.1", 0), progress_api.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=4)
    path = f"/partial-inspection.json?line=local&order={campaign.wo}"
    body = {"action": "configure", "revision": 1, "enabled": True, "automatic": False, "threshold": 91}
    headers = {"Content-Type": "application/json", "X-Forge-Control": "partial-inspection"}
    try:
        for origin, code in (("http://unrelated.invalid", 403), (f"http://127.0.0.1:{server.server_port}", 200)):
            conn.request("POST", path, json.dumps(body), {**headers, "Origin": origin})
            result = conn.getresponse()
            doc = json.loads(result.read())
            assert result.status == code
        assert doc["settings"]["threshold"] == 91
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_only_render_the_pilot_path_for_compatible_graphs(campaign):
    args = {"phases": ["SWE.1"], "inspect_phases": ["SWE.1"], "model": "qwen", "two_phase_inspection": True}
    plain, _ = build(campaign.wo, structured=args)
    pilot, _ = build(campaign.wo, structured={**args, "partial_inspection": True})
    assert "partial-pilot-boundary" not in plain
    assert 'swe1_advisory -> swe2_author [condition="outcome=succeeded"]' in pilot
    assert "partial_pilot_boundary -> release_manager" in pilot
    assert not partial.in_scope({**campaign.manifest, "phase_scope": {"stop_after": "SWE.1"}})
    assert not partial.in_scope({**campaign.manifest, "purpose": "FORMAL_REVIEW"})
    assert not partial.in_scope({**campaign.manifest, "safety_target": "B"})


def test_latest_author_rejection_blocks_the_old_inspection(campaign):
    c = campaign
    gate._state(c.ws, "SWE.1", {"step": "inspect", "agent_status": "PASS", "agent_ok": True,
                                "gate": {"reason": "PARTIAL_INSPECTION_GAPS"}})
    gate._state(c.ws, "SWE.1", {"step": "author", "result": "REJECTED", "issues": ["UNBOUND_INPUT"]})
    assert gate.partial_route(c.st, {"decision": "BLOCKED", "reason": "exhausted"})["decision"] == "BLOCKED"
    assert not partial.has_continuation(c.ws)
