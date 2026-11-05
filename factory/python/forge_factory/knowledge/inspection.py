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
instructions, and their ids and hashes are recorded with the inspection. The production structured inspector
(`lrtx/review.py`, every phase) and the semantic SWE.1 inspector use the same selection.

Every lesson has a purpose (owner 2026-11-02, cloud cross-inspection: production stays local, so findings the local
inspector missed become validated lessons). CLARIFICATION (IL-001..003) explains a work product or policy that
inspectors misread, so that false rejections fall; its paired seeded defects are a guard. DETECTION states what makes a
work product defective that the local inspector missed; its paired seeded defects are the target and it is promoted
only on a paired trial (`detection_promotion_issues`): the same holdouts, seeds and sampling with and without the
lesson, (a) each paired defect detected more often with it and no catalogue case detected less often, (b) no finding
in its scope on baselines certified clean for its class, (c) the frozen real misses it was written from now fail on its
item naming the same element, (d) no refuter cancels a finding in its scope; plus every check above and the CRE
decision that promotes it.
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
PURPOSES = ("DETECTION", "CLARIFICATION")
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
    purpose = lesson.get("purpose")
    if purpose not in PURPOSES:
        out.append("SCHEMA:purpose")
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
    pending = lesson.get("pending_evidence_refs") or []
    if any(not isinstance(r, str) or r.startswith("/") or ".." in r for r in pending):
        out.append("SCHEMA:pending_evidence_refs")
    if purpose == "DETECTION":
        out += _detection_schema(lesson.get("detection") or {})
    if state == "VALIDATED":
        dec = (lesson.get("promotion") or {}).get("cre_decision", "")
        if not re.fullmatch(r"pd-[0-9a-f]{20}", dec) or not _resolves(f"evidence/cre/decisions/{dec}.json"):
            out.append("NOT_PROMOTED_BY_CRE")
        out += [f"PENDING_EVIDENCE_UNRESOLVED:{r[:60]}" for r in pending if isinstance(r, str) and not _resolves(r)]
    if state == "RETRACTED" and not (lesson.get("retraction") or {}).get("reason"):
        out.append("SCHEMA:retraction.reason")
    exp = lesson.get("expires_at")
    if exp and str(exp) < (today or datetime.now(UTC).strftime("%Y-%m-%d")):
        out.append("EXPIRED")
    return out


HASH = re.compile(r"^[0-9a-f]{64}$")


def _detection_schema(det: dict) -> list[str]:
    """A DETECTION lesson names the frozen real misses it was written from (each must fail with it, criterion c) and
    the baselines certified clean for its class (no finding with it, criterion b), each bound by its baseline hash."""
    out = []
    misses = det.get("real_misses") or []
    if not misses:
        out.append("NO_REAL_MISS")
    for m in misses:
        if not (isinstance(m, dict) and m.get("work_order") and HASH.match(str(m.get("baseline_hash", "")))
                and re.fullmatch(r"SWE[1-6]-\d{2}", str(m.get("item", ""))) and str(m.get("element", "")).strip()):
            out.append("SCHEMA:detection.real_misses")
            break
    clean = det.get("certified_clean") or []
    if not clean:
        out.append("NO_CERTIFIED_CLEAN_BASELINE")
    for c in clean:
        if not (isinstance(c, dict) and c.get("holdout") and HASH.match(str(c.get("baseline_hash", "")))
                and c.get("certified_by")):
            out.append("SCHEMA:detection.certified_clean")
            break
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
        ref = {"id": les["id"], "version": les["version"], "sha256": les["_hash"], "purpose": les["purpose"],
               "statement": les["statement"], "source": f"{les['source']['kind']}: {les['source']['ref']}"}
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
    if lesson.get("purpose") == "DETECTION":  # a detection gain needs its control: detection_promotion_issues
        return ["DETECTION_LESSON_NEEDS_PAIRED_TRIAL"]
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


TRIAL_SCHEMA = "forge-c/inspection-lesson-trial/1"
REPLAY_SCHEMA = "forge-c/inspection-lesson-replay/1"
MIN_SAMPLES = 3  # paired samples (seeds) per arm; one sample cannot separate a gain from sampling variance
PAIRED_KEYS = ("model", "inspector", "catalogue", "catalogue_sha256", "inspector_options")
PAIRED_TRIAL_KEYS = ("sampling", "holdouts", "phase")


