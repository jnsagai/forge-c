"""The qualification lane (feature 017, T024; research R7).

A separate factory lane that runs in external model service mode: its own data root, Fabro instance, ports and
state, with the external gateway as its only model path. It exists so the production-like setup can be qualified
without touching the owner lane, whose signed transport proof pins the gateway and the stack sources. The lane
never starts a model server and never takes the GPU lock: its processes are Fabro and the external gateway only.

Collisions with the owner lane, the production lane, the observer or the floors are refused before anything starts.
"""
from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..lrtx import stack

DATA = Path("/mnt/data/forge-c")
HOME = Path("/home/omniverse2")
# Ports and roots of everything else on Omniverse2 that this lane must never share (window-controls.md, memory).
TAKEN_PORTS = {11455, 11456, 11457, 11460, 32392, 32397, 32398, 8765, 8787, 8788, 18480, 18501, 18502}
TAKEN_ROOTS = (DATA / "swe1-fabro-20261031", DATA / "owner-autodeploy", DATA / "line",
               HOME / ".local/state/forge-c-production-014", HOME / ".config/forge-c/line-local")
FORBIDDEN_IN_ARGV = ("llama-server", "ollama", "gpu.lock", "nvidia-smi")


class LaneError(RuntimeError):
    pass


@dataclass
class LaneConfig:
    root: Path = DATA / "model-service/qual-lane"
    fabro_port: int = 32420
    gateway_port: int = 32421
    model_service: Path = DATA / "model-service/qual-lane/model-service.yaml"
    secrets: Path = DATA / "model-service/secrets/model-service.secrets"
    python: str = sys.executable
    unit_prefix: str = "forge-017-qual"
    extra_taken_ports: set = field(default_factory=set)


def check(cfg: LaneConfig) -> None:
    taken = TAKEN_PORTS | set(cfg.extra_taken_ports)
    for name, port in (("fabro", cfg.fabro_port), ("gateway", cfg.gateway_port)):
        if port in taken:
            raise LaneError(f"PORT_COLLISION:{name}:{port}")
    if cfg.fabro_port == cfg.gateway_port:
        raise LaneError("PORT_COLLISION:fabro=gateway")
    root = Path(cfg.root).resolve()
    for t in TAKEN_ROOTS:
        t = Path(t).resolve()
        if root == t or t in root.parents or root in t.parents:
            raise LaneError(f"ROOT_COLLISION:{t}")


def settings(cfg: LaneConfig, profile: dict) -> dict:
    """The stack settings of this lane: the given factory profile, with this lane's own root and ports."""
    return {"profile": profile, "root": Path(cfg.root), "ports": {**profile["deployment"]["ports"],
                                                                  "fabro": cfg.fabro_port, "gateway": cfg.gateway_port}}


def fabro_settings(cfg: LaneConfig, profile: dict) -> str:
    """Fabro's configuration for the lane: its provider is the external gateway (stack.fabro_config, unchanged)."""
    return stack.fabro_config(settings(cfg, profile))


def processes(cfg: LaneConfig, profile: dict) -> dict[str, list[str]]:
    """Every process the lane runs. There is no model server among them (FR-001)."""
    check(cfg)
    s = settings(cfg, profile)
    env = stack.envmap(s)
    r = Path(cfg.root)
    procs = {
        "gateway": [cfg.python, "-m", "forge_factory.modelservice.gateway_external", "--port", str(cfg.gateway_port),
                    "--model-service", str(cfg.model_service), "--secrets", str(cfg.secrets),
                    "--meter", str(r / "state/llm-gateway/usage.jsonl"), "--calls", str(r / "state/model-service/calls.jsonl"),
                    "--capture-root", str(r / "state/model-exchanges")],
        "fabro": [env["FORGE_FABRO_BIN"], "server", "start", "--foreground", "--no-web", "--no-upgrade-check",
                  "--config", str(r / "fabro/settings.toml"), "--storage-dir", str(r / "fabro/storage")],
    }
    for name, argv in procs.items():
        if any(bad in a for a in argv for bad in FORBIDDEN_IN_ARGV):
            raise LaneError(f"MODEL_SERVER_IN_LANE:{name}")
    return procs


def unit_commands(cfg: LaneConfig, profile: dict) -> list[str]:
    """systemd-run commands that start the lane's processes as transient user units (not run here)."""
    env = stack.envmap(settings(cfg, profile))
    keep = {k: env[k] for k in ("FORGE_LRTX_ROOT", "FORGE_LRTX_PROFILE", "FORGE_STATE_DIR", "FORGE_DATA_ROOT", "PYTHONPATH",
                                 "FORGE_REPO_ROOT", "HOME", "PATH")}
    out = []
    for name, argv in processes(cfg, profile).items():
        setenv = " ".join(f"--setenv={k}={shlex.quote(v)}" for k, v in keep.items())
        out.append(f"systemd-run --user --unit {cfg.unit_prefix}-{name} --collect -p Restart=no {setenv} "
                   + " ".join(shlex.quote(a) for a in argv))
    return out


def describe(cfg: LaneConfig, profile: dict) -> dict:
    return {"root": str(cfg.root), "ports": {"fabro": cfg.fabro_port, "gateway": cfg.gateway_port},
            "processes": {k: v[:4] for k, v in processes(cfg, profile).items()}, "model_service_mode": "external"}


if __name__ == "__main__":
    from ..lrtx import profile as lp

    prof = lp.load(sys.argv[1])
    print(json.dumps(describe(LaneConfig(), prof), indent=1))
