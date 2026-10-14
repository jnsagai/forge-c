#!/usr/bin/env python3
"""Inventory open-source tools; do not mistake absent tools for passing gates."""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess

CORE = ('python3', 'cmake', 'ninja', 'clang', 'ctest', 'llvm-profdata', 'llvm-cov')
ENGINEERING = ('cppcheck', 'scan-build', 'cbmc', 'frama-c', 'arm-none-eabi-gcc', 'arm-none-eabi-size')
FACTORY = ('fabro', 'ollama')


def inspect(tool: str) -> dict[str, str | bool]:
    path = shutil.which(tool)
    if path is None:
        return {"installed": False, "version": "NOT_INSTALLED"}
    try:
        result = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=8, check=False)
        version = (result.stdout or result.stderr).splitlines()
        return {"installed": True, "version": version[0] if version else "VERSION_UNAVAILABLE"}
    except (OSError, subprocess.TimeoutExpired):
        return {"installed": True, "version": "VERSION_QUERY_FAILED"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--strict-demo', action='store_true')
    p.add_argument('--strict-factory', action='store_true')
    opts = p.parse_args()
    tools = {name: inspect(name) for name in (*CORE, *ENGINEERING, *FACTORY)}
    print(json.dumps({"tools": tools, "note": "Tool presence does not imply tool qualification."}, indent=2))
    required = CORE if opts.strict_demo else (*CORE, *ENGINEERING, *FACTORY) if opts.strict_factory else ()
    missing = [name for name in required if not tools[name]["installed"]]
    if missing:
        print('MISSING_REQUIRED=' + ','.join(missing))
    return int(bool(missing))


if __name__ == '__main__':
    raise SystemExit(main())
