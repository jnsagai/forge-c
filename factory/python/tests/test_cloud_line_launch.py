"""Real Git/queue/owner-signature controls; native submission is an explicit transport fixture."""
import json
import subprocess
import sys
from types import SimpleNamespace as S

import pytest
import test_line_conductor_m3 as M3
import yaml
from forge_factory.afo import authz
from forge_factory.afo import line_cloud as C
from forge_factory.afo import line_orders as LO
from forge_factory.common import REPO_ROOT
from test_cloud_line_scheduler import cloud
from test_line_conductor_m3 import _git


@pytest.fixture
def env(tmp_path, monkeypatch):
    return M3.env.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def admitted(env, monkeypatch):
    source = env["tmp"] / "source"
    source.mkdir()
    _git(source, "init", "-q")
    profile = REPO_ROOT / f"config/factory/profiles/{C.PROFILE}.yaml"
    target = source / f"config/factory/profiles/{C.PROFILE}.yaml"
    target.parent.mkdir(parents=True)
    target.write_bytes(profile.read_bytes())
    for ex in ("ex-crc-hal", "ex-wwdg-hal"):
        p = source / "examples" / ex / "workorder.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"inputs": []}))
    p = source / "factory/python/fixture.py"
    p.parent.mkdir(parents=True)
    p.write_text("# Transport fixture only; no inference.\n")
    _git(source, "add", ".")
    _git(source, "commit", "-qm", "fixture source")
    rev = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    env["line"].revs[rev] = rev
    p = cloud(env, revision=rev)
    env["line"].spawn_launch = lambda *a: {"pid": 0, "start": None}
    out = p.cycle()
    assert out["actions"][-1]["outcome"] == "LAUNCHING"
    monkeypatch.setenv("FORGE_LINE_POLICY", str(env["tmp"] / "line-policy.yaml"))
    monkeypatch.setattr(authz, "AUTH_DIR", env["tmp"] / "auth")
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", env["signers"])
    wo = "WO-F014-CMP-SWE1-CRCHAL-20261104-T1"
    spec = LO.supervisor_dir() / "line-orders" / f"{wo}.json"
    cfg = S(repo=source, runs_root=env["line"].runs, launch_dir=env["line"].launch_d,
            python=sys.executable, stack_root=env["tmp"], inputs_cache=None, references=(source,), fabro_bin="fixture")
    ws = env["line"].workspace(wo)
    native = {"id": "01CLOUDFIXTURE", "source_directory": str(ws)}
    line = S(cfg=cfg, workspace=env["line"].workspace, live_runs=lambda: [], host=S(fabro_run=lambda rid: native))
    return env, line, spec, wo, ws


def test_child_checks_real_signature_queue_campaign_and_dispatches_once(admitted):
    _, line, spec, wo, ws = admitted
    calls = []

    def submit(argv, **kwargs):
        calls.append(argv)
        assert argv[2:7] == ["forge_factory.lrtx.stack", "exec", "--", str(line.cfg.python), "-m"]
        assert "serve" not in argv and "stop" not in argv and "start" not in argv
        assert kwargs["env"]["FORGE_LRTX_PROFILE"] == C.PROFILE
        assert kwargs["cwd"].name == "python"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": wo}))
        (ws / ".forge-run/fabro_run_id").write_text("01CLOUDFIXTURE")
        return S(returncode=0)

    result = C.launch(spec, line=line, run=submit)
    assert result["outcome"] == "LAUNCHED"
    with pytest.raises(ValueError, match="ALREADY_PREPARED"):
        C.launch(spec, line=line, run=submit)
    assert len(calls) == 1


def test_uncertain_submit_is_persisted_before_call_and_never_resent(admitted):
    _, line, spec, wo, _ = admitted
    calls = []

    def timeout(argv, **kwargs):
        marker = line.cfg.runs_root / ".launch" / wo / "attempt-1.json"
        assert json.loads(marker.read_text())["outcome"] == "CLOUD_DISPATCH_UNCERTAIN"
        calls.append(True)
        raise subprocess.TimeoutExpired("fixture command", 600)

    assert C.launch(spec, line=line, run=timeout)["outcome"] == "CLOUD_DISPATCH_UNCERTAIN"
    with pytest.raises(ValueError, match="ALREADY_ATTEMPTED"):
        C.launch(spec, line=line, run=timeout)
    assert len(calls) == 1


@pytest.mark.parametrize("cause", ["signature", "queue", "campaign", "spec", "capacity", "unobservable"])
def test_child_refuses_changed_authority_or_busy_capacity_before_transport(admitted, cause):
    env, line, spec, _, _ = admitted
    if cause == "signature":
        (env["tmp"] / "auth/AUTH-T.sig").unlink()
    elif cause == "queue":
        LO._load(spec)  # Keep the spec but remove its admitted authority.
        (LO.supervisor_dir() / "line-queue.sqlite3").rename(env["tmp"] / "preserved-queue.sqlite3")
    elif cause == "campaign":
        with (env["camp"] / "c.yaml").open("a") as f:
            f.write("\n# changed after approval\n")
    elif cause == "spec":
        d = json.loads(spec.read_text())
        d["resume_from"] = "WO-FOREIGN-FIXTURE"
        spec.write_text(json.dumps(d))
    elif cause == "capacity":
        line.live_runs = lambda: ["first", "second"]
    else:
        line.live_runs = lambda: None
    with pytest.raises(ValueError):
        C.launch(spec, line=line, run=lambda *a, **kw: pytest.fail("refused launch reached transport"))


def test_cloud_profile_must_keep_account_transport_and_actual_role_models():
    profile = yaml.safe_load((REPO_ROOT / f"config/factory/profiles/{C.PROFILE}.yaml").read_text())
    C.validate_profile(profile)
    profile["runtime"]["cloud_bridge"]["models"]["gpt-6.1-sol"]["backend"] = "openai-api"
    with pytest.raises(ValueError, match="ACCOUNT_ROLE_BINDING"):
        C.validate_profile(profile)
