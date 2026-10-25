"""AFO-T023 (AFO-FR-018/026) - operator CLI for the Conductor queue.

  python -m forge_factory.afo.cli submit <envelope.json>     # needs a signed owner authorization (submit_workorder)
  python -m forge_factory.afo.cli status | list [--state S]
  python -m forge_factory.afo.cli pause|drain|resume --reason "..."
  python -m forge_factory.afo.cli backup <dest.sqlite3>
  python -m forge_factory.afo.cli external-change <order_id> --revision <sha> --approval-ref <ref> --reason "..."
  python -m forge_factory.afo.cli maintainer-process|maintainer-publish <proposal_id>     # AFO M5 broker steps

Operator controls are authenticated by the OS: only the account that owns the Conductor state directory may run
them (agents run under policy-scoped MCP roles and never get this CLI), and every control is recorded with actor and
reason. Pause stops new admissions; drain lets in-flight work reach a safe point without admitting more; resume
re-enables admission (re-admission still passes the preflight).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from ..common import REPO_ROOT, state_dir
from . import authz
from .policy import load
from .queue import QueueError, Store


def approve(env: dict, eff=None) -> tuple[bool, str]:
    """Intake approval: the envelope's authorization_ref must be a valid signed owner authorization for this policy,
    allowing submit_workorder for this request, driver class and model."""
    eff = eff or load()
    if eff.mode not in ("PILOT", "ACTIVE"):
        return False, f"AFO_MODE_{eff.mode}"
    d = authz.find(
        eff.mode,
        eff.sha256 or "",
        ref=env["authorization_ref"],
        action="submit_workorder",
        request={"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]},
    )
    return d.allow, d.code


def operator_ok() -> bool:
    d = state_dir()
    return d.exists() and d.stat().st_uid == os.getuid()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.afo.cli")
    ap.add_argument(
        "cmd",
        choices=[
            "submit",
            "status",
            "list",
            "pause",
            "drain",
            "resume",
            "backup",
            "external-change",
            "maintainer-process",
            "maintainer-publish",
            "operator-token",
            "dead-letter-ack",
            "dead-letter-close",
            "shutdown",
            "mission-register",
        ],
    )
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--state")
    ap.add_argument("--reason", default="")
    ap.add_argument("--revision", default="")
    ap.add_argument("--approval-ref", default="")
    ap.add_argument("--capa")
    a = ap.parse_args(argv)
    store = Store()
    if a.cmd == "submit":
        eff = load()
        try:
            oid, created = store.submit(
                json.loads(Path(a.arg).read_text()),
                repo=REPO_ROOT,
                max_queued=int(eff.get("queue.max_queued_orders", 0)),
                approve=lambda env: approve(env, eff),
            )
        except QueueError as e:
            print(json.dumps({"rejected": e.code, "detail": e.detail}))
            return 2 if e.code == "CONFLICT" else 1
        print(json.dumps({"order_id": oid, "created": created}))
        return 0
    if a.cmd in ("status", "list"):
        orders = store.orders((a.state,) if a.state else None)
        from .continuous_metrics import status as continuous_status

        print(
            json.dumps(
                {
                    "mode": load().mode,
                    "control": store.control(),
                    "continuous": continuous_status(store) if a.cmd == "status" else None,
                    "orders": [{k: o[k] for k in ("order_id", "request_id", "state", "priority", "defer_count")} for o in orders]
                    if a.cmd == "list"
                    else {s: sum(o["state"] == s for o in orders) for s in sorted({o["state"] for o in orders})},
                    "pending_commands": len(store.commands("PENDING")),
                },
                indent=1,
            )
        )
        return 0
    if a.cmd == "backup":
        print(json.dumps(store.backup(Path(a.arg))))
        return 0
    if not operator_ok():
        print("refused: operator controls need the account that owns the Conductor state directory", file=sys.stderr)
        return 3
    if not a.reason.strip():
        print("refused: give --reason", file=sys.stderr)
        return 3
    actor = getpass.getuser()
    if a.cmd == "mission-register":
        from .mission_admin import register
        from .durable import Refused

        try:
            result = register(store, json.loads(Path(a.arg).read_text()), load())
        except Refused as exc:
            print(json.dumps({"refused": exc.code, "detail": exc.detail}))
            return 1
        print(json.dumps(result, indent=2))
        return 0
    if a.cmd == "external-change":  # AFO-T051: an externally approved and deployed factory change re-queues the order
        try:
            store.external_change_approved(a.arg, a.revision, a.approval_ref, actor)
        except QueueError as e:
            print(json.dumps({"refused": e.code, "detail": e.detail}))
            return 1
        print(json.dumps({"order_id": a.arg, "state": store.order(a.arg)["state"]}))
        return 0
    if a.cmd in ("maintainer-process", "maintainer-publish"):  # AFO M5: deterministic broker steps, never the agent
        from ..reliability.policy import load as cre_policy
        from ..reliability.store import CREStore
        from . import maintainer as M

        try:
            rec = (
                M.process(store, a.arg, CREStore(), cre_policy(), capa_id=a.capa)
                if a.cmd == "maintainer-process"
                else M.publish(store, a.arg, load())
            )
        except M.MaintainerDenied as e:
            print(json.dumps({"refused": e.code, "detail": e.detail}))
            return 1
        print(
            json.dumps(
                {
                    "proposal_id": a.arg,
                    "outcome": rec["outcome"],
                    "branch_ref": rec["branch_ref"],
                    "pr_url": rec["pr_url"],
                    "cre_promotion_id": rec["cre_promotion_id"],
                }
            )
        )
        return 0
    if a.cmd == "operator-token":  # AFO-T058: printed once; the dashboard POST controls accept only this bearer token
        from .dashboard_api import issue_operator_token

        print(
            json.dumps(
                {
                    "operator_token": issue_operator_token(),
                    "note": "store it like a password; rotate by re-running (the old token stops working)",
                }
            )
        )
        return 0
    if a.cmd in ("dead-letter-ack", "dead-letter-close"):  # AFO-T054: operator case state only; the record is immutable
        from . import deadletter

        try:
            deadletter.set_state(store, a.arg, "ACKNOWLEDGED" if a.cmd.endswith("ack") else "CLOSED", actor, a.reason)
        except QueueError as e:
            print(json.dumps({"refused": e.code, "detail": e.detail}))
            return 1
        print(json.dumps({"case_id": a.arg, "state": "ACKNOWLEDGED" if a.cmd.endswith("ack") else "CLOSED"}))
        return 0
    from .operations import configured, synchronize

    if a.cmd in ("pause", "drain", "resume", "shutdown") and configured():
        print(json.dumps({"operations": synchronize(store, a.cmd, actor, a.reason), "control": store.control()}))
        return 0
    if a.cmd == "shutdown":
        raise SystemExit("durable operations intent must be configured for shutdown")
    if a.cmd == "pause":
        store.set_control("paused", "1", actor, a.reason)
    elif a.cmd == "drain":
        store.set_control("draining", "1", actor, a.reason)
    else:
        store.set_control("paused", "0", actor, a.reason)
        store.set_control("draining", "0", actor, a.reason)
    print(json.dumps({"control": store.control()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
