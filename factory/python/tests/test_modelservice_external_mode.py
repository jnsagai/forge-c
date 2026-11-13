"""Feature 017 T015/T024: the qualification lane runs in external mode and never owns a model or the GPU."""
import hashlib
import subprocess
from pathlib import Path

import pytest
from forge_factory.lrtx import profile as lp
from forge_factory.modelservice import lane as L

ROOT = Path(__file__).resolve().parents[3]
PINNED = ("llm_gateway.py", "afo/product_job.py", "afo/execution_lifecycle.py", "fabro/client.py", "lrtx/stack.py")
PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"


@pytest.fixture
def prof():
    try:
        return lp.load(PROFILE)
    except Exception as exc:  # pragma: no cover - environment without the profile
        pytest.skip(f"NOT_RUN: profile {PROFILE} unavailable: {exc}")


def test_lane_processes_hold_no_model_server_and_no_gpu_lock(prof, tmp_path):
    cfg = L.LaneConfig(root=tmp_path / "qual-lane")
    procs = L.processes(cfg, prof)
    assert set(procs) == {"gateway", "fabro"}  # FR-001: no ollama, no llama-server
    flat = " ".join(" ".join(a) for a in procs.values())
    assert "llama-server" not in flat and "ollama serve" not in flat and "gpu.lock" not in flat
    assert "forge_factory.modelservice.gateway_external" in flat
    cmds = L.unit_commands(cfg, prof)
    assert all(c.startswith("systemd-run --user --unit forge-017-qual-") and "Restart=no" in c for c in cmds)


def test_fabro_talks_only_to_the_external_gateway(prof, tmp_path):
    cfg = L.LaneConfig(root=tmp_path / "qual-lane", fabro_port=32430, gateway_port=32431)
    toml = L.fabro_settings(cfg, prof)
    assert 'base_url = "http://127.0.0.1:32431/v1"' in toml and 'address = "127.0.0.1:32430"' in toml
    assert str(tmp_path / "qual-lane") in toml


@pytest.mark.parametrize("kw,reason", [
    ({"fabro_port": 11460}, "PORT_COLLISION:fabro:11460"),      # production gateway
    ({"gateway_port": 11456}, "PORT_COLLISION:gateway:11456"),  # owner lane gateway
    ({"gateway_port": 18480}, "PORT_COLLISION:gateway:18480"),  # the tenant gateway itself
    ({"fabro_port": 8788}, "PORT_COLLISION:fabro:8788"),        # the floor
    ({"root": Path("/mnt/data/forge-c/swe1-fabro-20261031/lrtx")}, "ROOT_COLLISION"),
    ({"root": Path("/mnt/data/forge-c")}, "ROOT_COLLISION"),
    ({"root": Path("/home/omniverse2/.local/state/forge-c-production-014/x")}, "ROOT_COLLISION"),
])
def test_collisions_with_other_lanes_are_refused(kw, reason):
    with pytest.raises(L.LaneError, match=reason):
        L.check(L.LaneConfig(**kw))


def test_owner_lane_pinned_sources_are_untouched():
    """Research R7: the owner lane's signed transport proof pins these sources; this feature must not change them.
    Before the merge the base is 017's fork point; once 017 is merged into the campaign (feature 022) it is the
    campaign side of that merge - the campaign may change a pinned source through its own CRE-gated fixes (CAPA-216)."""
    tip017 = "3ffdf141"
    merges = subprocess.run(["git", "-C", str(ROOT), "log", "--merges", "--ancestry-path", "--reverse", "--format=%H",
                             f"{tip017}..HEAD"], capture_output=True, text=True, check=False).stdout.split()
    ref = f"{merges[0]}^1" if merges else "482b824b"
    for rel in PINNED:
        base = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:factory/python/forge_factory/{rel}"],
                              capture_output=True, check=False)
        if base.returncode != 0:
            pytest.skip("NOT_RUN: no git history in this checkout")
        now = (ROOT / "factory/python/forge_factory" / rel).read_bytes()
        assert hashlib.sha256(base.stdout).digest() == hashlib.sha256(now).digest(), rel


def test_default_mode_stays_owned():
    import yaml
    assert yaml.safe_load((ROOT / "config/factory/model-service.yaml").read_text())["mode"] == "owned"  # FR-007
