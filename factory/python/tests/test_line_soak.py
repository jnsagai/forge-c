"""Line-local read-only observation controls. Synthetic fixtures below are never live soak evidence."""
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_soak as L, fault_observer as O, qualification as Q, operational_campaign as C
from forge_factory.afo import operational_collection, soak
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file
from test_da014_qualification import identity

PROFILE = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"


@pytest.fixture
def local_plan(tmp_path, monkeypatch):
    # Fixed synthetic candidate identity belongs only to these deterministic fixtures.
    monkeypatch.setattr(L, "_revision", lambda: {"commit": "a" * 40, "dirty": False})
    monkeypatch.setattr(Q, "revision", lambda: "a" * 40)
    data = tmp_path / "application"
    line = data / "line"
    state = line / "lrtx/state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data))
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    control = tmp_path / "private-control"
    control.mkdir(mode=0o700)
    intent = control / "fixture-intent.json"
    immutable_json(intent, {"mode": "RUNNING", "epoch": 1})
    Store(state / "supervisor/line-queue.sqlite3")
    raw = L.observer_plan(data_root=data, launch_dir=line, intent=intent, evidence_root=evidence,
                          mount_uuid="12345678-abcd", profile=PROFILE, max_samples=8)
    path = evidence / "observer-plan.json"
    immutable_json(path, raw)
    ref = {"path": str(path), "sha256": sha256_file(path)}
    manifest = Q.freeze("operation-24", evidence / "manifest.json", identity=identity(), inputs=[path])
    heartbeat = Path(raw["heartbeat"])
    immutable_json(heartbeat, {"pid": 12345, "cycle": 1, "epoch": time.time(), "ok": True, "mode": "PILOT"})
    unit = {"ActiveState": "active", "SubState": "running", "Result": "success", "MainPID": "12345",
            "ControlGroup": "/fixture-line-conductor.service", "NRestarts": "0"}
    monkeypatch.setattr(O, "unit_status", lambda unit_name: dict(unit))
    calls = []
    status = {"status": "UP", "health": {"fabro": True, "gateway": True, "ollama": True, "llama_server": True}}

    def run(args, **kw):
        calls.append((args, kw))
        if args[0] == "findmnt":
            return SimpleNamespace(returncode=0, stdout="12345678-abcd\n")
        assert args[-1] == "status" and "start" not in args and "serve" not in args
        return SimpleNamespace(returncode=0, stdout=json.dumps(status))
    monkeypatch.setattr(L.subprocess, "run", run)
    http = []
    monkeypatch.setattr(O, "_healthy", lambda url: http.append(url) or True)
    return SimpleNamespace(tmp=tmp_path, raw=raw, ref=ref, manifest=manifest, status=status, calls=calls,
                           http=http, unit=unit, heartbeat=heartbeat, evidence=evidence)


def test_fixed_line_paths_and_profile_are_frozen_in_existing_observer_plan(local_plan):
    p = local_plan
    assert O.plan(p.manifest, p.ref) == p.raw
    assert p.raw["unit"] == "forge-line-conductor-local.service"
    assert p.raw["database"].endswith("supervisor/line-queue.sqlite3")
    assert p.raw["heartbeat"].endswith("supervisor/line-conductor.heartbeat")
    before = copy.deepcopy(p.raw)
    L.validate_runtime(p.raw["line_runtime"], p.raw)
    assert p.raw == before


@pytest.mark.parametrize("patch", [
    {"unit": "forge-conductor.service"}, {"database": "/tmp/other.sqlite"},
    {"heartbeat": "/tmp/other-heartbeat"}, {"intent": "APPLICATION"}, {"evidence_root": "APPLICATION"},
])
def test_wrong_line_or_application_bound_survivor_is_refused(local_plan, patch):
    raw = copy.deepcopy(local_plan.raw)
    raw.update({k: raw["data_root"] if v == "APPLICATION" else v for k, v in patch.items()})
    with pytest.raises(Refused):
        L.validate_runtime(raw["line_runtime"], raw)


def test_changed_profile_source_route_and_unbounded_probe_are_refused(local_plan):
    for key, value in [("profile_sha256", "0" * 64), ("adapter_sha256", "0" * 64),
                       ("timeout_seconds", 0), ("timeout_seconds", True), ("fabro_host_port", 65536)]:
        raw = copy.deepcopy(local_plan.raw)
        raw["line_runtime"][key] = value
        with pytest.raises(Refused):
            L.validate_runtime(raw["line_runtime"], raw)
    raw = copy.deepcopy(local_plan.raw)
    raw["health_urls"]["fabro"] = "http://127.0.0.1:32291/health"
    with pytest.raises(Refused, match="HEALTH_ROUTE_MISMATCH"):
        L.validate_runtime(raw["line_runtime"], raw)


@pytest.mark.parametrize("actual", [{"commit": "b" * 40, "dirty": False}, {"commit": "a" * 40, "dirty": True}])
def test_changed_or_dirty_executing_candidate_cannot_add_qualified_observations(local_plan, monkeypatch, actual):
    monkeypatch.setattr(L, "_revision", lambda: actual)
    with pytest.raises(Refused, match="CANDIDATE_CHANGED_OR_DIRTY"):
        O.plan(local_plan.manifest, local_plan.ref)
    assert local_plan.calls == []


