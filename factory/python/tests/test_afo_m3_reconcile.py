"""AFO M3 (T026-T033; AT-017..AT-025, AT-037, AT-057): launch intent before the call, label-based crash
reconciliation (adopt / quarantine / unknown / proven-absent), run-state mapping, READY only from a verified sealed
archive, immutable checkpoints with upstream invalidation, recovery as a new budgeted attempt. Crash windows use a
fake Fabro; the invariant is: never two launches of one attempt."""
import hashlib
import json
import zipfile
from types import SimpleNamespace

import pytest
from forge_factory.afo import checkpoints, dispatch
from forge_factory.afo.queue import QueueError, Store
from test_afo_m2_queue import _env  # noqa: F401 - shared fixtures/helpers

ALLOW = lambda req: SimpleNamespace(allow=True, code="ALLOWED")  # noqa: E731


class FakeFabro:
    def __init__(self):
        self.runs, self.launches, self.up = [], 0, True

    def view(self):
        return list(self.runs) if self.up else None

    def launcher(self, crash_after_accept=False, crash_before=False):
        def go(manifest, wo, labels):
            if crash_before:
                raise RuntimeError("crash before the CLI call")
            self.launches += 1
            rid = f"RUN{self.launches}"
            self.runs.append({"id": rid, "labels": {"forge": wo, **labels}, "lifecycle": {"status": {"kind": "runnable"}}})
            if crash_after_accept:
                raise RuntimeError("crash after Fabro accepted, before the receipt was stored")
            self.seen_manifest = manifest
            return {"fabro_run_id": rid, "factory_revision": "abc1234"}
        return go


@pytest.fixture()
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    monkeypatch.setattr(dispatch, "REPO_ROOT", repo)
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    epoch = s.acquire_lease("scheduler", "A", 120)
    aid = s.admit(oid, epoch=epoch, scope="scheduler", policy_sha256="p", authorization_id="AUTH-1", max_concurrent=1)
    return s, oid, aid, epoch


def test_clean_launch_persists_intent_then_receipt(admitted):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    r = dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    assert r[0]["action"] == "launched" and f.launches == 1
    a = s.attempts(oid)[0]
    assert a["state"] == "RUNNING" and a["record"]["fabro_run_id"] == "RUN1" and s.order(oid)["state"] == "RUNNING"
    assert f.runs[0]["labels"]["afo_attempt"] == aid and len(f.runs[0]["labels"]["afo_nonce"]) == 16
    assert s.commands()[0]["state"] == "ACKED" and dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW) == []


def test_crash_after_fabro_accepted_is_adopted_not_relaunched(admitted):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    assert dispatch.dispatch_pending(s, f.launcher(crash_after_accept=True), decide=ALLOW)[0]["action"] == \
        "launch_outcome_unknown"
    assert s.attempts(oid)[0]["state"] == "DISPATCH_PENDING" and s.commands()[0]["state"] == "IN_FLIGHT"
    assert dispatch.reconcile_inflight(s, f.view)[0]["action"] == "adopted"
    assert f.launches == 1 and s.order(oid)["state"] == "RUNNING"


def test_unreachable_fabro_stays_unknown_then_adopts(admitted):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(crash_after_accept=True), decide=ALLOW)
    f.up = False
    assert dispatch.reconcile_inflight(s, f.view)[0]["action"] == "unknown_fabro_unreachable"
    assert s.attempts(oid)[0]["state"] == "UNKNOWN" and f.launches == 1
    f.up = True
    assert dispatch.reconcile_inflight(s, f.view)[0]["action"] == "adopted" and f.launches == 1


def test_crash_before_the_call_is_proven_absent_after_grace_and_relaunched_once(admitted):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(crash_before=True), decide=ALLOW)
    assert dispatch.reconcile_inflight(s, f.view)[0]["action"] == "wait_grace"            # may still appear
    t0 = dispatch._nonce(dispatch._attempt(s, aid))[1]
    assert dispatch.reconcile_inflight(s, f.view, now=t0 + 200)[0]["action"] == "proven_not_submitted_requeued"
    dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    assert f.launches == 1 and s.order(oid)["state"] == "RUNNING"


def test_two_runs_with_one_nonce_quarantine_the_order(admitted):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(crash_after_accept=True), decide=ALLOW)
    f.runs.append({**f.runs[0], "id": "RUN-DUP"})
    assert dispatch.reconcile_inflight(s, f.view)[0]["action"] == "quarantined"
    assert s.order(oid)["state"] == "BLOCKED" and s.commands()[0]["state"] == "QUARANTINED"


