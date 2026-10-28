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
import tempfile
import time
import urllib.request
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now
from . import pidfd
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
    env = {
        "FORGE_LRTX_ROOT": str(r),
        "FORGE_LRTX_PROFILE": s["profile"]["id"],
        "FORGE_REPO_ROOT": str(REPO_ROOT),
        "PYTHONPATH": str(REPO_ROOT / "factory/python"),  # the checkout this stack runs (work orders, gates)
        "FORGE_DATA_ROOT": str(r),
        "FORGE_VENV": str(r / "venv"),
        "FORGE_STATE_DIR": str(r / "state"),
        "FORGE_ARCHIVE_DIR": str(r / "archives"),
        "UV_CACHE_DIR": str(r / "cache/uv"),
        "PIP_CACHE_DIR": str(r / "cache/pip"),
        "FORGE_OLLAMA_URL": f"http://127.0.0.1:{p['ollama']}",
        "FORGE_FABRO_BIN": fabro_bin,
        "FORGE_FABRO_URL": f"http://127.0.0.1:{p['fabro']}/api/v1",
        "FORGE_FABRO_CONFIG": str(r / "fabro/settings.toml"),
        "FORGE_FABRO_STORAGE": str(r / "fabro/storage"),
        "FORGE_FABRO_HOME": str(r / "fabro/home"),
        "FORGE_LLVM_BIN": str(r / "toolchains/LLVM-19.1.7-Linux-X64/bin"),
        "FORGE_FORMAL_BIN": str(r / "toolchains/formal/bin"),
        "HOME": str(r / "home"),
        "XDG_CACHE_HOME": str(r / "cache/xdg"),
        "XDG_CONFIG_HOME": str(r / "home/.config"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": "dumb",
        "PATH": ":".join(
            [str(r / "venv/bin"), str(r / "toolchains/LLVM-19.1.7-Linux-X64/bin"), SYSTEM_PATH, str(r / "toolchains/formal/bin")]
        ),
    }
    if os.environ.get("FORGE_OPERATIONS_INTENT"):
        env["FORGE_LRTX_ROOT"] = str(r)
        # Explicit continuous profile only. No provider credentials or unrelated deployment environment is inherited.
        for name in (
            "FORGE_OPERATIONS_INTENT",
            "FORGE_OPERATIONS_PROFILE",
            "FORGE_CONDUCTOR_UNIT",
            "FORGE_DURABLE_AUTONOMY",
            "FORGE_DURABLE_NATIVE_HEADER",
            "FORGE_AFO_POLICY",
            "FORGE_CPU_JOBS",
            "FORGE_AFO_AUTH_DIR",
            "FORGE_AFO_ALLOWED_SIGNERS",
            "FORGE_CRE_POLICY",
            "NOTIFY_SOCKET",
            "WATCHDOG_USEC",
            "WATCHDOG_PID",
            "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS",
        ):
            if name in os.environ:
                env[name] = os.environ[name]
    iso = r / "standards/iso26262-6-2018/part6.md"
    if iso.is_file():
        env["FORGE_ISO26262_6_2018_PATH"] = str(iso)
    return env


def fabro_config(s: dict) -> str:
    r, p = s["root"], s["ports"]
    runtime = s["profile"].get("runtime") or {}
    context = runtime.get("fabro_context_tokens", 32768)
    output = runtime.get("fabro_max_output_tokens", 16384)
    if (type(context) is not int or type(output) is not int or not 0 < output <= context
            or not 0 < context <= 65536):
        raise ValueError("FABRO_MODEL_LIMITS_INVALID")
    if "fabro_context_tokens" in runtime and context > int(runtime["ollama"]["OLLAMA_CONTEXT_LENGTH"]):
        raise ValueError("FABRO_CONTEXT_EXCEEDS_PROVIDER")
    models = "\n".join(
        f'[llm.providers.ollama.models."{m}"]\ndisplay_name = "{m} (local, profile {s["profile"]["id"]})"\n'
        f'api_model = "{m}"\ncapabilities = {{ text = true, tools = true }}\n'
        f"limits = {{ context_tokens = {context}, max_output_tokens = {output} }}\n"
        for m in s["profile"]["models"]["allowed"]
    )
    return f"""_version = 1
# Forge-C feature 010 local RTX Fabro server (profile {s["profile"]["id"]}): own storage/home/port, local provider only.
[server.listen]
type = "tcp"
address = "127.0.0.1:{p["fabro"]}"
[server.api]
url = "http://127.0.0.1:{p["fabro"]}/api/v1"
[server.web]
enabled = false
url = "http://127.0.0.1:{p["fabro"]}"
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
base_url = "http://127.0.0.1:{p["gateway"]}/v1"
auth = {{ type = "none" }}
default_model = "{s["profile"]["models"]["default"]}"
priority = 100

[llm.providers.ollama.metadata.agent]
profile = "openai"
reasoning_by_default = false

{models}
[run.model]
name = "{s["profile"]["models"]["default"]}"
provider = "ollama"
[run.environment]
id = "local"

[cli.target]
type = "http"
url = "http://127.0.0.1:{p["fabro"]}/api/v1"
"""


def init(s: dict) -> dict:
    """Create the isolated root (idempotent). Needs network once, outside the namespace, for the hash-pinned venv
    packages; everything the stack uses afterwards is local."""
    r = s["root"]
    issues = [i for i in lp.isolation_issues(s["profile"], envmap(s)) if not i.startswith("PROFILE_ENV_UNSET")]
    issues = [i for i in issues if "PATH_OUTSIDE_ROOT" not in i]
    if issues:
        raise lp.ProfileRefused(issues)
    for d in (
        "state",
        "archives",
        "fabro/storage",
        "fabro/home/.fabro",
        "logs",
        "run",
        "cache/uv",
        "cache/pip",
        "cache/xdg",
        "home/.config",
        "ollama-home",
    ):
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
        f'_version = 1\n[cli.target]\ntype = "http"\nurl = "http://127.0.0.1:{p["fabro"]}/api/v1"\n'
    )
    senv = r / "fabro/storage/server.env"
    if not senv.is_file() or not senv.stat().st_size:
        old = os.umask(0o077)
        try:  # fresh secrets of this isolated server only (0600); never logged
            senv.write_text(f"SESSION_SECRET={secrets.token_hex(32)}\nFABRO_DEV_TOKEN=fabro_dev_{secrets.token_hex(32)}\n")
            tok = next(ln.split("=", 1)[1] for ln in senv.read_text().splitlines() if ln.startswith("FABRO_DEV_TOKEN="))
            (r / "fabro/home/.fabro/auth.json").write_text(
                json.dumps(
                    {
                        "servers": {
                            f"http://127.0.0.1:{p['fabro']}": {"kind": "dev-token", "token": tok, "logged_in_at": utc_now()}
                        }
                    }
                )
            )
        finally:
            os.umask(old)
    venv = r / "venv"
    if not (venv / "bin/python").exists():
        env = {**envmap(s), "PATH": f"{Path.home() / '.local/bin'}:{SYSTEM_PATH}"}
        py = os.path.realpath(sys.executable)
        subprocess.run(["uv", "venv", "--python", py, str(venv)], check=True, env=env)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv / "bin/python"),
                "--require-hashes",
                "-r",
                str(REPO_ROOT / "requirements/forge-factory.lock"),
            ],
            check=True,
            env=env,
        )
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


