"""T011 — shared Forge MCP wrapper SDK (OSS, stdio, MCP Python SDK 2.3).

Every Forge domain server is built from this SDK, which enforces, independent of any prompt:
  * authorization: a one-time ticket written by the policy hook (role, node, args SHA-256, <=120 s)
    must exist for the exact call (production); `FORGE_MCP_TRUST=env` + FORGE_ROLE is test-only;
  * JSON input validation (pydantic models per operation, extra fields forbidden);
  * canonical workspace-restricted paths (no traversal/absolute/symlink escape/NUL/metacharacters);
  * subprocess with argv arrays only (never a shell), executable allowlist, cleared env, timeouts,
    RLIMIT_AS/CPU/FSIZE resource limits;
  * raw stdout/stderr saved to a content-addressed evidence store and referenced by SHA-256;
  * bounded, schema-valid `tool-result` envelopes (<= max_tool_result_bytes), secret redaction;
  * audit events for every allow/deny on `tools` / `security` channels.
"""
from __future__ import annotations

import json
import os
import re
import resource
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..common import canonical_json, schema_errors, sha256_bytes, state_dir, utc_now
from ..events.emit import emit
from ..events.redact import redact_text
from ..registry.mcp_registry import load_registry

MAX_RESULT_BYTES = 2048
TICKET_TTL_S = 120
SAFE_REL = re.compile(r"^[A-Za-z0-9_./+-]+$")


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolDenied(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}:{detail}")
        self.code, self.detail = code, detail


# --- authorization tickets -----------------------------------------------------------------
SERVER_MODULES = {
    "forge-build-mcp": "forge_factory.mcp.servers.build",
    "forge-analysis-mcp": "forge_factory.mcp.servers.analysis",
    "forge-tests-mcp": "forge_factory.mcp.servers.tests",
    "forge-sim-mcp": "forge_factory.mcp.servers.sim",
    "forge-evidence-mcp": "forge_factory.mcp.servers.evidence",
    "forge-repo-mcp": "forge_factory.mcp.servers.repo",
    "forge-observer-mcp": "forge_factory.mcp.servers.observer",
    "forge-knowledge-mcp": "forge_factory.mcp.servers.knowledge",
    "forge-docs-mcp": "forge_factory.mcp.servers.docs",
    "forge-afo-mcp": "forge_factory.mcp.servers.afo",  # Feature 005 overlay (load_registry(include_afo=True))
    "forge-maintainer-mcp": "forge_factory.mcp.servers.maintainer",  # Feature 005 overlay (AFO-T045)
}
AFO_SERVERS = ("forge-afo-mcp", "forge-maintainer-mcp")


def _op_model(tool_name: str) -> type[BaseModel] | None:
    import importlib

    m = re.match(r"^mcp__(forge_[a-z]+_mcp)__([a-z_]+)$", tool_name)
    if not m:
        return None
    server = m.group(1).replace("_", "-")
    mod = SERVER_MODULES.get(server)
    if not mod:
        return None
    ops = getattr(importlib.import_module(mod), "OPERATIONS", [])
    return next((o.model for o in ops if o.name == m.group(2)), None)


def normalize_args(tool_name: str, args: dict) -> dict:
    """Drop optional arguments equal to their declared default, identically for hook and server."""
    model = _op_model(tool_name)
    args = dict(args or {})
    if model is None:
        return args
    for k in list(args):  # undeclared keys are dropped by the MCP SDK before the server sees them
        if k not in model.model_fields:
            del args[k]
    for k, f in model.model_fields.items():
        # MCP materializes builtin container factories before calling the
        # wrapper. FieldInfo.default is Undefined for these, so comparing only
        # that value makes a valid hook ticket differ from defines=[] (or an
        # empty tool_versions map) injected by MCP. Do not execute arbitrary or
        # context-dependent factories while authenticating arguments.
        default = f.default_factory() if f.default_factory in (list, dict) else f.default
        if not f.is_required() and k in args and args[k] == default:
            del args[k]
    return args


def args_digest(tool_name: str, args: dict) -> str:
    return sha256_bytes(tool_name.encode() + b"\0" + canonical_json(normalize_args(tool_name, args)))


