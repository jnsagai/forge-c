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
import fcntl
import hashlib
import json
import math
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from ..common import REPO_ROOT, pretty_json, utc_now
from . import pidfd
from . import profile as lp

SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"
LOCK_FD_ENV = "FORGE_STACK_LOCK_FD"


_EFFECT_GUARD = ContextVar("forge_line_stack_effect_guard", default=None)


@contextmanager
def line_effect_guard(guard):
    token = _EFFECT_GUARD.set(guard)
    try:
        yield
    finally:
        _EFFECT_GUARD.reset(token)


def _guard_effect():
    guard = _EFFECT_GUARD.get()
    if guard is not None:
        guard()


class StackLockHeld(RuntimeError):
    """Autonomous line M2: another start/stop of this stack root is in progress (a raced start is refused)."""


def lock_path(root: Path) -> Path:
    return Path(root) / "run/stack.lock"


def _inherited_lock_fd(path: Path) -> int | None:
    """The descriptor a caller that already holds this root's stack lock passed down (FORGE_STACK_LOCK_FD), when it
    really is an open file description of that lock file; else None."""
    raw = os.environ.get(LOCK_FD_ENV, "")
    if not raw.isdigit():
        return None
    try:
        held, want = os.fstat(int(raw)), os.stat(path)
    except OSError:
        return None
    return int(raw) if (held.st_dev, held.st_ino) == (want.st_dev, want.st_ino) else None


@contextmanager
def stack_lock(root: Path):
    """Autonomous line M2 (owner 2026-11-03): one lifecycle action (start/stop) per stack root at a time. flock -n on
    <root>/run/stack.lock; a second start/stop is refused with STACK_LOCK_HELD, never queued. The line launcher holds
    the lock across stop -> sweep -> start -> smoke -> launch and passes its descriptor in FORGE_STACK_LOCK_FD to the
    start/stop it runs: flock on that same open file description succeeds, so only foreign callers are refused. The
    daemons never inherit the descriptor (subprocess closes it), so the lock ends with the action. A root without
    its run/ folder (never initialised, or moved aside by the rollback drill) is not created here: start refuses it
    ("run `init` first") and stop has nothing to stop."""
    path = lock_path(root)
    if not path.parent.is_dir():
        yield None
        return
    inherited = _inherited_lock_fd(path)
    fd = inherited if inherited is not None else os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StackLockHeld(f"STACK_LOCK_HELD:{path}") from None
        yield path
    finally:
        if inherited is None:  # closing our own description releases the lock; an inherited one stays the caller's
            os.close(fd)


def gateway_reasoning(prof: dict) -> str:
    """The profile's per-model reasoning exception for the gateway (owner decision 2026-10-22); '{}' when none."""
    return json.dumps((prof.get("gateway") or {}).get("reasoning") or {}, sort_keys=True)


def gateway_timeout(prof: dict) -> int | float:
    value = (prof.get("gateway") or {}).get("request_timeout_s", 600)
    if type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 86400:
        raise ValueError("GATEWAY_REQUEST_TIMEOUT_INVALID")
    return value


def settings(profile_id: str = "local-rtx-v1") -> dict:
    prof = lp.load(profile_id)
    gateway_timeout(prof)  # reject invalid configuration before creating any serving process
    root = Path(os.environ.get(prof["deployment"]["root_env"]) or prof["deployment"]["default_root"])
    return {"profile": prof, "root": root, "ports": prof["deployment"]["ports"]}