def _in_ns(holder: int, argv: list[str], env: dict, log: Path, cwd: Path, *, serving=None) -> subprocess.Popen:
    enter = _nsenter(holder)
    if serving is not None:
        enter = ["nsenter", "-t", str(serving["init_pid"]), "-U", "-n", "-m", "-p", "--preserve-credentials"]
    with log.open("ab") as fh:
        return subprocess.Popen(
            enter + argv,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
        )


def _probe(holder: int, env: dict, url: str) -> bool:
    code = f"import urllib.request; urllib.request.urlopen('{url}', timeout=2)"
    return (
        subprocess.run(
            _nsenter(holder) + [env["FORGE_VENV"] + "/bin/python", "-c", code], env=env, capture_output=True, timeout=20
        ).returncode
        == 0
    )


def process_identity(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw[raw.rfind(")") + 2 :].split()
        return {
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "start_ticks": fields[19],
            "netns": os.readlink(f"/proc/{pid}/ns/net"),
            "uid": Path(f"/proc/{pid}").stat().st_uid,
        }
    except (OSError, IndexError):
        return None


def _pinned_process_ended(expected, current):
    """A different boot/start proves the OLD process ended, never ownership of the new PID."""
    if not expected or not current:
        return False
    return bool(
        expected.get("boot_id")
        and expected.get("start_ticks")
        and current.get("boot_id")
        and current.get("start_ticks")
        and (expected["boot_id"], expected["start_ticks"]) != (current["boot_id"], current["start_ticks"])
    )


def start(s: dict, *, recovery=False) -> dict:
    from ..afo.operations import Intent, configured, fenced_call

    if configured():
        epoch = Intent().read()["epoch"]

        def effect():
            if managed_serving():
                from ..afo.durable import Refused
                from ..afo.queue import Store

                _managed_scope(s)

                database = s["root"] / "state/conductor/conductor.sqlite3"
                if not database.exists() and (s["root"] / "run/services.json").exists():
                    raise Refused("DURABLE_PROFILE_STATE_MISSING")
                with Store(database).tx() as c:
                    held = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
                    if held and held[0]:
                        raise Refused("NATIVE_QUIESCENCE_UNPROVEN")
                    return _start(s, recovery=recovery)
            return _start(s, recovery=recovery)

        return fenced_call(epoch, effect)
    if recovery:
        raise ValueError("OPERATIONS_INTENT_REQUIRED")
    return _start(s)


def llama_server_spec(r: Path, prof: dict, p: dict, env: dict) -> tuple | None:
    """F014 (owner 2026-10-26: "install a new runtime on Omniverse2 to allow parallel model calls"). Ollama 0.34 serves
    qwen35moe with one request slot ("model architecture does not currently support parallel requests"); its bundled
    llama.cpp server serves the same model file with N slots. The model is the one the profile pins: the Ollama
    manifest's sha256 must equal the pinned digest, and its model layer (content-addressed blob) must have the recorded
    size. Returns (argv, env, health, models) or None when the profile has no runtime.llama_server."""
    ls = (prof.get("runtime") or {}).get("llama_server")
    if not ls:
        return None
    from ..common import sha256_file

    model, mdir = ls["model"], r / "ollama-models"
    name, tag = model.split(":", 1)
    man = mdir / "manifests/registry.ollama.ai/library" / name / tag
    if not man.is_file() or sha256_file(man) != prof["models"]["allowed"][model]["digest"]:
        raise RuntimeError(f"LLAMA_SERVER_MODEL_DIGEST_MISMATCH:{model}")
    layer = next(x for x in json.loads(man.read_text())["layers"] if x["mediaType"].endswith(".image.model"))
    blob = mdir / "blobs" / layer["digest"].replace(":", "-")
    if not blob.is_file() or blob.stat().st_size != layer["size"]:
        raise RuntimeError(f"LLAMA_SERVER_MODEL_BLOB_MISSING:{layer['digest'][:19]}")
    lib, slots = r / "ollama-0.34.0/lib/ollama", int(ls["slots"])
    ctx, kv = int(prof["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"]), prof["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"]
    argv = [str(lib / "llama-server"), "--model", str(blob), "--alias", model, "--host", "127.0.0.1",
            "--port", str(p["llama"]), "--no-webui", "--offline", "-c", str(ctx * slots), "-np", str(slots),
            "--jinja", "--reasoning", "off", "--cache-type-k", kv, "--cache-type-v", kv, "--flash-attn", "on",
            "-b", "2048", "-ub", "2048"]
    if ls.get("mtp_draft"):
        argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(int(ls["mtp_draft"]))]
    penv = {**env, "LD_LIBRARY_PATH": f"{lib}:{lib}/cuda_v13", "GGML_BACKEND_PATH": f"{lib}/cuda_v13/libggml-cuda.so"}
    return argv, penv, f"http://127.0.0.1:{p['llama']}/health", [model]