def test_campaign_and_observer_candidate_pins_must_match(local_plan):
    manifest = dict(local_plan.manifest, source_revision="b" * 40)
    with pytest.raises(Refused, match="CAMPAIGN_REVISION_MISMATCH"):
        O.plan(manifest, local_plan.ref)


def test_probes_use_actual_line_unit_and_namespace_status_without_a_model_call(local_plan):
    p = local_plan
    assert O.health(p.raw, 120) == {"conductor": True, "fabro": True, "gateway": True, "data_volume": True}
    command, kwargs = p.calls[0]
    assert command[-4:] == ["forge_factory.lrtx.stack", "--profile", PROFILE, "status"]
    assert kwargs["timeout"] == 15 and kwargs["env"]["FORGE_LRTX_ROOT"].endswith("/line/lrtx")
    assert p.http == ["http://127.0.0.1:32397/health"]  # namespace gateway is not the unrelated host default


def test_provider_down_or_replaced_conductor_is_not_healthy_worker_or_control(local_plan):
    p = local_plan
    p.status["health"]["llama_server"] = False
    assert O.health(p.raw, 120) == {"conductor": True, "fabro": True, "gateway": False, "data_volume": True}
    p.status["health"]["llama_server"] = "true"
    p.unit["MainPID"] = "9"
    health = O.health(p.raw, 120)
    assert health["gateway"] is False and health["conductor"] is False


def test_live_start_refuses_missing_authority_without_creating_a_soak(local_plan, monkeypatch):
    p = local_plan
    seen = []
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: seen.append(kw) or {"status": "BLOCKED", "blockers": ["AUTH_NOT_CURRENT"]})
    result = L.start(p.manifest, "soak-line-fixture", "missing", p.ref)
    assert "AUTH_NOT_CURRENT" in result["blockers"] and seen[0]["live"] is True
    assert not soak.path("soak-line-fixture").exists()


def test_campaign_authority_alone_cannot_replace_missing_autonomy_qualification(local_plan, monkeypatch):
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    monkeypatch.setattr(C, "start", lambda *a, **kw: pytest.fail("preparation cannot start a live campaign"))
    result = L.start(local_plan.manifest, "soak-line-fixture", "synthetic-authority", local_plan.ref)
    assert result["status"] == "BLOCKED"
    assert result["blockers"] == ["LINE_AUTONOMY_PREREQUISITES_NOT_QUALIFIED"]


def test_existing_campaign_entrypoint_cannot_bypass_line_qualification(local_plan, monkeypatch):
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    result = C.start(local_plan.manifest, "soak-line-fixture", "synthetic-authority", observer_plan_ref=local_plan.ref)
    assert result["blockers"] == ["LINE_AUTONOMY_PREREQUISITES_NOT_QUALIFIED"]
    assert not soak.path("soak-line-fixture").exists()


def test_existing_collection_replays_real_artifacts_but_cannot_claim_short_fixture_is_live_soak(local_plan):
    p = local_plan
    sid = "soak-line-fixture"
    soak.start(sid, 24, 30, "SYNTHETIC-FIXTURE-NOT-LIVE-AUTHORITY")
    immutable_json(soak.path(sid).with_suffix(".manifest.json"), p.manifest)
    collector = operational_collection.Collector(p.manifest, sid, p.ref)
    first = collector(sid)
    second = collector(sid)
    assert first["healthy"] is True and second["collection_sequence"] == 1
    assert collector.verify()["status"] == "SOURCE_REPLAY_PASS"
    report = C.report(p.manifest, sid, observer_plan_ref=p.ref)
    assert report["status"] != "DEMONSTRATED" and report["missing_faults"] and report["real_work_exposures"] == 0


def test_resume_after_grant_expiry_keeps_existing_nonterminating_collector_path(local_plan, monkeypatch):
    p = local_plan
    calls = []
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"blockers": ["AUTH_NOT_CURRENT"]} if kw.get("live") else {"blockers": []})
    monkeypatch.setattr(C, "collect", lambda *a, **kw: calls.append(kw) or {"service_stop_at_end": False})
    assert L.collect(p.manifest, "soak-line-fixture", p.ref, max_samples=2)["service_stop_at_end"] is False
    assert calls[0]["max_samples"] == 2


def test_prepare_cli_is_immutable_and_never_runs_a_campaign(local_plan, tmp_path, capsys):
    p = local_plan
    out = tmp_path / "prepared.json"
    args = ["prepare", "--data-root", p.raw["data_root"], "--launch-dir", p.raw["line_runtime"]["launch_dir"],
            "--intent", p.raw["intent"], "--evidence-root", p.raw["evidence_root"],
            "--mount-uuid", p.raw["mount_uuid"], "--profile", PROFILE, "--out", str(out)]
    assert L.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PREPARED_NOT_RUN"
    assert json.loads(out.read_text())["line_runtime"]["candidate_revision"] == "a" * 40
    assert p.calls == [] and not soak.path("soak-line-fixture").exists()
    assert L.main(args) == 0  # identical replay is permitted by the shared immutable publisher
    args[args.index("--mount-uuid") + 1] = "bbbbbbbb-cccc"
    with pytest.raises(Refused):
        L.main(args)


def test_frozen_plan_retains_existing_independent_work_proof_verifier(local_plan):
    from forge_factory.afo.operational_work import work_plan

    assert work_plan(local_plan.manifest, local_plan.ref) == local_plan.raw
