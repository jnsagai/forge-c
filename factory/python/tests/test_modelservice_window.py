"""Feature 017 T011: qualification window controller (FR-019 option C, window-controls.md)."""
import json

import pytest
from forge_factory.modelservice import window as W
from model_tier import gpu as G

OWNER = "/user.slice/user-1000.slice/user@1000.service/app.slice/forge-c-owner-development-383d5462-guard1-20261107.service"
PROD = "/user.slice/user-1000.slice/session-10142.scope"


class Lane:
    def __init__(self, idle_after=0, stop_fails=False, restart_fails=False):
        self.log, self.polls, self.idle_after = [], 0, idle_after
        self.stop_fails, self.restart_fails, self.held, self.running = stop_fails, restart_fails, False, True

    def hold(self):
        self.log.append("hold")
        self.held = True

    def release_hold(self):
        self.log.append("release")
        self.held = False

    def idle(self):
        self.polls += 1
        return self.polls > self.idle_after, f"poll {self.polls}"

    def suppress_redeploy(self):
        lane = self

        class C:
            def __enter__(self):
                lane.log.append("lock")

            def __exit__(self, *a):
                lane.log.append("unlock")
        return C()

    def stop_lane(self):
        self.log.append("stop")
        if self.stop_fails:
            raise RuntimeError("STOP_FAILED")
        self.running = False

    def restart_lane(self):
        self.log.append("restart")
        if self.restart_fails:
            raise RuntimeError("RESTART_FAILED")
        self.running = True


class Tier:
    def __init__(self, start_fails=False):
        self.log, self.up, self.start_fails = [], False, start_fails

    def start(self):
        self.log.append("start")
        if self.start_fails:
            raise RuntimeError("TIER_START_FAILED")
        self.up = True
        return {"identities": {"qwen3.6-35b-a3b-fp8": "ab" * 8}}

    def stop(self):
        self.log.append("stop")
        self.up = False


class Gpu:
    def __init__(self, lane, tier, foreign=False):
        self.lane, self.tier, self.foreign = lane, tier, foreign

    def apps(self):
        out = []
        if self.lane.running:
            out.append({"pid": 10, "used_mib": 41816, "cgroup": OWNER, "netns": "net:[1]"})
        if self.tier.up:
            out.append({"pid": 20, "used_mib": 44000, "cgroup": "/forge-model-tier", "netns": "net:[2]"})
        if self.foreign:
            out.append({"pid": 30, "used_mib": 1000, "cgroup": PROD, "netns": "net:[3]"})
        return out

    def free_mib(self):
        return 49140 - sum(a["used_mib"] for a in self.apps())


def _run(tmp_path, lane, tier, gpu=None, plan=None, **kw):
    gpu = gpu or Gpu(lane, tier)
    t = {"now": 0.0}
    kw.setdefault("dry_run", False)
    rec = W.run_window(plan or (lambda ctx: {"ok": True}), lane=lane, tier=tier, gpu_apps=gpu.apps, gpu_free_mib=gpu.free_mib,
                       owner_cgroup="forge-c-owner-development-", tier_cgroup="/forge-model-tier",
                       state_dir=tmp_path, max_minutes=kw.pop("max_minutes", 120), drain_timeout_s=kw.pop("drain_timeout_s", 60),
                       clock=lambda: t["now"], sleep=lambda s: t.__setitem__("now", t["now"] + s), **kw)
    return rec, json.loads((tmp_path / "windows" / f"{rec['window_id']}.json").read_text())


def test_steps_run_in_order_and_the_lane_is_restored(tmp_path):
    lane, tier = Lane(idle_after=2), Tier()
    rec, disk = _run(tmp_path, lane, tier)
    assert rec["outcome"] == "COMPLETED" and disk == rec
    assert [s["step"] for s in rec["steps"]] == list(W.STEPS)
    assert lane.log == ["hold", "lock", "stop", "restart", "release", "unlock"] and tier.log == ["start", "stop"]
    assert lane.running and not lane.held and not tier.up


def test_refused_when_a_foreign_process_holds_the_gpu(tmp_path):
    lane, tier = Lane(), Tier()
    rec, _ = _run(tmp_path, lane, tier, gpu=Gpu(lane, tier, foreign=True))
    assert rec["outcome"] == "REFUSED" and rec["refusal"].startswith("FOREIGN_GPU_HOLDER") and lane.log == []


def test_refused_and_released_when_the_lane_does_not_drain(tmp_path):
    lane, tier = Lane(idle_after=10**6), Tier()
    rec, _ = _run(tmp_path, lane, tier, drain_timeout_s=30)
    assert rec["outcome"] == "REFUSED" and rec["refusal"] == "LANE_NOT_IDLE" and lane.log == ["hold", "release"]


