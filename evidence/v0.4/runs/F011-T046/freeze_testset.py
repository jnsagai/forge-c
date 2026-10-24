"""F011-T046 (F011-FR-032, F011-AT-037): select and freeze the inspector test set before any local inspection.

    python3 freeze_testset.py select <workorders dir> <out.json>     # loop10: candidates, seeded draw, tree hashes
    python3 freeze_testset.py verify <workorders dir> <testset.json> # any host: every selected tree unchanged

Clean-baseline candidates are SWE.1 baselines of the Codex/Claude line that no local model has inspected:
- layer LL or HAL, Codex ACP author and Claude ACP inspector for SWE.1 (manifest acp_authors/acp_inspectors);
- the last SWE.1 inspect gate decision is PASS, and the inspection it names has verdict PASS, no findings, is not
  stale and judged the latest SWE.1 baseline;
- not one of the seven learning-set holdouts, and one per distinct requirements text (sha256), first by name.
Measured 2026-10-24: only 22 candidates qualify (fewer than the planned 20-case stratified draw needs per stratum),
so every candidate is selected; the seed and quota stay recorded and apply only when a stratum has more candidates than
its quota. Each selected workspace tree is hashed (every file
except build/ and .forge-run/lrtx/, which the harness never reads or clears); a changed tree voids a measurement.
Nothing here reads a local inspector result: none exists for these work orders.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

SEED = 20261024
QUOTA = {("RCC", "LL"): 10, ("RCC", "HAL"): 6, ("IWDG", "LL"): 4, ("IWDG", "HAL"): 7}
LEARNING = {"WO-0009A-STM32N6-IWDG-LL-rc1", "WO-0002A-STM32N6-RCC-LL-rc1", "WO-0002B-STM32N6-RCC-HAL-rc1",
            "WO-0008A-STM32N6-RCC-LL-rc1b", "WO-0008B-STM32N6-RCC-HAL-rc1", "WO-0008C-ST-RCC-LL-rc1",
            "WO-0009B-STM32N6-IWDG-HAL-rc4"}
REQ = "workproducts/SWE.1/software_requirements.md"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tree_hash(ws: Path) -> str:
    rows = []
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws).as_posix()
        if rel.startswith(("build/", ".forge-run/lrtx/")) or not p.is_file() or p.is_symlink():
            continue
        rows.append(f"{rel}\0{sha(p)}")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def candidate(ws: Path) -> dict | None:
    try:
        m = json.loads((ws / ".forge-run/manifest.json").read_text())
    except (OSError, ValueError):
        return None
    if m.get("layer") not in ("LL", "HAL") or "swe1_author" not in (m.get("acp_authors") or []) or \
            "swe1_inspector" not in (m.get("acp_inspectors") or []) or not (ws / REQ).is_file():
        return None
    log = ws / ".forge-run/gates/gate-log.jsonl"
    insp = [json.loads(x) for x in log.read_text().splitlines() if '"inspect"' in x] if log.is_file() else []
    insp = [d for d in insp if d.get("phase") == "SWE.1" and d.get("step") == "inspect"]
    if not insp or (insp[-1].get("gate") or {}).get("decision") != "PASS":
        return None
    ins_id = insp[-1]["gate"].get("reason", "")
    try:
        ins = json.loads((ws / f"inspection/SWE.1/{ins_id}.json").read_text())
    except (OSError, ValueError):
        return None
    bls = sorted((ws / "configuration/baselines/SWE.1").glob("BL-SWE.1-*.json"))
    if ins.get("verdict") != "PASS" or ins.get("findings") or ins.get("stale_reason") or not bls or \
            ins.get("baseline_id") != bls[-1].stem:
        return None
    wo = ws.parent.name
    return {"workorder": wo, "peripheral": "IWDG" if "IWDG" in wo else "RCC", "layer": m["layer"],
            "requirements_sha256": sha(ws / REQ), "inspection": ins_id, "baseline_id": ins["baseline_id"]}


def select(root: Path, out: Path) -> dict:
    cands, seen = [], set()
    learning_req = {sha(root / w / "workspace" / REQ) for w in LEARNING if (root / w / "workspace" / REQ).is_file()}
    for d in sorted(root.iterdir()):
        if d.name in LEARNING:
            continue
        c = candidate(d / "workspace")
        if c and c["requirements_sha256"] not in seen | learning_req:
            seen.add(c["requirements_sha256"])
            cands.append(c)
    rng = random.Random(SEED)
    chosen = []
    for (per, lay), n in QUOTA.items():
        pool = [c for c in cands if (c["peripheral"], c["layer"]) == (per, lay)]
        chosen += sorted(rng.sample(pool, min(n, len(pool))), key=lambda c: c["workorder"])
    for c in chosen:
        c["tree_sha256"] = tree_hash(root / c["workorder"] / "workspace")
    rec = {"schema": "forge-c/f011-t046-testset/1", "frozen_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "seed": SEED, "quota": {f"{a}-{b}": n for (a, b), n in QUOTA.items()},
           "candidates": {f"{a}-{b}": sum((c["peripheral"], c["layer"]) == (a, b) for c in cands) for (a, b) in QUOTA},
           "candidate_list": [{k: c[k] for k in ("workorder", "requirements_sha256")} for c in cands],
           "selected": chosen, "learning_set": sorted(LEARNING),
           "note": "clean = passed the deterministic SWE.1 gate and the Claude inspector; a disputed case goes to the "
                   "owner for a ruling, never to a local inspector's result"}
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def verify(root: Path, testset: Path) -> list[str]:
    rec = json.loads(testset.read_text())
    return [f"TREE_CHANGED:{c['workorder']}" for c in rec["selected"]
            if not (root / c["workorder"] / "workspace").is_dir() or
            tree_hash(root / c["workorder"] / "workspace") != c["tree_sha256"]]


if __name__ == "__main__":
    cmd, root, path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if cmd == "select":
        r = select(root, path)
        print(json.dumps({"candidates": r["candidates"], "selected": len(r["selected"])}))
    else:
        bad = verify(root, path)
        print(json.dumps({"status": "UNCHANGED" if not bad else "CHANGED", "issues": bad}))
        raise SystemExit(1 if bad else 0)