def _arm(report: dict) -> dict:
    return report.get("trial") or {}


def _lesson_set(report: dict) -> set[tuple]:
    return {(x.get("id"), x.get("sha256")) for x in (report.get("inspection_lessons") or {}).get("lessons") or []
            if x.get("state") in ("VALIDATED", "PROPOSED")}


def _rows(report: dict) -> list[dict]:
    return [r for r in report.get("rows") or [] if not str(r.get("detected_by", "")).startswith("NOT_APPLICABLE")]


def _cancelled(entries: list[str], items: tuple) -> list[str]:
    return [e for e in entries if str(e).startswith(items)]


def _names(text: str, element: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(element.strip())}(?![\w-])", text, re.I))


def detection_promotion_issues(lesson: dict, reports: list[dict], replays: list[dict]) -> list[str]:
    """Why a DETECTION lesson may not be promoted on this paired trial (empty: the CRE decision may promote it).

    `reports` are `forge-c/lrtx-seeded/1` summaries, each one sample of one arm: `trial` = {schema TRIAL_SCHEMA,
    lesson {id, sha256}, arm WITH|WITHOUT, seed, sampling, holdouts [{name, baseline_hash}], phase}. The two arms of a
    seed must be identical except for this lesson. `replays` are REPLAY_SCHEMA inspections, with the lesson, of the
    frozen baselines the lesson names as real misses. Every count is over the paired seeds only."""
    out = list(check(lesson))
    if lesson.get("purpose") != "DETECTION":
        return out + ["NOT_A_DETECTION_LESSON"]
    out += [f"PENDING_EVIDENCE_UNRESOLVED:{r[:60]}" for r in lesson.get("pending_evidence_refs") or []
            if isinstance(r, str) and not _resolves(r)]
    key = {"id": lesson.get("id"), "sha256": lesson_hash(lesson)}
    items = tuple(f"{i}:" for i in (lesson.get("scope") or {}).get("items", []))
    arms: dict[str, dict] = {"WITH": {}, "WITHOUT": {}}
    for r in reports:
        t = _arm(r)
        if t.get("schema") != TRIAL_SCHEMA or t.get("lesson") != key or t.get("arm") not in arms:
            continue
        if t.get("seed") in arms[t["arm"]]:
            out.append(f"DUPLICATE_SAMPLE:{t['arm']}:{t.get('seed')}")
        arms[t["arm"]][t.get("seed")] = r
    if not arms["WITH"] or not arms["WITHOUT"]:
        return out + ["NO_PAIRED_TRIAL_WITH_THIS_LESSON_VERSION"]
    seeds = sorted(set(arms["WITH"]) & set(arms["WITHOUT"]), key=str)
    out += [f"UNPAIRED_SAMPLE:{s}" for s in sorted(set(arms["WITH"]) ^ set(arms["WITHOUT"]), key=str)]
    if len(seeds) < MIN_SAMPLES:
        out.append(f"TOO_FEW_PAIRED_SAMPLES:{len(seeds)}<{MIN_SAMPLES}")
    det = {"WITH": {}, "WITHOUT": {}}
    applicable: dict[str, int] = {}
    for s in seeds:
        w, wo = arms["WITH"][s], arms["WITHOUT"][s]
        out += [f"NOT_PAIRED:{k}:{s}" for k in PAIRED_KEYS if w.get(k) != wo.get(k)]
        out += [f"NOT_PAIRED:trial.{k}:{s}" for k in PAIRED_TRIAL_KEYS if _arm(w).get(k) != _arm(wo).get(k)]
        ws_, wos = _lesson_set(w), _lesson_set(wo)
        if (key["id"], key["sha256"]) not in ws_ or any(i == key["id"] for i, _h in wos) or \
                ws_ - {(key["id"], key["sha256"])} != wos:
            out.append(f"NOT_PAIRED:lesson_set:{s}")
        if {(r.get("holdout"), r.get("case")) for r in _rows(w)} != {(r.get("holdout"), r.get("case")) for r in _rows(wo)}:
            out.append(f"NOT_PAIRED:cases:{s}")
        for arm, rep in (("WITH", w), ("WITHOUT", wo)):
            for row in _rows(rep):
                c = row.get("case")
                if c == "BASELINE":
                    continue
                det[arm][c] = det[arm].get(c, 0) + (row.get("detected_by") in DETECTED)
                if arm == "WITH":
                    applicable[c] = applicable.get(c, 0) + 1
    # (a) each paired defect is detected in a majority of its samples with the lesson and more often than without it;
    # no catalogue case is detected less often with the lesson
    for c in lesson.get("must_still_detect") or []:
        n, a, b = applicable.get(c, 0), det["WITH"].get(c, 0), det["WITHOUT"].get(c, 0)
        if not n:
            out.append(f"PAIRED_DEFECT_NOT_RUN:{c}")
        elif not (2 * a > n and a > b):
            out.append(f"PAIRED_DEFECT_DETECTION_NOT_RAISED:{c}:with {a}/{n}, without {b}/{n}")
    out += [f"CATALOGUE_CASE_LOST_DETECTION:{c}:with {det['WITH'].get(c, 0)}, without {b}"
            for c, b in sorted(det["WITHOUT"].items()) if det["WITH"].get(c, 0) < b]
    # (b) no finding in the lesson's scope on a baseline certified clean for its class
    det_cfg = lesson.get("detection") or {}
    for cert in det_cfg.get("certified_clean") or []:
        name, h = cert.get("holdout"), cert.get("baseline_hash")
        for s in seeds:
            w = arms["WITH"][s]
            if not any(x.get("name") == name and x.get("baseline_hash") == h for x in _arm(w).get("holdouts") or []):
                out.append(f"CERTIFIED_CLEAN_NOT_RUN:{name}:{s}")
                continue
            rows = [r for r in _rows(w) if r.get("holdout") == name and r.get("case") == "BASELINE"]
            if not rows or any(str(r.get("detected_by", "")).startswith("NO_INSPECTION") for r in rows):
                out.append(f"CERTIFIED_CLEAN_NOT_INSPECTED:{name}:{s}")
            elif any(_cancelled((r.get("inspection") or {}).get("findings") or [], items) for r in rows):
                out.append(f"FINDING_ON_CERTIFIED_CLEAN:{name}:{s}")
    # (c) real-miss replay: each frozen false-PASS baseline fails on the lesson's item with a finding naming the element
    mine = [r for r in replays if r.get("schema") == REPLAY_SCHEMA and r.get("lesson") == key]
    for m in det_cfg.get("real_misses") or []:
        got = {r.get("seed"): r for r in mine if r.get("baseline_hash") == m.get("baseline_hash")}
        if not got:
            out.append(f"REAL_MISS_NOT_REPLAYED:{m.get('work_order')}")
            continue
        out += [f"REAL_MISS_NOT_REPLAYED:{m.get('work_order')}:{s}" for s in seeds if s not in got]
        hits = 0
        for r in got.values():
            it = (r.get("items") or {}).get(m["item"]) or {}
            hits += it.get("verdict") == "FAIL" and any(_names(str(f), m["element"]) for f in it.get("findings") or [])
        if not 2 * hits > len(got):
            out.append(f"REAL_MISS_STILL_PASSES:{m.get('work_order')}:{m['item']}:{hits}/{len(got)}")
    # (d) no refuter cancels (contests, or makes the inspector withdraw) a finding in the lesson's scope
    for s in seeds:
        for row in _rows(arms["WITH"][s]):
            ins = row.get("inspection") or {}
            if _cancelled((ins.get("contested") or []) + (ins.get("withdrawn") or []), items):
                out.append(f"REFUTER_CANCELS_LESSON_FINDING:{s}:{row.get('holdout')}:{row.get('case')}")
    for r in mine:
        for i in (lesson.get("scope") or {}).get("items", []):
            it = (r.get("items") or {}).get(i) or {}
            if it.get("contested") or it.get("withdrawn"):
                out.append(f"REFUTER_CANCELS_LESSON_FINDING:{r.get('seed')}:{r.get('work_order')}:{i}")
    return list(dict.fromkeys(out))


def render(lessons: list[dict]) -> str:
    """The reference block of the inspector packet (empty when no lesson applies)."""
    if not lessons:
        return ""
    rows = "\n".join(f"- [{x['id']} v{x['version']}] ({x.get('purpose', 'CLARIFICATION').lower()}) {x['statement']} "
                     f"(source: {x['source']})" for x in lessons)
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