def tickets_dir(binding_id: str) -> Path:
    return state_dir() / "tickets" / re.sub(r"[^A-Za-z0-9_.-]", "_", binding_id)


def issue_ticket(binding_id: str, tool_name: str, args: dict, role: str, node_id: str, phase: str | None,
                 workspace: str) -> Path:
    d = tickets_dir(binding_id)
    d.mkdir(parents=True, exist_ok=True)
    digest = args_digest(tool_name, args)
    p = d / f"{digest}-{uuid.uuid4().hex[:8]}.json"
    p.write_text(json.dumps({"tool": tool_name, "digest": digest, "role": role, "node_id": node_id,
                             "phase": phase, "workspace": workspace, "issued": time.time()}))
    return p


def consume_ticket(binding_id: str, tool_name: str, args: dict) -> dict:
    d = tickets_dir(binding_id)
    digest = args_digest(tool_name, args)
    now = time.time()
    for p in sorted(d.glob(f"{digest}-*.json")) if d.is_dir() else []:
        try:
            t = json.loads(p.read_text())
            p.unlink()
        except (OSError, ValueError):
            continue
        if t.get("tool") == tool_name and now - float(t.get("issued", 0)) <= TICKET_TTL_S:
            return t
    raise ToolDenied("NO_AUTHORIZATION_TICKET", tool_name)


# --- context ---------------------------------------------------------------------------------
@dataclass
class ToolContext:
    server: str
    op: str
    role: str
    phase: str | None
    workspace: Path
    run_id: str
    invocation_id: str = field(default_factory=lambda: f"inv-{uuid.uuid4().hex[:16]}")

    # path handling --------------------------------------------------------------------------
    def path(self, raw: str, must_exist: bool = True, kind: str = "any") -> Path:
        if not isinstance(raw, str) or not raw or "\x00" in raw or len(raw) > 400:
            raise ToolDenied("PATH_INVALID", str(raw)[:60])
        ws_prefix = str(self.workspace).rstrip("/") + "/"
        if raw.startswith(ws_prefix):  # absolute path inside the workspace (Fabro native tools use absolute paths)
            raw = raw[len(ws_prefix):] or "."
        if raw.startswith("/") or "\\" in raw or not SAFE_REL.match(raw):
            raise ToolDenied("PATH_INVALID", raw[:60])
        parts = PurePosixPath(raw).parts
        if ".." in parts or (parts and parts[0].startswith(".git")):
            raise ToolDenied("PATH_TRAVERSAL", raw[:60])
        p = (self.workspace / raw)
        real = Path(os.path.realpath(p))
        if real != self.workspace and self.workspace not in real.parents:
            raise ToolDenied("PATH_ESCAPE", raw[:60])
        if must_exist and not real.exists():
            raise ToolDenied("PATH_NOT_FOUND", raw[:60])
        if kind == "file" and must_exist and not real.is_file():
            raise ToolDenied("NOT_A_FILE", raw[:60])
        if kind == "dir" and must_exist and not real.is_dir():
            raise ToolDenied("NOT_A_DIR", raw[:60])
        return real

    def rel(self, p: Path) -> str:
        return p.relative_to(self.workspace).as_posix()

    # evidence store ----------------------------------------------------------------------------
    def store(self, data: bytes, kind: str = "log") -> str:
        clean, _ = redact_text(data.decode("utf-8", errors="replace"))
        blob = clean.encode("utf-8")
        digest = sha256_bytes(blob)
        d = self.workspace / "evidence" / "raw"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{digest}.{kind}"
        if not f.exists():
            f.write_bytes(blob)
        return f"artifact:sha256:{digest}"


# --- subprocess --------------------------------------------------------------------------------
def _limits(mem_mb: int, cpu_s: int, fsize_mb: int) -> Callable[[], None]:
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb << 20, fsize_mb << 20))
        os.setsid()
    return apply


@dataclass
class ProcResult:
    argv: list[str]
    exit_code: int
    stdout: bytes
    stderr: bytes
    duration_ms: float
    timed_out: bool


