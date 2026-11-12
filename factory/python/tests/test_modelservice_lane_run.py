"""017 T048/T049: qualification orders run in the lane's own user+network namespace, on the profile's own ports, with
the model service as the only way out; the owner lane is never reached and no model server is started."""
from __future__ import annotations

import subprocess

import pytest
import yaml

from forge_factory.lrtx import profile as lp
from forge_factory.modelservice import lane, lane_run, window_plans
from forge_factory.modelservice.lane import LaneConfig, LaneError

PROFILE = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"


def _lane(tmp_path, mode="external", base_url=None):
    r = tmp_path / "qual-lane"
    r.mkdir()
    ms = {"mode": mode, "base_url": base_url or f"unix:{r / 'run/tier.sock'}", "credential_ref": "forge-qual",
          "expected_identity": {}, "share": {"concurrency": 1, "queue_wait_max_s": 900}}
    (r / "model-service.yaml").write_text(yaml.safe_dump(ms))
    return r


@pytest.fixture
def clean_env(monkeypatch):
    for k in lane_run.OWNER_CONTEXT:
        monkeypatch.delenv(k, raising=False)


def test_only_an_external_lane_outside_the_taken_roots_is_external(tmp_path, monkeypatch):
    r = _lane(tmp_path)
    assert lane_run.external_model_service(r)["mode"] == "external"
    o = tmp_path / "o"
    o.mkdir()
    assert lane_run.external_model_service(_lane(o, mode="owned")) is None
    monkeypatch.setattr(lane_run, "TAKEN_ROOTS", (tmp_path,))
    assert lane_run.external_model_service(r) is None
    assert lane_run.external_model_service(None) is None and lane_run.external_model_service(tmp_path / "none") is None


def test_the_namespace_program_starts_only_gateway_and_fabro_on_the_profile_ports(tmp_path, clean_env):
    r = _lane(tmp_path)
    lr = lane_run.LaneRunner(LaneConfig(root=r), PROFILE)
    e = lr.env()
    s = lr.script(["/v/bin/python", "-m", "forge_factory.workorder", "--wo", "WO-X"], e)
    ports = lp.load(PROFILE)["deployment"]["ports"]
    assert s.splitlines()[1] == "ip link set lo up || exit 90"
    assert f"gateway_external --port {ports['gateway']}" in s and f"127.0.0.1:{ports['fabro']}/health" in s
    assert "FORGE_GATEWAY_REASONING=" in s and "FORGE_GATEWAY_REQUEST_TIMEOUT_S=" in s
    assert "forge_factory.workorder --wo WO-X" in s
    for bad in ("llama-server", "ollama serve", "lrtx.stack serve", "gpu.lock", "nvidia-smi"):
        assert bad not in s
    assert e["FORGE_LRTX_ROOT"] == str(r) and e["FORGE_FABRO_URL"].endswith(f":{ports['fabro']}/api/v1")
    assert e["FORGE_STATE_DIR"] == str(r / "state")


def test_an_order_runs_in_a_fresh_namespace_with_the_lane_venv(tmp_path, clean_env, monkeypatch):
    r = _lane(tmp_path)
    lr = lane_run.LaneRunner(LaneConfig(root=r), PROFILE)
    seen = {}
    monkeypatch.setattr(lane_run.subprocess, "run", lambda argv, **kw: seen.update(argv=argv, env=kw["env"]) or 0)
    lr.run(["python", "-m", "forge_factory.workorder"], cwd="/", env={}, capture_output=True, text=True, timeout=60)
    assert seen["argv"][:5] == ["unshare", "-rn", "--kill-child", "bash", "-c"]
    assert f"{r}/venv/bin/python -m forge_factory.workorder" in seen["argv"][5]
    assert seen["env"]["FORGE_MODEL_SERVICE_SECRETS"]


def test_an_owner_lane_context_is_refused(tmp_path, clean_env, monkeypatch):
    lr = lane_run.LaneRunner(LaneConfig(root=_lane(tmp_path)), PROFILE)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", "/x/intent.json")
    with pytest.raises(LaneError, match="OWNER_LANE_CONTEXT"):
        lr.env()


def test_the_owner_root_is_refused_as_a_lane():
    with pytest.raises(LaneError, match="ROOT_COLLISION"):
        lane_run.LaneRunner(LaneConfig(root=lane.TAKEN_ROOTS[0] / "lrtx"), PROFILE)


def test_ready_names_what_is_missing(tmp_path, monkeypatch):
    r = _lane(tmp_path, base_url="http://127.0.0.1:18480/v1")
    lr = lane_run.LaneRunner(LaneConfig(root=r, secrets=tmp_path / "s"), PROFILE)
    assert lr.ready() == "LANE_NOT_BOOTSTRAPPED:venv"
    (r / "venv/bin").mkdir(parents=True)
    (r / "venv/bin/python").write_text("")
    assert lr.ready() == "LANE_MODEL_SERVICE_NOT_RELAYED"
    (r / "model-service.yaml").write_text(yaml.safe_dump({"mode": "external", "base_url": f"unix:{r / 'run/tier.sock'}"}))
    monkeypatch.setattr(lane_run, "FABRO_BIN", tmp_path / "fabro")
    assert lr.ready() == "FABRO_BINARY_MISSING"
    (tmp_path / "fabro").write_text("")
    assert lr.ready() == "MODEL_SERVICE_SECRETS_MISSING"
    (tmp_path / "s").write_text("forge-qual=x\n")
    assert lr.ready() is None


