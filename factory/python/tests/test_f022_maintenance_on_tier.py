"""Feature 022: the factory maintainer on the model service (owner 2026-11-13). A guardian crash takes the owner lane -
and with it the line's maintainer - down; the maintenance window plan builds a maintainer case for the crash CAPA, runs
the line's own maintainer workflow in the qualification lane (Fabro + external gateway -> model tier) and processes
the submission through the unchanged veto -> baseline reproducer -> CRE evaluation -> append-only record."""
import json
import subprocess
from pathlib import Path

import pytest
from forge_factory.afo import maintainer as M
from forge_factory.afo.queue import Store
from forge_factory.modelservice import maintenance as MS
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_m5_maintainer import REPRO, SIG, _good_candidate, factory  # noqa: F401 - the M5 factory fixture

JOURNAL = """forge-c-owner-development-857440bc-guard6860-20261107.service: Unit process 1 (sleep) remains running
Traceback (most recent call last):
  File "/x/forge_factory/afo/owner_supervised_development.py", line 1364, in main
    readiness = provider_preflight(cfg.stack_root)
  File "/x/forge_factory/afo/queue.py", line 839, in bounded_row
    raise QueueError("OBSERVATION_SNAPSHOT_BOUND_EXCEEDED")
forge_factory.afo.queue.QueueError: OBSERVATION_SNAPSHOT_BOUND_EXCEEDED
forge-c-owner-development-857440bc-guard6860-20261107.service: Main process exited, code=exited, status=1/FAILURE""".splitlines()
KEY = "GUARDIAN|QueueError:OBSERVATION_SNAPSHOT_BOUND_EXCEEDED"


def test_the_crash_traceback_is_cut_from_the_journal():
    tb = MS.traceback_tail(JOURNAL)
    assert tb[0] == "Traceback (most recent call last):" and tb[-1].endswith("QueueError: OBSERVATION_SNAPSHOT_BOUND_EXCEEDED")
    assert MS.traceback_tail(["nothing here"]) == []


def test_the_crash_evidence_stays_within_what_prepare_keeps():
    capa = {"capa_id": "CAPA-901", "key": KEY, "hypothesis": "h" * 5000}
    ev = MS.crash_evidence(capa, journal=JOURNAL[:1] + ["x" * 290] * 400 + JOURNAL[1:], latch={"error": "e" * 5000})
    assert len(json.dumps(ev).encode()) <= MS.EVIDENCE_MAX
    assert ev["routed_capa"]["capa_id"] == "CAPA-901" and ev["guardian_crash"]["signature"] == KEY.split("|", 1)[1]
    assert ev["guardian_crash"]["traceback"][-1].endswith("OBSERVATION_SNAPSHOT_BOUND_EXCEEDED")


@pytest.fixture()
def owner(tmp_path):
    """The owner CRE store (host): one crash CAPA opened by the observer rule, one already fixed, one WORK CAPA."""
    reg = CapaRegistry(CREStore(tmp_path / "owner/incidents.sqlite3"), cre_policy())
    for cid, key, fixed in (("CAPA-901", KEY, False), ("CAPA-902", "GUARDIAN|ValueError:OTHER", True),
                            ("CAPA-903", "WORK|UARTM|SWE.1|MODEL_CONVERGENCE|INSPECTION_FAIL", False)):
        reg.open(cid, [f"INC-{cid}"], [], f"rule-opened {key}")
        reg.triage(cid, f"Failure key {key}", None, "RULE:auto-capa")
        reg.link(cid, "FAILURE_KEY", key)
        if fixed:
            reg.link(cid, "FIX_REVISION", "f" * 40)
    return reg


def test_the_crash_capa_is_the_unfixed_guardian_one(owner):
    assert MS.crash_capa(owner)["capa_id"] == "CAPA-901"
    assert MS.crash_capa(owner, "CAPA-902")["capa_id"] == "CAPA-902"  # a drill may name a fixed one


