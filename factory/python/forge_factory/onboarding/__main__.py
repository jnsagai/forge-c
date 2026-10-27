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


def _derive(a) -> int:
    from . import derive

    if len(a.args) not in (1, 2):
        print(json.dumps({"status": "USAGE", "usage": "derive <example> [key (default: the example name)]"}))
        return 2
    pkg = derive(*a.args)
    print(json.dumps({"status": pkg["status"], "sha256": pkg["sha256"], "facts": len(pkg["facts"]),
                      "gaps": [f"{g['id']}:{g['kind']}:{g['ref']}" for g in pkg["gaps"]]}))
    return 0 if pkg["status"] == "READY_FOR_OWNER" else 1


def _summary(a) -> int:
    from . import onboarding_dir
    from .approval import summary

    print(json.dumps({"summary": str(summary(onboarding_dir(a.args[0])))}))
    return 0


def _verify(a) -> int:
    from . import onboarding_dir
    from .approval import verify

    r = verify(onboarding_dir(a.args[0]))
    print(json.dumps({"code": r["code"], "reason": r["reason"]}))
    return 0 if r["code"] == "APPROVAL_OK" else 1


def _prompts(a) -> int:
    from .leftovers import run

    found = run(a.args[0])
    print(json.dumps({"leftovers": found, "status": "PASS" if not found else "FAIL"}))
    return 0 if not found else 1


HANDLERS: dict = {"derive": _derive, "summary": _summary, "verify": _verify, "prompts": _prompts}

if __name__ == "__main__":
    sys.exit(main())