def envmap(s: dict) -> dict[str, str]:
    """The complete environment of every process of the local stack and its work orders (nothing inherited from the
    existing deployment's forge-env.sh)."""
    r, p = s["root"], s["ports"]
    fabro_bin = os.environ.get("FORGE_FABRO_BIN") or str(Path.home() / ".fabro/bin/fabro")  # shared binary, read-only
    optional_tools = [r / "toolchains" / name for name in ("plantuml", "renode/renode_1.17.0-portable")]
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
            [str(r / "venv/bin"), str(r / "toolchains/LLVM-19.1.7-Linux-X64/bin"),
             *[str(path) for path in optional_tools if path.is_dir()], SYSTEM_PATH,
             str(r / "toolchains/formal/bin"), str(r / "toolchains/sysroot/usr/bin")]
        ),
    }
    if os.environ.get("FORGE_OPERATIONS_INTENT"):
        env["FORGE_LRTX_ROOT"] = str(r)
        # Explicit continuous profile only. No provider credentials or unrelated deployment environment is inherited.
        for name in (
            "FORGE_OPERATIONS_INTENT",
            "FORGE_OPERATIONS_PROFILE",
            "FORGE_LINE_STACK_PAYLOAD",
            "FORGE_LINE_STACK_PAYLOAD_SHA256",
            "FORGE_LINE_STACK_ROOT",
            "FORGE_LINE_GPU_LOCK",
            "FORGE_LINE_FABRO_PORT",
            "FORGE_LINE_LAUNCH_DIR",
            "FORGE_CONDUCTOR_UNIT",
            "FORGE_DURABLE_AUTONOMY",
            "FORGE_DURABLE_NATIVE_HEADER",
            "FORGE_OWNER_DEVELOPMENT_RECORD", "FORGE_OWNER_DEVELOPMENT_SHA256",
            "FORGE_AFO_POLICY",
            "FORGE_AFO_QUEUE_SCOPE",
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


API_READY_SECONDS = 180


def fabro_config(s: dict) -> str:
    r, p = s["root"], s["ports"]
    runtime = s["profile"].get("runtime") or {}
    context = runtime.get("fabro_context_tokens", 32768)
    output = runtime.get("fabro_max_output_tokens", 16384)
    ceiling = runtime.get("context_limit_tokens", 65536)
    if (type(context) is not int or type(output) is not int or not 0 < output <= context
            or type(ceiling) is not int or not 0 < ceiling <= 262144 or not 0 < context <= ceiling):
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
    # setns into the current user namespace is EINVAL. Enter USER before NET
    # only when that user namespace actually differs from the caller's.
    target = Path(f"/proc/{pid}/ns")
    args = ["nsenter", "-t", str(pid)]
    if os.readlink(target / "user") != os.readlink("/proc/self/ns/user"):
        args.append("-U")
    if os.readlink(target / "net") != os.readlink("/proc/self/ns/net"):
        args.append("-n")
    return args + ["--preserve-credentials"]


def _wait(url: str, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):  # noqa: S310 - loopback health URL
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _in_ns(holder: int, argv: list[str], env: dict, log: Path, cwd: Path, *, serving=None, pass_fds=()) -> subprocess.Popen:
    enter = _nsenter(holder)
    if serving is not None:
        from ..afo.durable import Refused
        from . import provider_process as provider

        provider.validate(serving)
        init = serving["init_pid"]
        provider.require_live_instance(serving)
        actual = provider.identity(init)
        if not actual or actual.get("state") == "Z" or any(
            actual.get(k) != v for k, v in serving["init"].items() if k != "uid"
        ):
            raise Refused("PROVIDER_ENTRY_INIT_CHANGED")
        target_user = os.readlink(f"/proc/{init}/ns/user")
        outer_user = os.readlink(f"/proc/{holder}/ns/user")
        outer_net = os.readlink(f"/proc/{holder}/ns/net")
        current_user = os.readlink("/proc/self/ns/user")
        if actual["uid"] != serving["init"]["uid"]:
            # The trusted outer Fabro caller sees host owner1000 as mapped0.
            # Normalize only this exact captured holder USER and full kernel
            # one-UID map. A foreign mapped user cannot choose a numeric UID.
            mapping = [list(map(int, line.split())) for line in Path("/proc/self/uid_map").read_text().splitlines()]
            if not (
                current_user == outer_user
                and os.getuid() == actual["uid"] == 0
                and mapping == [[0, serving["init"]["uid"], 1]]
                and serving["init_owner_view"]["observer_uid"] == serving["init"]["uid"]
            ):
                raise Refused("PROVIDER_ENTRY_OWNER_CHANGED")
        if target_user != serving["init_owner_view"]["user_namespace"] or os.readlink(f"/proc/{init}/ns/net") != outer_net:
            raise Refused("PROVIDER_ENTRY_NAMESPACE_CHANGED")
        # A development provider owns a child USER/MNT/PID namespace but
        # inherits NET from the outer holder. Joining that child USER first
        # would lose the capability to enter its ancestor-owned NET (EPERM).
        # A caller already inside the exact provider must not enter an ancestor
        # USER; it must already share the pinned outer NET instead.
        if current_user == target_user:
            if os.readlink("/proc/self/ns/net") != outer_net:
                raise Refused("PROVIDER_ENTRY_CALLER_NETWORK_CHANGED")
            enter = []
        inner = ["nsenter", "-t", str(init)]
        if target_user != (current_user if not enter else outer_user):
            inner.append("-U")
        enter += inner + ["-m", "-p", "--preserve-credentials"]
    with log.open("ab") as fh:
        _guard_effect()
        return subprocess.Popen(
            enter + argv,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
            pass_fds=pass_fds,
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


def _ns_identity(pid, holder, timeout=5.0):
    """CAPA-216 (TIM LL L43L): a stack process is spawned through nsenter, which enters the holder's namespaces after the
    fork. An identity read before that names the caller's network namespace and later refuses the managed stop
    (LOCAL_PROCESS_OWNERSHIP_UNPROVEN). Record it once the process has left the caller's netns (bounded wait)."""
    own, deadline = os.readlink("/proc/self/ns/net"), time.monotonic() + timeout
    try:
        target = os.readlink(f"/proc/{holder}/ns/net")
    except OSError:
        return process_identity(pid)
    while True:
        ident = process_identity(pid)
        if ident is None or target == own or ident["netns"] != own or time.monotonic() > deadline:
            return ident
        time.sleep(0.02)


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
    with stack_lock(s["root"]):
        return _locked_start(s, recovery=recovery)


def _locked_start(s: dict, *, recovery=False) -> dict:
    from ..afo import line_stack_lifecycle

    if line_stack_lifecycle.selected():
        return line_stack_lifecycle.start(s, recovery=recovery)
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


def _manifest(mdir: Path, model: str) -> Path:
    """The Ollama manifest of a pinned model: library names (qwen3.8:27b-q8_0) or registry-qualified names such as
    hf.co/<org>/<repo>:<tag> (owner 2026-10-31: Ornith is pinned by its hf.co name)."""
    name, tag = model.split(":", 1)
    parts = name.split("/")
    if any(x in ("", ".", "..") for x in parts + [tag]):
        raise RuntimeError(f"LLAMA_SERVER_MODEL_NAME_INVALID:{model}")
    if len(parts) > 1:
        return mdir / "manifests" / Path(*parts) / tag
    return mdir / "manifests/registry.ollama.ai/library" / name / tag


def served_models(prof: dict) -> list[str]:
    """The models this stack's llama-server may serve: the one started with the stack, then the profile's alternates
    (one at a time; `serve` swaps between them)."""
    ls = (prof.get("runtime") or {}).get("llama_server")
    if not ls:
        return []
    return [ls["model"], *((prof["runtime"].get("llama_server_alternates") or {}).keys())]


def llama_server_spec(r: Path, prof: dict, p: dict, env: dict, model: str | None = None) -> tuple | None:
    """F014 (owner 2026-10-26: "install a new runtime on Omniverse2 to allow parallel model calls"). Ollama 0.34 serves
    qwen35moe with one request slot ("model architecture does not currently support parallel requests"); its bundled
    llama.cpp server serves the same model file with N slots. The model is the one the profile pins: the Ollama
    manifest's sha256 must equal the pinned digest, and its model layer (content-addressed blob) must have the recorded
    size. Returns (argv, env, health, models) or None when the profile has no runtime.llama_server."""
    ls = (prof.get("runtime") or {}).get("llama_server")
    if not ls:
        return None
    if model is not None and model != ls["model"]:  # an alternate served model (in-run swap, owner 2026-10-31)
        alt = (prof["runtime"].get("llama_server_alternates") or {}).get(model)
        if not isinstance(alt, dict):
            raise RuntimeError(f"LLAMA_SERVER_MODEL_NOT_SERVED:{model}")
        ls = {**alt, "model": model}
    from ..common import sha256_file

    model, mdir = ls["model"], r / "ollama-models"
    man = _manifest(mdir, model)
    if not man.is_file() or sha256_file(man) != prof["models"]["allowed"][model]["digest"]:
        raise RuntimeError(f"LLAMA_SERVER_MODEL_DIGEST_MISMATCH:{model}")
    layer = next(x for x in json.loads(man.read_text())["layers"] if x["mediaType"].endswith(".image.model"))
    blob = mdir / "blobs" / layer["digest"].replace(":", "-")
    if not blob.is_file() or blob.stat().st_size != layer["size"]:
        raise RuntimeError(f"LLAMA_SERVER_MODEL_BLOB_MISSING:{layer['digest'][:19]}")
    if ls.get("model_blob_sha256") and layer["digest"] != "sha256:" + ls["model_blob_sha256"]:
        raise RuntimeError(f"LLAMA_SERVER_MODEL_BLOB_PIN_MISMATCH:{model}")
    lib, slots = r / "ollama-0.34.0/lib/ollama", int(ls["slots"])
    reasoning = ls.get("reasoning", "off")
    effort = ls.get("reasoning_effort")
    if reasoning not in ("on", "off", "auto") or effort not in (None, "low", "medium", "high", "xhigh"):
        raise RuntimeError("LLAMA_SERVER_REASONING_CONFIGURATION_INVALID")
    ctx = int(ls.get("context_tokens") or prof["runtime"]["ollama"]["OLLAMA_CONTEXT_LENGTH"])
    kv = ls.get("kv_cache_type") or prof["runtime"]["ollama"]["OLLAMA_KV_CACHE_TYPE"]
    batch, microbatch = ls.get("batch_tokens", 2048), ls.get("microbatch_tokens", 2048)
    if (type(batch) is not int or type(microbatch) is not int
            or not 1 <= microbatch <= batch <= 65536):
        raise RuntimeError("LLAMA_SERVER_BATCH_CONFIGURATION_INVALID")
    argv = [str(lib / "llama-server"), "--model", str(blob), "--alias", model, "--host", "127.0.0.1",
            "--port", str(p["llama"]), "--no-webui", "--offline", "-c", str(ctx * slots), "-np", str(slots),
            "--jinja", "--reasoning", reasoning, "--cache-type-k", kv, "--cache-type-v", kv, "--flash-attn", "on",
            "-b", str(batch), "-ub", str(microbatch)]
    if "mtp_draft" in ls:
        if type(ls["mtp_draft"]) is not int or not 1 <= ls["mtp_draft"] <= 8:
            raise RuntimeError("LLAMA_SERVER_MTP_CONFIGURATION_INVALID")
        argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(int(ls["mtp_draft"]))]
    elif ls.get("spec_type") == "none":
        argv += ["--spec-type", "none"]
    if effort:
        argv += ["--reasoning-effort", effort, "--reasoning-format", "deepseek"]
    if ls.get("gpu_layers") == "all":
        argv += ["--gpu-layers", "all"]
    if ls.get("fit") in ("on", "off"):
        argv += ["--fit", ls["fit"]]
    penv = {**env, "LD_LIBRARY_PATH": f"{lib}:{lib}/cuda_v13", "GGML_BACKEND_PATH": f"{lib}/cuda_v13/libggml-cuda.so"}
    return argv, penv, f"http://127.0.0.1:{p['llama']}/health", [model]


def cloud_bridge(prof: dict) -> dict | None:
    """Owner 2026-11-02 (comparison line): runtime.cloud_bridge {socket (under the root), models} - the gateway forwards
    these models to the cloud bridge (lrtx/cloud_bridge.py) over a unix socket; no ollama or llama-server runs."""
    cb = (prof.get("runtime") or {}).get("cloud_bridge")
    return cb if isinstance(cb, dict) and cb.get("models") else None


def bridge_socket(r: Path, prof: dict) -> Path:
    return Path(r) / cloud_bridge(prof)["socket"]


def bridge_healthy(sock: Path) -> bool:
    """GET /health over the bridge socket (from the host; the socket file is on the shared filesystem)."""
    import socket as _socket

    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as c:
            c.settimeout(10)
            c.connect(str(sock))
            c.sendall(b"GET /health HTTP/1.1\r\nHost: cloud-bridge\r\nConnection: close\r\n\r\n")
            data = b""
            while chunk := c.recv(4096):
                data += chunk
        return data.startswith(b"HTTP/1.") and b" 200 " in data.split(b"\r\n", 1)[0] and b'"ok"' in data
    except OSError:
        return False


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


def require_current_fabro_settings(s: dict) -> None:
    """A retained root can hold settings from an older profile. Fabro then omits the output
    limit for any model that file does not list, and the gateway refuses every request."""
    path = s["root"] / "fabro/settings.toml"
    if not path.is_file() or path.read_text() != fabro_config(s):
        raise ValueError("FABRO_SETTINGS_STALE")


def _start(s: dict, *, recovery=False, control_only=False) -> dict:
    from ..afo import owner_supervised_development as development
    from . import provider_process as provider

    guard = _guard_effect
    guard()
    if development.selected():
        require_current_fabro_settings(s)
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
        guard()
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

        if serving is not None:
            serving = serving_instance(s)
            if not provider.quiet(serving) and os.environ.get("FORGE_OWNER_DEVELOPMENT_RECORD"):
                from ..afo.owner_supervised_development import require_compatible_provider

                require_compatible_provider(serving)
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
                guard()
                provider_command = ["unshare", "--mount", "--pid", "--fork", "--mount-proc",
                                    "--kill-child=SIGKILL", "sleep", "infinity"]
                development_view = None
                development_handles = ()
                from ..afo import owner_supervised_development as owner_development

                if owner_development.selected():
                    from ..afo.owner_development_view import prepare

                    provider_command, development_view, development_handles = prepare(r, owner_development.current())
                try:
                    proc = _in_ns(
                        holder, provider_command, env, r / "logs/provider-holder.log", r,
                        pass_fds=development_handles,
                    )
                finally:
                    for fd in development_handles:
                        os.close(fd)
                parent_pid = proc.pid
                rec["serving_holder"] = {"pid": proc.pid, "identity": _ns_identity(proc.pid, holder)}  # CAPA-216
                if development_view is not None:
                    rec["serving_holder"]["owner_development_view"] = development_view
                _save_services(r, {**rec, "processes": procs})
            deadline = time.monotonic() + 3
            while True:
                try:
                    serving = provider.capture(
                        r, profile=prof["id"], profile_sha256=prof["_sha256"], parent_pid=parent_pid, outer_pid=holder
                    )
                    break
                except Refused:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            if view := (rec.get("serving_holder") or {}).get("owner_development_view"):
                serving["owner_development_view"] = view
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
    from .request_measurement import policy as request_measurement_policy

    gw_env["FORGE_GATEWAY_REQUEST_MEASUREMENT"] = json.dumps(request_measurement_policy(prof))
    if prof.get("gateway", {}).get("measure_unbound_requests") is True:
        gw_env["FORGE_GATEWAY_MEASURE_UNBOUND"] = "1"
        gw_env["FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT"] = str(prof["runtime"]["context_limit_tokens"])
    gw_env["FORGE_GATEWAY_REQUEST_TIMEOUT_S"] = str(gateway_timeout(prof))
    if prof.get("gateway", {}).get("live_tap") is True:  # owner 2026-11-01: display-only answer tokens (live_tap.py)
        gw_env["FORGE_GATEWAY_LIVE_TAP"] = str(live_tap_path(r))
    if "drop_retries" in prof.get("gateway", {}):
        retries = prof["gateway"]["drop_retries"]
        if type(retries) is not int or not 0 <= retries <= 2:
            raise ValueError("GATEWAY_DROP_RETRIES_INVALID")
        gw_env["FORGE_GATEWAY_DROP_RETRIES"] = str(retries)
    cb = cloud_bridge(prof)
    if cb is not None:  # comparison line (owner 2026-11-02): every model of the bridge goes to its unix socket
        gw_env["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"unix:{bridge_socket(r, prof)}" for m in cb["models"]})
    ls = llama_server_spec(r, prof, p, env) if cb is None else None
    if ls is not None:  # the served model's chat requests go to the llama.cpp server, every other model to Ollama
        served = served_models(prof)
        gw_env["FORGE_GATEWAY_ROUTES"] = json.dumps({m: f"http://127.0.0.1:{p['llama']}" for m in served})
        if len(served) > 1:  # in-run swap: a request is answered only by the model it names (never another one)
            gw_env["FORGE_GATEWAY_VERIFY_SERVED"] = "1"
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
    if cb is not None:
        specs.pop("ollama", None)  # no local model server in the comparison line
    for name, (argv, penv, health) in specs.items():
        if control_only and name != "fabro":
            continue
        old = procs.get(name)
        if old and _alive(old["pid"], {"ollama": "ollama", "llama_server": "llama-server"}.get(name, argv[1])):
            continue
        guard()
        if managed_serving() and name in ("ollama", "llama_server", "gateway"):
            proc = _in_ns(holder, argv, penv, r / f"logs/{name}.log", r, serving=serving)
        else:
            proc = _in_ns(holder, argv, penv, r / f"logs/{name}.log", r)
        procs[name] = {"pid": proc.pid, "argv": argv, "health": health}
        startup_binding = getattr(_EFFECT_GUARD.get(), "startup_binding", None)
        bootstrap_binding = getattr(_EFFECT_GUARD.get(), "bootstrap_binding", None)
        if startup_binding is not None or bootstrap_binding is not None:
            procs[name]["identity"] = _ns_identity(proc.pid, holder)  # CAPA-216
            procs[name]["owner_view"] = provider.owner_view(proc.pid)
            _save_services(r, {**rec, "processes": procs,
                               **({"startup_binding": startup_binding} if startup_binding is not None else {}),
                               **({"owner_bootstrap_binding": bootstrap_binding} if bootstrap_binding is not None else {}),
                               "holder_pid": holder, "holder_identity": process_identity(holder),
                               "profile": prof["id"], "profile_sha256": prof["_sha256"], "root": str(r),
                               "netns": os.readlink(f"/proc/{holder}/ns/net"), "ports": p})
        deadline = time.monotonic() + (5 if recovery else 60)
        while time.monotonic() < deadline and not _probe(holder, env, health):
            guard()
            time.sleep(1)
        procs[name]["identity"] = _ns_identity(proc.pid, holder)  # CAPA-216
        if managed_serving():
            procs[name]["owner_view"] = provider.owner_view(proc.pid)
        if managed_serving() and serving is not None and name == "llama_server":
            procs[name]["worker"] = provider.capture_worker(serving, proc.pid, argv)
    health = {n: _probe(holder, env, v["health"]) for n, v in procs.items()}
    if cb is not None:
        health["cloud_bridge"] = bridge_healthy(bridge_socket(r, prof))
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
        **({"owner_bootstrap_binding": rec["owner_bootstrap_binding"]} if rec.get("owner_bootstrap_binding") else {}),
        # Recovery refreshes service health frequently. Keep the relay ownership
        # record so a later managed stop can retire its exact processes.
        **({"api_bridge": rec["api_bridge"]} if rec.get("api_bridge") else {}),
    }
    if bootstrap_binding := getattr(_EFFECT_GUARD.get(), "bootstrap_binding", None):
        rec["owner_bootstrap_binding"] = bootstrap_binding
    _save_services(r, rec)
    return rec


def _get(url: str, holder: int, env: dict, inside: bool) -> str | None:
    if inside:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - loopback
                return resp.read().decode()
        except OSError:
            return None
    code = f"import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('{url}', timeout=5).read().decode())"
    p = subprocess.run(_nsenter(holder) + [env["FORGE_VENV"] + "/bin/python", "-c", code], env=env,
                       capture_output=True, text=True, timeout=30)
    return p.stdout if p.returncode == 0 else None


def _serves(port: int, model: str, holder: int, env: dict, inside: bool) -> bool:
    """llama-server is healthy and its /v1/models lists exactly `model` (the --alias)."""
    if _get(f"http://127.0.0.1:{port}/health", holder, env, inside) is None:
        return False
    raw = _get(f"http://127.0.0.1:{port}/v1/models", holder, env, inside)
    try:
        ids = [m.get("id") for m in json.loads(raw or "{}").get("data") or []]
    except ValueError:
        return False
    return ids == [model]


def _vram_free_mib() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20)
        total, used = (int(x) for x in out.stdout.strip().splitlines()[0].split(","))
        return total - used
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _same_process(observed: dict | None, recorded: dict | None) -> bool:
    """The same process as recorded: boot, start time and network namespace. The uid is left out: inside the stack's
    user namespace the owner reads as 0 while `stack start` recorded it from outside (1000) - run -04 smoke test."""
    keys = ("boot_id", "start_ticks", "netns")
    return bool(observed and recorded) and all(observed.get(k) == recorded.get(k) and recorded.get(k) for k in keys)


