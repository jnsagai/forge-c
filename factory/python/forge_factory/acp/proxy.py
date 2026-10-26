"""ACP proxy that Fabro starts for a Codex node (acp.command):

  python -m forge_factory.acp.proxy --binding <binding.json> --node <node_id>

Between Fabro (ACP client) and codex-acp (ACP agent):
  * initialize: the client's fs/terminal capabilities are removed (the agent cannot read/write through Fabro);
  * the agent's MCP servers are the policy gate servers only (forge_fs + every forge MCP server of the run), set in
    the Codex session config with default_tools_approval_mode="approve" (the gate decides; codex-acp 2.1.1 cannot
    relay Codex's MCP approval question); session/new|load mcpServers from the client are dropped;
  * session/request_permission and every other agent->client request: denied here, never forwarded (a permission
    request is answered with its reject option, CAPA-049);
  * session/prompt: a short tool note is prepended (file tools are the gate's mcp__forge_fs__* tools; no shell) and
    the reply rule appended (final message = the requested JSON only; CAPA-045).
Codex runs with the factory CODEX_HOME (acp.codex_home) and its shell/exec/browser/plugin/sub-agent features off.
With --agent claude (OD-2026-10-19-08) the agent is claude-agent-acp on the owner's Claude login (acp.claude_home):
the gate servers are set in session/new instead (ACP mcpServers, each allowed without a prompt) together with
_meta.claudeCode.options that remove every built-in tool and every settings source; the rest is identical.
Everything denied is logged to .forge-run/acp/<node>.proxy.jsonl (method and reason, no content), and so is the
token usage the agent reports in each prompt result (counts and model ID only; feature 007, CR-T029).
A prompt that ends in a JSON-RPC error is logged as `prompt_error` (code + redacted, truncated message): the run's
only workspace evidence that the agent backend was unavailable (F015: 'ACP turn failed' at sign-in, 2026-10-25).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import tomllib
from pathlib import Path

from ..common import data_root, utc_now
from . import claude_home, codex_home

CODEX_ACP = "toolchains/codex-acp-2.1.1/node_modules/.bin/codex-acp"
TOOL_NOTE = ("[factory tool note] You have no shell. Files: mcp__forge_fs__read_file, read_many_files, glob, grep, "
             "list_dir, write_file, edit_file; load your skill with mcp__forge_fs__use_skill (skill_name = your role). "
             "Factory MCP operations keep their names (e.g. mcp__forge_build_mcp__compile). Writes outside your role "
             "scope are refused by policy.")
SECRET = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+|sk-[A-Za-z0-9]{12,}|eyJ[\w-]{20,}")
# CAPA-045 (r143-r154: Codex added prose to most replies; r153 SWE.1 blocked on two replies with no JSON at all).
# Owner decision 2026-10-19: produce only what is expected. Appended LAST so it is the most recent instruction.
REPLY_NOTE = ("[factory reply rule] Your final message must be exactly the JSON object the task asks for: no text "
              "before or after it, no summary, no markdown fence. Any other text is a contract violation.")


def gate_servers(binding: Path, node: str, ws: Path) -> dict[str, dict]:
    """Codex config mcp_servers: one policy gate per server name (names match the prompts' mcp__<server>__<op>)."""
    run = tomllib.loads((ws / ".forge-run/workflow.toml").read_text())
    keys = sorted(((run.get("run") or {}).get("agent") or {}).get("mcps", {}))
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[2]),
           "FORGE_STATE_DIR": os.environ.get("FORGE_STATE_DIR", str(data_root() / "state")),
           "PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    def srv(server: str) -> dict:
        return {"command": sys.executable, "args": ["-m", "forge_factory.acp.gate", "--binding", str(binding),
                                                    "--node", node, "--server", server],
                "env": env, "default_tools_approval_mode": "approve"}
    return {"forge_fs": srv("forge_fs"), **{k: srv(k.replace("_", "-")) for k in keys}}