def run_argv(argv: list[str], cwd: Path, timeout_s: int, allow: set[str], env_extra: dict[str, str] | None = None,
             mem_mb: int = 2048, fsize_mb: int = 256) -> ProcResult:
    if not argv or not isinstance(argv, list) or not all(isinstance(a, str) and "\x00" not in a for a in argv):
        raise ToolDenied("ARGV_INVALID")
    exe = shutil.which(argv[0]) if os.sep not in argv[0] else argv[0]
    if not exe or os.path.basename(argv[0]) not in allow:
        raise ToolDenied("EXECUTABLE_NOT_ALLOWED", argv[0][:60])
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "HOME": str(cwd), "TZ": "UTC", "SOURCE_DATE_EPOCH": "0", **(env_extra or {})}
    t0 = time.monotonic()
    try:
        p = subprocess.run([exe, *argv[1:]], cwd=cwd, env=env, capture_output=True, timeout=timeout_s,
                           preexec_fn=_limits(mem_mb, timeout_s + 5, fsize_mb), check=False, stdin=subprocess.DEVNULL)
        return ProcResult(argv, p.returncode, p.stdout, p.stderr, (time.monotonic() - t0) * 1000, False)
    except subprocess.TimeoutExpired as exc:
        return ProcResult(argv, 124, exc.stdout or b"", (exc.stderr or b"") + b"\nTIMEOUT", (time.monotonic() - t0) * 1000,
                          True)


def tool_version(exe: str, args: tuple[str, ...] = ("--version",)) -> str:
    try:
        out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=10, check=False)
        return ((out.stdout or out.stderr).strip().splitlines() or ["unknown"])[0][:80]
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


# --- result envelope ----------------------------------------------------------------------------
def result(ctx: ToolContext, status: str, summary: str, artifact_refs: list[str] | None = None,
           issues: list[str] | None = None, metrics: dict[str, Any] | None = None, tool: str = "forge",
           version: str = "0.4.0", exit_code: int | None = None, duration_ms: float | None = None,
           input_obj: Any = None, output_bytes: bytes | None = None, max_bytes: int = MAX_RESULT_BYTES) -> dict:
    prov: dict[str, Any] = {"tool": tool[:128], "version": (version or "unknown")[:80],
                            "invocation_id": ctx.invocation_id}
    if input_obj is not None:
        prov["input_sha256"] = sha256_bytes(canonical_json(input_obj))
    if output_bytes is not None:
        prov["output_sha256"] = sha256_bytes(output_bytes)
    if exit_code is not None:
        prov["exit_code"] = int(exit_code)
    if duration_ms is not None:
        prov["duration_ms"] = round(float(duration_ms), 1)
    env: dict[str, Any] = {"status": status, "summary": redact_text(summary)[0][:160],
                           "artifact_refs": list(artifact_refs or [])[:20],
           "issues": [redact_text(str(i))[0][:120] for i in (issues or [])], "provenance": prov,
           "metrics": {k: v for k, v in (metrics or {}).items() if isinstance(v, (int, float, str, bool, type(None)))}}
    # Bound the payload the model sees: drop issues/metrics tail, keep counts.
    total = len(env["issues"])
    while len(canonical_json(env)) > max_bytes and (env["issues"] or env["metrics"]):
        if env["issues"]:
            env["issues"].pop()
            env["metrics"]["issues_total"] = total
        else:
            env["metrics"].popitem()
    errs = schema_errors("tool-result.schema.json", env)
    if errs:
        raise RuntimeError(f"tool-result schema violation: {errs[:2]}")
    return env


# --- server assembly ---------------------------------------------------------------------------
@dataclass
class Operation:
    name: str
    model: type[ToolInput]
    handler: Callable[[ToolContext, Any], dict]
    description: str


