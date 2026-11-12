"""Cloud slots preserve existing local admission and require their own policy."""
import json
from types import SimpleNamespace as S

import pytest
import test_line_conductor_m3 as M3
import yaml
from forge_factory.afo import line_orders as LO
from forge_factory.afo.line_cloud import PROFILE, CloudPlacer
from test_line_conductor_m3 import X, _git, grant, lin, lineage, write_campaign


@pytest.fixture
def env(tmp_path, monkeypatch):
    return M3.env.__wrapped__(tmp_path, monkeypatch)


def planner(live):
    line = S(live_runs=lambda: live, gpu_holders=lambda: pytest.fail("cloud queried local GPU"))
    return CloudPlacer(line, policy_path="unused")


def running(rid):
    return S(state="RUNNING", current=S(rid=rid))


def test_cloud_admits_a_second_driver_without_touching_gpu():
    p = planner(["first"])
    assert p._gpu([running("first")]) == {"busy": False, "reason": None, "wo": None, "used": 1, "capacity": 2}
    assert p._gpu([running("first"), running("second")])["busy"]


@pytest.mark.parametrize("live,reason", [(None, "FABRO_API_UNREACHABLE"),
                                         (["unowned"], "RUN_LIVE_NOT_IN_CAMPAIGN")])
def test_unknown_or_unobservable_cloud_work_prevents_dispatch(live, reason):
    assert planner(live)._gpu([])["reason"] == reason


def test_local_admission_capacity_remains_one_and_cloud_needs_distinct_policy():
    local = LO.Placer(S())
    assert local._admission_capacity(None) == 1
    p = planner([])
    policy = LO.LinePolicy({"line": "local", "pacing": {"max_concurrent_cloud_runs": 2}, "models": PROFILE},
                           "fixture", [], None)
    with pytest.raises(ValueError, match="CLOUD_POLICY_REQUIRED"):
        p._admission_capacity(policy)
    policy.raw["line"] = "cloud"
    assert p._admission_capacity(policy) == 2
    policy.raw["pacing"]["max_concurrent_cloud_runs"] = 3
    with pytest.raises(ValueError, match="CLOUD_POLICY_REQUIRED"):
        p._admission_capacity(policy)


def test_cloud_requests_rework_authority_without_local_service_actions():
    p = planner([])
    plan = S(lineage=S(driver_class="CRC", profile=PROFILE), action="PLACE",
             order={"kind": "RETRY", "wo": "WO-F014-CMP-SWE3-CRCHAL-20261104-T1"})
    assert [a for a, _ in p._requests(plan)] == ["submit_workorder", "launch_workorder", "recover_workorder"]
    assert all("service_action" not in args for _, args in p._requests(plan))
    assert all(args["order_id"] == plan.order["wo"] for _, args in p._requests(plan))


def test_cloud_act_cannot_select_local_launcher_by_omitting_cloud_flag(monkeypatch):
    from forge_factory.afo import line_conductor
    monkeypatch.setattr(LO, "RealLine", lambda *a, **k: pytest.fail("constructed local GPU launcher"))
    with pytest.raises(SystemExit, match="CLOUD_ACT_REQUIRES_CLOUD_ACCOUNT_LINE"):
        line_conductor.main(["--mode", "ACT", "--line", "cloud", "--once"])


def cloud(env, *, signed=True, revision="82fabdb9"):
    path = env["tmp"] / "line-policy.yaml"
    policy = yaml.safe_load(path.read_text())
    policy.update(line="cloud", models=PROFILE, campaigns_dir=str(env["camp"]))
    policy["pacing"]["max_concurrent_cloud_runs"] = 2
    path.write_text(yaml.safe_dump(policy))
    entries = [lineage("crc-hal", "CRCHAL", "20261104-T1", priority=60),
               lineage("wwdg-hal", "WWDGHAL", "20261104-T1", priority=50)]
    for item in entries:
        item.update(profile=PROFILE, run_model="gpt-6.1-terra", factory_revision=revision)
    campaign = write_campaign(env, entries, commit=False)
    d = yaml.safe_load(campaign.read_text())
    d.update(line="cloud", wo_prefix="WO-F014-CMP")
    campaign.write_text(yaml.safe_dump(d))
    _git(env["camp"], "add", campaign.name)
    _git(env["camp"], "commit", "-qm", "cloud campaign")
    grant(env, models=[PROFILE], sign=signed)
    env["line"].gpu_holders = lambda: pytest.fail("queried local GPU")
    def ended(wo, rid):
        recorded = env["line"].workspace(wo) / ".forge-run/fabro_run_id"
        return (recorded.is_file() and recorded.read_text().strip() == rid
                and env["line"].fabro.get(rid, "").startswith(("succeeded", "failed", "cancelled")))
    env["line"].ended_run = ended
    return CloudPlacer(env["line"], policy_path=path, campaigns_dir=env["camp"],
                       auth_base=env["tmp"] / "auth", allowed_signers=env["signers"],
                       clock=env["clock"], capa_of={})