def managed_serving() -> bool:
    return os.environ.get("FORGE_DURABLE_AUTONOMY") == "1" and bool(os.environ.get("FORGE_OPERATIONS_INTENT"))


def _managed_scope(s):
    from ..afo.durable import Refused

    selected = os.environ.get("FORGE_OPERATIONS_PROFILE")
    if not selected or s["profile"]["id"] != selected or s["root"].resolve() != settings(selected)["root"].resolve():
        raise Refused("MANAGED_PROFILE_SCOPE_MISMATCH")


def _save_services(root: Path, record: dict) -> None:
    """Crash-safe projection; provider instance evidence is separately immutable."""
    from ..afo.durable import canonical

    path = root / "run/services.json"
    fd, temp = tempfile.mkstemp(prefix=".services-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def serving_instance(s: dict) -> dict:
    """Read a hash-bound kernel-captured instance; never upgrade legacy PID records."""
    from ..afo.durable import Refused, digest, strict_json
    from . import provider_process as provider

    path = s["root"] / "run/services.json"
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
        raise Refused("SERVING_INSTANCE_REFERENCE_INVALID")
    rec = strict_json(path.read_bytes(), 65536)
    instance = rec.get("serving_instance")
    if not isinstance(instance, dict):
        raise Refused("MANAGED_SERVING_INSTANCE_REQUIRED")
    provider.validate(instance)
    evidence = s["root"] / "run/provider-instances" / (digest(instance) + ".json")
    if (
        evidence.is_symlink()
        or evidence.stat().st_uid != os.getuid()
        or evidence.stat().st_mode & 0o022
        or strict_json(evidence.read_bytes(), 16384) != instance
        or instance["root"] != str(s["root"].resolve())
        or instance["profile"] != s["profile"]["id"]
        or instance["profile_sha256"] != s["profile"]["_sha256"]
    ):
        raise Refused("SERVING_INSTANCE_REFERENCE_INVALID")
    return instance


def _start(s: dict, *, recovery=False, control_only=False) -> dict:
    r, p, prof = s["root"], s["ports"], s["profile"]
    env = envmap(s)
    if not (r / "venv/bin/python").exists():
        raise RuntimeError("run `init` first")
    holder = _holder(s)
    saved = r / "run/services.json"
    retired = set()
    if recovery and saved.is_file():
        prior = json.loads(saved.read_text())
        # A live legacy PID without a pinned start identity is not safe to adopt automatically.
        if holder and (not prior.get("holder_identity") or process_identity(holder) != prior["holder_identity"]):
            if _pinned_process_ended(prior.get("holder_identity"), process_identity(holder)):
                # The old process ended. Forget its stale projection without
                # signaling or adopting the unrelated process now at that PID.
                (r / "run/holder.pid").unlink(missing_ok=True)
                holder = None
            else:
                raise ValueError("LOCAL_NAMESPACE_OWNERSHIP_UNPROVEN")
        for name, pr in (prior.get("processes") or {}).items():
            if control_only and name in ("ollama", "gateway"):
                continue
            current = process_identity(pr["pid"])
            if current and (not pr.get("identity") or current != pr["identity"]):
                if _pinned_process_ended(pr.get("identity"), current):
                    retired.add(name)
                else:
                    raise ValueError("LOCAL_PROCESS_OWNERSHIP_UNPROVEN")
    if holder is None:
        # user + network namespace: loopback only; the GPU device nodes stay usable
        subprocess.Popen(
            [
                "setsid",
                "unshare",
                "--user",
                "--map-root-user",
                "--net",
                "--fork",
                "bash",
                "-c",
                f"ip link set lo up && echo $$ > {r}/run/holder.pid && exec sleep infinity",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            time.sleep(0.1)
            if (holder := _holder(s)) is not None:
                break
        if holder is None:
            raise RuntimeError("network namespace holder did not start")
    rec = json.loads((r / "run/services.json").read_text()) if (r / "run/services.json").is_file() else {}
    procs = {k: v for k, v in (rec.get("processes") or {}).items() if k not in retired}
    serving = rec.get("serving_instance")
    known_serving = serving is not None
    if managed_serving() and not control_only:
        from ..afo.durable import Refused, digest, immutable_json
        from . import provider_process as provider

        if serving is not None:
            serving = serving_instance(s)
            if provider.quiet(serving):
                serving = None
                # nsenter waiters can briefly outlive the retired namespace.
                # They are not a serving instance and cannot be reused.
                procs = {k: v for k, v in procs.items() if k not in ("ollama", "gateway")}
        if serving is None:
            if not known_serving and any(
                _alive(pr["pid"], "ollama" if name == "ollama" else "forge_factory.llm_gateway")
                for name, pr in procs.items()
                if name in ("ollama", "gateway")
            ):
                raise Refused("LEGACY_SERVING_LIFETIME_UNPROVEN")
            pending = rec.get("serving_holder")
            observed = process_identity(pending["pid"]) if pending else None
            if (
                pending
                and observed
                and pending.get("identity")
                and all(observed[k] == pending["identity"][k] for k in ("boot_id", "start_ticks", "uid"))
            ):
                parent_pid = pending["pid"]
            else:
                proc = _in_ns(
                    holder,
                    ["unshare", "--mount", "--pid", "--fork", "--mount-proc", "--kill-child=SIGKILL", "sleep", "infinity"],
                    env,
                    r / "logs/provider-holder.log",
                    r,
                )
                parent_pid = proc.pid
                rec["serving_holder"] = {"pid": proc.pid, "identity": process_identity(proc.pid)}
                _save_services(r, {**rec, "processes": procs})
            deadline = time.monotonic() + 3
            while True:
                try:
                    serving = provider.capture(r, profile=prof["id"], profile_sha256=prof["_sha256"], parent_pid=parent_pid)
                    break
                except Refused:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            immutable_json(r / "run/provider-instances" / (digest(serving) + ".json"), serving)
            rec["serving_instance"] = serving
            _save_services(r, {**rec, "processes": procs})
    ollama_env = {
        **env,
        **prof["runtime"]["ollama"],
        "OLLAMA_HOST": f"127.0.0.1:{p['ollama']}",
        "OLLAMA_MODELS": str(r / "ollama-models"),
        "HOME": str(r / "ollama-home"),
    }
    adm = prof["admission"]
    gw_env = {
        **env,
        "PYTHONPATH": str(REPO_ROOT / "factory/python"),
        "FORGE_GATEWAY_MAX_INFLIGHT": str(adm["max_inflight"]),
        "FORGE_GATEWAY_MAX_QUEUE": str(adm["max_queue"]),
        "FORGE_GATEWAY_MAX_WAIT_S": str(adm["max_wait_s"]),
        "FORGE_GATEWAY_SAMPLE_S": str((prof.get("measurement") or {}).get("sample_s", 10)),
        "FORGE_GATEWAY_REASONING": gateway_reasoning(prof),
    }
    ls = llama_server_spec(r, prof, p, env)
    if ls is not None:  # the served model's chat requests go to the llama.cpp server, every other model to Ollama
        gw_env["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"http://127.0.0.1:{p['llama']}" for m in ls[3]})
    specs = {
        "ollama": ([str(r / "ollama-0.34.0/bin/ollama"), "serve"], ollama_env, f"http://127.0.0.1:{p['ollama']}/api/version"),
        "gateway": (
            [
                env["FORGE_VENV"] + "/bin/python",
                "-m",
                "forge_factory.llm_gateway",
                "--port",
                str(p["gateway"]),
                "--upstream",
                f"http://127.0.0.1:{p['ollama']}",
                "--meter",
                str(r / "state/llm-gateway/usage.jsonl"),
            ],
            gw_env,
            f"http://127.0.0.1:{p['gateway']}/health",
        ),
        **({"llama_server": ls[:3]} if ls is not None else {}),
        "fabro": (
            [
                env["FORGE_FABRO_BIN"],
                "server",
                "start",
                "--foreground",
                "--no-web",
                "--no-upgrade-check",
                "--config",
                env["FORGE_FABRO_CONFIG"],
                "--storage-dir",
                env["FORGE_FABRO_STORAGE"],
            ],
            {**env, "HOME": env["FORGE_FABRO_HOME"]},
            f"http://127.0.0.1:{p['fabro']}/health",
        ),
    }
    for name, (argv, penv, health) in specs.items():
        if control_only and name != "fabro":
            continue
        old = procs.get(name)
        if old and _alive(old["pid"], {"ollama": "ollama", "llama_server": "llama-server"}.get(name, argv[1])):
            continue
        if managed_serving() and name in ("ollama", "llama_server", "gateway"):
            proc = _in_ns(holder, argv, penv, r / f"logs/{name}.log", r, serving=serving)
        else:
            proc = _in_ns(holder, argv, penv, r / f"logs/{name}.log", r)
        procs[name] = {"pid": proc.pid, "argv": argv, "health": health}
        deadline = time.monotonic() + (5 if recovery else 60)
        while time.monotonic() < deadline and not _probe(holder, env, health):
            time.sleep(1)
        procs[name]["identity"] = process_identity(proc.pid)
    health = {n: _probe(holder, env, v["health"]) for n, v in procs.items()}
    rec = {
        "schema": "forge-c/lrtx-services/1",
        "profile": prof["id"],
        "profile_sha256": prof["_sha256"],
        "started_at": rec.get("started_at") or utc_now(),
        "updated_at": utc_now(),
        "root": str(r),
        "netns": os.readlink(f"/proc/{holder}/ns/net"),
        "holder_pid": holder,
        "holder_identity": process_identity(holder),
        "ports": p,
        "ollama_env": {k: v for k, v in ollama_env.items() if k.startswith("OLLAMA_")},
        "admission": adm,
        "processes": procs,
        "health": health,
        "shared_readonly": prof["deployment"]["shared_readonly"],
        **({"serving_instance": serving} if serving else {}),
        **({"serving_holder": rec["serving_holder"]} if rec.get("serving_holder") else {}),
        # Recovery refreshes service health frequently. Keep the relay ownership
        # record so a later managed stop can retire its exact processes.
        **({"api_bridge": rec["api_bridge"]} if rec.get("api_bridge") else {}),
    }
    _save_services(r, rec)
    return rec


def stop(s: dict) -> dict:
    if managed_serving():
        from ..afo import operations
        from ..afo.durable import Refused
        from ..afo.queue import Store

        _managed_scope(s)
        store = Store(s["root"] / "state/conductor/conductor.sqlite3")
        requested = operations.synchronize(store, "shutdown", str(os.getuid()), "Explicit local stack stop")
        settlement = operations.settle_shutdown(store, external=True)
        if not settlement["settled"]:
            return {"stopped": [], "settlement": settlement}
        intent = operations.Intent()
        with intent.lock():
            current = intent.read()
            if current["mode"] != "STOPPED" or current["epoch"] != requested["epoch"]:
                raise Refused("SHUTDOWN_INTENT_SUPERSEDED")
            return _stop(s, managed=True)
    return _stop(s)


def _stop(s: dict, *, managed=False) -> dict:
    r = s["root"]
    f = r / "run/services.json"
    rec = json.loads(f.read_text()) if f.is_file() else {"processes": {}}
    stopped = []

    def signal_owned(pid, expected, sig):
        from ..afo.durable import Refused

        observed = process_identity(pid)
        if observed is None:
            return
        if not expected or observed != expected:
            raise Refused("LOCAL_PROCESS_OWNERSHIP_UNPROVEN")
        try:
            descriptor = pidfd.open_pid(pid)
        except ProcessLookupError:
            return
        try:
            if process_identity(pid) != expected:
                raise Refused("LOCAL_PROCESS_OWNERSHIP_UNPROVEN")
            pidfd.send_signal(descriptor, sig)
        finally:
            os.close(descriptor)

    for name, pr in (rec.get("processes") or {}).items():
        marker = "ollama" if name == "ollama" else pr["argv"][1]
        if _alive(pr["pid"], marker):
            if managed:
                signal_owned(pr["pid"], pr.get("identity"), signal.SIGTERM)
            else:
                os.kill(pr["pid"], signal.SIGTERM)
            stopped.append(name)
    for name, pr in (rec.get("api_bridge") or {}).items():
        if isinstance(pr, dict) and _alive(pr["pid"], "socat"):
            if managed:
                signal_owned(pr["pid"], pr.get("identity"), signal.SIGTERM)
            else:
                os.kill(pr["pid"], signal.SIGTERM)
            stopped.append(f"api-bridge-{name}")
    rec.pop("api_bridge", None)
    holder = _holder(s)
    if holder is not None:  # `sleep infinity` may inherit an ignored SIGTERM from the launching shell
        if managed:
            signal_owned(holder, rec.get("holder_identity"), signal.SIGKILL)
        else:
            os.kill(holder, signal.SIGKILL)
        stopped.append("netns-holder")
        # F011-T040 (drill on loop10): a start right after a stop found the killed holder still in /proc and tried to
        # reuse its namespace; wait until it is gone (bounded) and forget it
        for _ in range(100):
            if not Path(f"/proc/{holder}").exists():
                break
            time.sleep(0.05)
    (r / "run/holder.pid").unlink(missing_ok=True)
    if f.is_file():
        rec["stopped_at"] = utc_now()
        rec["processes"] = {}
        _save_services(r, rec)
    return {"stopped": stopped}


def bridge_argv(s: dict, host_port: int | None = None) -> tuple[list[str], list[str], Path]:
    """Inbound-only relay of the profile's Fabro API to the host's loopback, for a read-only monitor: socat inside the
    namespace accepts on a 0600 unix socket in the profile root and connects to Fabro there; socat on the host listens
    on 127.0.0.1 only. Nothing inside the namespace gains a route out (the network check stays DENIED_VERIFIED)."""
    sock = s["root"] / "run/fabro-api.sock"
    port = s["ports"]["fabro"]
    inner = ["socat", f"UNIX-LISTEN:{sock},fork,mode=600,unlink-early", f"TCP:127.0.0.1:{port}"]
    outer = ["socat", f"TCP-LISTEN:{host_port or port},bind=127.0.0.1,reuseaddr,fork", f"UNIX-CONNECT:{sock}"]
    return inner, outer, sock


def _host_port_free(port: int) -> bool:
    import socket

    with socket.socket() as so:
        return so.connect_ex(("127.0.0.1", port)) != 0


def expose_api(s: dict, host_port: int | None = None) -> dict:
    """`host_port` lets a second isolated stack of the same profile be monitored while another holds the profile port."""
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
    inner, outer, sock = bridge_argv(s, host_port)
    port = host_port or s["ports"]["fabro"]
    if port in s["profile"]["deployment"].get("forbidden_ports", []):
        raise SystemExit(f"HOST_PORT_FORBIDDEN_BY_PROFILE:{port}")
    if not _host_port_free(port):
        raise SystemExit(f"HOST_PORT_IN_USE:127.0.0.1:{port} (never shared with another server)")
    log = s["root"] / "logs/api-bridge.log"
    pi = _in_ns(holder, inner, envmap(s), log, s["root"])
    deadline = time.monotonic() + 10
    while not sock.exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    with log.open("ab") as fh:
        po = subprocess.Popen(
            outer,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={"PATH": SYSTEM_PATH},
        )
    # A managed stop signals only processes whose recorded identity still matches (never a reused PID).
    rec["api_bridge"] = {
        "inner": {"pid": pi.pid, "argv": inner, "identity": process_identity(pi.pid)},
        "outer": {"pid": po.pid, "argv": outer, "identity": process_identity(po.pid)},
        "started_at": utc_now(),
    }
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
    return {
        "status": "UP",
        "holder_pid": holder,
        "netns": os.readlink(f"/proc/{holder}/ns/net"),
        "health": {n: _probe(holder, env, v["health"]) for n, v in (rec.get("processes") or {}).items()},
    }


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
    ap.add_argument("--host-port", type=int, help="expose-api only: host loopback port when the profile port is taken")
    # Parse stack options before the explicit command separator. REMAINDER
    # consumed --profile/--host-port after cmd, including the unit renderer's
    # `exec --profile ... -- ...`, forwarding them to nsenter instead.
    args = list(sys.argv[1:] if argv is None else argv)
    separator = args.index("--") if "--" in args else len(args)
    a, remainder = ap.parse_known_args(args[:separator])
    rest = remainder + args[separator + 1:]
    if a.cmd != "exec" and rest:
        ap.error("unrecognized arguments: " + " ".join(rest))
    s = settings(a.profile)
    if a.cmd == "env":
        print("unset PYTHONPATH")
        for k, v in envmap(s).items():
            print(f"export {k}={json.dumps(v)}")
        return 0
    if a.cmd == "exec":
        return exec_in(s, rest)
    if shutil.which("unshare") is None or shutil.which("nsenter") is None:
        raise SystemExit("util-linux unshare/nsenter required")
    if a.cmd == "expose-api":
        out = expose_api(s, a.host_port)
    else:
        out = {"init": init, "start": start, "stop": stop, "status": status}[a.cmd](s)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
