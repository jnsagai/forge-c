"""Evidence-only routing into existing CAPA/CRE or external engineering lanes.

No synthetic defect, incident, repair or source-promotion authority is created by a
successful ordinary job. Existing CAPA links require actual reproducer provenance.
"""

from __future__ import annotations
import json
from ..afo.durable import digest, immutable_json
from ..common import state_dir


def route(store, *, capa_registry=None, minimum_executions=2, limit=32):
    if minimum_executions < 2 or not 1 <= limit <= 128:
        raise ValueError("bounded recurrence criteria required")
    with store._conn() as c:
        rows = c.execute("SELECT record FROM job_experience ORDER BY created_at DESC LIMIT 1024").fetchall()
    groups = {}
    for row in rows:
        record = json.loads(row[0])
        facts = record["facts"]
        cohort = record["cohort"]
        if cohort.get("evaluation_holdout"):
            continue
        pattern = facts.get("fingerprint") or facts.get("failed_items") or facts.get("successful_scope")
        if not pattern:
            continue
        key = digest([record["phase"], pattern, cohort])
        groups.setdefault(key, []).append(record)
    out = []
    capas = capa_registry.all() if capa_registry else []
    for key, records in sorted(groups.items()):
        if len({r["execution_id"] for r in records}) < minimum_executions:
            continue
        refs = sorted({r["experience_id"] for r in records})
        fingerprint = records[0]["facts"].get("fingerprint")
        capa = (
            next(
                (
                    c
                    for c in capas
                    if (c.get("fingerprint") == fingerprint or fingerprint in capa_registry.links(c["capa_id"], "fingerprint"))
                    and c.get("reproducer_id")
                ),
                None,
            )
            if fingerprint
            else None
        )
        lane = (
            "CAPA_REPAIR"
            if capa
            else "CRE_MEASURED_BASELINE_CHANGE"
            if records[0]["outcome"] in ("PASS", "SUCCEEDED", "READY_FOR_OFFLINE_REVIEW")
            else "PRODUCT_OR_EXTERNAL_ENGINEERING_REVIEW"
        )
        record = {
            "schema": "forge-c/learning-improvement-intent/1",
            "pattern_sha256": key,
            "lane": lane,
            "experience_refs": refs,
            "unique_executions": len({r["execution_id"] for r in records}),
            "capa_id": capa["capa_id"] if capa else None,
            "requires": "EXISTING_REPRODUCER_AND_CRE" if capa else "MEASURED_BASELINE_AND_INDEPENDENT_HOLDOUT",
            "authority": "PROPOSAL_ONLY_NO_DEPLOYMENT",
            "candidate_status": "NOT_CREATED",
        }
        path = state_dir() / "afo/learning-cases" / f"{key}-{digest(refs)[:12]}.json"
        immutable_json(path, record)
        if capa:
            for ref in refs:
                capa_registry.link(capa["capa_id"], "experience", ref)
        out.append({"path": str(path), "record": record})
        if len(out) >= limit:
            break
    return out
