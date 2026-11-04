"""CAPA-151: changing campaign series must not strand a terminal own run's capacity."""
import json
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_orders as LO, line_launcher as LL
from forge_factory.afo.queue import Store
from test_line_conductor_m3 import env, grant, placer, lineage, write_campaign, queue_rows


def setup_old(env):
    write_campaign(env, [lineage("crc", "CRCHAL", "20261103-L1", phases=["SWE.1"])])
    grant(env)
    pl = placer(env)
    pl.cycle()
    pl.cycle()
    wo = env["line"].launched[-1]["wo"]
    row = queue_rows()[wo]
    rid = (env["line"].workspace(wo) / ".forge-run/fabro_run_id").read_text()
    env["line"].LL = LL
    env["line"].host = SimpleNamespace(fabro_run=lambda run_id: {
        "id": rid, "source_directory": str(env["line"].workspace(wo)),
        "lifecycle": {"status": {"kind": "failed"}}})
    env["line"].ended_run = lambda w, r: LO.RealLine.ended_run(env["line"], w, r)
    env["line"].finish(wo, "NO")
    policy = LO.load_policy(env["tmp"] / "line-policy.yaml")
    auth = LO.verify_grant(policy, now=env["clock"](), base=env["tmp"] / "auth", allowed_signers=env["signers"])
    return pl, wo, row, rid, policy, auth


def test_terminal_old_series_releases_capacity_without_changing_payload(env):
    pl, wo, row, rid, policy, auth = setup_old(env)
    store = Store(pl.queue_path)
    before = store.order(row["order_id"])
    spec = LO.supervisor_dir() / "line-orders" / (wo + ".json")
    spec_bytes = spec.read_bytes()
    events = pl._reconcile([], policy, auth, [], env["clock"]())
    assert events == [{"action": "QUEUE_SYNC", "wo": wo, "outcome": "ENDED_NO"}]
    after = store.order(row["order_id"])
    assert after["state"] == "BLOCKED"
    assert after["envelope"] == before["envelope"] and spec.read_bytes() == spec_bytes
    assert store.attempts(row["order_id"])[-1]["state"] == "FAILED"
    count = len(store.events(row["order_id"]))
    assert pl._reconcile([], policy, auth, [], env["clock"]()) == []
    assert len(store.events(row["order_id"])) == count
    write_campaign(env, [lineage("crc", "CRCHAL", "20261104-L2", phases=["SWE.1"])])
    pl.cycle()
    assert len(env["line"].launched) == 2


@pytest.mark.parametrize("problem", ["live", "unknown", "wrong_source", "wrong_id", "wrong_attempt", "spec_changed", "denied", "foreign_line"])
def test_old_series_is_not_settled_without_matching_terminal_authority(env, problem):
    pl, wo, row, rid, policy, auth = setup_old(env)
    if problem in ("live", "unknown", "wrong_source", "wrong_id"):
        def probe(_):
            if problem == "unknown": raise LL.FabroUnavailable("offline")
            return {"id": "another" if problem == "wrong_id" else rid,
                    "source_directory": "/other/tenant" if problem == "wrong_source" else str(env["line"].workspace(wo)),
                    "lifecycle": {"status": {"kind": "running" if problem == "live" else "failed"}}}
        env["line"].host.fabro_run = probe
    elif problem == "wrong_attempt":
        (env["line"].workspace(wo) / ".forge-run/fabro_run_id").write_text("another")
    elif problem == "spec_changed":
        spec = LO.supervisor_dir() / "line-orders" / (wo + ".json")
        d = json.loads(spec.read_text()); d["revision"] = "other"; spec.write_text(json.dumps(d))
    elif problem == "denied":
        auth.allow = False
    elif problem == "foreign_line":
        pl.line_id = "foreign"
    assert pl._reconcile([], policy, auth, [], env["clock"]()) == []
    assert Store(pl.queue_path).order(row["order_id"])["state"] == "RUNNING"
