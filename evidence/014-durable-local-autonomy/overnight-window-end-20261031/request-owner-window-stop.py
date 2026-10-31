"""Prepared owner-window stop request. Existing guard performs fenced settlement.

No service signal, model call, grant renewal or inference-capacity release is
performed by this request. It is not a second watchdog/scheduler.
"""
from pathlib import Path
import argparse
import json
import os
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--request-stop", action="store_true")
p.add_argument("--owner-clock-utc")
args = p.parse_args()
if not args.request_stop:
    print(json.dumps({"status": "PREPARED_NOT_EXECUTED", "deadline_utc": "2026-10-31T07:57:59Z",
                      "expected_epoch": 6, "model_calls": 0}))
    raise SystemExit(0)
if not args.owner_clock_utc:
    raise ValueError("EXTERNAL_OWNER_CLOCK_OBSERVATION_REQUIRED")
E = Path("/mnt/data/forge-c/delivery-first-afo-014-20261030-v1")
os.environ.update(json.loads((E / "control/runtime-env-v6.json").read_text()))
sys.path.insert(0, str(E / "source/factory/python"))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import digest, immutable_json
from forge_factory.common import utc_now, sha256_file

scope = json.loads((E / "control/delivery-first-afo-authority-20261031-v4/scope.json").read_text())
assert scope["deadline_utc"] == "2026-10-31T07:57:59Z"
before = operations.Intent().read()
if before["mode"] == "STOPPED":
    print(json.dumps({"status": "ALREADY_STOPPED_NO_INTENT_CHANGE", "epoch": before["epoch"],
                      "effective_stop": before.get("effective_stop"), "model_calls": 0}))
    raise SystemExit(0)
if before["epoch"] != 6:
    print(json.dumps({"status": "FENCED_NEWER_OPERATOR_INTENT", "epoch": before["epoch"],
                      "mode": before["mode"], "signal_sent": False}))
    raise SystemExit(0)
rec = operations.synchronize(
    Store(), "shutdown", "jnsagai-delegated-10h-window",
    "Enforce original ten-hour owner window with external UTC margin; no renewal", expected_epoch=6)
out = {"at_remote": utc_now(), "owner_clock_utc": args.owner_clock_utc,
       "deadline_utc": scope["deadline_utc"], "previous_epoch": before["epoch"],
       "mode": rec["mode"], "epoch": rec["epoch"], "effective_stop": rec.get("effective_stop"),
       "settlement": "PENDING_EXISTING_GUARD_OR_RECONCILIATION; NO_QUIESCENCE_CLAIM",
       "model_calls": 0, "source_deployment": False, "grant_renewal": False,
       "production_instance_changed": False}
path = E / "control/qualification-observations" / ("owner-window-stop-" + digest(out) + ".json")
immutable_json(path, out)
print(json.dumps({**out, "path": str(path), "sha256": sha256_file(path)}))