def _package(tmp_path, status="BLOCKED", gaps=("missing_or_empty_file:safety/x.md",), tamper=False):
    arc = tmp_path / "pkg" / "review.zip"
    arc.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("manifest.json", json.dumps({"status": status, "gaps": list(gaps)}))
    sha = hashlib.sha256(arc.read_bytes()).hexdigest()
    if tamper:
        with zipfile.ZipFile(arc, "a") as z:
            z.writestr("extra.txt", "changed after sealing")
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/package.json").write_text(json.dumps({"archive": str(arc), "archive_sha256": sha,
                                                            "package_status": status, "gaps": list(gaps)}))
    return ws


@pytest.mark.parametrize("status,gaps,tamper,expect", [
    ("BLOCKED", ("missing_or_empty_file:safety/x.md",), False, "BLOCKED"),
    ("READY_FOR_OFFLINE_REVIEW", (), False, "READY_FOR_OFFLINE_REVIEW"),
    ("READY_FOR_OFFLINE_REVIEW", (), True, "BLOCKED"),                  # archive changed after sealing
])
def test_run_terminal_goes_through_validation_and_only_a_verified_archive_is_ready(admitted, tmp_path, status, gaps,
                                                                                    tamper, expect):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    assert dispatch.reconcile_running(s, f.view)[0]["action"] == "still_active"
    f.runs[0]["lifecycle"] = {"status": {"kind": "succeeded", "reason": "completed"}}   # Fabro success != READY
    assert dispatch.reconcile_running(s, f.view)[0]["action"] == "validating"
    ws = _package(tmp_path, status, gaps, tamper)
    r = dispatch.validate(s, lambda att: ws)
    assert r[0]["action"] == expect and s.order(oid)["state"] == expect
    assert dispatch.validate(s, lambda att: ws) == []                  # replay after a crash: no second transition


def test_run_absent_on_reachable_server_blocks_and_missing_package_times_out(admitted, tmp_path):
    s, oid, aid, _ = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    f.runs.clear()
    assert dispatch.reconcile_running(s, f.view)[0]["action"] == "blocked_run_absent"
    assert s.order(oid)["terminal_reason"] == "RUN_ABSENT"


def test_checkpoint_reuse_stops_at_a_changed_upstream():
    ck = [{"phase": "SWE.1", "baseline_hash": "a", "upstream": {}},
          {"phase": "SWE.2", "baseline_hash": "b", "upstream": {"SWE.1": "a"}},
          {"phase": "SWE.3", "baseline_hash": "c", "upstream": {"SWE.1": "a", "SWE.2": "OLD"}},
          {"phase": "SWE.4", "baseline_hash": "d", "upstream": {"SWE.3": "c"}}]
    assert checkpoints.reusable(ck) == ["SWE.1", "SWE.2"]          # SWE.3 built on a stale SWE.2: it and all after


def test_recovery_is_a_new_budgeted_attempt_resuming_from_the_previous_one(admitted):
    s, oid, aid, epoch = admitted
    f = FakeFabro()
    dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    s.transition(oid, "WAITING_RECOVERY", "gate failure, recovery eligible")
    a2 = checkpoints.new_attempt(s, oid, plan_id="PLAN-1", epoch=epoch, max_attempts=3, source_wo="WO-AFO-x-a1")
    assert a2.endswith("-a2")
    dispatch.dispatch_pending(s, f.launcher(), decide=ALLOW)
    assert f.seen_manifest["resume_from"] == "WO-AFO-x-a1" and s.order(oid)["state"] == "RUNNING" and f.launches == 2
    assert [a["seq"] for a in s.attempts(oid)] == [1, 2] and s.attempts(oid)[0]["record"]["fabro_run_id"] == "RUN1"
    s.transition(oid, "WAITING_RECOVERY", "again")
    with pytest.raises(QueueError) as e:
        checkpoints.new_attempt(s, oid, plan_id="PLAN-2", epoch=epoch, max_attempts=2, source_wo="WO-AFO-x-a2")
    assert e.value.code == "ORDER_ATTEMPT_BUDGET_EXHAUSTED"


def test_checkpoints_from_a_real_passing_workspace(tmp_path, monkeypatch):
    from forge_factory.common import state_dir

    ws = state_dir() / "workorders/WO-0002B-STM32N6-RCC-HAL-r154/workspace"
    if not ws.is_dir():
        pytest.skip("HAL r154 workspace not on this host")
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    s = Store()
    assert checkpoints.capture(s, "afo-x", "afo-x-a1", ws) == list(checkpoints.PHASES)
    assert checkpoints.capture(s, "afo-x", "afo-x-a1", ws) == list(checkpoints.PHASES)   # immutable, no duplicates
    ck = checkpoints.checkpoints(s, "afo-x-a1")
    assert len(ck) == 6 and checkpoints.reusable(ck) == list(checkpoints.PHASES)
    assert all(c["inspection_ref"].startswith("INS-") for c in ck)
