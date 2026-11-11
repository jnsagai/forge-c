"""CAPA-225 / feature 014 DA-T036 (owner 2026-11-11 "go ahead with 1, 2 and 3"): typed missing-evidence disposition.

Every successful recovery-planner diagnosis on the owner lane (5 of 17 jobs) answered NEEDS_EVIDENCE and the order ended
BLOCKED "LOCAL_DIAGNOSIS_FAILED:MISSING_EVIDENCE:<job>": nothing said which evidence, nor whether the workspace even has
it. The disposition names the requested evidence kind and whether a phase-scoped source exists in the workspace
(IN_WORKSPACE) or not (ABSENT), deterministically, without another model call. No retry, budget, model or cloud bypass."""
from __future__ import annotations

import json
from pathlib import Path

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")
# evidence kind -> (first phase that can produce it, workspace globs); phase-scoped like the diagnosis packet
SOURCES = {
    "REQUIREMENT": ("SWE.1", ["workproducts/SWE.1/*"]),
    "DESIGN": ("SWE.2", ["workproducts/SWE.2/*", "workproducts/SWE.3/*"]),
    "IMPLEMENTATION": ("SWE.3", ["software/**/*.c", "software/**/*.h"]),
    "TEST_DIAGNOSTIC": ("SWE.4", ["evidence/*.log", "evidence/*.xml", "verification/*.log", "verification/*.xml"]),
    "INSPECTION": ("SWE.1", ["inspection/*/INS-*.json"]),
    "AUTHORITATIVE_INPUT": ("SWE.1", ["inputs/**/*"]),
    "PRIOR_STRATEGY": ("SWE.1", []),
}
KINDS = tuple(SOURCES)


def available(workspace: Path, phase: str, kind: str) -> bool:
    first, globs = SOURCES.get(kind, ("SWE.6", []))
    if phase not in PHASES or PHASES.index(first) > PHASES.index(phase):
        return False
    ws = Path(workspace)
    return any(p.is_file() and not p.is_symlink() for g in globs for p in ws.glob(g))


def disposition(workspace: Path, phase: str, kinds: list[str]) -> str:
    """'<KIND>:<IN_WORKSPACE|ABSENT>' for the first requested kind (a stable, short failure key)."""
    known = [k for k in kinds if k in SOURCES] or ["UNSPECIFIED"]
    kind = known[0]
    return f"{kind}:{'IN_WORKSPACE' if kind in SOURCES and available(workspace, phase, kind) else 'ABSENT'}"


def requested_kinds(store, job_id: str) -> list[str]:
    """The evidence kinds of the job's accepted NEEDS_EVIDENCE proposal (afo_semantic_proposals), in request order."""
    try:
        with store.tx() as c:
            rows = c.execute("SELECT record FROM afo_semantic_proposals WHERE job_id=?", (job_id,)).fetchall()
    except Exception:  # noqa: BLE001 - an unreadable proposal names no kind (UNSPECIFIED)
        return []
    out = []
    for (raw,) in rows:
        try:
            rec = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for item in (rec.get("missing_evidence") or (rec.get("proposal") or {}).get("missing_evidence") or []):
            k = str(item.get("evidence_kind") or "")
            if k and k not in out:
                out.append(k)
    return out
