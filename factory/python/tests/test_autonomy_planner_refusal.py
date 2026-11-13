"""Owner 2026-11-13 autonomy item 3: a recovery planner packet the GATEWAY refuses is a factory defect for the
maintainer (L49: GATEWAY_HTTP_400:CAPABILITY_LIMIT closed the order as LOCAL_DIAGNOSIS_FAILED and the maintainer never
heard of it). The admission-time refusal (role_capability, before any HTTP call) keeps its designed advisory path."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory.afo import bundle, planner, recovery
from forge_factory.afo import planner_refusal as PR
from test_afo_m4_recovery import _real, order  # noqa: F401

GW = "GATEWAY_HTTP_400:CAPABILITY_LIMIT"


def _failed(agent_error: str | None, job: str = "afo-agent-x"):
    exc = planner.Failed(f"FAILED:{job}")
    if agent_error is not None:
        exc.agent_error, exc.job_id = agent_error, job
    return exc


def test_only_a_gateway_refusal_is_recorded_and_only_once(tmp_path):
    b = {"order_id": "afo-o", "attempt_id": "afo-o-a1", "phase": "SWE.1", "bundle_id": "afo-fb-1",
         "failure_class": "PRODUCT_QUALITY", "error_code": "INSPECTION_FAIL:SWE1-02"}
    assert not PR.record(tmp_path, b, "CAPABILITY_LIMIT", "j")  # admission-time code: not ours
    assert not PR.record(tmp_path, b, "GATEWAY_HTTP_503:UPSTREAM_DOWN", "j")  # infrastructure, not the packet
    assert PR.record(tmp_path, b, GW, "afo-agent-1")
    assert not PR.record(tmp_path, b, GW, "afo-agent-2")  # once per attempt
    r = PR.of(tmp_path, "afo-o-a1")
    assert r["code"] == GW and r["job_id"] == "afo-agent-1" and r["source_error_code"] == "INSPECTION_FAIL:SWE1-02"
    cls, fp, code, summary = PR.apply(tmp_path, "afo-o-a1", "PRODUCT_QUALITY", "cfp-x", "INSPECTION_FAIL:SWE1-02", "s")
    assert (cls, code) == ("FACTORY_CODE_DEFECT", f"PLANNER_REFUSED:{GW}") and fp.startswith("afo-planner-refusal-")
    assert "recovery planner packet" in summary
    assert PR.apply(tmp_path, "afo-o-a2", "PRODUCT_QUALITY", "cfp-x", "E", "s") == ("PRODUCT_QUALITY", "cfp-x", "E", "s")


def test_decide_routes_a_gateway_refusal_once_and_keeps_the_admission_path(order, tmp_path, monkeypatch):
    s, o, b, _epoch, eff = order
    monkeypatch.setattr(recovery, "rule_plan", lambda *a, **kw: None)
    ws = tmp_path / "ws"
    ws.mkdir()
    err = {"value": GW}

    def refused(bundle_, budget, ws_):
        raise _failed(err["value"])
    d = recovery.decide(s, o, {**b, "phase": "SWE.1"}, ws=ws, eff=eff, auth_models=None, planner=refused)
    assert d["status"] == PR.STATUS and d["plan"] is None and d["reasons"] == [GW]
    assert PR.of(ws, b["attempt_id"])["code"] == GW
    d2 = recovery.decide(s, o, {**b, "phase": "SWE.1"}, ws=ws, eff=eff, auth_models=None, planner=refused)
    assert d2["plan"]["rationale_code"].startswith("LOCAL_DIAGNOSIS_FAILED:FAILED:")  # once only: then as before

    def admission(bundle_, budget, ws_):
        raise planner.Failed("CAPABILITY_LIMIT")  # role_capability refusal before any HTTP call
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    d3 = recovery.decide(s, o, {**b, "phase": "SWE.1"}, ws=ws2, eff=eff, auth_models=None, planner=admission)
    assert d3["plan"]["rationale_code"] == "LOCAL_DIAGNOSIS_FAILED:CAPABILITY_LIMIT"
    assert not (ws2 / PR.REL).exists()


def test_the_rebuilt_failure_bundle_is_the_factory_defect(tmp_path):
    src = _real("WO-0002B-STM32N6-RCC-HAL-r148")
    ws = tmp_path / "ws"
    shutil.copytree(src, ws, symlinks=True)  # never write into a real run's workspace
    before = bundle.build(ws, "afo-x", "afo-x-a1", open_capa=set())
    assert before is not None and before["failure_class"] != "FACTORY_CODE_DEFECT"
    assert PR.record(ws, before, GW, "afo-agent-1")
    after = bundle.build(ws, "afo-x", "afo-x-a1", open_capa=set())
    assert after["failure_class"] == "FACTORY_CODE_DEFECT" and after["error_code"] == f"PLANNER_REFUSED:{GW}"
    assert after["fingerprint"].startswith("afo-planner-refusal-") and after["bundle_id"] != before["bundle_id"]
    assert bundle.build(ws, "afo-x", "afo-x-a1", open_capa=set()) == after  # deterministic (maintenance rebuild)
    other = bundle.build(ws, "afo-x", "afo-x-a2", open_capa=set())  # another attempt is untouched
    assert other["failure_class"] == before["failure_class"]
    rec = json.loads((ws / PR.REL).read_text())
    assert list(rec["attempts"]) == ["afo-x-a1"]


def test_the_planner_failure_carries_the_gateway_reason_with_an_unchanged_message():
    from forge_factory.afo import local_agent

    src = __import__("inspect").getsource(local_agent.make_planner)
    assert 'planner.Failed(f"{job[\'state\']}:{job[\'job_id\']}")' in src and "agent_error" in src