def test_the_workflow_is_the_lines_own_maintainer_workflow_on_the_case_state(factory, tmp_path, monkeypatch):  # noqa: F811
    case = M.prepare("mnt-wf-a1", "HEAD", {"incident_id": "INC-1"}, factory)
    case_path = M.case_dir("mnt-wf-a1") / "case.json"
    ws = tmp_path / "run-ws"
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "lane-state"))  # the lane process has its own state (drill 1)
    toml = MS.workflow(case_path, ws, model=MS.DEFAULT_MODEL, seconds=600)
    text = "\n".join(p.read_text() for p in ws.rglob("*") if p.is_file() and p.suffix in (".toml", ".fabro", ".json"))
    assert Path(toml).is_file() and (ws / f".fabro/skills/{MS.ROLE}/SKILL.md").is_file()
    assert str(case_path) in text and str(MS.case_state(case_path)) in text  # MCP server scoped to the case + its state
    assert "agent-output.json" in text and "local_agent record-output" not in text  # no line job bookkeeping
    # CAPA-258: the policy hook issues tickets where the MCP server consumes them - the same state directory
    import re as _re
    toml_text = Path(toml).read_text()
    hooks = _re.findall(r'script = "([^"]*fabro_hook[^"]*)"', toml_text)
    assert hooks and all(f"FORGE_STATE_DIR={MS.case_state(case_path)}" in h for h in hooks), hooks
    server_state = _re.search(r'\[run\.agent\.mcps\.forge_maintainer_mcp\.env\][^\[]*?FORGE_STATE_DIR = "([^"]+)"',
                              toml_text, _re.S)
    assert server_state and server_state.group(1) == str(MS.case_state(case_path))
    with pytest.raises(MS.MaintenanceError):
        MS.case_state(tmp_path / "case.json")


class FakeLane:
    """Plays the lane: the 'agent' writes the good candidate and submits it through the maintainer API."""

    def __init__(self, behave="fix"):
        self.behave, self.argv = behave, None

    def run(self, argv, **kw):
        self.argv = argv
        case = json.loads(Path(argv[argv.index("--case") + 1]).read_text())
        if self.behave == "fix":
            _good_candidate(case)
            M.submit(case, "fix calc.add sign error", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
        return subprocess.CompletedProcess(argv, 0, '{"exit": 0}\n', "")


def _spec(tmp_path, factory, **kw):  # noqa: F811
    p = tmp_path / "spec.json"
    j = tmp_path / "journal.txt"
    j.write_text("\n".join(JOURNAL))
    p.write_text(json.dumps({"capa_id": "CAPA-901", "base": subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=factory, capture_output=True, text=True).stdout.strip(), "repo": str(factory),
        "state_dir": str(tmp_path / "state"), "owner_cre": str(tmp_path / "owner/incidents.sqlite3"),
        "journal": str(j), "drill": True, "pid": "mnt-capa-901-drill", **kw}))
    return str(p)


def _ctx():
    import time

    return {"clock": time.time, "deadline": time.time() + 4 * 3600}


def test_the_plan_turns_an_agent_fix_into_an_eligible_proposal_linked_to_the_owner_capa(factory, tmp_path, owner, monkeypatch):  # noqa: F811
    seen = {}

    def evaluator(cand, base, cstore, pol, **kw):
        seen.update(cand=cand, base=base, **kw)
        return {"decision": "ELIGIBLE_FOR_OFFLINE_REVIEW", "decision_id": "pd-drill", "allowed_auto_deployment": False}

    monkeypatch.setattr(M, "evaluate", lambda case, sub, cs, pol, ev=None: evaluator(
        sub["candidate"], case["base"], cs, pol, reproducers=[sub["staged"]["id"]]))
    lane = FakeLane()
    out = MS.maintenance(_ctx(), spec_path=_spec(tmp_path, factory), runner=lane)
    assert out["outcome"] == "ELIGIBLE_FOR_OFFLINE_REVIEW" and out["capa_id"] == "CAPA-901" and out["drill"] is True
    assert lane.argv[:4] == ["python", "-m", "forge_factory.modelservice.maintenance", "agent"]
    case = M.load_case("mnt-capa-901-drill")
    ev = case["run_evidence"]["record"]
    assert ev["routed_capa"]["capa_id"] == "CAPA-901" and ev["guardian_crash"]["traceback"][-1].endswith("BOUND_EXCEEDED")
    rec = Store().proposal("mnt-capa-901-drill")["record"]
    assert "owner-capa:CAPA-901" in rec["evidence_refs"] and rec["auto_deployment_allowed"] is False
    assert rec["reproducer_id"] != "NONE" and seen["base"] == case["base"]
    assert str(tmp_path / "state") in str(M.case_dir("mnt-capa-901-drill"))  # the drill's own state, never the line's


