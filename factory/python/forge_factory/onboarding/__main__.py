"""CLI of the onboarding stage (feature 016); subcommands not built yet exit 2 NOT_IMPLEMENTED."""
from __future__ import annotations

import argparse
import json
import sys

COMMANDS = ("derive", "summary", "verify", "prompts", "check-model")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m forge_factory.onboarding")
    ap.add_argument("cmd", choices=COMMANDS)
    ap.add_argument("args", nargs="*")
    ap.add_argument("--no-author", action="store_true", help="derive only; no onboarding Fabro run")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    handler = HANDLERS.get(a.cmd)
    if handler is None:
        print(json.dumps({"status": "NOT_IMPLEMENTED", "command": a.cmd}))
        return 2
    return handler(a)


HANDLERS: dict = {}

if __name__ == "__main__":
    sys.exit(main())
