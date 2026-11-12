"""Paired promotion trial of one DETECTION inspection lesson (knowledge/inspection.py, owner 2026-11-02).

    python -m forge_factory.knowledge.detection_trial --lesson IL-005 --holdout <READY ws> [--holdout ...] \
        --replay <frozen false-PASS ws> [--replay ...] --model <local inspector> --seed 1 --seed 2 --seed 3 \
        --out <dir> [--inspector structured|semantic] [--case S1-DOMAIN ...] [--plan-only]

For every seed the same holdouts, catalogue cases and sampling run twice through the unchanged seeded harness
(lrtx/seeded.py): WITHOUT = the repository's VALIDATED lessons, WITH = the same set plus the candidate lesson (its
PROPOSED retrieval is recorded in the report). The frozen baselines the lesson names as real misses are then
re-inspected with the lesson (one replay per seed). The reports, replays and `detection_promotion_issues` are written to
--out; exit 0 only when the issue list is empty. Inference runs on the local GPU through the normal gateway: this
module never chooses a model or a backend. A passing trial is evidence for a CRE decision, not a promotion.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from ..common import pretty_json, sha256_file
from . import inspection as IL


def lesson_dirs(lesson_id: str, root: Path, source: Path | None = None) -> tuple[dict, Path, Path]:
    """The candidate and the two lesson directories of the trial: control (VALIDATED only) and control + candidate."""
    rows = IL.load(source)
    cand = next((r for r in rows if r.get("id") == lesson_id), None)
    if cand is None:
        raise ValueError(f"LESSON_NOT_FOUND:{lesson_id}")
    if cand["_state"] != "PROPOSED" or cand.get("purpose") != "DETECTION":
        raise ValueError(f"NOT_A_PROPOSED_DETECTION_LESSON:{lesson_id}:{cand['_state']}:{cand.get('purpose')}:"
                         + ",".join(cand["_reasons"])[:120])
    control, treatment = root / "lessons-without", root / "lessons-with"
    for d in (control, treatment):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for r in rows:
        if r["_state"] == "VALIDATED":
            shutil.copy2(r["_file"], control / Path(r["_file"]).name)
            shutil.copy2(r["_file"], treatment / Path(r["_file"]).name)
    shutil.copy2(cand["_file"], treatment / Path(cand["_file"]).name)
    return cand, control, treatment


def _holdout_record(ws: Path, phase: str) -> dict:
    from ..inspection.engine import Store

    bl = Store(ws).latest_baseline(phase)
    return {"name": ws.parent.name, "baseline_hash": bl["baseline_hash"] if bl else None}


def _set_arm(arm: str, lessons_dir: Path, seed: int, inspector: str) -> None:
    from ..lrtx import review as R
    from ..lrtx import review_semantic as RS
    from ..lrtx import seeded

    R.LESSONS.update({"dir": lessons_dir, "include_proposed": arm == "WITH", "off": False})
    RS.LESSONS.update({"dir": lessons_dir, "include_proposed": arm == "WITH"})
    if inspector == "semantic":
        RS.INSPECTOR["seed"] = seed
    else:
        R.INSPECTOR["sampling"] = {"seed": seed}
    seeded.LESSON_SET["value"] = {"dir": str(lessons_dir), "trial": arm == "WITH",
                                  "lessons": [{"id": x.get("id"), "version": x.get("version"), "state": x["_state"],
                                               "sha256": x["_hash"]} for x in IL.load(lessons_dir)]}


def _reset() -> None:
    from ..lrtx import review as R
    from ..lrtx import review_semantic as RS
    from ..lrtx import seeded

    R.LESSONS.update({"dir": None, "include_proposed": False, "off": False})
    RS.LESSONS.update({"dir": None, "include_proposed": False})
    R.INSPECTOR["sampling"], RS.INSPECTOR["seed"] = None, None
    seeded.LESSON_SET["value"], seeded.OPTIONS["value"], seeded.TRIAL["value"] = None, None, None


def replay(ws: Path, cand: dict, model: str, seed: int, scratch: Path, inspector: str) -> dict:
    """One inspection, with the lesson, of a copy of a frozen false-PASS baseline (never the original workspace)."""
    from importlib import import_module

    review = import_module("forge_factory.lrtx." + {"structured": "review", "semantic": "review_semantic"}[inspector])
    phase = cand["scope"]["phase"]
    dst = scratch / f"replay-{ws.parent.name}-{seed}" / "workspace"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ws, dst, symlinks=True, ignore=shutil.ignore_patterns("build"))
    for p in (dst / ".forge-run/lrtx").glob("*"):
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    man = dst / ".forge-run/manifest.json"
    m = json.loads(man.read_text())
    m["evaluation_holdout"] = True
    man.write_text(json.dumps(m, sort_keys=True))
    earlier = {q.name for q in (dst / "inspection" / phase).glob("INS-*.json")}
    rep = review.visit(dst, phase, model)
    ins = sorted(q for q in (dst / "inspection" / phase).glob("INS-*.json") if q.name not in earlier)
    rec = json.loads(ins[-1].read_text()) if ins else {}
    lrec_p = dst / ".forge-run/lrtx" / phase / "inspection-record.json"
    lrec = json.loads(lrec_p.read_text()) if lrec_p.is_file() else {}
    items = {}
    for iid, it in sorted((rec.get("items") or {}).items()):
        items[iid] = {"verdict": it.get("verdict"), "findings": [str(x)[:400] for x in it.get("findings") or []],
                      "contested": list((lrec.get("contested_findings") or {}).get(iid) or []),
                      "withdrawn": list((lrec.get("withdrawn_in_repair") or {}).get(iid) or [])}
    return {"schema": IL.REPLAY_SCHEMA, "lesson": {"id": cand["id"], "sha256": cand["_hash"]}, "seed": seed,
            "work_order": m.get("work_order"), "baseline_hash": _holdout_record(ws, phase)["baseline_hash"],
            "reply": rep.get("status"), "items": items, "inspector": inspector, "model": model}


def run(lesson_id: str, holdouts: list[Path], replays: list[Path], model: str, seeds: list[int], out: Path,
        inspector: str = "structured", cases: list[str] | None = None, plan_only: bool = False,
        source: Path | None = None) -> dict:
    from ..lrtx import seeded

    out.mkdir(parents=True, exist_ok=True)
    cand, control, treatment = lesson_dirs(lesson_id, out, source)
    phase = cand["scope"]["phase"]
    holdouts, replays = [h.resolve() for h in holdouts], [r.resolve() for r in replays]
    hrec = [_holdout_record(h, phase) for h in holdouts]
    plan = {"schema": "forge-c/inspection-lesson-trial-plan/1", "lesson": {"id": cand["id"], "sha256": cand["_hash"]},
            "seeds": seeds, "holdouts": hrec, "replays": [_holdout_record(r, phase) for r in replays],
            "cases": cases, "model": model, "inspector": inspector, "catalogue": seeded.CATALOGUE_VERSION,
            "catalogue_sha256": seeded.catalogue_hash(), "lesson_file_sha256": sha256_file(Path(cand["_file"])),
            "arms": {"WITHOUT": str(control), "WITH": str(treatment)}}
    (out / "plan.json").write_text(pretty_json(plan))
    if plan_only:
        return {"plan": plan, "issues": None}
    if len(set(seeds)) < IL.MIN_SAMPLES:
        raise ValueError(f"TOO_FEW_SEEDS:{len(set(seeds))}<{IL.MIN_SAMPLES}")
    reports, reps = [], []
    try:
        with tempfile.TemporaryDirectory(prefix="il-trial-", dir=out) as td:
            for seed in seeds:
                for arm, d in (("WITHOUT", control), ("WITH", treatment)):
                    _set_arm(arm, d, seed, inspector)
                    seeded.OPTIONS["value"] = {"sampling": {"seed": seed}, "inspector": inspector}
                    seeded.TRIAL["value"] = {"schema": IL.TRIAL_SCHEMA, "lesson": plan["lesson"], "arm": arm,
                                             "seed": seed, "sampling": {"seed": seed}, "holdouts": hrec,
                                             "phase": phase}
                    path = out / f"seeded-{arm.lower()}-{seed}.json"
                    reports.append(seeded.run(holdouts, model, path, cases, inspector))
                _set_arm("WITH", treatment, seed, inspector)
                for r in replays:
                    doc = replay(r, cand, model, seed, Path(td), inspector)
                    (out / f"replay-{r.parent.name}-{seed}.json").write_text(pretty_json(doc))
                    reps.append(doc)
    finally:
        _reset()
    issues = IL.detection_promotion_issues(cand, reports, reps)
    result = {"schema": "forge-c/inspection-lesson-trial-result/1", "lesson": plan["lesson"], "issues": issues,
              "status": "PROMOTABLE_BY_CRE_DECISION" if not issues else "NOT_PROMOTABLE",
              "note": "Trial evidence for a CRE decision; it promotes nothing and qualifies nothing."}
    (out / "result.json").write_text(pretty_json(result))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lesson", required=True)
    ap.add_argument("--holdout", type=Path, action="append", required=True)
    ap.add_argument("--replay", type=Path, action="append", default=[])
    ap.add_argument("--model", required=True)
    ap.add_argument("--seed", type=int, action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--inspector", choices=("structured", "semantic"), default="structured")
    ap.add_argument("--case", action="append", default=None)
    ap.add_argument("--plan-only", action="store_true", help="write plan.json (lesson dirs, hashes) without inference")
    a = ap.parse_args(argv)
    res = run(a.lesson, a.holdout, a.replay, a.model, a.seed, a.out, a.inspector, a.case, a.plan_only)
    print(json.dumps({k: res[k] for k in ("status", "issues") if k in res} if not a.plan_only else {"plan": "written"}))
    return 0 if a.plan_only or not res["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