def test_no_submission_is_recorded_as_such_and_the_worktree_discarded(factory, tmp_path, owner):  # noqa: F811
    out = MS.maintenance(_ctx(), spec_path=_spec(tmp_path, factory, pid="mnt-capa-901-none"), runner=FakeLane("idle"))
    assert out["outcome"] == "NO_SUBMISSION"
    assert not Path(M.load_case("mnt-capa-901-none")["src"]).exists()


def test_an_incomplete_spec_is_refused(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"capa_id": "CAPA-1"}))
    with pytest.raises(MS.MaintenanceError, match="MAINTENANCE_SPEC_INCOMPLETE"):
        MS.maintenance(_ctx(), spec_path=str(p), runner=FakeLane())


def test_crash_mode_runs_only_for_a_latched_crash_with_an_unfixed_capa_on_a_down_lane(tmp_path, owner, factory):  # noqa: F811
    live = subprocess.run(["git", "rev-parse", "HEAD"], cwd=factory, capture_output=True, text=True).stdout.strip()
    dep, q = tmp_path / "deployer", tmp_path / "qual"
    dep.mkdir()
    (dep / "state.json").write_text(json.dumps({"live": {"commit": live}}))
    newS = q / f"owner-allowance-{live[:8]}-main-20261107/newS"
    newS.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(factory), str(newS)], check=True)
    env = {"tip": live, "active": False, "free": 47000, "tier": False}

    def plan():
        return MS.crash_plan(deployer=dep, owner_cre=tmp_path / "owner/incidents.sqlite3", qroot=q,
                             git=lambda *a: env["tip"], unit_active=lambda c8: env["active"], gpu_free=lambda: env["free"],
                             tier_active=lambda: env["tier"])

    assert plan() == {"skip": "NOT_LATCHED"}
    (dep / "FAILED_LATCHED.json").write_text(json.dumps({"at": "T1", "note": "deploy failed, rollback failed"}))
    assert plan() == {"skip": "LATCH_NOT_A_GUARDIAN_CRASH"}
    (dep / "FAILED_LATCHED.json").write_text(json.dumps({"at": "T1", "note": "live guardian crashed, automatic recovery failed: lane down"}))
    for key, val, why in (("tip", "b" * 40, "BRANCH_AHEAD_NOT_GATED"), ("active", True, "LANE_NOT_DOWN"),
                          ("tier", True, "TIER_IN_USE"), ("free", 1913, "GPU_NOT_FREE")):
        old, env[key] = env[key], val
        assert plan() == {"skip": why}
        env[key] = old
    p = plan()
    assert p["capa"]["capa_id"] == "CAPA-901" and p["base"] == live and p["repo"] == str(newS) and p["latch_at"] == "T1"
    # CAPA-255: a GATED tip ahead of the crashed live revision becomes the base, in its own checkout under qualification/
    from forge_factory.reliability.store import CREStore
    with CREStore(tmp_path / "owner/incidents.sqlite3").conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(cre_promotion_decisions)")]
        row = {k: "x" for k in cols}
        row.update(decision_id="pd-t", candidate="b" * 40, baseline=live, decision="ELIGIBLE_FOR_OFFLINE_REVIEW", at="T")
        c.execute(f"INSERT INTO cre_promotion_decisions ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    env["tip"] = "b" * 40
    p = plan()
    assert p["base"] == "b" * 40 and p["live"] == live and p["repo"] == str(q / "maintenance-bbbbbbbb/src")
    env["tip"] = live
    (dep / "maintenance-attempts.json").write_text(json.dumps({"T1": {}}))
    assert plan() == {"skip": "ALREADY_ATTEMPTED_FOR_THIS_LATCH"}  # one maintenance per latch


def test_checkout_makes_a_clean_detached_tree_of_the_revision(tmp_path, factory):  # noqa: F811
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=factory, capture_output=True, text=True).stdout.strip()
    repo = MS.checkout(tmp_path / "qual/maintenance-x/src", rev, source=factory)
    assert MS._git(repo, "rev-parse", "HEAD") == rev and MS.checkout(repo, rev, source=factory) == repo  # idempotent