def serve(s: dict, model: str, workspace: Path | None = None) -> dict:
    """Owner 2026-10-31 ("go ahead with the swap"): make the stack's llama-server serve `model`, one model at a time.

    A no-op when it already serves that model. Otherwise, in order: refuse under managed serving or while the gateway
    has a request in flight or queued; stop the recorded llama-server (process identity checked); wait for the GPU
    memory the profile states for the model; start it with its pinned spec; wait for health and require /v1/models
    to list exactly that model. Any failure leaves no llama-server running and raises: the graph's serve node then
    goes to the finalizer (fail closed, never a fallback to the other model). Every swap is recorded."""
    from ..afo import line_stack_lifecycle

    if line_stack_lifecycle.selected():
        return line_stack_lifecycle.serve(s, model, workspace)
    if managed_serving():
        # Nothing to swap, so nothing to refuse. A real swap still needs the line payload.
        saved = s["root"] / "run/services.json"
        current = ((json.loads(saved.read_text()) if saved.is_file() else {}).get("processes") or {}).get("llama_server") or {}
        if current.get("model") == model:
            return {"model_swap": "NOT_NEEDED", "model": model}
        raise RuntimeError("MODEL_SWAP_REFUSED_MANAGED_SERVING")
    return _serve_model(s, model, workspace)


