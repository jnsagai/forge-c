"""Feature 015 (F015-T080): the benchmark queue as AFO work orders, so the factory's Conductor runs, recovers and
records them by itself (owner 2026-10-25: "the factory should be self-managed", "AFO ... solve it! I want it running
with codex and claude as inspector").

Each queue item has a pinned launch manifest (`config/factory/benchmark/afo/<id>.json`: example and model profile
codex-claude). `submit` builds the AFO intake envelope for every onboarded item, in queue order, and submits it through
the AFO intake (schema, manifest hash, the owner-signed authorization for `submit_workorder`); an item whose example
does not exist yet is skipped. Submitting twice is idempotent (same request id and manifest).

    python -m forge_factory.benchmark.afo_orders envelopes [--out DIR]   # write the envelopes only
    python -m forge_factory.benchmark.afo_orders submit                  # needs AFO PILOT (owner-signed)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, state_dir, utc_now
from .queue import QUEUE, load

TENANT = "forge-c-benchmark-015"
MANIFEST_DIR = "config/factory/benchmark/afo"


def driver_class(item_id: str, layer: str = "LL") -> str:
    """e.g. crc-st -> STM32N6_CRC_LL_ST, crc-st-hal (layer HAL) -> STM32N6_CRC_HAL_ST (the authorization scope lists
    these; F015-T065: ST's HAL items are their own driver classes)."""
    return f"STM32N6_{item_id.split('-')[0].upper()}_{'HAL' if layer == 'HAL' else 'LL'}_ST"


def envelopes(q: dict, approved_by: str, authorization_ref: str) -> list[dict]:
    rev = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = []
    for i in q["items"]:
        if not (REPO_ROOT / i["example"] / "workorder.json").is_file():
            continue
        ref = f"{MANIFEST_DIR}/{i['id']}.json"
        m = json.loads((REPO_ROOT / ref).read_text())
        out.append({"schema_version": "1.0", "request_id": f"BENCH-{i['id'].upper()}", "tenant_scope": TENANT,
                    "manifest_sha256": hashlib.sha256((REPO_ROOT / ref).read_bytes()).hexdigest(),
                    "input_manifest_ref": ref, "approved_by": approved_by, "authorization_ref": authorization_ref,
                    "driver_class": driver_class(i["id"], i.get("layer", "LL")), "target": "STM32N657X0 (RM0486 Rev 4)",
                    "safety_scope": "NOT_PROVIDED (offline review candidate only)", "model_profile": m["model_profile"],
                    "submitted_utc": utc_now(), "priority": "NORMAL", **({"git_revision": rev} if rev else {})})
    return out


def main(argv: list[str] | None = None) -> int:
    from ..afo.policy import load as afo_policy

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["envelopes", "submit"])
    ap.add_argument("--queue", type=Path, default=QUEUE)
    ap.add_argument("--approved-by", default="jnsagai")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    eff = afo_policy()
    envs = envelopes(load(a.queue), a.approved_by, eff.get("authorization_ref") or "")
    out = a.out or state_dir() / "benchmark" / "afo-envelopes"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for e in envs:
        p = out / f"{e['request_id']}.json"
        p.write_text(json.dumps(e, indent=1) + "\n")
        paths.append(p)
    if a.cmd == "envelopes":
        print(json.dumps([str(p) for p in paths], indent=1))
        return 0
    from ..afo import cli

    rc = 0
    for p in paths:
        rc = max(rc, cli.main(["submit", str(p)]))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
