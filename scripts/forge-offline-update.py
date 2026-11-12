#!/usr/bin/env python3
"""Portable operator entry point for an already provisioned offline Forge-C install.

Transfer a reviewed copy of this script with the patch and detached signature.
Run it with the machine's existing Forge-C Python environment. The trusted local
runtime performs all signature, CRE, release-identity, policy and test checks.
This script does not install dependencies or execute code from the patch bundle.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("apply", "rollback"))
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path,
                        help="trusted installed verifier; default: <install-root>/current")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--allowed-signers", type=Path)
    parser.add_argument("--preflight-cmd", help="explicit local check command; no shell expansion")
    args = parser.parse_args(argv)
    install = args.install_root.resolve()
    runtime = (args.runtime_root or install / "current").resolve()
    if args.action == "apply" and not all((args.bundle, args.allowed_signers, args.preflight_cmd)):
        parser.error("apply requires --bundle, --allowed-signers and --preflight-cmd")
    required = [runtime / "factory/python/forge_factory/offline/patch.py",
                runtime / "specs/014-durable-local-autonomy/contracts/patch-bundle.schema.json"]
    if not all(path.is_file() for path in required):
        print(json.dumps({"decision": "REFUSED", "code": "OFFLINE_RUNTIME_MISSING"}))
        return 1
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")}
    env.update(FORGE_REPO_ROOT=str(runtime), PYTHONPATH=str(runtime / "factory/python"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    command = [sys.executable, "-s", "-m", "forge_factory.offline.patch",
               "import" if args.action == "apply" else "rollback", "--install-root", str(install)]
    if args.action == "apply":
        command += [str(args.bundle.resolve()), "--allowed-signers", str(args.allowed_signers.resolve()),
                    "--preflight-cmd", args.preflight_cmd]
    result = subprocess.run(command, cwd=runtime, env=env, check=False)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
