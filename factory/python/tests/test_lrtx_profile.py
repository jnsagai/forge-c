"""Feature 010 P1: explicit local-profile selection, isolation, endpoints, network enforcement (LRTX-T005..T008)."""
from __future__ import annotations

import errno
import json
import time

import pytest
from forge_factory import workorder
from forge_factory.lrtx import profile as lp
from forge_factory.lrtx import stack

PROF = lp.load("local-rtx-v1")


def _env(root, **over):
    s = {"profile": PROF, "root": root, "ports": PROF["deployment"]["ports"]}
    return {**stack.envmap(s), **over}


def _prof(tmp_path, existing):
    return {**PROF, "existing_deployment": {"roots": [str(existing)]},
            "deployment": {**PROF["deployment"], "shared_readonly": {"toolchains": str(existing / "toolchains")}}}


def test_absent_profile_changes_nothing_and_cli_flag_is_optional():
    import inspect

    assert inspect.signature(workorder.run).parameters["profile"].default is None


def test_acp_cloud_and_unknown_models_are_refused_before_launch():
    issues = lp.selection_issues(PROF, model="deepseek-flash", provider="deepseek", code_model="qwen3:8b",
                                 acp_authors="codex", acp_inspectors="claude")
    assert issues == ["PROFILE_REJECTS_ACP:codex,claude", "PROFILE_PROVIDER_NOT_LOCAL:deepseek",
                      "PROFILE_MODEL_NOT_ALLOWED:deepseek-flash"]
    assert lp.selection_issues(PROF, model="qwen3-coder:30b", provider="ollama", code_model=None, acp_authors=None,
                               acp_inspectors=None) == []
    with pytest.raises(lp.ProfileRefused, match="PROFILE_UNKNOWN"):
        lp.load("no-such-profile")


