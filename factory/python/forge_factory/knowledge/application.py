"""DA-FR-040: verified lesson APPLICATION, recorded separately from EXPOSURE ("a retrieved lesson does not prove it was
followed", continuous-learning.md).

Only a packet that carries lessons offers the author an optional `applied_lessons` answer field, restricted to the
offered lesson ids; packets without lessons keep their exact schema. The declaration is taken out of the answer before
any caller sees it (work products never change shape) and kept in the run's records. It becomes an APPLICATION transfer
only when the phase's deterministic author gate later freezes a baseline AND the lesson was really exposed to that
packet; the evidence names both. Benefit (DA-FR-042) remains a separate, measured claim.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..common import utc_now

DECLARED = ".forge-run/knowledge/declared.jsonl"
FIELD = "applied_lessons"


def augment(schema: dict, lesson_ids: list[str]) -> dict:
    """The output schema plus the optional declaration field; unchanged when it cannot take one."""
    if not lesson_ids or schema.get("type") != "object" or not isinstance(schema.get("properties"), dict) \
            or FIELD in schema["properties"]:
        return schema
    out = copy.deepcopy(schema)
    out["properties"][FIELD] = {"type": "array", "maxItems": len(lesson_ids), "uniqueItems": True,
                                "items": {"type": "string", "enum": sorted(lesson_ids)}}
    return out


def declare(ws: Path | None, p: dict, doc):
    """Remove the declaration from the answer; record the offered ids the author says it applied."""
    if not isinstance(doc, dict) or FIELD not in doc:
        return doc
    doc = dict(doc)
    said = doc.pop(FIELD)
    offered = set(p.get("lessons_offered") or [])
    ids = sorted({x for x in said if isinstance(x, str) and x in offered}) if isinstance(said, list) else []
    if ws is not None and ids:
        f = Path(ws) / DECLARED
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"packet_input_hash": p["input_hash"], "phase": p["phase"], "role": p["role"],
                                 "task": p["task"], "lesson_ids": ids, "at": utc_now()}, sort_keys=True) + "\n")
    return doc


def verify_on_freeze(ws: Path, phase: str, baseline: dict, store=None) -> list[str]:
    """APPLICATION transfers for this phase's declarations whose lesson was exposed to the declaring packet."""
    from ..knowledge import experience
    from ..knowledge.store import LessonStore

    f = Path(ws) / DECLARED
    if not f.is_file():
        return []
    m = Path(ws) / ".forge-run/manifest.json"
    run_id = (json.loads(m.read_text()) if m.is_file() else {}).get("work_order")
    store = store or LessonStore()
    with store._conn() as c:
        exposed = {(r["lesson_id"], (r.get("data") or {}).get("packet_input_hash"))
                   for r in (json.loads(x[0]) for x in
                             c.execute("SELECT record FROM lesson_transfers WHERE kind='EXPOSURE'"))
                   if r.get("run_id") == run_id}
    out = []
    for d in (json.loads(x) for x in f.read_text().splitlines() if x.strip()):
        if d.get("phase") != phase:
            continue
        for lid in d["lesson_ids"]:
            if (lid, d["packet_input_hash"]) not in exposed:
                continue  # a declaration about a lesson this packet never received is not evidence
            out.append(experience.transfer(
                store, lid, run_id, "APPLICATION",
                evidence_refs=[f"packet:{d['packet_input_hash']}",
                               f"baseline:{baseline['baseline_id']}:{baseline['baseline_hash']}"],
                data={"phase": phase, "role": d["role"], "task": d["task"], "declared_by": "author",
                      "verified_by": "author_gate_freeze"}))
    return out
