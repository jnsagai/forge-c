"""Feature 021 FR-008 / US2: the carry manifest of a run.

Every artifact this run took over from an earlier run - an author requirement kept byte-identical (a whole carried
task or a requirement restored after a rework answer), a per-requirement inspection verdict, the governance answer -
is listed with its provenance and labelled CARRIED: a carried verdict is never presented as a direct verdict of this
run. Read from the records the carry already writes (`lrtx/swe1_carry.py`); written into the package staging area,
never changing the package status. SWE.1 functional today; the later phases add their units here (T012-T015)."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import canonical_json, pretty_json, sha256_bytes, utc_now

SCHEMA = "forge-c/carry-manifest/1"
STAGE_PATH = "carry/carry-manifest.json"


def _json(p: Path):
    try:
        return json.loads(p.read_text()) if p.is_file() else None
    except (OSError, ValueError):
        return None


def _swe1(ws: Path) -> list[dict]:
    from . import swe1_carry as C
    from . import swe1_functional as F
    from . import swe1_quality as Q
    from . import visit as V

    items = []
    try:
        tasks = [t["id"] for t in F.plan(ws)]
    except (ValueError, OSError, KeyError):
        return items
    for task in tasks:
        rec = _json(V._ckpt(ws, "SWE.1", task)) or {}
        reqs = ((rec.get("doc") or {}).get("requirements")) or []
        whole = rec.get("carried_from")
        restored = set((rec.get("carry_merge") or {}).get("restored") or [])
        prov = whole or (_json(C._keep_path(ws, task)) or {}).get("carried_from") or {}
        for r in reqs:
            if whole or r.get("key") in restored:
                items.append({"kind": "author_requirement", "phase": "SWE.1", "item": f"{task}|{r.get('key')}",
                              "content_sha256": sha256_bytes(canonical_json(r)), "label": "CARRIED",
                              "source_work_order": prov.get("source_work_order"), "provenance": prov})
    for v in Q._lines(ws, Q.VERDICTS):
        if v.get("carried_from"):
            prov = v["carried_from"]
            items.append({"kind": "iq_verdict", "phase": "SWE.1", "item": v.get("tk"), "content_sha256": v.get("sha"),
                          "label": "CARRIED", "verdict": "PASS" if v.get("passed") else "NOT_PASSED",
                          "source_work_order": prov.get("source_work_order"), "provenance": prov})
    from ..governance import package as GP

    g = _json(V._ckpt(ws, GP.VISIT, GP.TASK)) or {}
    if g.get("carried_from"):
        prov = g["carried_from"]
        items.append({"kind": "governance_answer", "phase": "SWE.1", "item": GP.TASK, "content_sha256": None,
                      "label": "CARRIED", "source_work_order": prov.get("source_work_order"), "provenance": prov})
    return items


def build(ws: Path) -> dict:
    ws = Path(ws)
    items = _swe1(ws)
    counts = {"total": len(items)}
    for i in items:
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    return {"schema": SCHEMA, "at": utc_now(), "items": items, "counts": counts,
            "rule": "owner 2026-11-13: inspected and validated artifacts are preserved between runs unless a dependency "
                    "changed; every carried item names its source run and record"}


def bundle_into(ws: Path, stage: Path, status: str) -> int:
    doc = build(ws)
    if not doc["items"]:
        return 0
    doc["package_status_at_bundle"] = status
    p = Path(stage) / STAGE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(pretty_json(doc))
    return doc["counts"]["total"]