def test_cli_reports_refusal_without_preparing(monkeypatch, capsys, tmp_path):
    called = []
    monkeypatch.setattr(workorder, "prepare", lambda *a, **k: called.append(a))
    rc = workorder.main(["--example", str(tmp_path), "--wo", "WO-X", "--profile", "local-rtx-v1",
                         "--acp-authors", "codex"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and out["status"] == "REFUSED" and out["issues"] == ["PROFILE_REJECTS_ACP:codex"] and not called


def test_isolated_root_passes(tmp_path):
    existing, root = tmp_path / "forge-c", tmp_path / "forge-c-lrtx"
    (existing / "toolchains").mkdir(parents=True)
    root.mkdir()
    (root / "toolchains").symlink_to(existing / "toolchains")
    assert lp.isolation_issues(_prof(tmp_path, existing), _env(root)) == []


def test_overlapping_inherited_and_symlinked_roots_are_refused(tmp_path):
    existing, root = tmp_path / "forge-c", tmp_path / "forge-c-lrtx"
    (existing / "state").mkdir(parents=True)
    (existing / "toolchains").mkdir()
    root.mkdir()
    prof = _prof(tmp_path, existing)
    # inherited production state dir (forge-env.sh sourced before the profile environment)
    env = _env(root, FORGE_STATE_DIR=str(existing / "state"))
    assert any(i.startswith("PROFILE_PATH_OUTSIDE_ROOT:FORGE_STATE_DIR") for i in lp.isolation_issues(prof, env))
    assert any(i.startswith("PROFILE_PATH_IN_DEPLOYMENT:FORGE_STATE_DIR") for i in lp.isolation_issues(prof, env))
    # a symlink alias inside the profile root that resolves into the deployment
    (root / "state").symlink_to(existing / "state")
    issues = lp.isolation_issues(prof, _env(root))
    assert "PROFILE_UNDECLARED_SYMLINK:state->" + str(existing / "state") in issues
    assert any(i.startswith("PROFILE_PATH_IN_DEPLOYMENT:FORGE_STATE_DIR") for i in issues)
    # the profile root nested in the deployment, or the deployment nested in it
    assert any(i.startswith("PROFILE_ROOT_OVERLAPS_DEPLOYMENT") for i in lp.isolation_issues(prof, _env(existing / "x")))
    assert any(i.startswith("PROFILE_ROOT_OVERLAPS_DEPLOYMENT") for i in lp.isolation_issues(prof, _env(tmp_path)))
    assert lp.isolation_issues(prof, {}) == ["PROFILE_ROOT_UNSET:FORGE_LRTX_ROOT"]


def _fabro_cfg(tmp_path, root, extra=""):
    s = {"profile": PROF, "root": root, "ports": PROF["deployment"]["ports"]}
    p = tmp_path / "settings.toml"
    p.write_text(stack.fabro_config(s) + extra)
    return p


def test_local_endpoints_pass_and_cloud_fallback_or_shared_ports_are_refused(tmp_path):
    root = tmp_path / "r"
    env = _env(root)
    assert lp.endpoint_issues(PROF, env, _fabro_cfg(tmp_path, root)) == []
    cloud = '\n[llm.providers.deepseek]\nenabled = true\nbase_url = "http://127.0.0.1:11437"\n'
    assert "FABRO_PROVIDERS_NOT_LOCAL_ONLY:deepseek,ollama" in lp.endpoint_issues(PROF, env, _fabro_cfg(tmp_path, root, cloud))
    bad = {**env, "FORGE_FABRO_URL": "http://127.0.0.1:32290/api/v1", "FORGE_OLLAMA_URL": "http://10.0.0.5:11445"}
    issues = lp.endpoint_issues(PROF, bad, _fabro_cfg(tmp_path, root))
    assert "ENDPOINT_PORT:fabro:32290 (profile 32390)" in issues and "ENDPOINT_NOT_LOOPBACK:ollama:10.0.0.5" in issues


def test_network_status_is_observed_not_declared(monkeypatch):
    class Sock:
        def __init__(self, err):
            self.err = err

        def settimeout(self, _t):
            pass

        def connect(self, _a):
            if self.err:
                raise OSError(self.err, "x")

        def close(self):
            pass
    for err, want in ((errno.ENETUNREACH, "DENIED_VERIFIED"), (None, "NOT_ENFORCED"), (errno.ETIMEDOUT, "INCONCLUSIVE")):
        monkeypatch.setattr(lp.socket, "socket", lambda *a, err=err: Sock(err))
        assert lp.network_enforcement()["status"] == want


def test_select_refuses_unenforced_network_and_mismatched_model(monkeypatch, tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    env = {**_env(root), "FORGE_FABRO_CONFIG": str(_fabro_cfg(tmp_path, root))}
    monkeypatch.setattr(lp, "isolation_issues", lambda *a: [])
    monkeypatch.setattr(lp, "network_enforcement", lambda: {"status": "NOT_ENFORCED"})
    monkeypatch.setattr(lp, "model_identity", lambda prof, m, url: {"model": m, "status": "MISMATCH"})
    with pytest.raises(lp.ProfileRefused) as e:
        lp.select("local-rtx-v1", model="qwen3-coder:30b", provider="ollama", code_model=None, acp_authors=None,
                  acp_inspectors=None, env=env)
    assert e.value.issues == ["NETWORK_NOT_DENIED:NOT_ENFORCED", "MODEL_IDENTITY_MISMATCH:qwen3-coder:30b"]
    monkeypatch.setattr(lp, "network_enforcement", lambda: {"status": "DENIED_VERIFIED"})
    monkeypatch.setattr(lp, "model_identity", lambda prof, m, url: {"model": m, "status": "MATCH"})
    rec = lp.select("local-rtx-v1", model="qwen3-coder:30b", provider="ollama", code_model=None, acp_authors=None,
                    acp_inspectors=None, env=env)
    assert rec["enforcement"]["network"]["status"] == "DENIED_VERIFIED" and rec["local_only"] is True
    assert rec["config_sha256"] == PROF["_sha256"] and rec["timeout_scale"] == 4


def test_stack_environment_inherits_nothing_from_the_existing_deployment(tmp_path):
    env = _env(tmp_path / "r")
    assert env["PYTHONPATH"].endswith("factory/python") and env["HOME"] == str(tmp_path / "r/home")
    assert all(str(tmp_path / "r") in env[k] for k in PROF["deployment"]["writable_env"])
    assert env["FORGE_FABRO_URL"].endswith(":32390/api/v1") and env["FORGE_OLLAMA_URL"].endswith(":11445")


def test_api_bridge_is_inbound_only_on_host_loopback(tmp_path):
    """Owner request 2026-10-21: show profile runs in the Fabro monitor without giving the namespace a route out."""
    s = {**stack.settings(), "root": tmp_path}
    inner, outer, sock = stack.bridge_argv(s)
    port = s["ports"]["fabro"]
    assert inner[0] == outer[0] == "socat" and sock == tmp_path / "run/fabro-api.sock"
    assert inner[1].startswith(f"UNIX-LISTEN:{sock},") and "mode=600" in inner[1]
    assert inner[2] == f"TCP:127.0.0.1:{port}"
    assert outer[1] == f"TCP-LISTEN:{port},bind=127.0.0.1,reuseaddr,fork" and outer[2] == f"UNIX-CONNECT:{sock}"
    inner2, outer2, _ = stack.bridge_argv(s, 32394)
    # A second stack of the same profile keeps its namespace port; only the host loopback listener moves.
    assert inner2 == inner and outer2[1] == "TCP-LISTEN:32394,bind=127.0.0.1,reuseaddr,fork"


def test_managed_stop_signals_an_exposed_bridge_only_with_its_recorded_identity(tmp_path):
    """Omniverse2 2026-10-25: expose-api recorded no identity, so a managed stop refused the bridge."""
    import subprocess

    from forge_factory.afo.durable import Refused

    s = {**stack.settings(), "root": tmp_path}
    (tmp_path / "run").mkdir()
    bridge = subprocess.Popen(["bash", "-c", "exec -a socat sleep 30"])
    try:
        time.sleep(0.2)
        entry = {"pid": bridge.pid, "argv": ["socat", "x"]}
        (tmp_path / "run/services.json").write_text(json.dumps({"processes": {}, "api_bridge": {"outer": entry}}))
        with pytest.raises(Refused, match="LOCAL_PROCESS_OWNERSHIP_UNPROVEN"):
            stack._stop(s, managed=True)
        assert bridge.poll() is None
        entry["identity"] = stack.process_identity(bridge.pid)
        (tmp_path / "run/services.json").write_text(json.dumps({"processes": {}, "api_bridge": {"outer": entry}}))
        assert stack._stop(s, managed=True)["stopped"] == ["api-bridge-outer"]
        assert bridge.wait(timeout=5) == -15
    finally:
        if bridge.poll() is None:
            bridge.kill()
