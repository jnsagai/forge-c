"""External operator only: opens the finite owner-development allowance authorized on 2026-11-06.

It adds one separate mission row beside the exhausted original. It never amends, refills,
resets or relabels that mission, is not a production grant, and admits no work by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import owner_supervised_development as D
from .durable import Refused
from .mission_ledger import MissionLedger

DIRECTIVE = "propose something and go"
CLOSE_DIRECTIVE = "go with all"


def open_allowance(store, *, directive):
    if (
        directive != DIRECTIVE
        or D.selected()
        or any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING"))
    ):
        raise Refused("OWNER_DEVELOPMENT_EXTERNAL_OPERATOR_REQUIRED")
    if time.time() >= D.DEADLINE:
        raise Refused("OWNER_DEVELOPMENT_ALLOWANCE_EXPIRED")
    D.prior_conserved(store)
    limits = {**D.CAPS, "deadline": D.DEADLINE}
    return MissionLedger(store).register(
        D.MISSION,
        D.LINEAGE,
        limits,
        D.ALLOWANCE_REF,
        authorize=lambda ref, value: ref == D.ALLOWANCE_REF and value == limits,
    )


def close_for_source_fix(store, *, directive):
    """Close the spent first order so a corrected source can place the last one from the original seed.

    Its attempt, charge and recovery plan stay as recorded. Nothing is refunded or reopened.
    """
    if (
        directive != CLOSE_DIRECTIVE
        or D.selected()
        or any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING"))
    ):
        raise Refused("OWNER_DEVELOPMENT_EXTERNAL_OPERATOR_REQUIRED")
    D.prior_conserved(store)
    rows = [r for r in store.orders() if r["request_id"] == D.ORDERS[0]]
    if len(rows) != 1:
        raise Refused("OWNER_DEVELOPMENT_SPENT_ORDER_UNKNOWN")
    order = rows[0]
    if order["state"] == "BLOCKED" and order["terminal_reason"] == D.SOURCE_FIX_CLOSED:
        return order
    attempts = store.attempts(order["order_id"])
    if (
        order["state"] != "WAITING_RECOVERY"
        or len(attempts) != 1
        or attempts[0]["state"] != "FAILED"
        or not attempts[0]["record"].get("fabro_run_id")
        or MissionLedger(store).for_order(order["order_id"]) != D.MISSION
    ):
        raise Refused("OWNER_DEVELOPMENT_SPENT_ORDER_NOT_CLOSABLE")
    store.transition(
        order["order_id"], "BLOCKED", "closed for a source fix by the owner step", terminal_reason=D.SOURCE_FIX_CLOSED
    )
    return store.order(order["order_id"])


def main(argv=None):
    from ..common import state_dir
    from .queue import Store

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--directive", required=True)
    ap.add_argument("--close-spent-order", action="store_true")
    a = ap.parse_args(argv)
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    action = close_for_source_fix if a.close_spent_order else open_allowance
    print(json.dumps(action(store, directive=a.directive), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