def acp_servers(servers: dict[str, dict]) -> list[dict]:
    """The same gate servers as ACP stdio McpServer entries (session/new mcpServers), for claude-agent-acp."""
    return [{"name": n, "command": s["command"], "args": s["args"],
             "env": [{"name": k, "value": v} for k, v in s["env"].items()]} for n, s in servers.items()]


def usage_record(result: dict, default_model: str) -> dict | None:
    """Token counts from a session/prompt result: ACP `usage` and/or the adapters' `_meta.quota` (feature 007).
    Counts and the model ID only - never prompt or response content. None when the agent reported nothing."""
    if not isinstance(result, dict):
        return None
    u = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    q = (result.get("_meta") or {}).get("quota") if isinstance(result.get("_meta"), dict) else None
    tc = (q or {}).get("token_count") or {}
    mu = (q or {}).get("model_usage") or []

    def pick(*vals):
        return next((int(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)), None)
    rec = {"input": pick(u.get("inputTokens"), tc.get("inputTokens")),
           "output": pick(u.get("outputTokens"), tc.get("outputTokens")),
           "cache_read": pick(u.get("cachedReadTokens"), tc.get("cachedInputTokens")),
           "cache_write": pick(u.get("cachedWriteTokens"), tc.get("cachedWriteTokens"))}
    if all(v is None for v in rec.values()):
        return None
    model = next((m.get("model") for m in mu if isinstance(m, dict) and m.get("model")), None) or default_model
    return {"event": "usage", "model": str(model)[:80], **rec}


def deny_outcome(params) -> dict:
    """CAPA-049 (LL r165): answering a permission request with outcome 'cancelled' means 'the prompt turn was
    cancelled' - Codex ended the turn and Fabro failed the whole run ('Pipeline cancelled'). A policy refusal selects
    the request's own reject option instead, so the agent sees a refusal and continues with the gate's MCP tools;
    'cancelled' is only the fallback when the request offers no reject option."""
    opts = [o for o in ((params or {}).get("options") or []) if isinstance(o, dict) and o.get("optionId")]
    rej = next((o for k in ("reject_once", "reject_always") for o in opts if o.get("kind") == k), None)
    return {"outcome": "selected", "optionId": rej["optionId"]} if rej else {"outcome": "cancelled"}


