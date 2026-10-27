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
            "inputs": package["inputs"], "approval_code": decision["code"], "approval": decision["approval"],
            "approval_sha256": digest(root / "onboarding/approval.json"),
            "signature_sha256": digest(root / "onboarding/approval.json.sig"),
            "prompt_origins": [{"section": section, "key": name, "from": entry["from"]}
                               for section, entries in package["texts"].items() for name, entry in entries.items()],
        }
    orders = []
    for order in afo_orders():
        match = REQUEST.fullmatch(order["request_id"])
        if match is None:
            continue
        entry = {**order, "peripheral": match[1].lower(), "attempts": []}
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
    return {"schema": "forge-c/st-hal-onboarding-acceptance/0.1", "recorded_at": utc_now(),
            "packages": packages, "orders": orders}


def check(record, selected=PERIPHERALS):
    assert record["schema"] == "forge-c/st-hal-onboarding-acceptance/0.1"
    for peripheral in selected:
        package = record["packages"][peripheral]
        assert package["canonical_hash_ok"] and package["approval_code"] == "APPROVAL_OK", peripheral
        assert package["approval"]["package_sha256"] == package["sha256"], peripheral
        signed = DECISIONS / package["approval"]["approval_id"] / "approval.json"
        assert digest(signed) == package["approval_sha256"], peripheral
        assert digest(Path(str(signed) + ".sig")) == package["signature_sha256"], peripheral
        assert read(signed) == package["approval"], peripheral
        assert signature_valid(signed, package["approval"]["decided_by"], ALLOWED_SIGNERS), peripheral
        origins = package["prompt_origins"]
        assert origins and all(p["from"].startswith(("template:", "owner:scope", "model:")) for p in origins), peripheral
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
        archive = Path(outcome["archive"])
        assert archive.is_file() and digest(archive) == outcome["archive_sha256"], f"{peripheral}: archive hash"
        # These checks establish bindings, inputs, origin labels and actual terminal outcomes.
        # SC-005 still needs a cited cause review of every gap; do not infer it from READY/BLOCKED alone.
        print(peripheral, outcome["package_status"], "gaps", outcome.get("gap_count"), "archive", outcome["archive_sha256"])
    print("PASS terminal outcomes and approved package bindings; gap-cause/SC-005 review remains separate")


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