def _serve_model(s: dict, model: str, workspace: Path | None = None, *, serving=None) -> dict:
    guard = _guard_effect
    guard()
    prof, r, p = s["profile"], s["root"], s["ports"]
    cb = cloud_bridge(prof)
    if cb is not None:  # comparison line: both models are answered by the bridge; nothing is swapped on any GPU
        if model not in cb["models"]:
            raise RuntimeError(f"MODEL_SWAP_MODEL_NOT_SERVED:{model}")
        ok = bridge_healthy(bridge_socket(r, prof))
        out = {"schema": "forge-c/model-swap/1", "at": utc_now(), "profile": prof["id"], "to": model,
               "digest": prof["models"]["allowed"][model]["digest"], "result": "BRIDGE_ROUTED" if ok else "FAILED",
               **({} if ok else {"reason": "CLOUD_BRIDGE_UNREACHABLE"})}
        for path in [r / "run/model-swaps.jsonl"] + ([Path(workspace) / ".forge-run/lrtx/serving/model-swaps.jsonl"]
                                                     if workspace else []):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as fh:
                fh.write(json.dumps(out, sort_keys=True) + "\n")
        if not ok:
            raise RuntimeError("MODEL_SWAP_CLOUD_BRIDGE_UNREACHABLE")
        return out
    if model not in served_models(prof):
        raise RuntimeError(f"MODEL_SWAP_MODEL_NOT_SERVED:{model}")
    holder = _holder(s)
    if holder is None:
        raise RuntimeError("MODEL_SWAP_STACK_NOT_RUNNING")
    env = envmap(s)
    inside = os.readlink("/proc/self/ns/net") == os.readlink(f"/proc/{holder}/ns/net")
    f = r / "run/services.json"
    rec = json.loads(f.read_text())
    procs = rec.setdefault("processes", {})
    cur = procs.get("llama_server")
    alive = bool(cur) and _alive(cur["pid"], "llama-server")
    current = cur["argv"][cur["argv"].index("--alias") + 1] if alive and "--alias" in cur["argv"] else None
    swap_cfg = (prof["runtime"].get("llama_server_swap") or {})
    out = {"schema": "forge-c/model-swap/1", "at": utc_now(), "profile": prof["id"], "from": current, "to": model,
           "digest": prof["models"]["allowed"][model]["digest"]}
    t0 = time.monotonic()

    def record(result: str, **extra) -> dict:
        out.update(result=result, seconds=round(time.monotonic() - t0, 2), **extra)
        line = json.dumps(out, sort_keys=True) + "\n"
        for path in [r / "run/model-swaps.jsonl"] + ([Path(workspace) / ".forge-run/lrtx/serving/model-swaps.jsonl"]
                                                     if workspace else []):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as fh:
                fh.write(line)
        return out

    if current == model and _serves(p["llama"], model, holder, env, inside):
        return record("ALREADY_SERVED")
    raw = _get(f"http://127.0.0.1:{p['gateway']}/health", holder, env, inside)
    try:
        adm = (json.loads(raw or "{}").get("admission") or {}) if raw else None
    except ValueError:
        adm = None
    if adm is None:
        record("REFUSED", reason="GATEWAY_STATE_UNKNOWN")
        raise RuntimeError("MODEL_SWAP_REFUSED_GATEWAY_STATE_UNKNOWN")
    busy = {k: adm.get(k) for k in ("inflight", "waiting") if adm.get(k)}  # Admission.snapshot fields
    if busy:
        record("REFUSED", reason="GATEWAY_BUSY", gateway=busy)
        raise RuntimeError("MODEL_SWAP_REFUSED_GATEWAY_BUSY")
    vram_before = _vram_free_mib()
    if alive:
        if cur.get("identity") and not _same_process(process_identity(cur["pid"]), cur["identity"]):
            record("REFUSED", reason="OWNERSHIP_UNPROVEN")
            raise RuntimeError("MODEL_SWAP_OWNERSHIP_UNPROVEN")
        def owned_signal(sig):
            guard()
            if serving is None:
                os.kill(cur["pid"], sig)
                return
            from ..afo.durable import Refused
            from . import provider_process as provider

            if not cur.get("identity") or not _same_process(process_identity(cur["pid"]), cur["identity"]):
                raise Refused("LINE_STACK_MODEL_PROCESS_OWNERSHIP_UNPROVEN")
            # The namespace observer may differ from the original host start.
            # Recapture the same exact waiter/argv's worker in this observer view.
            worker = provider.capture_worker(serving, cur["pid"], cur["argv"])
            provider.signal_worker(serving, worker, cur["argv"], sig,
                                   fenced_effect=lambda effect: (guard(), effect())[1])

        owned_signal(signal.SIGTERM)
        for _ in range(60):
            guard()
            if not _alive(cur["pid"], "llama-server"):
                break
            time.sleep(1)
        else:
            owned_signal(signal.SIGKILL)
            time.sleep(2)
    procs.pop("llama_server", None)
    _save_services(r, {**rec, "updated_at": utc_now()})
    argv, penv, health, _models = llama_server_spec(r, prof, p, env, model)
    spec = prof["runtime"]["llama_server"] if model == prof["runtime"]["llama_server"]["model"] else \
        prof["runtime"]["llama_server_alternates"][model]
    need = int(spec.get("vram_required_mib") or 0)
    free = _vram_free_mib()
    for _ in range(int(swap_cfg.get("vram_wait_s", 120))):
        guard()
        if free is not None and free >= need:
            break
        time.sleep(1)
        free = _vram_free_mib()
    if free is None or free < need:
        record("FAILED", reason="VRAM_NOT_AVAILABLE", vram_free_mib=free, vram_required_mib=need)
        raise RuntimeError("MODEL_SWAP_VRAM_NOT_AVAILABLE")
    log = r / "logs/llama_server.log"
    guard()
    if inside and serving is None:
        with log.open("ab") as fh:
            proc = subprocess.Popen(argv, env=penv, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    cwd=r, start_new_session=True)
    else:
        proc = _in_ns(holder, argv, penv, log, r, **({"serving": serving} if serving else {}))
    worker = None
    binding = getattr(_EFFECT_GUARD.get(), "startup_binding", None)
    try:
        if serving is not None:
            from . import provider_process as provider

            worker = provider.capture_worker(serving, proc.pid, argv, startup_binding=binding)
        deadline = time.monotonic() + float(swap_cfg.get("health_timeout_s", 600))
        ok = False
        while time.monotonic() < deadline and proc.poll() is None:
            guard()
            if _serves(p["llama"], model, holder, env, inside):
                ok = True
                break
            time.sleep(1)
        if not ok:
            raise RuntimeError("MODEL_SWAP_NOT_SERVED")
    except Exception:
        if serving is not None:
            from ..afo.durable import Refused

            try:
                cleanup = provider.retire_startup_worker(serving, worker, argv, binding=binding, parent_pid=proc.pid)
            except Exception as exc:
                reporter = getattr(_EFFECT_GUARD.get(), "record_cleanup_unknown", None)
                if reporter is not None:
                    reporter(serving)
                record("FAILED", reason="STARTUP_CLEANUP_UNKNOWN")
                raise Refused("LINE_STACK_FAILED_STARTUP_CLEANUP_UNKNOWN") from exc
            record("FAILED", reason="NOT_HEALTHY_OR_AUTHORITY_CHANGED", cleanup=cleanup)
        else:
            if proc.poll() is None:
                proc.kill()  # unchanged legacy cleanup; managed workers use their exact captured PID instead
            record("FAILED", reason="NOT_HEALTHY_OR_WRONG_MODEL", exit=proc.poll())
        raise
    procs["llama_server"] = {"pid": proc.pid, "argv": argv, "health": health, "identity": process_identity(proc.pid),
                             "model": model, **({"worker": worker} if worker else {})}
    rec["health"] = {**(rec.get("health") or {}), "llama_server": True}
    _save_services(r, {**rec, "updated_at": utc_now()})
    return record("SWAPPED", pid=proc.pid, argv_sha256=hashlib.sha256("\0".join(argv).encode()).hexdigest(),
                  vram_free_mib_before=vram_before, vram_free_mib_at_start=free)