def test_the_window_plan_refuses_an_unprepared_lane_without_running_anything(tmp_path):
    q = tmp_path / "set.yaml"
    q.write_text(yaml.safe_dump({"phases": [{"phase": "SWE.1", "baseline": {
        "order": "WO-F014-SWE1-CRCHAL-20261103-L27",
        "launch": {"example": "examples/0014m-crc-hal", "profile": PROFILE}}}]}))
    r = _lane(tmp_path)
    out = window_plans.qualification({"deadline": 10 ** 10, "clock": lambda: 0}, qset_path=q, lane_root=r)
    assert out == {"ran": [], "refused": f"LANE_NOT_BOOTSTRAPPED:venv:{PROFILE}"}


def test_select_reads_model_identity_from_the_model_service_in_the_lane(tmp_path, monkeypatch):
    r = _lane(tmp_path)
    calls = []

    def fake(prof, ms, m, env):
        calls.append(m)
        return {"model": m, "status": "MATCH", "identity_basis": "model_service_identity"}

    monkeypatch.setattr(lane_run, "served_identity", fake)
    monkeypatch.setattr(lp, "model_identity", lambda *a: pytest.fail("no Ollama identity in the lane"))
    for name in ("selection_issues", "isolation_issues", "endpoint_issues", "served_model_issues"):
        monkeypatch.setattr(lp, name, lambda *a, **k: [])
    monkeypatch.setattr(lp, "network_enforcement", lambda: {"status": "DENIED_VERIFIED"})
    prof = lp.load(PROFILE)
    model = next(iter(prof["models"]["allowed"]))
    rec = lp.select(PROFILE, model=model, provider="x", code_model=None, acp_authors=None, acp_inspectors=None,
                    env={**{k: str(r / k.lower()) for k in prof["deployment"]["writable_env"]}, prof["deployment"]["root_env"]: str(r)})
    assert calls and all(m["identity_basis"] == "model_service_identity" for m in rec["models"])
    assert rec["enforcement"]["network"]["status"] == "DENIED_VERIFIED"


def test_select_outside_the_lane_keeps_the_ollama_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(lane_run, "served_identity", lambda *a: pytest.fail("not a lane"))
    seen = []
    monkeypatch.setattr(lp, "model_identity", lambda prof, m, url: seen.append(m) or {"model": m, "status": "MATCH"})
    for name in ("selection_issues", "isolation_issues", "endpoint_issues", "served_model_issues"):
        monkeypatch.setattr(lp, name, lambda *a, **k: [])
    monkeypatch.setattr(lp, "network_enforcement", lambda: {"status": "DENIED_VERIFIED"})
    prof = lp.load(PROFILE)
    lp.select(PROFILE, model=next(iter(prof["models"]["allowed"])), provider="x", code_model=None, acp_authors=None,
              acp_inspectors=None, env={**{k: str(tmp_path / k.lower()) for k in prof["deployment"]["writable_env"]}, prof["deployment"]["root_env"]: str(tmp_path)})
    assert seen


def test_served_identity_maps_a_mismatch_and_a_match(tmp_path, monkeypatch):
    from forge_factory.modelservice import client as C

    prof = lp.load(PROFILE)
    m = next(iter(prof["models"]["allowed"]))
    ms = {"mode": "external", "base_url": f"unix:{tmp_path / 's.sock'}", "credential_ref": "forge-qual",
          "expected_identity": {m: {}}, "share": {"concurrency": 1, "queue_wait_max_s": 900}}
    env = {lane_run.SECRETS_ENV: str(tmp_path / "secrets")}
    monkeypatch.setattr(C.ModelServiceClient, "preflight", lambda self, ms_: {m: {"revision_fingerprint": "f", "context_limit": 65536}})
    ok = lane_run.served_identity(prof, ms, m, env)
    assert ok["status"] == "MATCH" and ok["identity_basis"] == "model_service_identity" and ok["revision_fingerprint"] == "f"

    def changed(self, ms_):
        raise C.ProfileError(f"IDENTITY_CHANGED:{m}:revision_fingerprint")
    monkeypatch.setattr(C.ModelServiceClient, "preflight", changed)
    assert lane_run.served_identity(prof, ms, m, env)["status"] == "MISMATCH"
    assert lane_run.served_identity(prof, ms, m, {})["status"] == "UNREACHABLE"


def test_relay_needs_socat_and_cleans_its_socket(tmp_path, clean_env):
    import shutil

    if not shutil.which("socat"):
        pytest.skip("socat")
    lr = lane_run.LaneRunner(LaneConfig(root=_lane(tmp_path)), PROFILE)
    with lr.relay() as sock:
        assert sock.exists()
    assert not sock.exists()
    assert subprocess.run(["true"]).returncode == 0


def test_inputs_named_by_the_work_order_are_found_in_sibling_examples(tmp_path):
    repo = tmp_path / "repo"
    ex = repo / "examples/0014m-crc-hal"
    ex.mkdir(parents=True)
    (ex / "workorder.json").write_text(
        '{"inputs": ["../0014-crc-st/inputs/RM.md", "inputs/local.md", "../../../outside.md"], "x": "plain"}')
    got = lane_run._referenced_files(ex)
    assert [str(p) for p in got] == ["examples/0014-crc-st/inputs/RM.md", "examples/0014m-crc-hal/inputs/local.md"]


def test_each_order_rewrites_the_fabro_settings_for_its_profile(tmp_path, clean_env, monkeypatch):
    r = _lane(tmp_path)
    (r / "fabro").mkdir()
    lr = lane_run.LaneRunner(LaneConfig(root=r), PROFILE)
    monkeypatch.setattr(lane_run.subprocess, "run", lambda argv, **kw: 0)
    lr.run(["python", "-m", "forge_factory.workorder"])
    from forge_factory.lrtx import stack
    assert (r / "fabro/settings.toml").read_text() == stack.fabro_config(lr.settings())
