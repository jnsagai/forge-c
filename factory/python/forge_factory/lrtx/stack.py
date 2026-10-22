"""LRTX-T006/T008: the isolated local RTX stack - own root, venv, Ollama, admission gateway and Fabro server on the
profile's loopback ports, all inside one user+network namespace with no external interface (no sudo needed).

    python -m forge_factory.lrtx.stack init|start|status|stop
    python -m forge_factory.lrtx.stack expose-api     # opt-in: the profile Fabro API on the host's 127.0.0.1 (monitor)
    python -m forge_factory.lrtx.stack env            # shell exports of the isolated environment
    python -m forge_factory.lrtx.stack exec -- CMD     # run CMD inside the namespace with that environment

The existing deployment (its checkout, state, archives, Fabro servers, gateways, Ollama :11435, supervisor) is never
started, stopped, configured or written by this module; processes are stopped by recorded PID only, after checking
that the PID still runs the recorded command.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now
from . import profile as lp

SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"


def gateway_reasoning(prof: dict) -> str:
    """The profile's per-model reasoning exception for the gateway (owner decision 2026-10-22); '{}' when none."""
    return json.dumps((prof.get("gateway") or {}).get("reasoning") or {}, sort_keys=True)

def settings(profile_id: str = "local-rtx-v1") -> dict:
    prof = lp.load(profile_id)
    root = Path(os.environ.get(prof["deployment"]["root_env"]) or prof["deployment"]["default_root"])
    return {"profile": prof, "root": root, "ports": prof["deployment"]["ports"]}


def envmap(s: dict) -> dict[str, str]:
    """The complete environment of every process of the local stack and its work orders (nothing inherited from the
    existing deployment's forge-env.sh)."""
    r, p = s["root"], s["ports"]
    fabro_bin = os.environ.get("FORGE_FABRO_BIN") or str(Path.home() / ".fabro/bin/fabro")  # shared binary, read-only
    env = {"FORGE_LRTX_ROOT": str(r), "FORGE_LRTX_PROFILE": s["profile"]["id"], "FORGE_REPO_ROOT": str(REPO_ROOT),
           "PYTHONPATH": str(REPO_ROOT / "factory/python"),  # the checkout this stack runs (work orders, gates)
           "FORGE_DATA_ROOT": str(r), "FORGE_VENV": str(r / "venv"), "FORGE_STATE_DIR": str(r / "state"),
           "FORGE_ARCHIVE_DIR": str(r / "archives"), "UV_CACHE_DIR": str(r / "cache/uv"),
           "PIP_CACHE_DIR": str(r / "cache/pip"), "FORGE_OLLAMA_URL": f"http://127.0.0.1:{p['ollama']}",
           "FORGE_FABRO_BIN": fabro_bin, "FORGE_FABRO_URL": f"http://127.0.0.1:{p['fabro']}/api/v1",
           "FORGE_FABRO_CONFIG": str(r / "fabro/settings.toml"), "FORGE_FABRO_STORAGE": str(r / "fabro/storage"),
           "FORGE_FABRO_HOME": str(r / "fabro/home"), "FORGE_LLVM_BIN": str(r / "toolchains/LLVM-19.1.7-Linux-X64/bin"),
           "FORGE_FORMAL_BIN": str(r / "toolchains/formal/bin"), "HOME": str(r / "home"),
           "XDG_CACHE_HOME": str(r / "cache/xdg"), "XDG_CONFIG_HOME": str(r / "home/.config"),
           "LANG": os.environ.get("LANG", "C.UTF-8"), "TERM": "dumb",
           "PATH": ":".join([str(r / "venv/bin"), str(r / "toolchains/LLVM-19.1.7-Linux-X64/bin"), SYSTEM_PATH,
                             str(r / "toolchains/formal/bin")])}
    iso = r / "standards/iso26262-6-2018/part6.md"
    if iso.is_file():
        env["FORGE_ISO26262_6_2018_PATH"] = str(iso)
    return env


