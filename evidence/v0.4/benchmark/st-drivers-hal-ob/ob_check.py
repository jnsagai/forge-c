"""Collect and check F016 acceptance evidence; never change a gate or package status.

  python .../ob_check.py collect --out <new record.json>
  python .../ob_check.py check <record.json> [--peripheral gpio]

Collection is also useful during a run and records incomplete outcomes honestly.
A check requires a terminal package for each selected driver. Frozen records are
created exclusively; collect refuses to overwrite one.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from forge_factory.benchmark.queue import load
from forge_factory.benchmark.record import afo_orders, work_order
from forge_factory.common import REPO_ROOT, state_dir, utc_now
from forge_factory.onboarding import facts, onboarding_dir
from forge_factory.onboarding.approval import ALLOWED_SIGNERS, signature_valid, verify

PERIPHERALS = ("gpio", "spi", "usart", "tim")
REQUEST = re.compile(r"BENCH-(GPIO|SPI|USART|TIM)-ST-HAL-OB(?:-R[0-9]+)?$")
DECISIONS = REPO_ROOT / "evidence/easa/owner-decisions/onboarding"


def read(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operational(order_id):
    """Read terminal reasons, attempt timing and recovery budgets; UNKNOWN tokens stay UNKNOWN."""
    db = state_dir() / "conductor/conductor.sqlite3"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT created_utc,admitted_utc,terminal_reason,authorization_id "
                                 "FROM afo_work_orders WHERE order_id=?", (order_id,)).fetchone()
        timing = {}
        for attempt in connection.execute("SELECT attempt_id,created_utc,finished_utc FROM afo_attempts WHERE order_id=?",
                                          (order_id,)):
            duration = ((datetime.fromisoformat(attempt["finished_utc"]) -
                         datetime.fromisoformat(attempt["created_utc"])).total_seconds()
                        if attempt["finished_utc"] else None)
            timing[attempt["attempt_id"]] = {"started_at": attempt["created_utc"], "finished_at": attempt["finished_utc"],
                                            "full_attempt_duration_s": duration}
        plans = []
        for plan in connection.execute("SELECT plan_id,attempt_id,strategy,source,status,reasons,budget_snapshot,decided_utc "
                                       "FROM afo_recovery_plans WHERE order_id=? ORDER BY decided_utc", (order_id,)):
            data = dict(plan)
            for key in ("reasons", "budget_snapshot"):
                data[key] = json.loads(data[key])
            plans.append(data)
    return {**dict(row), "attempt_timing": timing, "recovery_plans": plans,
            "usage_note": "Phase ACP counters are in each attempt. Recovery budget tokens remain native UNKNOWN; "
                          "not zero and not estimated from a budget ceiling."}


def collect():
    packages = {}
    queue = load(REPO_ROOT / "config/factory/benchmark/st-driver-onboarding-queue.yaml")
    for item in queue["items"]:
        peripheral = item["id"].split("-")[0]
        key = Path(item["example"]).name
        root = onboarding_dir(key)
        package = facts.read_package(root)
        decision = verify(root)
        packages[peripheral] = {
            "key": key, "sha256": package["sha256"], "canonical_hash_ok": facts.canonical_hash(package) == package["sha256"],
            "package_snapshot": package,
            "inputs": package["inputs"], "approval_code": decision["code"], "approval": decision["approval"],
            "approval_sha256": digest(root / "onboarding/approval.json")
            if (root / "onboarding/approval.json").is_file() else None,
            "signature_sha256": digest(root / "onboarding/approval.json.sig")
            if (root / "onboarding/approval.json.sig").is_file() else None,
            "prompt_origins": [{"section": section, "key": name, "from": entry["from"]}
                               for section, entries in package["texts"].items() for name, entry in entries.items()],
        }
    orders = []
    for order in afo_orders():
        match = REQUEST.fullmatch(order["request_id"])
        if match is None:
            continue
        entry = {**order, "peripheral": match[1].lower(), "attempts": [], "operational": operational(order["order_id"])}
        for attempt in order["attempts"]:
            ws = state_dir() / "workorders" / ("WO-AFO-" + attempt["attempt_id"].removeprefix("afo-")) / "workspace"
            manifest = read(ws / ".forge-run/manifest.json")
            package_path = ws / ".forge-run/package.json"
            baselines = []
            for path in sorted((ws / "configuration/baselines").glob("SWE.*/*.json")):
                baseline = read(path)
                baselines.append({"path": str(path), "sha256": digest(path),
                                  "onboarding_sha256": baseline.get("onboarding_sha256")})
            entry["attempts"].append({**attempt, **(work_order(ws) if ws.is_dir() else {}), "workspace": str(ws),
                                      "onboarding": manifest.get("onboarding"), "baselines": baselines,
                                      "package_record": read(package_path),
                                      "package_record_sha256": digest(package_path) if package_path.is_file() else None})
        orders.append(entry)
    return {"schema": "forge-c/st-hal-onboarding-acceptance/0.2", "recorded_at": utc_now(),
            "packages": packages, "orders": orders}


def check(record, selected=PERIPHERALS):
    assert record["schema"] in ("forge-c/st-hal-onboarding-acceptance/0.1", "forge-c/st-hal-onboarding-acceptance/0.2")
    complete_inputs = record["schema"].endswith("/0.2")
    for peripheral in selected:
        package = record["packages"][peripheral]
        assert package["canonical_hash_ok"] and package["approval_code"] == "APPROVAL_OK", peripheral
        assert package["approval"]["package_sha256"] == package["sha256"], peripheral
        if complete_inputs:
            snapshot = package["package_snapshot"]
            assert facts.canonical_hash(snapshot) == package["sha256"], f"{peripheral}: signed facts snapshot"
            assert snapshot["inputs"] == package["inputs"], f"{peripheral}: input metadata"
        signed = DECISIONS / package["approval"]["approval_id"] / "approval.json"
        assert digest(signed) == package["approval_sha256"], peripheral
        assert digest(Path(str(signed) + ".sig")) == package["signature_sha256"], peripheral
        assert read(signed) == package["approval"], peripheral
        assert signature_valid(signed, package["approval"]["decided_by"], ALLOWED_SIGNERS), peripheral
        origins = package["prompt_origins"]
        assert origins and all(p["from"].startswith(("template:", "owner:scope", "model:")) for p in origins), peripheral
        if complete_inputs:
            expected_origins = [{"section": section, "key": name, "from": entry["from"]}
                                for section, entries in snapshot["texts"].items() for name, entry in entries.items()]
            assert origins == expected_origins, f"{peripheral}: signed text origins"
        orders = [o for o in record["orders"] if o["peripheral"] == peripheral]
        assert orders, f"{peripheral}: NOT_RUN"
        order = orders[-1]
        assert order["state"] in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED"), f"{peripheral}: {order['state']}"
        assert order["attempts"], f"{peripheral}: no launched attempt"
        attempt = order["attempts"][-1]
        binding = attempt["onboarding"] or {}
        assert binding.get("sha256") == package["sha256"], f"{peripheral}: package binding"
        assert binding.get("approval_id") == package["approval"]["approval_id"], f"{peripheral}: approval binding"
        assert attempt.get("fabro_run_id") and attempt.get("factory_revision"), peripheral
        outcome = attempt["package_record"]
        assert outcome.get("package_status") in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED"), f"{peripheral}: no release package"
        marker = Path(attempt["workspace"]) / ".forge-run/package.json"
        assert digest(marker) == attempt["package_record_sha256"] and read(marker) == outcome, peripheral
        assert all(b["onboarding_sha256"] == package["sha256"] for b in attempt["baselines"]), peripheral
        if complete_inputs:
            workspace = Path(attempt["workspace"])
            manifest = read(workspace / ".forge-run/manifest.json")
            recorded = {i["path"]: i["sha256"] for i in attempt["inputs"] + attempt["delivered_code"]}
            for item in package["inputs"]:
                # Configured dependency headers differ from their raw input templates;
                # the delivery manifest binds those exact configured bytes below.
                if item["role"] != "delivered_dependency":
                    assert recorded.get(item["path"]) == item["sha256"], f"{peripheral}: input binding {item['path']}"
                    assert digest(workspace / item["path"]) == item["sha256"], f"{peripheral}: signed input bytes"
            for item in manifest.get("inputs", []) + manifest.get("delivered", []):
                assert digest(workspace / item["path"]) == item["sha256"], f"{peripheral}: input bytes {item['path']}"
            for baseline in attempt["baselines"]:
                assert digest(Path(baseline["path"])) == baseline["sha256"], f"{peripheral}: baseline bytes"
        archive = Path(outcome["archive"])
        assert archive.is_file() and digest(archive) == outcome["archive_sha256"], f"{peripheral}: archive hash"
        # These checks establish bindings, inputs, origin labels and actual terminal outcomes.
        # SC-005 still needs a cited cause review of every gap; do not infer it from READY/BLOCKED alone.
        print(peripheral, outcome["package_status"], "gaps", outcome.get("gap_count"), "archive", outcome["archive_sha256"])
    print("PASS terminal outcomes and approved package bindings; gap-cause/SC-005 review remains separate")
    if not complete_inputs:
        print("Historical schema 0.1: input metadata retained; full signed facts and live byte checks require schema 0.2")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("collect")
    capture.add_argument("--out", required=True, type=Path)
    verify_parser = sub.add_parser("check")
    verify_parser.add_argument("record", type=Path)
    verify_parser.add_argument("--peripheral", choices=PERIPHERALS)
    args = parser.parse_args()
    if args.command == "collect":
        record = collect()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            json.dump(record, stream, indent=2)
            stream.write("\n")
        print("Recorded", len(record["orders"]), "orders at", args.out)
    else:
        check(read(args.record), (args.peripheral,) if args.peripheral else PERIPHERALS)


if __name__ == "__main__":
    main()
