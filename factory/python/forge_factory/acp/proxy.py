"""ACP proxy that Fabro starts for a Codex node (acp.command):

  python -m forge_factory.acp.proxy --binding <binding.json> --node <node_id>

Between Fabro (ACP client) and codex-acp (ACP agent):
  * initialize: the client's fs/terminal capabilities are removed (the agent cannot read/write through Fabro);
  * the agent's MCP servers are the policy gate servers only (forge_fs + every forge MCP server of the run), set in
    the Codex session config with default_tools_approval_mode="approve" (the gate decides; codex-acp 2.1.1 cannot
    relay Codex's MCP approval question); session/new|load mcpServers from the client are dropped;
  * session/request_permission and every other agent->client request: denied here, never forwarded;
  * session/prompt: a short tool note is prepended (file tools are the gate's mcp__forge_fs__* tools; no shell) and
    the reply rule appended (final message = the requested JSON only; CAPA-045).
Codex runs with the factory CODEX_HOME (acp.codex_home) and its shell/exec/browser/plugin/sub-agent features off.
Everything denied is logged to .forge-run/acp/<node>.proxy.jsonl (method and reason, no content).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import tomllib
from pathlib import Path

from ..common import data_root, utc_now
from . import codex_home

CODEX_ACP = "toolchains/codex-acp-2.1.1/node_modules/.bin/codex-acp"
TOOL_NOTE = ("[factory tool note] You have no shell. Files: mcp__forge_fs__read_file, read_many_files, glob, grep, "
             "list_dir, write_file, edit_file; load your skill with mcp__forge_fs__use_skill (skill_name = your role). "
             "Factory MCP operations keep their names (e.g. mcp__forge_build_mcp__compile). Writes outside your role "
             "scope are refused by policy.")
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


class Proxy:
    def __init__(self, binding: Path, node: str, agent_argv: list[str] | None = None, fin=sys.stdin, fout=sys.stdout):
        from ..policy.authz import Binding

        self.binding_path, self.node = binding, node
        self.ws = Path(os.path.realpath(Binding.load(binding).workspace))
        self.fin, self.fout, self.lock = fin, fout, threading.Lock()
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
            self._log({"event": "session", "method": meth, "client_mcp_servers_dropped": dropped})
        elif meth == "session/prompt" and isinstance(p, dict) and isinstance(p.get("prompt"), list):
            p["prompt"] = [{"type": "text", "text": TOOL_NOTE}] + p["prompt"] + [{"type": "text", "text": REPLY_NOTE}]
        return m

    def from_agent(self, m: dict) -> None:
        if "method" in m and "id" in m:  # a request the agent makes of the client: never forwarded
            meth = m["method"]
            if meth == "session/request_permission":
                tc = (m.get("params") or {}).get("toolCall") or {}
                self._log({"event": "denied_permission", "kind": tc.get("kind"), "title": str(tc.get("title"))[:120]})
                self.to_agent({"jsonrpc": "2.0", "id": m["id"], "result": {"outcome": {"outcome": "cancelled"}}})
            else:
                self._log({"event": "denied_request", "method": meth})
                self.to_agent({"jsonrpc": "2.0", "id": m["id"],
                               "error": {"code": -32601, "message": f"refused by factory policy: {meth}"}})
            return
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
    a = ap.parse_args(argv)
    if not codex_home.logged_in():
        print(json.dumps({"jsonrpc": "2.0", "method": "forge/error", "params": {"message": "CODEX_HOME not logged in"}}))
        return 2
    return Proxy(a.binding, a.node).run()


if __name__ == "__main__":
    sys.exit(main())