def fabro_config(s: dict) -> str:
    r, p = s["root"], s["ports"]
    models = "\n".join(f'[llm.providers.ollama.models."{m}"]\ndisplay_name = "{m} (local, profile {s["profile"]["id"]})"\n'
                       f'api_model = "{m}"\ncapabilities = {{ text = true, tools = true }}\n'
                       f'limits = {{ context_tokens = 32768, max_output_tokens = 16384 }}\n'
                       for m in s["profile"]["models"]["allowed"])
    return f"""_version = 1
# Forge-C feature 010 local RTX Fabro server (profile {s['profile']['id']}): own storage/home/port, local provider only.
[server.listen]
type = "tcp"
address = "127.0.0.1:{p['fabro']}"
[server.api]
url = "http://127.0.0.1:{p['fabro']}/api/v1"
[server.web]
enabled = false
url = "http://127.0.0.1:{p['fabro']}"
[server.auth]
methods = ["dev-token"]
[server.storage]
root = "{r}/fabro/storage"
[server.artifacts]
provider = "local"
prefix = "artifacts"
[server.artifacts.local]
root = "{r}/fabro/storage/objects"
[server.scheduler]
max_concurrent_runs = 1
[server.sandbox.providers.local]
enabled = true

[llm.providers.ollama]
enabled = true
base_url = "http://127.0.0.1:{p['gateway']}/v1"
auth = {{ type = "none" }}
default_model = "{s['profile']['models']['default']}"
priority = 100

[llm.providers.ollama.metadata.agent]
profile = "openai"
reasoning_by_default = false

{models}
[run.model]
name = "{s['profile']['models']['default']}"
provider = "ollama"
[run.environment]
id = "local"

[cli.target]
type = "http"
url = "http://127.0.0.1:{p['fabro']}/api/v1"
"""


def init(s: dict) -> dict:
    """Create the isolated root (idempotent). Needs network once, outside the namespace, for the hash-pinned venv
    packages; everything the stack uses afterwards is local."""
    r = s["root"]
    issues = [i for i in lp.isolation_issues(s["profile"], envmap(s)) if not i.startswith("PROFILE_ENV_UNSET")]
    issues = [i for i in issues if "PATH_OUTSIDE_ROOT" not in i]
    if issues:
        raise lp.ProfileRefused(issues)
    for d in ("state", "archives", "fabro/storage", "fabro/home/.fabro", "logs", "run", "cache/uv", "cache/pip",
              "cache/xdg", "home/.config", "ollama-home"):
        (r / d).mkdir(parents=True, exist_ok=True)
    for name, target in s["profile"]["deployment"]["shared_readonly"].items():
        link = r / name
        if not link.is_symlink():
            if link.exists():
                raise lp.ProfileRefused([f"PROFILE_ROOT_ENTRY_NOT_A_LINK:{name}"])
            link.symlink_to(target)
    (r / "fabro/settings.toml").write_text(fabro_config(s))
    p = s["ports"]
    (r / "fabro/home/.fabro/settings.toml").write_text(
        f'_version = 1\n[cli.target]\ntype = "http"\nurl = "http://127.0.0.1:{p["fabro"]}/api/v1"\n')
    senv = r / "fabro/storage/server.env"
    if not senv.is_file() or not senv.stat().st_size:
        old = os.umask(0o077)
        try:  # fresh secrets of this isolated server only (0600); never logged
            senv.write_text(f"SESSION_SECRET={secrets.token_hex(32)}\nFABRO_DEV_TOKEN=fabro_dev_{secrets.token_hex(32)}\n")
            tok = next(ln.split("=", 1)[1] for ln in senv.read_text().splitlines() if ln.startswith("FABRO_DEV_TOKEN="))
            (r / "fabro/home/.fabro/auth.json").write_text(json.dumps({"servers": {f"http://127.0.0.1:{p['fabro']}": {
                "kind": "dev-token", "token": tok, "logged_in_at": utc_now()}}}))
        finally:
            os.umask(old)
    venv = r / "venv"
    if not (venv / "bin/python").exists():
        env = {**envmap(s), "PATH": f"{Path.home() / '.local/bin'}:{SYSTEM_PATH}"}
        py = os.path.realpath(sys.executable)
        subprocess.run(["uv", "venv", "--python", py, str(venv)], check=True, env=env)
        subprocess.run(["uv", "pip", "install", "--python", str(venv / "bin/python"), "--require-hashes", "-r",
                        str(REPO_ROOT / "requirements/forge-factory.lock")], check=True, env=env)
    return {"root": str(r), "venv": str(venv), "fabro_config": str(r / "fabro/settings.toml")}


def _alive(pid: int, marker: str) -> bool:
    try:
        return marker in Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False


def _holder(s: dict) -> int | None:
    f = s["root"] / "run/holder.pid"
    if f.is_file():
        pid = int(f.read_text().strip())
        if _alive(pid, "sleep infinity"):
            return pid
    return None


def _nsenter(pid: int) -> list[str]:
    return ["nsenter", "-t", str(pid), "-U", "-n", "--preserve-credentials"]


def _wait(url: str, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):  # noqa: S310 - loopback health URL
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _in_ns(holder: int, argv: list[str], env: dict, log: Path, cwd: Path) -> subprocess.Popen:
    with log.open("ab") as fh:
        return subprocess.Popen(_nsenter(holder) + argv, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, cwd=cwd, start_new_session=True)