def _authorize(server: str, op: str, args: dict) -> tuple[str, str | None, Path, str]:
    from ..registry.mcp_registry import fabro_tool_name

    reg = load_registry(include_afo=server in AFO_SERVERS)  # AFO ops exist only for the AFO servers
    key = f"{server}.{op}"
    if key not in reg.ops():
        raise ToolDenied("OP_NOT_REGISTERED", key)
    if os.environ.get("FORGE_MCP_TRUST") == "env":  # unit tests only, never set in generated run configs
        role = os.environ.get("FORGE_ROLE", "")
        phase = os.environ.get("FORGE_PHASE") or None
        ws = Path(os.environ.get("FORGE_WORKSPACE", ".")).resolve()
        run = os.environ.get("FORGE_RUN_ID", "local")
    else:
        binding = os.environ.get("FORGE_BINDING_ID", "")
        if not binding:
            raise ToolDenied("NO_BINDING")
        t = consume_ticket(binding, fabro_tool_name(key), args)
        role, phase, ws, run = t["role"], t.get("phase"), Path(t["workspace"]).resolve(), binding
    if role not in reg.ops()[key].role_grants:
        raise ToolDenied("ROLE_NOT_GRANTED", f"{role}->{key}")
    return role, phase, ws, run


def invoke(server: str, operation: Operation, args: dict) -> dict:
    t0 = time.monotonic()
    try:
        role, phase, ws, run = _authorize(server, operation.name, args)
        ctx = ToolContext(server, operation.name, role, phase, ws, run)
        try:
            parsed = operation.model.model_validate(args)
        except ValidationError as exc:
            loc = ",".join(map(str, exc.errors()[0].get("loc", ())))
            raise ToolDenied("INPUT_INVALID", loc) from exc
        from ..development_execution import verification

        verify = operation.name.startswith(("run_", "check_", "compile", "build", "measure"))
        key = server + "." + operation.name
        if verify and not verification(ws, phase, role, key):
            raise ToolDenied("DEVELOPMENT_PHASE_REPAIR_EXHAUSTED", key)
        try:
            out = operation.handler(ctx, parsed)
        except Exception:
            if verify:
                verification(ws, phase, role, key, "UNKNOWN")
            raise
        if verify:
            verification(ws, phase, role, key, out["status"])
        try:  # durable, append-only record of every tool result for deterministic gates/finalizer
            rec = {"ts_utc": utc_now(), "server": server, "op": operation.name, "role": role, "phase": phase,
                   "run_id": run, "result": out}
            (ws / "evidence").mkdir(parents=True, exist_ok=True)
            with open(ws / "evidence" / "tool-results.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        except OSError:
            out = result(ctx, "FAIL", "evidence write failed", issues=["EVIDENCE_WRITE_FAILED"])
        emit("tools", "INFO" if out["status"] == "PASS" else "WARN",
             f"{server}.{operation.name} {out['status']} role={role}", correlation_id=run, run_id=run,
             agent_id=role, tool_id=f"{server}.{operation.name}", duration_ms=round((time.monotonic() - t0) * 1000, 1),
             payload_ref=(out["artifact_refs"] or [None])[0])
        return out
    except ToolDenied as exc:
        emit("security", "WARN", f"DENY {server}.{operation.name} {exc.code}", correlation_id="mcp",
             tool_id=f"{server}.{operation.name}")
        dummy = ToolContext(server, operation.name, "unknown", None, Path("."), "mcp")
        return result(dummy, "BLOCKED", f"denied: {exc.code}", issues=[f"{exc.code}:{exc.detail}"[:120]])


def build_server(server_id: str, operations: list[Operation]):
    from mcp.server.mcpserver import MCPServer

    app = MCPServer(server_id, version="0.4.0")
    for op in operations:
        def make(op: Operation) -> Callable[..., str]:
            def tool(**kwargs: Any) -> str:
                return json.dumps(invoke(server_id, op, kwargs), separators=(",", ":"))
            tool.__name__ = op.name
            tool.__doc__ = op.description
            return tool

        fn = make(op)
        # Preserve FieldInfo: bare annotations lose bounds/descriptions when MCP
        # rebuilds its argument model from this callable signature.
        annotations = {k: Annotated[f.annotation, f] for k, f in op.model.model_fields.items()}
        fn.__annotations__ = {**annotations, "return": str}
        import inspect

        params = [inspect.Parameter(k, inspect.Parameter.KEYWORD_ONLY, annotation=annotations[k],
                                    default=(inspect.Parameter.empty if f.is_required() else f.default))
                  for k, f in op.model.model_fields.items()]
        fn.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
        app.add_tool(fn, name=op.name, description=op.description)
    return app


def utc_stamp() -> str:
    return utc_now()