class Proxy:
    # class-level defaults: frozen CRE reproducers (RPR-049, RPR-053) build a bare Proxy without __init__
    kind = "codex"
    prompts: set | None = None
    def __init__(self, binding: Path, node: str, agent_argv: list[str] | None = None, fin=sys.stdin, fout=sys.stdout,
                 agent: str = "codex"):
        from ..policy.authz import Binding

        self.binding_path, self.node, self.kind = binding, node, agent
        self.prompts = set()  # ids of session/prompt requests whose results carry usage (feature 007)
        self.ws = Path(os.path.realpath(Binding.load(binding).workspace))
        self.fin, self.fout, self.lock = fin, fout, threading.Lock()
        if agent == "claude":
            self.servers = gate_servers(binding, node, self.ws)
            self.agent = subprocess.Popen(agent_argv or [str(data_root() / claude_home.ADAPTER)], stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                          env=claude_home.agent_env(dict(os.environ)), cwd=str(self.ws))
            return
        env = {**os.environ, "CODEX_HOME": str(codex_home.home()), "INITIAL_AGENT_MODE": "read-only", "NO_BROWSER": "1",
               "CODEX_PATH": str(data_root() / codex_home.CODEX),
               "CODEX_CONFIG": json.dumps({"features": {f: False for f in codex_home.DISABLED_FEATURES},
                                        "model_verbosity": codex_home.VERBOSITY,
                                           "mcp_servers": gate_servers(binding, node, self.ws)})}
        argv = agent_argv or [str(data_root() / CODEX_ACP)]
        self.agent = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      text=True, env=env, cwd=str(self.ws))

    def _log(self, rec: dict) -> None:
        try:
            d = self.ws / ".forge-run/acp"
            d.mkdir(parents=True, exist_ok=True)
            with (d / f"{self.node}.proxy.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": utc_now(), **rec}) + "\n")
        except OSError:
            pass

    def to_client(self, m: dict) -> None:
        with self.lock:
            self.fout.write(json.dumps(m) + "\n")
            self.fout.flush()

    def to_agent(self, m: dict) -> None:
        self.agent.stdin.write(json.dumps(m) + "\n")
        self.agent.stdin.flush()

    def from_client(self, m: dict) -> dict:
        meth, p = m.get("method"), m.get("params")
        if meth == "initialize" and isinstance(p, dict):
            p["clientCapabilities"] = {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}
        elif meth in ("session/new", "session/load") and isinstance(p, dict):
            dropped = [s.get("name") for s in p.get("mcpServers") or []]
            p["mcpServers"] = []  # the gate servers come from the Codex session config only
            if self.kind == "claude":  # ... or, for Claude, from here: gate servers only, no built-in tool/settings
                p["mcpServers"] = acp_servers(self.servers)
                p["_meta"] = {"claudeCode": {"options": claude_home.session_options(sorted(self.servers))},
                              "disableBuiltInTools": True}
            self._log({"event": "session", "method": meth, "client_mcp_servers_dropped": dropped})
        elif meth == "session/prompt" and isinstance(p, dict) and isinstance(p.get("prompt"), list):
            if "id" in m:
                if self.prompts is None:
                    self.prompts = set()
                self.prompts.add(m["id"])
            p["prompt"] = [{"type": "text", "text": TOOL_NOTE}] + p["prompt"] + [{"type": "text", "text": REPLY_NOTE}]
        return m

    def from_agent(self, m: dict) -> None:
        if "method" in m and "id" in m:  # a request the agent makes of the client: never forwarded
            meth = m["method"]
            if meth == "session/request_permission":
                tc = (m.get("params") or {}).get("toolCall") or {}
                self._log({"event": "denied_permission", "kind": tc.get("kind"), "title": str(tc.get("title"))[:120]})
                self.to_agent({"jsonrpc": "2.0", "id": m["id"], "result": {"outcome": deny_outcome(m.get("params"))}})
            else:
                self._log({"event": "denied_request", "method": meth})
                self.to_agent({"jsonrpc": "2.0", "id": m["id"],
                               "error": {"code": -32601, "message": f"refused by factory policy: {meth}"}})
            return
        if "id" in m and "result" in m and self.prompts and m["id"] in self.prompts:
            self.prompts.discard(m["id"])
            rec = usage_record(m["result"], claude_home.MODEL if self.kind == "claude" else codex_home.MODEL)
            if rec:
                self._log(rec)
        elif "id" in m and "error" in m and self.prompts and m["id"] in self.prompts:
            self.prompts.discard(m["id"])
            err = m["error"] if isinstance(m["error"], dict) else {"message": str(m["error"])}
            self._log({"event": "prompt_error", "code": err.get("code"),
                       "message": SECRET.sub("[REDACTED]", str(err.get("message", "")))[:160]})
        self.to_client(m)

    def run(self) -> int:
        def pump_agent() -> None:
            for line in self.agent.stdout:
                if line.strip():
                    try:
                        self.from_agent(json.loads(line))
                    except ValueError:
                        continue
        t = threading.Thread(target=pump_agent, daemon=True)
        t.start()
        for line in self.fin:
            if not line.strip():
                continue
            try:
                self.to_agent(self.from_client(json.loads(line)))
            except (ValueError, BrokenPipeError):
                break
        try:
            self.agent.stdin.close()
            self.agent.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self.agent.kill()
        t.join(timeout=5)
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.acp.proxy")
    ap.add_argument("--binding", type=Path, required=True)
    ap.add_argument("--node", required=True)
    ap.add_argument("--agent", choices=["codex", "claude"], default="codex")
    a = ap.parse_args(argv)
    home = claude_home if a.agent == "claude" else codex_home
    if not home.logged_in():
        print(json.dumps({"jsonrpc": "2.0", "method": "forge/error",
                          "params": {"message": f"{home.home()} not logged in"}}))
        return 2
    return Proxy(a.binding, a.node, agent=a.agent).run()


if __name__ == "__main__":
    sys.exit(main())
