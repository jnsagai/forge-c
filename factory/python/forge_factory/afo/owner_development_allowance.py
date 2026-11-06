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


def main(argv=None):
    from ..common import state_dir
    from .queue import Store

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--directive", required=True)
    a = ap.parse_args(argv)
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    print(json.dumps(open_allowance(store, directive=a.directive), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
