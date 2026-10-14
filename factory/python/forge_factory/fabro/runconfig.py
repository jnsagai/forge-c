"""Deterministic builder for Fabro run workspaces + run configs (T007/T009/T018).

A product run gets its own git workspace (Fabro discovers skills at the git root, ADR-0002) containing
only the role SKILLs and approved inputs. The run config wires: local model via gateway, the Forge
MCP servers for the roles used, and the blocking policy hook bound to the run binding.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..common import REPO_ROOT, state_dir
from ..policy.authz import Binding

GIT_ENV = {"GIT_AUTHOR_NAME": "forge-factory", "GIT_AUTHOR_EMAIL": "factory@forge-c.local",
           "GIT_COMMITTER_NAME": "forge-factory", "GIT_COMMITTER_EMAIL": "factory@forge-c.local"}


def _git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def create_workspace(ws: Path, inputs: dict[str, bytes | str] | None = None) -> str:
    """Create a fresh product workspace git repo; returns the initial commit SHA."""
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / ".fabro" / "skills", ws / ".fabro" / "skills")
    for rel, data in (inputs or {}).items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode() if isinstance(data, str) else data)
    (ws / ".gitignore").write_text(".forge-run/\n")
    _git(ws, "init", "-q", "-b", "main")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-q", "-m", "forge: approved input baseline")
    return _git(ws, "rev-parse", "HEAD")


def toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_run_toml(graph_file: str, goal: str, binding_path: Path, mcp_servers: dict[str, dict] | None = None,
                    model: str = "qwen3:8b") -> str:
    py = sys.executable
    pp = str(REPO_ROOT / "factory" / "python")
    lines = ["_version = 1", "[workflow]", f"graph = {toml_str(graph_file)}", "[run]", f"goal = {toml_str(goal)}",
             "[run.model]", f"name = {toml_str(model)}", 'provider = "ollama"']
    for name, spec in sorted((mcp_servers or {}).items()):
        key = name.replace("-", "_")
        lines += [f"[run.agent.mcps.{key}]", 'type = "stdio"',
                  "command = [" + ", ".join(toml_str(c) for c in [py, "-m", spec["module"]]) + "]",
                  f'startup_timeout = "{spec.get("startup_timeout", "20s")}"',
                  f'tool_timeout = "{spec.get("tool_timeout", "200s")}"',
                  f"[run.agent.mcps.{key}.env]", f"PYTHONPATH = {toml_str(pp)}"]
        for k, v in sorted(spec.get("env", {}).items()):
            lines.append(f"{k} = {toml_str(str(v))}")
    hook = f"PYTHONPATH={pp} FORGE_STATE_DIR={state_dir()} {py} -m forge_factory.policy.fabro_hook " \
           f"--binding {binding_path}"
    lines += ["[[run.hooks]]", 'id = "forge-policy-gate"', 'event = "pre_tool_use"', f"script = {toml_str(hook)}",
              "blocking = true", "sandbox = false", 'timeout = "20s"']
    return "\n".join(lines) + "\n"


def write_run(ws: Path, graph_text: str, goal: str, binding: Binding,
              mcp_servers: dict[str, dict] | None = None) -> Path:
    run_dir = ws / ".forge-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "workflow.fabro").write_text(graph_text, encoding="utf-8")
    bpath = run_dir / "binding.json"
    binding.dump(bpath)
    (run_dir / "workflow.toml").write_text(render_run_toml("workflow.fabro", goal, bpath, mcp_servers))
    return run_dir / "workflow.toml"


def fabro_env() -> dict[str, str]:
    return {**os.environ, "HOME": os.environ.get("FORGE_FABRO_HOME", str(Path.home())),
            "FABRO_NO_UPGRADE_CHECK": "1"}


def fabro_run(ws: Path, toml_path: Path, label: str, timeout: int = 1800) -> str:
    fab = os.environ.get("FORGE_FABRO_BIN", str(Path.home() / ".fabro/bin/fabro"))
    out = subprocess.run([fab, "run", str(toml_path), "--detach", "--auto-approve", "--environment", "local",
                          "--label", f"forge={label}"], cwd=ws, env=fabro_env(), capture_output=True, text=True,
                         timeout=120)
    run_id = (out.stdout.strip().splitlines() or [""])[-1]
    if not run_id or " " in run_id:
        raise RuntimeError(f"fabro run failed: {out.stderr.strip()[-300:]}")
    subprocess.run([fab, "wait", run_id], env=fabro_env(), capture_output=True, timeout=timeout)
    return run_id


def default_state_workspace(name: str) -> Path:
    return state_dir() / "workspaces" / name
