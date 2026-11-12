# ruff: noqa: E501
"""Running qualification orders in the qualification lane (feature 017, T048/T049).

The lane reproduces the owner lane's isolation instead of relaxing it: every order runs in its own user+network
namespace (`unshare -rn`, no external interface, so `lrtx.profile.select` measures DENIED_VERIFIED exactly as on the
baseline) on the profile's own loopback ports, with its own Fabro and the external-mode gateway inside. The only way
out is a unix socket on the shared filesystem, relayed by `socat` on the host to the model tier (the channel; the
`gateway_external` upstream `unix:` form). No model server, GPU lock or owner-lane process is touched: the owner
lane's ports live in its own namespace, and its root is refused (`lane.TAKEN_ROOTS`).

Pinned owner-lane sources (`lrtx/stack.py`, `llm_gateway.py`, ...) are only called, never changed: `stack.init`
builds the lane root, `stack.envmap`/`fabro_config` give the same environment and Fabro settings as the owner lane.
`<root>/model-service.yaml` with `mode: external` marks the lane: the workflow then adds no in-run serve nodes
(`workflow.builder.serve_swaps`) and `profile.select` reads each model's identity from the model service.
"""
from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import yaml

from .lane import TAKEN_ROOTS, LaneConfig, LaneError, check

FABRO_BIN = Path("/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro")
OWNER_UV_CACHE = Path("/mnt/data/forge-c/swe1-fabro-20261031/lrtx/cache/uv")
OWNER_EXAMPLES = Path("/mnt/data/forge-c/swe1-fabro-20261031/repo/examples")
TIER_TCP = ("127.0.0.1", 18480)
SECRETS_ENV = "FORGE_MODEL_SERVICE_SECRETS"
OWNER_CONTEXT = ("FORGE_OPERATIONS_INTENT", "FORGE_LINE_STACK_PAYLOAD", "FORGE_LINE_STACK_ROOT", "FORGE_LINE_GPU_LOCK")


def _taken(root: Path) -> bool:
    for t in TAKEN_ROOTS:
        t = Path(t).resolve()
        if root == t or t in root.parents or root in t.parents:
            return True
    return False


