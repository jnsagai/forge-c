"""CLI for onboarding derivation, owner review, approval verification, prompts and model checks."""
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
    ap.add_argument("--hide-model", metavar="PREFIX", help="test-only held-out model, recorded in package")
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
    pkg = derive(*a.args, author_missing=not a.no_author, hide_model=a.hide_model)
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


def _check_model(a) -> int:
    from . import onboarding_dir
    from .approval import verify
    from .facts import read_package
    from .model_gate import check

    if len(a.args) != 1:
        return 2
    key = a.args[0]
    pkg = read_package(onboarding_dir(key))
    if pkg is None:
        print(json.dumps({"status": "MODEL_PACKAGE_MISSING", "key": key}))
        return 2
    decision = verify(onboarding_dir(key))
    confirmations = {i["id"]: i["value"] for i in (decision["approval"] or {}).get("assumption_confirmations", [])}
    confirmed = {i["symbol"]: confirmations[i["id"]] for i in pkg["assumptions"] if i["id"] in confirmations}
    report = check(key, confirmed=confirmed if decision["code"] == "APPROVAL_OK" else {}, pkg=pkg)
    print(json.dumps(report))
    return 0 if report["verdict"] == "PASS" else 1


HANDLERS: dict = {"derive": _derive, "summary": _summary, "verify": _verify, "prompts": _prompts, "check-model": _check_model}

if __name__ == "__main__":
    sys.exit(main())
