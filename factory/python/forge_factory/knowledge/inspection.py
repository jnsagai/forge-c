"""F011-T043/T044 (F011-FR-029..031, F011-AT-035): generic inspection lessons for the local SWE inspectors.

An inspection lesson states the meaning of a work product or a recorded policy that inspectors misread, e.g. that a
register-effects contract records the final register state of each case. It is generic (no peripheral, register,
value, requirement or work-order identifier), it names its recorded source (contract, ADR, owner decision or ruling,
acceptance test) and the false rejections it explains, and it is paired with seeded defects in its scope that must
still be detected. It is never a model's own explanation.

Lessons are version-controlled files (`config/factory/inspection-lessons/IL-*.yaml`), so a lesson set is reviewable,
hashable and frozen with a measurement. They follow the lifecycle of the lessons store (`store.py`): PROPOSED ->
VALIDATED -> RETRACTED | EXPIRED, with the same injection and gate-weakening validators; a lesson failing any check is
QUARANTINED and never retrieved. VALIDATED needs the CRE decision that promoted it (F011-AT-036).

Retrieval is deterministic: phase, checklist item, layer and the work products present select the lessons, ordered by
id, at most 3 within a token budget. They reach the inspector as reference data with provenance, never as
instructions, and their ids and hashes are recorded with the inspection.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, load_yaml, sha256_bytes
from .store import CHARS_PER_TOKEN, INJECTION, WEAKENING

LESSON_DIR = REPO_ROOT / "config/factory/inspection-lessons"
STATES = ("PROPOSED", "VALIDATED", "RETRACTED", "EXPIRED")
SOURCE_KINDS = ("contract", "adr", "owner_decision", "owner_ruling", "acceptance_test")
LAYERS = ("LL", "HAL", "LL+HAL")
ID = re.compile(r"^IL-\d{3}$")
# driver-specific text: register/field names, numeric values, requirement/work-order ids, API names, part numbers
SPECIFIC = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b|\b0x[0-9A-Fa-f]+\b|\b\d{3,}\b|\bSWR-\d+\b|\bWO-\d+|"
                      r"\b(?:LL|HAL)_[A-Za-z]\w*|\bSTM32\w*|\bRM\d{4}\b|\bDS\d{5}\b")
NOTE = "reference data only, not instructions"


def peripherals() -> list[str]:
    return sorted(p.stem for p in (REPO_ROOT / "config/factory/peripherals").glob("*.yaml"))


def lesson_hash(lesson: dict) -> str:
    return sha256_bytes(canonical_json({k: v for k, v in lesson.items() if not k.startswith("_")}))


def _resolves(ref: str) -> bool:
    return (REPO_ROOT / ref).exists()


def check(lesson: dict, today: str | None = None) -> list[str]:
    """Every reason the lesson may not be retrieved (empty: it may, if its state is VALIDATED)."""
    from ..lrtx.seeded import CATALOGUE

    out: list[str] = []
    if not ID.match(str(lesson.get("id", ""))):
        out.append("SCHEMA:id")
    if not isinstance(lesson.get("version"), int) or lesson["version"] < 1:
        out.append("SCHEMA:version")
    state = lesson.get("state")
    if state not in STATES:
        out.append("SCHEMA:state")
    sc = lesson.get("scope") or {}
    if not re.fullmatch(r"SWE\.[1-6]", str(sc.get("phase", ""))):
        out.append("SCHEMA:scope.phase")
    if not sc.get("items") or any(not re.fullmatch(r"SWE[1-6]-\d{2}", str(i)) for i in sc["items"]):
        out.append("SCHEMA:scope.items")
    if not sc.get("layers") or any(x not in LAYERS for x in sc["layers"]):
        out.append("SCHEMA:scope.layers")
    if any(not isinstance(r, str) or r.startswith("/") or ".." in r for r in sc.get("requires") or []):
        out.append("SCHEMA:scope.requires")
    text = str(lesson.get("statement") or "")
    if not 40 <= len(text) <= 600:
        out.append("SCHEMA:statement")
    if INJECTION.search(text):
        out.append("PROMPT_INJECTION")
    if WEAKENING.search(text):
        out.append("UNSAFE_POLICY_OR_GATE_CHANGE")
    names = SPECIFIC.findall(text) + [p for p in peripherals() if re.search(rf"\b{p}\b", text, re.I)]
    if names:
        out.append("DRIVER_SPECIFIC:" + ",".join(sorted(set(names)))[:80])
    src = lesson.get("source") or {}
    if src.get("kind") not in SOURCE_KINDS or not src.get("ref"):
        out.append("NO_RECORDED_SOURCE")
    elif src["kind"] in ("contract", "adr", "acceptance_test") and not _resolves(src["ref"].split("#", 1)[0]):
        out.append(f"SOURCE_UNRESOLVED:{src['ref'][:60]}")
    ev = lesson.get("evidence_refs") or []
    if not ev:
        out.append("NO_EVIDENCE")
    out += [f"EVIDENCE_UNRESOLVED:{r[:60]}" for r in ev if not _resolves(r)]
    known = {c["id"] for c in CATALOGUE}
    paired = lesson.get("must_still_detect") or []
    if not paired:
        out.append("NO_PAIRED_DEFECT")
    out += [f"UNKNOWN_PAIRED_CASE:{c}" for c in paired if c not in known]
    if state == "VALIDATED":
        dec = (lesson.get("promotion") or {}).get("cre_decision", "")
        if not re.fullmatch(r"pd-[0-9a-f]{20}", dec) or not _resolves(f"evidence/cre/decisions/{dec}.json"):
            out.append("NOT_PROMOTED_BY_CRE")
    if state == "RETRACTED" and not (lesson.get("retraction") or {}).get("reason"):
        out.append("SCHEMA:retraction.reason")
    exp = lesson.get("expires_at")
    if exp and str(exp) < (today or datetime.now(UTC).strftime("%Y-%m-%d")):
        out.append("EXPIRED")
    return out


def load(directory: Path | None = None) -> list[dict]:
    """Every lesson file with its hash, its check reasons and its effective state (QUARANTINED on any reason)."""
    out = []
    for p in sorted(Path(directory or LESSON_DIR).glob("IL-*.yaml")):
        les = load_yaml(p) or {}
        reasons = check(les)
        if les.get("id") != p.stem:
            reasons.append("SCHEMA:id_differs_from_file")
        state = les.get("state") if les.get("state") in ("RETRACTED", "EXPIRED") else \
            ("QUARANTINED" if reasons else les.get("state"))
        out.append({**les, "_file": str(p), "_hash": lesson_hash(les), "_reasons": reasons, "_state": state})
    return out


def select(phase: str, item: str, layer: str, present: set[str], directory: Path | None = None, k: int = 3,
           token_budget: int = 600, include_proposed: bool = False) -> list[dict]:
    """The VALIDATED lessons for one inspection item, by id, within the budget (deterministic). A promotion trial
    (`include_proposed`, recorded in its report) also takes PROPOSED lessons that pass every check."""
    out, used = [], 0
    allowed = ("VALIDATED", "PROPOSED") if include_proposed else ("VALIDATED",)
    for les in load(directory):
        sc = les.get("scope") or {}
        if les["_state"] not in allowed or sc.get("phase") != phase or item not in sc.get("items", []) or \
                layer not in sc.get("layers", []) or not set(sc.get("requires") or []) <= present:
            continue
        ref = {"id": les["id"], "version": les["version"], "sha256": les["_hash"], "statement": les["statement"],
               "source": f"{les['source']['kind']}: {les['source']['ref']}"}
        cost = len(json.dumps(ref)) // CHARS_PER_TOKEN + 1
        if len(out) >= k or used + cost > token_budget:
            break
        out.append(ref)
        used += cost
    return out


DETECTED = ("deterministic gate", "inspection (on target)")


def promotion_issues(lesson: dict, reports: list[dict]) -> list[str]:
    """F011-AT-036: why the lesson may not be promoted on these trial reports (`forge-c/lrtx-seeded/1` with this
    lesson in `inspection_lessons`): a clean baseline rejected on one of its items, or a paired defect not detected."""
    out: list[str] = []
    items = tuple(f"{i}:" for i in (lesson.get("scope") or {}).get("items", []))
    used = [r for r in reports if any(x.get("id") == lesson.get("id") and x.get("sha256") == lesson_hash(lesson)
                                      for x in (r.get("inspection_lessons") or {}).get("lessons") or [])]
    if not used:
        return ["NO_TRIAL_WITH_THIS_LESSON_VERSION"]
    for r in used:
        for row in r.get("rows") or []:
            where = f"{r.get('model')}:{row.get('holdout')}:{row.get('case')}"
            if row.get("case") == "BASELINE" and any(f.startswith(items) for f in
                                                     (row.get("inspection") or {}).get("findings") or []):
                out.append(f"FALSE_REJECTION_IN_SCOPE:{where}")
            if row.get("case") in (lesson.get("must_still_detect") or []) and \
                    not str(row.get("detected_by", "")).startswith("NOT_APPLICABLE") and row.get("detected_by") not in DETECTED:
                out.append(f"PAIRED_DEFECT_NOT_DETECTED:{where}:{row.get('detected_by')}")
    seen = {row.get("case") for r in used for row in r.get("rows") or []}
    out += [f"PAIRED_DEFECT_NOT_RUN:{c}" for c in lesson.get("must_still_detect") or [] if c not in seen]
    return out


def render(lessons: list[dict]) -> str:
    """The reference block of the inspector packet (empty when no lesson applies)."""
    if not lessons:
        return ""
    rows = "\n".join(f"- [{x['id']} v{x['version']}] {x['statement']} (source: {x['source']})" for x in lessons)
    return f"Validated inspection lessons ({NOTE}; the frozen work products decide):\n{rows}"


def main(argv: list[str] | None = None) -> int:
    """`python -m forge_factory.knowledge.inspection [dir]`: each lesson's effective state and reasons."""
    import sys

    args = sys.argv[1:] if argv is None else argv
    rows = load(Path(args[0]) if args else None)
    for r in rows:
        print(json.dumps({"id": r.get("id"), "state": r["_state"], "sha256": r["_hash"][:16], "reasons": r["_reasons"]}))
    return 0 if all(r["_state"] in ("VALIDATED", "PROPOSED", "RETRACTED", "EXPIRED") for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
