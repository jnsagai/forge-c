"""CAPA-123 (Fabro run WO-F014-CMP-SWE3-IWDGHAL-20261102-10, cloud comparison line, loop10, 2026-11-03): an inspection
that could not examine its evidence is INCOMPLETE - re-run, bounded - never a product finding for the author.

The native SWE.3 inspector's grep returned nothing and the role policy reserved its last calls (16/20). It recorded
INS-SWE.3-001 PASS, then, following the prompt rule "retain an explicit finding for evidence you could not examine",
INS-SWE.3-002 FAIL with SWE3-01 "interface section not examined (grep empty, budget reserved)" and SWE3-06 "... not
examined (call budget reserved)". check_inspection recorded both as major product findings and the author was sent to
rework. The next three inspector sessions failed on the account outage before any call; each time the inspect gate
re-used INS-SWE.3-002 as a new failed inspection, until "rework budget exhausted (5 failed cycles)".

Two rules, both deterministic:
* not examined: a FAIL item whose every finding states that the inspector did not examine its evidence (the
  NOT_EXAMINED marker the prompt asks for, or the incident's wording) is no product finding. With no other major
  finding the submission is recorded as an INCOMPLETE inspection (inspection/<phase>/incomplete/INC-*.json, newer than
  any earlier verdict of the baseline, so it also voids a PASS given without that evidence) and the gate re-inspects
  (REINSPECT, at most INCOMPLETE_LIMIT times per baseline, then BLOCKED INSPECTION_INCOMPLETE_REPEATEDLY). With real
  major findings the inspection is recorded FAIL as before, the unexamined items flagged and kept out of the author's
  findings. Never a PASS: the inspector's ability to fail a real defect is unchanged.
* not performed: an inspector visit that recorded nothing (session failed) does not re-use the baseline's earlier
  verdict as a new failed inspection: REINSPECT, at most NOT_PERFORMED_LIMIT times per baseline, then BLOCKED
  INSPECTION_NOT_PERFORMED_REPEATEDLY (a retryable inspection/infrastructure outcome).
Neither outcome is a rework cycle; the reinspect node sends the baseline straight back to the inspector."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import pretty_json, utc_now

MARK = "NOT_EXAMINED"
INCOMPLETE = "INSPECTION_INCOMPLETE"
NOT_PERFORMED = "INSPECTION_NOT_PERFORMED"
INCOMPLETE_LIMIT = 3
NOT_PERFORMED_LIMIT = 3

# The inspector's own limitation, not a property of the work product. Deliberately narrow: "not checked", "not
# verified", "cannot read" or "per-call budget" describe real code/design defects and stay product findings.
_NOT_EXAMINED = re.compile(
    r"\bNOT_EXAMINED\b"
    r"|\bnot\s+(?:(?:yet|been|fully|all)\s+)*(?:examined|inspected)\b"
    r"|\b(?:could\s*n[o']?t|could\s+not|was\s+unable\s+to|unable\s+to|did\s*n[o']?t|did\s+not)\s+(?:examine|inspect)\b"
    r"|\b(?:call|turn|tool[- ]call)\s+budget\s+(?:was\s+|is\s+)?reserved\b|\bbudget\s+reserved\b"
    r"|\b(?:remaining\s+)?(?:tool\s+)?calls?\s+(?:were\s+|are\s+)?reserved\b|\bout\s+of\s+(?:tool\s+)?calls\b"
    r"|\bINSPECTION_CALLS_RESERVED\b|\bunverified\s+by\s+(?:the\s+)?inspector\b",
    re.I)


def not_examined_text(text: str) -> bool:
    return bool(_NOT_EXAMINED.search(str(text)))


def unexamined(verdicts: dict[str, dict], deterministic: dict[str, dict]) -> dict[str, list[str]]:
    """Inspector-judged FAIL items whose findings all state unexamined evidence (deterministic items never)."""
    out = {}
    for item, v in (verdicts or {}).items():
        if item in deterministic or not isinstance(v, dict) or v.get("verdict") != "FAIL":
            continue
        fs = [str(f) for f in v.get("findings") or []]
        if fs and all(not_examined_text(f) for f in fs):
            out[item] = fs
    return out


def _dir(ws: Path, phase: str) -> Path:
    return Path(ws) / "inspection" / phase / "incomplete"


def records(ws: Path, phase: str) -> list[dict]:
    d = _dir(ws, phase)
    return [json.loads(p.read_text()) for p in sorted(d.glob("INC-*.json"))] if d.is_dir() else []


def record(ws: Path, phase: str, inspector_role: str, bl: dict, checklist: dict, items: dict[str, dict],
           unexamined_items: dict[str, list[str]]) -> dict:
    n = len(records(ws, phase)) + 1
    rec = {"schema": "forge-c/inspection-incomplete/1", "inspection_id": f"INC-{phase}-{n:03d}", "phase": phase,
           "inspector_role": inspector_role, "baseline_id": bl["baseline_id"], "baseline_hash": bl["baseline_hash"],
           "checklist_version": checklist["version"], "checklist_sha256": checklist["sha256"], "verdict": "INCOMPLETE",
           "not_examined": unexamined_items, "items": items, "recorded_at": utc_now(),
           "record_ref": f"inspection/{phase}/incomplete/INC-{phase}-{n:03d}.json",
           "meaning": "the inspector did not examine the evidence of these items: no product finding, no PASS; the "
                      "baseline is re-inspected"}
    _dir(ws, phase).mkdir(parents=True, exist_ok=True)
    with open(Path(ws) / rec["record_ref"], "x", encoding="utf-8") as f:
        f.write(pretty_json(rec))
    return rec


def gate_outcome(ws: Path, phase: str, bl: dict, last: dict | None, since: str) -> tuple[str, str] | None:
    """(decision, reason) when the newest inspection activity on the current baseline is an INCOMPLETE record."""
    mine = [r for r in records(ws, phase) if r.get("baseline_hash") == bl["baseline_hash"]
            and str(r.get("recorded_at") or "") >= since]
    if not mine:
        return None
    newest = mine[-1]
    if last is not None and last.get("baseline_hash") == bl["baseline_hash"] and \
            str(last.get("recorded_at") or "") > str(newest.get("recorded_at") or ""):
        return None  # a complete inspection followed the incomplete one
    items = ",".join(sorted(newest.get("not_examined") or {}))
    if len(mine) >= INCOMPLETE_LIMIT:
        return "BLOCKED", (f"{INCOMPLETE}_REPEATEDLY: {len(mine)} inspections of {bl['baseline_id']} did not examine "
                           f"the evidence of {items}; inspection outcome, not a product finding")
    return "REINSPECT", f"{INCOMPLETE}:{newest['inspection_id']}:{items}"


# ---- not performed: an inspector visit that recorded nothing ------------------------------------------------------
def _gate_rows(ws: Path, phase: str) -> list[dict]:
    log = Path(ws) / ".forge-run" / "gates" / "gate-log.jsonl"
    rows = [json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
    return [r for r in rows if r.get("phase") == phase]


def not_performed(store, phase: str, g: dict) -> dict:
    """The inspect gate's decision when the inspector visit just ended recorded no inspection while the baseline's
    earlier verdict would be re-used as a new failed inspection (REWORK/BLOCKED on that inspection's id)."""
    ins = store.inspections(phase)
    bl = store.latest_baseline(phase)
    if not ins or bl is None or g.get("decision") not in ("REWORK", "BLOCKED") or g.get("reason") != \
            ins[-1].get("inspection_id") or ins[-1].get("baseline_hash") != bl["baseline_hash"]:
        return g
    rows = _gate_rows(store.workspace, phase)
    if not rows:
        return g
    newest = max([str(ins[-1].get("recorded_at") or "")] + [str(r.get("recorded_at") or "")
                                                           for r in records(store.workspace, phase)])
    if newest > str(rows[-1].get("ts") or ""):
        return g  # this visit recorded an inspection
    since = store.budget_start()
    n = 1 + sum(1 for r in rows if r.get("step") == "inspect" and r.get("ts", "") >= since
                and str((r.get("gate") or {}).get("reason", "")).startswith(NOT_PERFORMED)
                and (r.get("gate") or {}).get("baseline_id") == bl["baseline_id"])
    base = {**g, "baseline_id": bl["baseline_id"], "reused_inspection": ins[-1]["inspection_id"]}
    if n >= NOT_PERFORMED_LIMIT:
        return {**base, "decision": "BLOCKED",
                "reason": f"{NOT_PERFORMED}_REPEATEDLY: {n} inspector visits recorded no inspection of "
                          f"{bl['baseline_id']} (sessions failed); retryable inspection outcome, not a product finding"}
    return {**base, "decision": "REINSPECT",
            "reason": f"{NOT_PERFORMED}: the inspector visit recorded no inspection of {bl['baseline_id']}; "
                      f"{ins[-1]['inspection_id']} is not re-used as a new failed inspection"}


def route_outcome(ws: Path, phase: str) -> dict | None:
    """The phase's latest gate record, when it is an inspect step that ended INCOMPLETE or NOT_PERFORMED."""
    rows = _gate_rows(ws, phase)
    g = (rows[-1].get("gate") or {}) if rows and rows[-1].get("step") == "inspect" else {}
    return g if str(g.get("reason", "")).startswith((INCOMPLETE, NOT_PERFORMED)) else None


def reinspect_requested(ws: Path, phase: str) -> bool:
    rows = _gate_rows(ws, phase)
    g = (rows[-1].get("gate") or {}) if rows and rows[-1].get("step") == "route" else {}
    return bool(rows and rows[-1].get("inspection_outcome")) and g.get("decision") == "REINSPECT"