def stop(s: dict) -> dict:
    with stack_lock(s["root"]):
        return _locked_stop(s)


def _locked_stop(s: dict) -> dict:
    from ..afo import line_stack_lifecycle

    if line_stack_lifecycle.selected():
        return line_stack_lifecycle.stop(s)
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
    guard = _guard_effect
    guard()
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
            guard()
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
    _guard_effect()
    pi = _in_ns(holder, inner, envmap(s), log, s["root"])
    deadline = time.monotonic() + 10
    while not sock.exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    _guard_effect()
    with log.open("ab") as fh:
        _guard_effect()
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
    # Fabro's startup integrity check took 29 s on a cold 400 MB database.
    ok = _wait(f"http://127.0.0.1:{port}/health", API_READY_SECONDS)
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
        "health": {**{n: _probe(holder, env, v["health"]) for n, v in (rec.get("processes") or {}).items()},
                   **({"cloud_bridge": bridge_healthy(bridge_socket(s["root"], s["profile"]))}
                      if cloud_bridge(s["profile"]) else {})},
    }


def live_tap_path(root: Path) -> Path:
    """The gateway's display-only answer-token socket (forge_factory.live_tap), in the stack's run folder."""
    return Path(root) / "run" / "gateway-live.sock"


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
    ap.add_argument("cmd", choices=["init", "start", "stop", "status", "env", "exec", "expose-api", "serve"])
    ap.add_argument("--model", help="serve only: the profile model the llama-server must serve (in-run swap)")
    ap.add_argument("--workspace", type=Path, help="serve only: also record the swap in this work-order workspace")
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
    if a.cmd == "serve":
        if not a.model:
            ap.error("serve needs --model")
        try:
            out = serve(s, a.model, a.workspace)
        except RuntimeError as exc:  # fail closed: the serve node's failure edge goes to the finalizer
            print(json.dumps({"model_swap": "FAILED", "model": a.model, "error": str(exc)}))
            return 1
        print(json.dumps(out, default=str))
        return 0
    if a.cmd == "expose-api":
        out = expose_api(s, a.host_port)
    else:
        try:
            out = {"init": init, "start": start, "stop": stop, "status": status}[a.cmd](s)
        except StackLockHeld as exc:  # M2: a raced start/stop is refused, typed, before any process action
            print(json.dumps({"refused": "STACK_LOCK_HELD", "cmd": a.cmd, "lock": str(exc).split(":", 1)[-1]}))
            return 3
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
