"""T010/T018 — MCP registry resolution, live handshake/tools-list preflight, Fabro MCP config generation.

Fail-closed rules (FR-005, FR-040):
* every registered op must be implemented by its Forge server module;
* an op whose backing executable is missing is DISABLED (optional) or MISSING (mandatory);
* a run is BLOCKED before any agent starts if any mandatory op granted to a used role is not OK, or a
  required server fails its MCP handshake / `tools/list` signature check. There is no direct-shell fallback.
"""
from __future__ import annotations

import importlib
import json
import shutil
import sys
import time
from pathlib import Path

import anyio

from ..common import REPO_ROOT, pretty_json, state_dir, utc_now
from ..registry.agents import load_agents
from ..registry.mcp_registry import McpRegistry, load_registry
from .sdk import SERVER_MODULES

BACKING: dict[str, list[str]] = {
    "forge-build-mcp.configure": ["arm-none-eabi-gcc"], "forge-build-mcp.compile": ["arm-none-eabi-gcc"],
    "forge-build-mcp.measure_elf": ["arm-none-eabi-size"], "forge-build-mcp.stack_usage": ["arm-none-eabi-gcc"],
    "forge-build-mcp.disassemble": ["arm-none-eabi-objdump"],
    "forge-analysis-mcp.cppcheck": ["cppcheck"], "forge-analysis-mcp.clang_analyze": ["clang"],
    "forge-analysis-mcp.clang_tidy": ["clang-tidy"], "forge-analysis-mcp.cbmc_verify": ["cbmc"],
    "forge-analysis-mcp.frama_check": ["frama-c"],
    "forge-tests-mcp.run_unit": ["clang"], "forge-tests-mcp.run_integration": ["clang"],
    "forge-tests-mcp.llvm_coverage": ["llvm-profdata", "llvm-cov"], "forge-tests-mcp.gcov_coverage": ["__disabled__"],
    "forge-sim-mcp.run_renode": ["renode"], "forge-sim-mcp.run_hwsim": ["__disabled__"],
    "forge-repo-mcp.diff_scoped": ["git"], "forge-repo-mcp.create_worktree": ["git"],
    "forge-repo-mcp.commit_candidate": ["git"], "forge-repo-mcp.get_commit": ["git"],
    "forge-docs-mcp.render_diagram": ["plantuml"], "forge-docs-mcp.build_docs": ["mkdocs"],
}


def op_catalog(reg: McpRegistry | None = None) -> dict[str, dict]:
    reg = reg or load_registry()
    cat: dict[str, dict] = {}
    for srv in reg.server_catalog:
        mod_name = SERVER_MODULES.get(srv.id)
        implemented = set()
        if mod_name:
            try:
                implemented = {o.name for o in importlib.import_module(mod_name).OPERATIONS}
            except Exception:  # noqa: BLE001 - import failure => not implemented
                implemented = set()
        for op in srv.ops:
            key = f"{srv.id}.{op.name}"
            missing = [t for t in BACKING.get(key, []) if t == "__disabled__" or not shutil.which(t)]
            status = "OK" if op.name in implemented and not missing else (
                "NOT_IMPLEMENTED" if op.name not in implemented else ("MISSING" if op.mandatory else "DISABLED"))
            cat[key] = {"server": srv.id, "op": op.name, "mandatory": op.mandatory, "status": status,
                        "missing_tools": missing, "role_grants": op.role_grants, "timeout_s": op.timeout_seconds}
    return cat


async def _handshake(server_id: str, timeout_s: float = 20.0) -> dict:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", SERVER_MODULES[server_id]],
                                   env={"PYTHONPATH": str(REPO_ROOT / "factory" / "python"),
                                        "FORGE_STATE_DIR": str(state_dir()), "PATH": "/usr/bin:/bin"})
    t0 = time.monotonic()
    with anyio.fail_after(timeout_s):
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            init = await s.initialize()
            tools = await s.list_tools()
    return {"server": server_id, "protocol": init.protocol_version, "server_info": init.server_info.name,
            "tools": sorted(t.name for t in tools.tools),
            "schemas_ok": all(t.input_schema and t.input_schema.get("type") == "object" for t in tools.tools),
            "handshake_ms": round((time.monotonic() - t0) * 1000, 1)}


def handshake(server_id: str) -> dict:
    try:
        return anyio.run(_handshake, server_id)
    except Exception as exc:  # noqa: BLE001
        return {"server": server_id, "error": f"{type(exc).__name__}:{str(exc)[:120]}", "tools": []}


def preflight(roles: list[str] | None = None, live: bool = True, *, include_afo: bool = False) -> dict:
    reg = load_registry(include_afo=include_afo)
    cat = op_catalog(reg)
    agents = {a.id: a for a in load_agents(include_afo=include_afo)[0]}
    roles = roles or sorted(agents)
    needed_ops = sorted({t for r in roles if r in agents for t in agents[r].allowed_tools})
    servers = sorted({k.split(".")[0] for k in needed_ops})
    issues = [f"MCP_ROLE_UNKNOWN:{r}" for r in roles if r not in agents]
    hs = {}
    for k in needed_ops:
        e = cat.get(k)
        if e is None:
            issues.append(f"MCP_OP_UNREGISTERED:{k}")
        elif e["status"] in ("MISSING", "NOT_IMPLEMENTED"):
            issues.append(f"MCP_MISSING:{k}:{e['status']}:{','.join(e['missing_tools'])}"[:120])
    if live:
        for s in servers:
            h = hs[s] = handshake(s)
            if "error" in h:
                issues.append(f"MCP_HANDSHAKE_FAILED:{s}:{h['error']}"[:120])
                continue
            expect = {e["op"] for e in cat.values() if e["server"] == s}
            if not expect <= set(h["tools"]) or not h["schemas_ok"]:
                issues.append(f"MCP_TOOLS_LIST_MISMATCH:{s}")
    disabled = sorted(k for k, e in cat.items() if e["status"] == "DISABLED")
    return {"schema": "forge-c/mcp-preflight/0.4", "ts_utc": utc_now(), "status": "PASS" if not issues else "BLOCKED",
            "roles": roles, "required_ops": needed_ops, "servers": servers, "issues": issues,
            "disabled_optional_ops": disabled, "handshakes": hs, "catalog": cat,
            "fallback": "NONE (no direct shell substitution)"}


def fabro_mcp_config(servers: list[str]) -> dict[str, dict]:
    return {s: {"module": SERVER_MODULES[s], "startup_timeout": "30s", "tool_timeout": "200s"} for s in servers}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", default="")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-live", action="store_true")
    a = ap.parse_args(argv)
    rep = preflight([r for r in a.roles.split(",") if r] or None, live=not a.no_live)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(rep))
    print(json.dumps({"status": rep["status"], "issues": rep["issues"][:10],
                      "disabled_optional_ops": rep["disabled_optional_ops"]}))
    return 0 if rep["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
