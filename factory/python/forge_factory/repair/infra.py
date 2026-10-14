"""Factory infrastructure repository (repair surface) + deterministic checks for it.

The infra repo lives under FORGE_DATA_ROOT/infra (factory-owned git repo, separate from product workspaces
and from the Forge-C source repo). It holds *runtime configuration* the services read. Repairs happen in
worktrees of this repo; promotion is an atomic fast-forward of `main` (rollback = reset to previous SHA).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from ..common import data_root

GIT_ENV = {"GIT_AUTHOR_NAME": "forge-factory", "GIT_AUTHOR_EMAIL": "factory@forge-c.local",
           "GIT_COMMITTER_NAME": "forge-factory", "GIT_COMMITTER_EMAIL": "factory@forge-c.local"}
# Paths a repair may change (allowlist) and paths it may never change (also chmod read-only in worktrees).
REPAIRABLE = ["runtime/**", "services/**"]
PROTECTED = ["policies/**", "safety/**", "evidence/**", "archives/**", "workproducts/**", "configuration/approved/**"]

DEFAULT_FILES = {
    "runtime/llm-gateway.json": {"bind": "127.0.0.1", "port": 11436, "upstream": "http://127.0.0.1:11435"},
    "runtime/dashboard.json": {"bind": "127.0.0.1", "port": 8765},
    "policies/supervisor-protected.json": {"note": "protected copy; repairs must never modify"},
    "safety/README.md": "Safety artefacts are out of automatic repair scope.\n",
}


def infra_root() -> Path:
    return Path(os.environ.get("FORGE_INFRA_REPO") or data_root() / "infra")


def git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo, check=check, capture_output=True,
                          text=True, env={**os.environ, **GIT_ENV}).stdout.strip()


def ensure_infra(root: Path | None = None) -> Path:
    root = root or infra_root()
    if (root / ".git").exists():
        return root
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in DEFAULT_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content, indent=2, sort_keys=True) + "\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "infra: initial runtime configuration")
    return root


def validate_runtime(tree: Path) -> list[str]:
    """Deterministic config contract checks (the regression gate for runtime config repairs)."""
    issues = []
    for name, ports in (("runtime/llm-gateway.json", {11436}), ("runtime/dashboard.json", {8765})):
        p = tree / name
        try:
            cfg = json.loads(p.read_text())
        except (OSError, ValueError) as exc:
            issues.append(f"CONFIG_INVALID:{name}:{type(exc).__name__}")
            continue
        if cfg.get("bind") not in ("127.0.0.1", "::1"):
            issues.append(f"NON_LOOPBACK_BIND:{name} (contract requires bind 127.0.0.1)")
        if cfg.get("port") not in ports:
            issues.append(f"UNEXPECTED_PORT:{name}:{cfg.get('port')} (contract requires port {sorted(ports)[0]})")
        up = cfg.get("upstream")
        if up is not None and not re.fullmatch(r"http://127\.0\.0\.1:1143[45]", str(up)):
            issues.append(f"UPSTREAM_INVALID:{name}:{up}")
    return issues
