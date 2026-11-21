"""OS-owner standing operating authority. Never a budget refill or runtime-agent operation.

An append-only receipt references a private owner file, outside runtime write mounts.
Historical finite missions/grants remain intact. Actual dispatch still requires the live
guardian, current RUNNING Intent, source/policy bindings and finite job envelopes.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from ..common import sha256_file, utc_now
from .durable import Refused, canonical, digest, strict_json

KIND = "OWNER_STANDING_OPERATING_AUTHORITY"
LIFETIME = "UNTIL_OWNER_STOP"
DIRECTIVE = "remove any authorization expiration, it should run forever"


def end(limits):
    """Comparison-only upper bound; infinity is never persisted in JSON or job records."""
    value = limits.get("deadline")
    if value is None and limits.get("authorization_lifetime") == LIFETIME:
        return math.inf
    if type(value) not in (int, float) or not math.isfinite(value):
        raise Refused("MISSION_TIME_AUTHORITY_INVALID")
    return value


def control_limits(mission):
    """An owner receipt changes effective time, retaining the original control's finite envelope."""
    limits = dict(mission["limits"])
    if limits.get("authorization_lifetime") == LIFETIME:
        limits.pop("authorization_lifetime")
        limits["deadline"] = mission["standing_authority"]["previous_deadline"]
    return limits


def effective(c, base, current):
    from . import owner_supervised_development as D

    row = c.execute("SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=? AND kind=?",
                    ("owner-standing-" + digest(base["mission_id"]), KIND)).fetchone()
    if not row:
        return current
    receipt = strict_json(row[0].encode(), 65536)
    ref = receipt.get("owner_record_ref") or {}
    path = Path(ref.get("path", ""))
    expected = Path(receipt.get("intent_path", "")).parent / "owner-standing-authority"
    if (digest(receipt) != row[1] or not path.is_absolute() or path.parent != expected
            or path.name != str(ref.get("sha256")) + ".json"):
        raise Refused("OWNER_STANDING_AUTHORITY_CHANGED")
    D._private(expected.parent, directory=True)
    D._private(expected, directory=True)
    D._private(path)
    document = strict_json(path.read_bytes(), 65536)
    if (sha256_file(path) != ref.get("sha256") or digest(document) != ref["sha256"]
            or document != {k: v for k, v in receipt.items() if k != "owner_record_ref"}
            or document.get("schema") != "forge-c/owner-standing-authority/1"
            or document.get("directive_sha256") != digest(DIRECTIVE)
            or document.get("initial_record_sha256") != digest(base)
            or document.get("mission_id") != D.MISSION or base["mission_id"] != D.MISSION
            or base["authorization_ref"] != D.ALLOWANCE_REF
            or document.get("previous_deadline") != current["limits"]["deadline"]
            or document.get("authorization_lifetime") != LIFETIME
            or document.get("non_time_caps_changed") is not False
            or document.get("allowance_counters_reset") is not False):
        raise Refused("OWNER_STANDING_AUTHORITY_CHANGED")
    return {**current, "limits": {**current["limits"], "deadline": None, "authorization_lifetime": LIFETIME},
            "initial_limits": base["limits"], "initial_authorization_ref": base["authorization_ref"],
            "standing_authority": receipt}


def enable(store, *, directive, snapshot_sha256):
    """External OS-owner CLI only; not registered with any production MCP server."""
    from ..lrtx.provider_process import owner_view
    from . import owner_supervised_development as D
    from .mission_ledger import MissionLedger
    from .operations import Intent, control_context

    if (directive != DIRECTIVE or D.selected()
            or any(os.environ.get(k) for k in ("FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING"))
            or owner_view(os.getpid())["uid_map"] != [[0, 0, 4294967295]]):
        raise Refused("OWNER_STANDING_EXTERNAL_OPERATOR_REQUIRED")
    intent = Intent()
    D._private(intent.path.parent, directory=True)
    with intent.lock(), store.tx() as c:
        state = intent.read()
        context = control_context(intent.path, state)
        if (state["mode"] != "RUNNING" or any((state.get("control_context") or {}).get(k) != context[k]
                                               for k in ("user_namespace", "uid_map"))):
            raise Refused("OWNER_STANDING_RUNNING_HOST_INTENT_REQUIRED")
        snapshot = MissionLedger._snapshot(c, D.MISSION)
        if snapshot.get("standing_authority"):
            return snapshot["standing_authority"]
        if digest(snapshot) != snapshot_sha256:
            raise Refused("MISSION_SNAPSHOT_CHANGED")
        for row in c.execute("SELECT record FROM afo_execution_liveness"):
            execution = json.loads(row[0])
            if execution.get("mission_id") == D.MISSION and execution.get("resource_lease") != "RELEASED":
                raise Refused("MISSION_NATIVE_QUIESCENCE_REQUIRED")
        base = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (D.MISSION,)).fetchone()[0])
        if (base["authorization_ref"] != D.ALLOWANCE_REF or base["lineage"] != D.LINEAGE
                or any(snapshot["limits"].get(k) != v for k, v in D.CAPS.items())):
            raise Refused("OWNER_STANDING_MISSION_SCOPE_CHANGED")
        document = dict(schema="forge-c/owner-standing-authority/1", mission_id=D.MISSION,
                        initial_record_sha256=digest(base), snapshot_sha256=snapshot_sha256,
                        previous_deadline=snapshot["limits"]["deadline"], authorization_lifetime=LIFETIME,
                        directive_sha256=digest(DIRECTIVE), intent_path=str(intent.path),
                        control_context=context, issued_at=utc_now(), non_time_caps_changed=False,
                        allowance_counters_reset=False, native_effects=False)
        parent = intent.path.parent / "owner-standing-authority"
        parent.mkdir(mode=0o700, exist_ok=True)
        D._private(parent, directory=True)
        sha = digest(document)
        path = parent / (sha + ".json")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(document))
            stream.flush()
            os.fsync(stream.fileno())
        receipt = {**document, "owner_record_ref": dict(path=str(path), sha256=sha)}
        c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                  ("owner-standing-" + digest(D.MISSION), KIND, canonical(receipt).decode(), digest(receipt)))
        return receipt


def main(argv=None):
    import argparse

    from ..common import state_dir
    from .queue import Store

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--directive", required=True)
    ap.add_argument("--snapshot-sha256", required=True)
    args = ap.parse_args(argv)
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    print(json.dumps(enable(store, directive=args.directive, snapshot_sha256=args.snapshot_sha256), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