def _probe(holder: int, env: dict, url: str) -> bool:
    code = f"import urllib.request; urllib.request.urlopen('{url}', timeout=2)"
    return subprocess.run(_nsenter(holder) + [env["FORGE_VENV"] + "/bin/python", "-c", code], env=env,
                          capture_output=True, timeout=20).returncode == 0


def start(s: dict) -> dict:
    r, p, prof = s["root"], s["ports"], s["profile"]
    env = envmap(s)
    if not (r / "venv/bin/python").exists():
        raise RuntimeError("run `init` first")
    holder = _holder(s)
    if holder is None:
        # user + network namespace: loopback only; the GPU device nodes stay usable
        subprocess.Popen(["setsid", "unshare", "--user", "--map-root-user", "--net", "--fork", "bash", "-c",
                          f"ip link set lo up && echo $$ > {r}/run/holder.pid && exec sleep infinity"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            time.sleep(0.1)
            if (holder := _holder(s)) is not None:
                break
        if holder is None:
            raise RuntimeError("network namespace holder did not start")
    rec = json.loads((r / "run/services.json").read_text()) if (r / "run/services.json").is_file() else {}
    procs = rec.get("processes") or {}
    ollama_env = {**env, **prof["runtime"]["ollama"], "OLLAMA_HOST": f"127.0.0.1:{p['ollama']}",
                  "OLLAMA_MODELS": str(r / "ollama-models"), "HOME": str(r / "ollama-home")}
    adm = prof["admission"]
    gw_env = {**env, "PYTHONPATH": str(REPO_ROOT / "factory/python"), "FORGE_GATEWAY_MAX_INFLIGHT": str(adm["max_inflight"]),
              "FORGE_GATEWAY_MAX_QUEUE": str(adm["max_queue"]), "FORGE_GATEWAY_MAX_WAIT_S": str(adm["max_wait_s"]),
              "FORGE_GATEWAY_SAMPLE_S": str((prof.get("measurement") or {}).get("sample_s", 10)),
              "FORGE_GATEWAY_REASONING": gateway_reasoning(prof)}
    specs = {
        "ollama": ([str(r / "ollama-0.34.0/bin/ollama"), "serve"], ollama_env, f"http://127.0.0.1:{p['ollama']}/api/version"),
        "gateway": ([env["FORGE_VENV"] + "/bin/python", "-m", "forge_factory.llm_gateway", "--port", str(p["gateway"]),
                     "--upstream", f"http://127.0.0.1:{p['ollama']}", "--meter",
                     str(r / "state/llm-gateway/usage.jsonl")], gw_env, f"http://127.0.0.1:{p['gateway']}/health"),
        "fabro": ([env["FORGE_FABRO_BIN"], "server", "start", "--foreground", "--no-web", "--no-upgrade-check",
                   "--config", env["FORGE_FABRO_CONFIG"], "--storage-dir", env["FORGE_FABRO_STORAGE"]],
                  {**env, "HOME": env["FORGE_FABRO_HOME"]}, f"http://127.0.0.1:{p['fabro']}/health")}
    for name, (argv, penv, health) in specs.items():
        old = procs.get(name)
        if old and _alive(old["pid"], argv[1] if name != "ollama" else "ollama"):
            continue
        proc = _in_ns(holder, argv, penv, r / f"logs/{name}.log", r)
        procs[name] = {"pid": proc.pid, "argv": argv, "health": health}
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not _probe(holder, env, health):
            time.sleep(1)
    health = {n: _probe(holder, env, v["health"]) for n, v in procs.items()}
    rec = {"schema": "forge-c/lrtx-services/1", "profile": prof["id"], "profile_sha256": prof["_sha256"],
           "started_at": rec.get("started_at") or utc_now(), "updated_at": utc_now(), "root": str(r),
           "netns": os.readlink(f"/proc/{holder}/ns/net"), "holder_pid": holder, "ports": p,
           "ollama_env": {k: v for k, v in ollama_env.items() if k.startswith("OLLAMA_")},
           "admission": adm, "processes": procs, "health": health,
           "shared_readonly": prof["deployment"]["shared_readonly"]}
    (r / "run/services.json").write_text(pretty_json(rec))
    return rec


def stop(s: dict) -> dict:
    r = s["root"]
    f = r / "run/services.json"
    rec = json.loads(f.read_text()) if f.is_file() else {"processes": {}}
    stopped = []
    for name, pr in (rec.get("processes") or {}).items():
        marker = "ollama" if name == "ollama" else pr["argv"][1]
        if _alive(pr["pid"], marker):
            os.kill(pr["pid"], signal.SIGTERM)
            stopped.append(name)
    for name, pr in (rec.get("api_bridge") or {}).items():
        if isinstance(pr, dict) and _alive(pr["pid"], "socat"):
            os.kill(pr["pid"], signal.SIGTERM)
            stopped.append(f"api-bridge-{name}")
    rec.pop("api_bridge", None)
    holder = _holder(s)
    if holder is not None:  # `sleep infinity` may inherit an ignored SIGTERM from the launching shell
        os.kill(holder, signal.SIGKILL)
        stopped.append("netns-holder")
    if f.is_file():
        rec["stopped_at"] = utc_now()
        rec["processes"] = {}
        f.write_text(pretty_json(rec))
    return {"stopped": stopped}


def bridge_argv(s: dict) -> tuple[list[str], list[str], Path]:
    """Inbound-only relay of the profile's Fabro API to the host's loopback, for a read-only monitor: socat inside the
    namespace accepts on a 0600 unix socket in the profile root and connects to Fabro there; socat on the host listens
    on 127.0.0.1 only. Nothing inside the namespace gains a route out (the network check stays DENIED_VERIFIED)."""
    sock = s["root"] / "run/fabro-api.sock"
    port = s["ports"]["fabro"]
    inner = ["socat", f"UNIX-LISTEN:{sock},fork,mode=600,unlink-early", f"TCP:127.0.0.1:{port}"]
    outer = ["socat", f"TCP-LISTEN:{port},bind=127.0.0.1,reuseaddr,fork", f"UNIX-CONNECT:{sock}"]
    return inner, outer, sock


def _host_port_free(port: int) -> bool:
    import socket

    with socket.socket() as so:
        return so.connect_ex(("127.0.0.1", port)) != 0


def expose_api(s: dict) -> dict:
    holder = _holder(s)
    if holder is None:
        raise RuntimeError("local stack is not running (start it first)")
    if shutil.which("socat") is None:
        raise SystemExit("socat required for expose-api")
    f = s["root"] / "run/services.json"
    rec = json.loads(f.read_text()) if f.is_file() else {}
    br = rec.get("api_bridge") or {}
    if br and all(_alive(br[k]["pid"], "socat") for k in ("inner", "outer")):
        return {"api_bridge": "already running", **{k: br[k]["pid"] for k in ("inner", "outer")}}
    inner, outer, sock = bridge_argv(s)
    port = s["ports"]["fabro"]
    if not _host_port_free(port):
        raise SystemExit(f"HOST_PORT_IN_USE:127.0.0.1:{port} (never shared with another server)")
    log = s["root"] / "logs/api-bridge.log"
    pi = _in_ns(holder, inner, envmap(s), log, s["root"])
    deadline = time.monotonic() + 10
    while not sock.exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    with log.open("ab") as fh:
        po = subprocess.Popen(outer, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              start_new_session=True, env={"PATH": SYSTEM_PATH})
    rec["api_bridge"] = {"inner": {"pid": pi.pid, "argv": inner}, "outer": {"pid": po.pid, "argv": outer},
                         "started_at": utc_now()}
    f.write_text(pretty_json(rec))
    ok = _wait(f"http://127.0.0.1:{port}/health", 15)
    return {"api_bridge": "UP" if ok else "NOT_HEALTHY", "url": f"http://127.0.0.1:{port}/api/v1"}


def status(s: dict) -> dict:
    holder = _holder(s)
    f = s["root"] / "run/services.json"
    rec = json.loads(f.read_text()) if f.is_file() else {}
    if holder is None:
        return {"status": "DOWN", "root": str(s["root"])}
    env = envmap(s)
    return {"status": "UP", "holder_pid": holder, "netns": os.readlink(f"/proc/{holder}/ns/net"),
            "health": {n: _probe(holder, env, v["health"]) for n, v in (rec.get("processes") or {}).items()}}


def exec_in(s: dict, argv: list[str]) -> int:
    holder = _holder(s)
    if holder is None:
        raise RuntimeError("local stack is not running (start it first)")
    env = envmap(s)
    os.chdir(REPO_ROOT)
    os.execvpe("nsenter", _nsenter(holder) + argv, env)  # noqa: S606 - argv is the operator command
    return 0  # unreachable


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["init", "start", "stop", "status", "env", "exec", "expose-api"])
    ap.add_argument("--profile", default=os.environ.get("FORGE_LRTX_PROFILE", "local-rtx-v1"))
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    s = settings(a.profile)
    if a.cmd == "env":
        print("unset PYTHONPATH")
        for k, v in envmap(s).items():
            print(f"export {k}={json.dumps(v)}")
        return 0
    if a.cmd == "exec":
        rest = a.rest[1:] if a.rest[:1] == ["--"] else a.rest
        return exec_in(s, rest)
    if shutil.which("unshare") is None or shutil.which("nsenter") is None:
        raise SystemExit("util-linux unshare/nsenter required")
    out = {"init": init, "start": start, "stop": stop, "status": status, "expose-api": expose_api}[a.cmd](s)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