def external_model_service(root: str | os.PathLike | None) -> dict | None:
    """The lane's model service profile when `root` is an external-mode lane; None for every other root (a file in
    the owner or production lane's root is ignored, so it can never change their graphs or checks)."""
    if not root:
        return None
    r = Path(root).resolve()
    f = r / "model-service.yaml"
    if not f.is_file() or _taken(r):
        return None
    try:
        doc = yaml.safe_load(f.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None
    return doc if isinstance(doc, dict) and doc.get("mode") == "external" else None


def served_identity(prof: dict, ms: dict, model: str, env: dict) -> dict:
    """`profile.select`'s identity record of `model` in an external-mode lane: the model service's attested identity
    (/forge/v1/identity) must match the lane profile's expected identity (precision, reasoning mode, context,
    revision fingerprint). The basis is recorded; there is no Ollama digest behind a model service."""
    import httpx

    from .client import ModelServiceClient, ProfileError
    from .secrets import resolve

    want = prof["models"]["allowed"][model]
    base = ms["base_url"]
    uds = base.startswith("unix:")
    doc = {**ms, "base_url": "http://model-service/v1"} if uds else ms
    sec = env.get(SECRETS_ENV)
    if not sec:
        return {"model": model, "status": "UNREACHABLE", "detail": f"{SECRETS_ENV} unset"}
    try:
        with httpx.Client(transport=httpx.HTTPTransport(uds=base[len("unix:"):]) if uds else None) as h:
            client = ModelServiceClient(doc, h, key=lambda: resolve(ms["credential_ref"], Path(sec)).reveal())
            ident = client.preflight([model])[model]
    except ProfileError as exc:
        return {"model": model, "status": "MISMATCH", "detail": str(exc)[:200]}
    except (PermissionError, OSError, httpx.HTTPError, KeyError, ValueError) as exc:
        return {"model": model, "status": "UNREACHABLE", "detail": f"{type(exc).__name__}: {exc}"[:200]}
    return {"model": model, "status": "MATCH", "identity_basis": "model_service_identity",
            "revision_fingerprint": ident.get("revision_fingerprint"), "context_limit": ident.get("context_limit"),
            "expected_digest": want["digest"], "role_qualification": want["role_qualification"]}


def _referenced_files(example: Path) -> list[Path]:
    """Repo-relative paths of the files an example's work order names (its inputs may live in sibling examples)."""
    import re

    try:
        text = (example / "workorder.json").read_text()
    except OSError:
        return []
    repo = example.parents[1]
    out = []
    for ref in sorted(set(re.findall(r'"([^"\s]+\.(?:md|h|c|json|yaml|pdf|txt))"', text))):
        target = (example / ref).resolve()
        if target.is_relative_to(repo.resolve()):
            out.append(target.relative_to(repo.resolve()))
    return out


class LaneRunner:
    """Runs one work order at a time inside the lane's namespace. `run` has `subprocess.run`'s calling shape."""

    def __init__(self, cfg: LaneConfig, profile_id: str):
        from ..lrtx import profile as lp

        check(cfg)
        self.cfg, self.root = cfg, Path(cfg.root)
        self.prof = lp.load(profile_id)
        self.sock = self.root / "run/tier.sock"
        self.logs = self.root / "logs"

    # ---- environment -------------------------------------------------------------------------------------------
    def settings(self) -> dict:
        """The profile's own ports: they are free inside the lane's namespace (the owner lane's are in another one)."""
        return {"profile": self.prof, "root": self.root, "ports": self.prof["deployment"]["ports"]}

    def env(self) -> dict:
        from ..lrtx import stack

        leaked = [k for k in OWNER_CONTEXT if os.environ.get(k)]
        if leaked:
            raise LaneError("OWNER_LANE_CONTEXT_IN_QUALIFICATION_LANE:" + ",".join(leaked))
        os.environ.setdefault("FORGE_FABRO_BIN", str(FABRO_BIN))  # envmap's shared read-only binary
        e = stack.envmap(self.settings())
        e[SECRETS_ENV] = str(self.cfg.secrets)
        return e

    def gateway_env(self, e: dict) -> dict:
        """The owner lane's gateway settings (stack._start), except the routes: the model service is the upstream."""
        from ..lrtx import stack
        from ..lrtx.request_measurement import policy

        prof, adm = self.prof, self.prof["admission"]
        g = {**e, "FORGE_GATEWAY_MAX_QUEUE": str(adm["max_queue"]), "FORGE_GATEWAY_MAX_WAIT_S": str(adm["max_wait_s"]),
             "FORGE_GATEWAY_SAMPLE_S": str((prof.get("measurement") or {}).get("sample_s", 10)),
             "FORGE_GATEWAY_REASONING": stack.gateway_reasoning(prof),
             "FORGE_GATEWAY_REQUEST_MEASUREMENT": json.dumps(policy(prof)),
             "FORGE_GATEWAY_REQUEST_TIMEOUT_S": str(stack.gateway_timeout(prof))}
        if (prof.get("gateway") or {}).get("measure_unbound_requests") is True:
            g["FORGE_GATEWAY_MEASURE_UNBOUND"] = "1"
            g["FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT"] = str(prof["runtime"]["context_limit_tokens"])
        if "drop_retries" in (prof.get("gateway") or {}):
            g["FORGE_GATEWAY_DROP_RETRIES"] = str(prof["gateway"]["drop_retries"])
        return g

    # ---- one-time preparation (outside a window: needs no GPU) ------------------------------------------------
    def bootstrap(self, examples: list[str] = ()) -> dict:
        """Idempotent: the lane root built by the unchanged `stack.init` (directories, shared read-only links,
        Fabro settings and dev token, hash-pinned venv - its package cache seeded from the owner lane's so nothing is
        downloaded), the model service reached through the relay socket, and the examples' git-ignored inputs copied
        from the owner lane's checkout (byte-identical copies; never edited)."""
        from ..lrtx import stack

        uv = self.root / "cache/uv"
        uv.mkdir(parents=True, exist_ok=True)
        if OWNER_UV_CACHE.is_dir() and not any(uv.iterdir()):
            shutil.copytree(OWNER_UV_CACHE, uv, symlinks=True, dirs_exist_ok=True)
        self.env()  # refuses an owner-lane context before anything is written
        out = stack.init(self.settings())
        ms_path = self.root / "model-service.yaml"
        ms = yaml.safe_load(ms_path.read_text())
        if ms.get("mode") != "external":
            raise LaneError("LANE_MODEL_SERVICE_NOT_EXTERNAL")
        if ms.get("base_url") != f"unix:{self.sock}":
            ms["base_url"] = f"unix:{self.sock}"
            ms_path.write_text("# Qualification lane model service (feature 017): external mode only; reached from the "
                               "lane's namespace through the relay socket.\n" + yaml.safe_dump(ms, sort_keys=False))
        copied = []
        repo = Path(stack.REPO_ROOT)
        for ex in examples:
            for rel in _referenced_files(repo / ex):
                src, dst = OWNER_EXAMPLES.parent / rel, repo / rel
                if src.is_file() and not dst.exists() and subprocess.run(
                        ["git", "-C", str(repo), "check-ignore", "-q", str(rel)]).returncode == 0:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied.append(str(rel))
        return {**out, "model_service": str(ms_path), "inputs_copied": copied}

    def prepare(self) -> None:
        """This runner's profile owns the lane's Fabro settings for the next order (the set mixes profiles)."""
        from ..lrtx import stack

        f = self.root / "fabro/settings.toml"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(stack.fabro_config(self.settings()))

    def ready(self) -> str | None:
        """Why the lane cannot run an order now (None = ready)."""
        if not (self.root / "venv/bin/python").exists():
            return "LANE_NOT_BOOTSTRAPPED:venv"
        ms = external_model_service(self.root)
        if not ms:
            return "LANE_NOT_EXTERNAL"
        if ms.get("base_url") != f"unix:{self.sock}":
            return "LANE_MODEL_SERVICE_NOT_RELAYED"
        if not FABRO_BIN.is_file():
            return "FABRO_BINARY_MISSING"
        if not Path(self.cfg.secrets).is_file():
            return "MODEL_SERVICE_SECRETS_MISSING"
        return None

    # ---- inside a window ---------------------------------------------------------------------------------------
    @contextlib.contextmanager
    def relay(self, timeout_s: float = 10.0):
        """The lane's only path out: socket -> the tier's loopback port, for the lifetime of the block."""
        self.sock.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            self.sock.unlink()
        self.logs.mkdir(parents=True, exist_ok=True)
        log = open(self.logs / "relay.log", "ab")  # noqa: SIM115
        p = subprocess.Popen(["socat", f"UNIX-LISTEN:{self.sock},fork,mode=600,unlink-early",
                              f"TCP:{TIER_TCP[0]}:{TIER_TCP[1]}"], stdout=log, stderr=log)
        try:
            end = time.monotonic() + timeout_s
            while not self.sock.exists():
                if p.poll() is not None or time.monotonic() > end:
                    raise LaneError("RELAY_NOT_STARTED")
                time.sleep(0.1)
            yield self.sock
        finally:
            p.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                p.wait(10)
            if p.poll() is None:
                p.kill()
            log.close()
            with contextlib.suppress(FileNotFoundError):
                self.sock.unlink()

    def script(self, argv: list[str], e: dict) -> str:
        """The namespace's program: loopback up, gateway and Fabro, wait for both, the order, then stop both."""
        p, r = self.prof["deployment"]["ports"], self.root
        gw = [e["FORGE_VENV"] + "/bin/python", "-m", "forge_factory.modelservice.gateway_external", "--port", str(p["gateway"]),
              "--model-service", str(r / "model-service.yaml"), "--secrets", str(self.cfg.secrets),
              "--meter", str(r / "state/llm-gateway/usage.jsonl"), "--calls", str(r / "state/model-service/calls.jsonl"),
              "--capture-root", str(r / "state/model-exchanges")]
        fabro = [e["FORGE_FABRO_BIN"], "server", "start", "--foreground", "--no-web", "--no-upgrade-check",
                 "--config", e["FORGE_FABRO_CONFIG"], "--storage-dir", e["FORGE_FABRO_STORAGE"]]
        genv = " ".join(f"{k}={shlex.quote(v)}" for k, v in sorted(self.gateway_env(e).items()) if k.startswith("FORGE_GATEWAY_"))
        q = " ".join
        return "\n".join([
            "set -u",
            "ip link set lo up || exit 90",
            f"mkdir -p {shlex.quote(str(r / 'state/llm-gateway'))} {shlex.quote(str(r / 'state/model-service'))}",
            f"env {genv} {q(shlex.quote(a) for a in gw)} >> {shlex.quote(str(self.logs / 'gateway.log'))} 2>&1 & GW=$!",
            f"env HOME={shlex.quote(e['FORGE_FABRO_HOME'])} {q(shlex.quote(a) for a in fabro)} >> "
            f"{shlex.quote(str(self.logs / 'fabro.log'))} 2>&1 & FB=$!",
            "ok=0; for i in $(seq 1 180); do "
            f"curl -sf -o /dev/null http://127.0.0.1:{p['gateway']}/health && "
            f"curl -sf -o /dev/null http://127.0.0.1:{p['fabro']}/health && ok=1 && break; sleep 1; done",
            "[ $ok = 1 ] || { kill $GW $FB 2>/dev/null; exit 91; }",
            f"{q(shlex.quote(a) for a in argv)}; rc=$?",
            "kill $GW $FB 2>/dev/null; wait $GW $FB 2>/dev/null",
            "exit $rc",
        ])

    def run(self, argv: list[str], *, cwd=None, env=None, capture_output=False, text=False, timeout=None):
        """`subprocess.run` for one order, inside a fresh namespace of the lane. `python` is the lane's venv."""
        e = self.env()
        self.prepare()
        argv = [e["FORGE_VENV"] + "/bin/python" if a == "python" and i == 0 else a for i, a in enumerate(argv)]
        return subprocess.run(["unshare", "-rn", "--kill-child", "bash", "-c", self.script(argv, e)],
                              cwd=cwd, env=e, capture_output=capture_output, text=text, timeout=timeout)
