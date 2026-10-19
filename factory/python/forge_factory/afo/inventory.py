"""AFO-T001/T005 (AFO-FR-001/005) - frozen source/tool/host baseline for Feature 005.

Records what AFO builds on, as observed (never assumed): the git heads of this branch and of the 004 branch, the
versions and licences of the Python packages AFO uses, the host tools it calls (OpenSSH signing, SQLite, systemd,
Fabro, git, GNU Arm, Renode) and host facts relevant to 24/7 operation (systemd user manager, lingering, the data
root mount). Missing tools are recorded as MISSING, not fixed. Output: evidence/afo/baseline/inventory-<sha>.json.
"""
from __future__ import annotations

import importlib.metadata as md
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys

from ..common import REPO_ROOT, data_root, pretty_json, utc_now

PACKAGES = ("jsonschema", "PyYAML", "fastapi", "uvicorn", "pydantic", "pytest", "ruff")
TOOLS = {"ssh-keygen": ["ssh", "-V"], "git": ["git", "--version"], "systemctl": ["systemctl", "--version"],
         "loginctl": ["loginctl", "--version"], "arm-none-eabi-gcc": ["arm-none-eabi-gcc", "--version"],
         "clang": ["clang", "--version"], "podman": ["podman", "--version"]}


def _run(argv: list[str]) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        return ((r.stdout or r.stderr).strip().splitlines() or ["?"])[0][:120]
    except (OSError, subprocess.SubprocessError):
        return "MISSING"


def _git(*args: str) -> str:
    return _run(["git", "-C", str(REPO_ROOT), *args])


def inventory() -> dict:
    pkgs = {}
    for p in PACKAGES:
        try:
            meta = md.metadata(p)
            pkgs[p] = {"version": md.version(p), "license": (meta.get("License-Expression") or meta.get("License") or
                                                               next((c.split("::")[-1].strip() for c in meta.get_all(
                                                                   "Classifier") or [] if c.startswith("License")),
                                                                    "UNKNOWN"))[:60]}
        except md.PackageNotFoundError:
            pkgs[p] = {"version": "MISSING", "license": None}
    tools = {k: (_run(v) if shutil.which(v[0]) else "MISSING") for k, v in TOOLS.items()}
    fabro = os.environ.get("FORGE_FABRO_BIN") or shutil.which("fabro")
    tools["fabro"] = _run([fabro, "--version"]) if fabro else "MISSING"
    renode = data_root() / "toolchains/renode/renode_1.17.0-portable/renode"
    tools["renode"] = "renode_1.17.0-portable" if renode.is_file() else "MISSING"
    user = os.environ.get("USER", "")
    linger = _run(["loginctl", "show-user", user, "--property=Linger"]) if shutil.which("loginctl") else "MISSING"
    mount = _run(["findmnt", "-n", "-o", "SOURCE,FSTYPE,UUID", "--target", str(data_root())])
    return {"schema": "forge-c/afo-baseline-inventory/0.1", "recorded_at": utc_now(),
            "source": {"branch_head": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                       "feature_004_head": _git("rev-parse", "origin/feat/004-continuous-reliability-engineering"),
                       "dirty": bool(_git("status", "--porcelain") not in ("", "?"))},
            "python": {"version": sys.version.split()[0], "executable": sys.executable, "packages": pkgs},
            "sqlite": {"library": sqlite3.sqlite_version}, "tools": tools,
            "host": {"system": platform.platform(), "node": platform.node(), "user_linger": linger,
                     "data_root": str(data_root()), "data_root_mount": mount,
                     "systemd_user_manager": _run(["systemctl", "--user", "is-system-running"])},
            "note": "observed facts only; MISSING means not found on this host, not fixed by this record"}


def main(argv: list[str] | None = None) -> int:
    inv = inventory()
    out = REPO_ROOT / f"evidence/afo/baseline/inventory-{inv['source']['branch_head'][:7]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pretty_json(inv))
    print(out.relative_to(REPO_ROOT))
    missing = [k for k, v in {**inv["tools"], **{k: v["version"] for k, v in inv["python"]["packages"].items()}}.items()
               if v == "MISSING"]
    print(json.dumps({"missing": missing, "linger": inv["host"]["user_linger"], "mount": inv["host"]["data_root_mount"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