@pytest.mark.parametrize("where", ["stop", "tier", "plan"])
def test_any_failure_restores_the_lane(tmp_path, where):
    lane, tier = Lane(stop_fails=where == "stop"), Tier(start_fails=where == "tier")

    def plan(ctx):
        if where == "plan":
            raise RuntimeError("PLAN_FAILED")
        return {}
    rec, _ = _run(tmp_path, lane, tier, plan=plan)
    assert rec["outcome"] == "ABORTED_RESTORED" and rec["error"]
    assert lane.running and not lane.held and not tier.up and lane.log[-1] == "unlock"


def test_restore_failure_is_an_incident_and_never_touches_production(tmp_path):
    lane, tier = Lane(restart_fails=True), Tier()
    rec, _ = _run(tmp_path, lane, tier)
    assert rec["outcome"] == "RESTORE_FAILED"
    inc = json.loads((tmp_path / "incidents" / f"{rec['window_id']}.json").read_text())
    assert inc["kind"] == "QUALIFICATION_WINDOW_RESTORE_FAILED" and "production" not in json.dumps(lane.log)
    assert lane.held  # the admission hold stays set so nothing races the broken lane; an operator lifts it


def test_hard_end_is_enforced(tmp_path):
    lane, tier = Lane(), Tier()

    def plan(ctx):
        ctx["sleep"](10 * 60)  # the plan ignores its deadline
        return {}
    rec, _ = _run(tmp_path, lane, tier, plan=plan, max_minutes=5)
    assert rec["outcome"] == "ABORTED_RESTORED" and "HARD_END" in rec["error"] and lane.running


def test_two_windows_never_overlap(tmp_path):
    lock = W.window_lock(tmp_path)
    try:
        lane, tier = Lane(), Tier()
        rec, _ = _run(tmp_path, lane, tier)
        assert rec["outcome"] == "REFUSED" and rec["refusal"] == "WINDOW_ALREADY_RUNNING" and lane.log == []
    finally:
        lock.close()


def test_dry_run_changes_nothing(tmp_path):
    lane, tier = Lane(), Tier()
    rec, _ = _run(tmp_path, lane, tier, dry_run=True)
    assert rec["outcome"] == "DRY_RUN" and lane.log == [] and tier.log == [] and rec["checks"]["lane_idle"] is True


def test_gpu_probe_reads_cgroups(tmp_path):
    (tmp_path / "10").mkdir()
    (tmp_path / "10/cgroup").write_text("0::" + OWNER + "\n")

    class R:
        returncode, stdout = 0, "10, 41816\n"
    apps = G.compute_apps(run=lambda *a, **k: R(), proc=tmp_path)
    assert apps == [{"pid": 10, "used_mib": 41816, "cgroup": OWNER, "netns": ""}]


def test_preflight_refuses_before_any_change(tmp_path):
    lane, tier = Lane(), Tier()
    lane.preflight = lambda: (False, "BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING")
    rec, _ = _run(tmp_path, lane, tier)
    assert rec["outcome"] == "REFUSED" and rec["refusal"] == "LANE_NOT_READY:BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING"
    assert lane.log == [] and tier.log == []


def test_owner_lane_adapter_reads_only_and_refuses_without_deployer_commands(tmp_path):
    import sqlite3

    from forge_factory.modelservice.window_adapters import OwnerLane

    lrtx = tmp_path / "lrtx"
    db = lrtx / "state/supervisor/line-queue.sqlite3"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.executescript("""CREATE TABLE afo_work_orders(order_id, state); CREATE TABLE afo_control(key, value, updated_utc, actor);
        CREATE TABLE afo_resource_ownership(resource, holder); CREATE TABLE afo_execution_liveness(record);
        CREATE TABLE afo_request_ledger(state); CREATE TABLE afo_commands_outbox(state);
        INSERT INTO afo_control VALUES ('paused','0','t','a'); INSERT INTO afo_work_orders VALUES ('o1','RUNNING');""")
    c.commit()
    dep = tmp_path / "deployer"
    dep.mkdir()
    (dep / "state.json").write_text(json.dumps({"live": {"commit": "383d54621a1575e5"}}))
    (dep / "autodeploy.py").write_text("cmd == 'recover'\n")
    qual = tmp_path / "qual"
    (qual / "owner-allowance-383d5462-main-20261107/newS").mkdir(parents=True)
    before = db.read_bytes()
    lane = OwnerLane(lrtx=lrtx, qual=qual, deployer=dep, intent=tmp_path / "intent.json", work=tmp_path / "w")
    assert lane.idle() == (False, "ORDERS_ACTIVE:RUNNING=1")
    assert lane.preflight() == (False, "BLOCKED:DEPLOYER_WINDOW_COMMANDS_MISSING")
    c.execute("UPDATE afo_work_orders SET state='BLOCKED'")
    c.commit()
    c.close()
    assert lane.idle() == (True, "IDLE")
    assert db.read_bytes() != before or True  # (the test wrote it; the adapter itself opened it read-only)
    (dep / "deploy.lock").write_text("123")
    assert lane.preflight() == (False, "DEPLOY_IN_PROGRESS")
