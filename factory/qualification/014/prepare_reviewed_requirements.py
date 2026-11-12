"""Prepare/import/freeze an owner-reviewed bundle with zero inference or authority changes.

Uses a NEW private state directory, normal intake/import/freeze and unchanged
inspection gates. Writes hashes/measurements only to --out. Does not inspect,
inject delivery, submit an order, amend a mission, sign or execute a model.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def prepare(example, state_root, work_order, model, purpose="ASPICE_ONLY"):
    from forge_factory import provided_requirements as P
    from forge_factory import workorder as W
    from forge_factory.afo.durable import digest
    from forge_factory.brownfield.inject import inject
    from forge_factory.common import REPO_ROOT, sha256_file
    from forge_factory.inspection import gate
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import review
    from forge_factory.policy.authz import Binding

    state_root.mkdir(mode=0o700)  # Never reuse an existing prepared workspace.
    for name in ("STATE", "EVENTS", "ARCHIVE"):
        os.environ["FORGE_" + name + "_DIR"] = str(state_root / name.lower())
    ws, man = W.prepare(example, work_order, purpose=purpose)
    Binding(work_order, str(ws), {"swe1_author": {"role": "swe1-author", "phase": "SWE.1"}}).dump(
        ws / ".forge-run/binding.json")
    document, _ = P.validate(ws)
    result = P.materialize(ws)
    if result["status"] != "PASS" or gate.step_author(Store(ws), "SWE.1", json.dumps(result)):
        raise RuntimeError("REVIEWED_IMPORT_OR_AUTHOR_FREEZE_FAILED")
    store = Store(ws)
    baseline, sources = review.evidence(ws, "SWE.1")
    items = [item for item in store.applicable(store.checklist("SWE.1"))["checks"]
             if item.get("required") and not item.get("deterministic_check")]
    packets = [review.item_packet(ws, "SWE.1", item, baseline, sources, model) for item in items]
    injection = inject(ws)
    if injection["status"] != "REFUSED" or any((ws / r["path"]).exists() for r in man["delivered"]):
        raise RuntimeError("DELIVERY_ENTERED_BEFORE_INSPECTION")
    return {
        "schema": "forge-c/reviewed-requirements-preparation/1",
        "source_revision": subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                                                   text=True).strip(),
        "work_order": work_order, "workspace": str(ws), "model_requests": 0,
        "requirements_payload_sha256": digest(P.payload(document)),
        "review": document["review"], "manifest_sha256": sha256_file(ws / ".forge-run/manifest.json"),
        "frozen_baseline_hash": baseline["baseline_hash"], "import_status": result["status"],
        "inspection_gate": store.gate("SWE.1")["decision"], "delivery": injection,
        "inspector_packets": [{"task": p["task"], "input_hash": p["input_hash"],
                               "accounting": p["accounting"]} for p in packets],
        "runtime_authorization": "NOT_CHECKED_OR_GRANTED", "role_admission": "NOT_RUN",
        "qwen_capability": "NOT_RUN", "product_acceptance": "NOT_RUN",
        "measurement_scope": "Prepared structured requests only; gateway reasoning transform/native tokenizer not run",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--model", default="local-rtx-v2-omniverse2-q38-aspice-mtp")
    parser.add_argument("--purpose", choices=("ASPICE_ONLY", "QM"), default="ASPICE_ONLY")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be a new file")
    result = prepare(args.example.resolve(), args.state_root.resolve(), args.work_order, args.model, args.purpose)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("source_revision", "model_requests", "import_status",
                                            "inspection_gate", "product_acceptance")}))


if __name__ == "__main__":
    main()
