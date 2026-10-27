#!/usr/bin/env python3
"""Read-only F016 preparation checks; never approve or submit a work order.

Run with forge-env.sh sourced and PYTHONPATH=factory/python.
  python scripts/onboarding_acceptance_checks.py manifests|inputs|packages
"""
import hashlib
import json
import sys
from pathlib import Path

from forge_factory.afo import cli
from forge_factory.benchmark.queue import load
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import intake_check, onboarding_dir
from forge_factory.onboarding import facts as F
from forge_factory.onboarding.leftovers import run

QUEUE = REPO_ROOT / "config/factory/benchmark/st-driver-onboarding-queue.yaml"


def manifests():
    items = load(QUEUE)["items"]
    assert [i["id"] for i in items] == [f"{p}-st-hal-ob" for p in ("gpio", "spi", "usart", "tim")]
    for item in items:
        path = REPO_ROOT / f"config/factory/benchmark/afo/{item['id']}.json"
        manifest = json.loads(path.read_text())
        assert manifest["example"] == item["example"]
        assert manifest["model_profile"] == "codex-claude"
        spec = json.loads((REPO_ROOT / item["example"] / "workorder.json").read_text())
        assert spec["delivery"]["onboarding"] is True
        assert not {"files", "dependencies", "configure"} & spec["delivery"].keys()
        peripheral = item["id"].split("-")[0].upper()
        allowed, code = cli.approve({"authorization_ref": "AUTH-AFO-PILOT-20261027",
                                     "request_id": f"BENCH-{peripheral}-ST-HAL-OB",
                                     "driver_class": f"STM32N6_{peripheral}_HAL_ST",
                                     "model_profile": "codex-claude"})
        assert allowed, code
        print(f"PASS {item['id']}: manifest, owner-only inputs, signed authorization {code}")


def inputs():
    count = 0
    for manifest in sorted((REPO_ROOT / "examples").glob("*/inputs/*manifest*.json")):
        for doc in json.loads(manifest.read_text()).get("documents", []):
            path = manifest.parent / doc["markdown"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == doc["markdown_sha256"], path
            count += 1
    assert count == 16, count
    print(f"PASS {count} converted input hashes match their tracked manifests")


def packages():
    for item in load(QUEUE)["items"]:
        key = Path(item["example"]).name
        package = F.read_package(onboarding_dir(key))
        assert package and package["status"] == "READY_FOR_OWNER", key
        assert F.canonical_hash(package) == package["sha256"], key
        assert all(f["status"] != "DERIVED" or f["sources"] for f in package["facts"]), key
        assert not run(key), key
        assert package["authored"] and all(a["gate"]["verdict"] == "PASS" for a in package["authored"]), key
        assert (onboarding_dir(key) / "onboarding/summary.md").is_file(), key
        # Until the owner signs, real-state intake must continue to refuse.
        manifest = {"example": item["example"]}
        refusal = intake_check(REPO_ROOT, manifest)
        assert refusal is None or refusal.startswith("APPROVAL_MISSING:"), refusal
        print(f"PASS {key}: {package['sha256']}, gaps={len(package['gaps'])}, intake={refusal or 'APPROVAL_OK'}")


if __name__ == "__main__":
    {"manifests": manifests, "inputs": inputs, "packages": packages}[sys.argv[1]]()