def test_two_cloud_drivers_run_then_failure_reworks_from_last_passed_phase(env):
    p = cloud(env)
    p.cycle()
    p.cycle()
    assert len(env["line"].launched) == 2
    assert p.cycle()["gpu"]["busy"]
    for item in list(env["line"].launched):
        env["line"].finish(item["wo"])
    p.cycle()
    p.cycle()
    assert len(env["line"].launched) == 4
    crc = "WO-F014-CMP-SWE2-CRCHAL-20261104-T1"
    env["line"].finish(crc, X)
    p.cycle()
    last = env["line"].launched[-1]
    assert last["wo"] == crc + "B"
    assert last["--resume-from"] == "WO-F014-CMP-SWE1-CRCHAL-20261104-T1"
    assert lin(p.cycle(), "wwdg-hal")["state"] == "RUNNING"
    env["clock"].tick()
    env["line"].finish(crc + "B", ["another current finding"])
    p.cycle()
    latest = LO._load(LO.supervisor_dir() / "line-orders" / f"{crc}C.json")
    assert latest["rework_context"]["source_work_order"] == crc + "B"


def test_unsigned_cloud_grant_never_places_orders(env):
    p = cloud(env, signed=False)
    out = p.cycle()
    assert out["mode"] == "OBSERVING"
    assert not env["line"].launched


def test_sparse_manual_attempt_names_keep_last_good_and_four_strikes(env):
    p = cloud(env)
    fake = env["line"]

    def existing(phase, suffix, result):
        wo = f"WO-F014-CMP-SWE{phase}-CRCHAL-20261104-T1{suffix}"
        fake.spawn_launch(["launch", "82fabdb9", wo, "ex-crc-hal", PROFILE, "--model", "gpt-6.1-terra",
                           "--stop-after", f"SWE.{phase}"], wo)
        fake.finish(wo, result)
        env["clock"].tick()
        return wo

    good = existing(1, "D", "PASS")
    for suffix in ("E", "F", "G", "H"):
        existing(2, suffix, X)
    out = p.cycle()
    crc = lin(out, "crc-hal")
    assert crc["last_good"]["wo"] == good
    assert crc["state"] == "ESCALATED" and crc["strikes"]["count"] == 4
    assert fake.launched[-1]["wo"] == "WO-F014-CMP-SWE1-WWDGHAL-20261104-T1"


def test_uncertain_native_submission_holds_its_lineage_and_only_one_slot(env):
    p = cloud(env)
    wo = "WO-F014-CMP-SWE1-CRCHAL-20261104-T1"
    folder = env["line"].runs / ".launch" / wo
    folder.mkdir(parents=True)
    (folder / "attempt-1.json").write_text(json.dumps({"outcome": "CLOUD_DISPATCH_UNCERTAIN", "class": "REFUSED"}))
    out = p.cycle()
    assert lin(out, "crc-hal")["state"] == "LAUNCHING"
    assert [a["wo"] for a in env["line"].launched] == ["WO-F014-CMP-SWE1-WWDGHAL-20261104-T1"]
    p.cycle()
    assert len(env["line"].launched) == 1


def test_cloud_act_feed_validates_and_reports_both_drivers(env):
    from forge_factory.afo import line_conductor as LC
    p = cloud(env)
    observer = LC.Observer("cloud", env["line"].launch_d, LC.FabroView(snapshot=env["line"].fabro))
    conductor = LC.LineConductor(observer, placer=p)
    conductor.cycle(env["clock"]())
    env["clock"].tick()
    conductor.cycle(env["clock"]())
    env["clock"].tick()
    feed = conductor.cycle(env["clock"]())
    assert feed["supervisor"]["mode"] == "PILOT"
    assert len(feed["placement"]["lineages"]) == 2
    assert {item["state"] for item in feed["placement"]["lineages"]} == {"RUNNING"}
    assert LC.feed_errors(feed) == []


def test_restart_after_retry_admission_preserves_its_name_and_findings(env):
    p = cloud(env)
    p.cycle()
    p.cycle()
    for item in list(env["line"].launched):
        env["line"].finish(item["wo"])
    p.cycle()
    p.cycle()
    crc = "WO-F014-CMP-SWE2-CRCHAL-20261104-T1"
    env["line"].finish(crc, X)
    original = env["line"].spawn_launch
    def crash(*args):
        raise RuntimeError("fixture interruption after durable admission")
    env["line"].spawn_launch = crash
    with pytest.raises(RuntimeError, match="after durable admission"):
        p.cycle()
    retry = LO.supervisor_dir() / "line-orders" / f"{crc}B.json"
    before = json.loads(retry.read_text())
    assert before["rework_context"]["source_work_order"] == crc
    env["line"].spawn_launch = original
    p.cycle()
    after = json.loads(retry.read_text())
    assert after["rework_context"] == before["rework_context"] and after["digest"] == before["digest"]
    assert env["line"].launched[-1]["wo"] == crc + "B"
    assert not retry.with_name(f"{crc}C.json").exists()
