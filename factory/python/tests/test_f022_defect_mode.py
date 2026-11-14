"""CAPA-260 (owner 2026-11-14: "finding and fixing a defect shall be done by omniverse"): a line order stopped on a
suspected factory defect (a repair stuck on a factory check) gets a maintainer window on the model service for the CAPA
the CRE observer opened, with the failed run's evidence - including the author rejection that blocked the phase."""
import json
import subprocess

import pytest
from forge_factory.afo import bundle as B
from forge_factory.modelservice import maintenance as MS
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_m5_maintainer import factory  # noqa: F401 - the M5 factory fixture

WO = "WO-F014-SWE1-SPIM-20261113-L51"
KEY = "WORK|SPIM|SWE.1|FACTORY_DEFECT|LRTX_REPAIR_STUCK"
STUCK = ["LRTX_TASK_INVALID:requirements:g_ll_crc: [crc_init_pattern_value] DESIGN_CONSTRAINT_OPERATIONS: a design "
         "constraint is not allocated", "LRTX_TASK_INVALID:requirements:g_ll_crc: LRTX_REPAIR_STUCK: the repair answer has "
         "the same findings as the answer it repaired"]


@pytest.fixture()
def owner(tmp_path):
    reg = CapaRegistry(CREStore(tmp_path / "owner/incidents.sqlite3"), cre_policy())
    for cid, key, fixed, order in (("CAPA-901", "GUARDIAN|QueueError:X", False, None),
                                   ("CAPA-904", KEY, False, WO), ("CAPA-905", "WORK|TIMM|SWE.1|FACTORY_DEFECT|X", True, WO + "Z"),
                                   ("CAPA-906", "WORK|UARTM|SWE.1|MODEL_CONVERGENCE|INSPECTION_FAIL", False, "WO-X")):
        reg.open(cid, [f"INC-{cid}"], [], f"rule-opened {key}")
        reg.triage(cid, f"Failure key {key}", None, "RULE:auto-capa")
        reg.link(cid, "FAILURE_KEY", key)
        if order:
            reg.link(cid, "WORK_ORDER", order)
        if fixed:
            reg.link(cid, "FIX_REVISION", "f" * 40)
    return reg


def _ws(root):
    ws = root / "workorders" / WO / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (
        {"phase": "SWE.1", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": STUCK, "ts": "T1"},
        {"phase": "SWE.1", "step": "route", "gate": {"decision": "BLOCKED", "reason": "rework budget exhausted"}})))
    (ws / ".forge-run/lrtx/SWE.1").mkdir(parents=True)
    (ws / ".forge-run/lrtx/SWE.1/reply-issues.json").write_text(json.dumps({"issues": [s + " (full text)" for s in STUCK]}))
    return ws


def test_the_defect_capa_is_the_unfixed_factory_defect_with_its_order(owner):
    c = MS.defect_capa(owner)
    assert (c["capa_id"], c["phase"], c["work_order"]) == ("CAPA-904", "SWE.1", WO)


def test_the_maintainer_sees_the_author_rejection_that_blocked_the_phase(owner, tmp_path):
    ev = MS.defect_evidence(MS.defect_capa(owner), _ws(tmp_path))
    rej = ev["run"]["author_rejections"][-1]["issues"]
    assert any("LRTX_REPAIR_STUCK" in i for i in rej) and any("DESIGN_CONSTRAINT_OPERATIONS" in i for i in rej)
    assert ev["run"]["last_author_reply_issues"][0].endswith("(full text)")
    assert ev["routed_capa"]["capa_id"] == "CAPA-904" and len(json.dumps(ev).encode()) <= MS.EVIDENCE_MAX
    big = B.run_evidence(_ws(tmp_path / "b"), "SWE.1")
    assert big["trust"] == "UNTRUSTED_RUN_DATA"


def test_defect_mode_runs_once_per_capa_on_a_gated_base(tmp_path, owner, factory):  # noqa: F811
    live = subprocess.run(["git", "rev-parse", "HEAD"], cwd=factory, capture_output=True, text=True).stdout.strip()
    dep = tmp_path / "deployer"
    dep.mkdir()
    (dep / "state.json").write_text(json.dumps({"live": {"commit": live}}))
    env = {"tip": live, "tier": False}
    root = tmp_path / "line"

    def plan():
        return MS.defect_plan(deployer=dep, owner_cre=tmp_path / "owner/incidents.sqlite3", qroot=tmp_path / "q",
                              workorders=root / "workorders", git=lambda *a: env["tip"], tier_active=lambda: env["tier"])

    assert plan() == {"skip": "WORK_ORDER_WORKSPACE_MISSING"}
    _ws(root)
    for key, val, why in (("tip", "b" * 40, "BRANCH_AHEAD_NOT_GATED"), ("tier", True, "TIER_IN_USE")):
        old, env[key] = env[key], val
        assert plan() == {"skip": why}
        env[key] = old
    p = plan()
    assert p["capa"]["capa_id"] == "CAPA-904" and p["base"] == live and p["ws"].endswith(WO + "/workspace")
    (dep / "maintenance-attempts.json").write_text(json.dumps({"defect:CAPA-904": {}}))
    assert plan() == {"skip": "ALREADY_ATTEMPTED_FOR_THIS_CAPA"}


def test_defect_mode_waits_for_an_idle_lane_and_records_nothing_before(tmp_path, owner, factory, monkeypatch):  # noqa: F811
    monkeypatch.setattr(MS, "defect_plan", lambda **k: {"capa": {"capa_id": "CAPA-904"}, "base": "x", "live": "x",
                                                          "repo": "r", "ws": "w"})
    dep = tmp_path / "deployer"
    dep.mkdir()
    out = MS.defect(execute=True, deployer=dep, window=lambda m, ex: {"outcome": "DRY_RUN",
                                                                      "checks": {"lane_idle": False, "lane_idle_detail": "RUNNING L51B"}})
    assert out["skip"] == "LANE_NOT_IDLE" and not (dep / "maintenance-attempts.json").exists()
