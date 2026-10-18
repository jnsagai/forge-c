"""Policy gate MCP server for Codex (ACP) nodes: the ONLY tools a Codex session gets.

  python -m forge_factory.acp.gate --binding <binding.json> --node <node_id> --server forge_fs|<forge MCP server id>

Every tools/call is decided by forge_factory.policy.fabro_hook.handle with the same context a Fabro pre_tool_use hook
receives (role grant, path scope, protected paths, turn budget per node visit), audited, and - for forge MCP
operations - ticketed before sdk.invoke consumes the ticket. A denial or any error returns an MCP tool error
(FORGE_POLICY:<code>); nothing runs. `forge_fs` serves Fabro-native-equivalent tools (read_file, read_many_files,
glob, grep, list_dir, write_file, edit_file, use_skill, update_plan) so the native-tool rules apply unchanged.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path

FS_TOOLS = {
    "read_file": ("Read a workspace file (text).", {"file_path": "string", "offset": "integer", "limit": "integer"},
                  ["file_path"]),
    "read_many_files": ("Read several workspace files.", {"paths": "array"}, ["paths"]),
    "glob": ("List workspace files matching a glob pattern (e.g. software/**/*.c).", {"pattern": "string",
                                                                                      "path": "string"}, ["pattern"]),
    "grep": ("Search workspace files for a regular expression.", {"pattern": "string", "path": "string",
                                                                  "include": "string"}, ["pattern"]),
    "list_dir": ("List a workspace directory.", {"path": "string"}, []),
    "write_file": ("Create or overwrite a workspace file with the given content.", {"file_path": "string",
                                                                                    "content": "string"},
                   ["file_path", "content"]),
    "edit_file": ("Replace an exact, unique old_string with new_string in a workspace file.",
                  {"file_path": "string", "old_string": "string", "new_string": "string", "replace_all": "boolean"},
                  ["file_path", "old_string", "new_string"]),
    "use_skill": ("Load your role's versioned SKILL.md (skill_name = your role id).", {"skill_name": "string"},
                  ["skill_name"]),
    "update_plan": ("Record a short plan (no side effects).", {"plan": "string"}, []),
}
MAX_READ = 400_000


def _schema(props: dict[str, str], required: list[str]) -> dict:
    p = {k: ({"type": "array", "items": {"type": "string"}} if t == "array" else {"type": t}) for k, t in props.items()}
    return {"type": "object", "properties": p, "required": required}


class Gate:
    def __init__(self, binding_path: Path, node: str, server: str):
        from ..policy.authz import Binding

        self.binding = Binding.load(binding_path)
        self.node, self.server = node, server
        self.ws = Path(os.path.realpath(self.binding.workspace))
        self.ops = {}
        if server != "forge_fs":
            self._load_server(server)

    # -- forge MCP server operations (in-process, exactly as the server would run them) ---------------------------
    def _load_server(self, server: str) -> None:
        run = tomllib.loads((self.ws / ".forge-run/workflow.toml").read_text())
        key = re.sub(r"[^A-Za-z0-9_]", "_", server)
        spec = ((run.get("run") or {}).get("agent") or {}).get("mcps", {}).get(key)
        if not spec:
            raise SystemExit(f"GATE_SERVER_NOT_IN_RUN:{server}")
        for k, v in (spec.get("env") or {}).items():
            os.environ[k] = str(v)
        cmd = spec.get("command") or []
        module = cmd[cmd.index("-m") + 1] if "-m" in cmd else None
        if not module or not module.startswith("forge_factory.mcp.servers."):
            raise SystemExit(f"GATE_SERVER_MODULE_REFUSED:{module}")
        mod = importlib.import_module(module)
        self.ops = {op.name: op for op in mod.OPERATIONS}

    def tools(self) -> list[dict]:
        if self.server == "forge_fs":
            return [{"name": n, "description": d, "inputSchema": _schema(p, r)} for n, (d, p, r) in FS_TOOLS.items()]
        return [{"name": op.name, "description": op.description, "inputSchema": op.model.model_json_schema()}
                for op in self.ops.values()]

    def _run_id(self) -> str:
        p = self.ws / ".forge-run/fabro_run_id"
        return p.read_text().strip() if p.is_file() else "acp"

    def policy_name(self, tool: str) -> str:
        from ..registry.mcp_registry import fabro_tool_name

        return tool if self.server == "forge_fs" else fabro_tool_name(f"{self.server}.{tool}")

    def call(self, tool: str, args: dict) -> tuple[bool, str]:
        """Returns (is_error, text). Fail closed: any exception before the action is a denial."""
        from ..policy import fabro_hook
        from ..policy.authz import Decision

        name = self.policy_name(tool)
        ctx = {"event": "pre_tool_use", "node_id": self.node, "run_id": self._run_id(), "tool_name": name,
               "tool_input": args, "workflow_name": "forge-acp-gate"}
        try:
            if self.server == "forge_fs" and tool not in FS_TOOLS or self.server != "forge_fs" and tool not in self.ops:
                d = Decision(False, "UNKNOWN_TOOL_DENIED", tool)
            else:
                d = fabro_hook.handle(ctx, self.binding)
            try:
                fabro_hook.audit(ctx, d, self.binding.binding_id)
            except Exception:  # noqa: BLE001 - an unauditable call is not allowed
                if d.allow:
                    d = Decision(False, "AUDIT_WRITE_FAILED", "cannot record audit event", d.role, d.op)
        except Exception as exc:  # noqa: BLE001 - fail closed
            return True, f"FORGE_POLICY:GATE_ERROR:{type(exc).__name__}"
        self._log({"tool": name, "allow": d.allow, "code": d.code})
        if not d.allow:
            return True, f"FORGE_POLICY:{d.code}:{d.reason}"[:600]
        try:
            if self.server == "forge_fs":
                return False, self._fs(tool, args)
            from ..mcp.sdk import invoke, issue_ticket

            node = self.binding.nodes.get(self.node, {})
            issue_ticket(self.binding.binding_id, name, args, d.role or "", self.node, node.get("phase"), str(self.ws))
            return False, json.dumps(invoke(self.server, self.ops[tool], args), separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 - a failing tool reports, it never opens anything
            return True, f"TOOL_ERROR:{type(exc).__name__}:{str(exc)[:300]}"

    def _log(self, rec: dict) -> None:
        from ..common import utc_now

        try:
            d = self.ws / ".forge-run/acp"
            d.mkdir(parents=True, exist_ok=True)
            with (d / f"{self.node}.gate.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": utc_now(), "server": self.server, **rec}) + "\n")
        except OSError:
            pass

    # -- Fabro-native-equivalent file and skill tools (paths already decided by the Authorizer) --------------------
    def _path(self, raw: str) -> Path:
        p = Path(os.path.realpath(raw if os.path.isabs(raw) else self.ws / raw))
        if p != self.ws and self.ws not in p.parents:  # defence in depth: the Authorizer already refused escapes
            raise PermissionError("PATH_OUTSIDE_WORKSPACE")
        return p

    def _fs(self, tool: str, a: dict) -> str:
        if tool == "read_file":
            lines = self._path(a["file_path"]).read_text(errors="replace").splitlines()
            off, lim = int(a.get("offset") or 0), int(a.get("limit") or 2000)
            return "\n".join(f"{i + 1:6}\t{t}" for i, t in enumerate(lines[off:off + lim], start=off))[:MAX_READ]
        if tool == "read_many_files":
            return "\n\n".join(f"==> {p} <==\n" + self._path(p).read_text(errors="replace")[:MAX_READ // 4]
                               for p in a.get("paths") or [])
        if tool == "write_file":
            p = self._path(a["file_path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(a["content"], encoding="utf-8")
            return f"wrote {p.relative_to(self.ws)} ({len(a['content'])} chars)"
        if tool == "edit_file":
            p = self._path(a["file_path"])
            t = p.read_text(errors="replace")
            n = t.count(a["old_string"])
            if n == 0:
                raise ValueError("old_string not found")
            if n > 1 and not a.get("replace_all"):
                raise ValueError(f"old_string occurs {n} times; make it unique or set replace_all")
            p.write_text(t.replace(a["old_string"], a["new_string"]) if a.get("replace_all")
                         else t.replace(a["old_string"], a["new_string"], 1), encoding="utf-8")
            return f"edited {p.relative_to(self.ws)}"
        if tool in ("glob", "list_dir"):
            base = self._path(a.get("path") or ".")
            if tool == "list_dir":
                return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in base.iterdir()))
            hits = sorted(str(x.relative_to(self.ws)) for x in base.glob(a["pattern"]) if x.is_file()
                          and ".git" not in x.relative_to(self.ws).parts)
            return "\n".join(hits[:500]) or "(no match)"
        if tool == "grep":
            base, rx = self._path(a.get("path") or "."), re.compile(a["pattern"])
            out = []
            files = [base] if base.is_file() else sorted(x for x in base.rglob("*") if x.is_file())
            for f in files:
                rel = f.relative_to(self.ws)
                if ".git" in rel.parts or (a.get("include") and not fnmatch.fnmatch(f.name, a["include"])):
                    continue
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if rx.search(line):
                        out.append(f"{rel}:{i}:{line[:200]}")
                        if len(out) >= 300:
                            return "\n".join(out)
            return "\n".join(out) or "(no match)"
        if tool == "use_skill":
            return self._path(f".fabro/skills/{a['skill_name']}/SKILL.md").read_text(errors="replace")
        if tool == "update_plan":
            return "plan recorded"
        raise ValueError(tool)


def serve(gate: Gate, stdin=sys.stdin, stdout=sys.stdout) -> None:
    def out(o: dict) -> None:
        stdout.write(json.dumps(o) + "\n")
        stdout.flush()

    for line in stdin:
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if "id" not in m:
            continue
        meth, mid, params = m.get("method"), m["id"], m.get("params") or {}
        if meth == "initialize":
            out({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": params.get("protocolVersion") or "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": f"forge-gate:{gate.server}", "version": "1.0"}}})
        elif meth == "tools/list":
            out({"jsonrpc": "2.0", "id": mid, "result": {"tools": gate.tools()}})
        elif meth == "tools/call":
            err, text = gate.call(str(params.get("name")), params.get("arguments") or {})
            out({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": err}})
        elif meth == "ping":
            out({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            out({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not supported: {meth}"}})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.acp.gate")
    ap.add_argument("--binding", type=Path, required=True)
    ap.add_argument("--node", required=True)
    ap.add_argument("--server", required=True)
    a = ap.parse_args(argv)
    serve(Gate(a.binding, a.node, a.server))
    return 0


if __name__ == "__main__":
    sys.exit(main())
