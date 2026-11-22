#!/usr/bin/env python3
"""Evaluation runner for PROTOCOL.md (T072). Writes one EvaluationRun JSON per run.

    run_eval.py baseline        --work DIR --out FILE
    run_eval.py with-package    --project DIR --out FILE
    run_eval.py seeded          --work DIR --corpus FILE --key FILE --out FILE [--plain]
    run_eval.py report          --dir DIR

Uses the package's own gate code for every metric, so both arms are measured the same way. Model calls go through the
harness CLIs of the reference configuration (no API keys).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parents[2] / "packages" / "forge-c-hi"
SKILLS = PKG / ".apm" / "skills"
sys.path.insert(0, str(SKILLS / "hi-gates" / "scripts"))
sys.path.insert(0, str(SKILLS / "hi-conductor" / "scripts"))

from forge_hi import quality, trace  # noqa: E402
from forge_hi.io import read_json, sha256_file, write_json  # noqa: E402
from forge_hi.provenance import utc_now  # noqa: E402

EXAMPLE = PKG / "examples" / "safety-supervisor"
AUTHOR_CMD = ["claude", "-p", "--allowedTools", "Read"]
INSPECTOR_CMD = ["codex", "exec", "-s", "read-only", "--skip-git-repo-check"]


def last_json(text: str):
    """The last top-level JSON array or object in a reply."""
    dec, i, found = json.JSONDecoder(), 0, None
    while True:
        starts = [p for p in (text.find("{", i), text.find("[", i)) if p >= 0]
        if not starts:
            return found
        i = min(starts)
        try:
            found, i = dec.raw_decode(text, i)
        except ValueError:
            i += 1


def setup(work: Path) -> Path:
    if work.exists():
        raise SystemExit(f"{work} exists; use a new directory per run")
    work.mkdir(parents=True)
    shutil.copytree(EXAMPLE / "needs", work / "needs")
    subprocess.run([sys.executable, str(SKILLS / "hi-gates/scripts/hi.py"), "init", "--from",
                    str(EXAMPLE / "hi-project.example.json")], cwd=work, check=True, capture_output=True)
    return work


def inputs_hash(work: Path) -> dict:
    return {p.relative_to(work).as_posix(): sha256_file(p) for p in sorted((work / "needs").glob("*.md"))}


def metrics_for(work: Path) -> dict:
    project = read_json(work / ".hi" / "project.json")
    wp = read_json(work / "hi" / "sys-req" / "requirements.json")
    items = wp.get("items", [])
    q = quality.check_items(items, stage="sys-req")
    issues, _, graph = trace.check(work, project, "sys-req")
    needs = [n for n, v in graph["nodes"].items() if v["stage"] == "input" and v.get("kind") == "needs"]
    uncovered = {i["target_id"] for i in issues if i["code"] == "TR-UNCOVERED"}
    return {
        "items": len(items),
        "rule_violations": len(q),
        "rule_violations_per_100": round(100.0 * len(q) / max(1, len(items)), 1),
        "rule_violations_by_code": _count(i["code"] for i in q),
        "trace_coverage": round(100.0 * (len(needs) - len(uncovered & set(needs))) / max(1, len(needs)), 1),
        "trace_issues": _count(i["code"] for i in issues),
        "open_points": len(wp.get("open_points", [])),
    }


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def harness_versions() -> dict:
    out = {}
    for name, cmd in (("claude", ["claude", "--version"]), ("codex", ["codex", "--version"])):
        try:
            out[name] = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            out[name] = None
    return out


BASELINE_PROMPT = """Write the system requirements for the product described by these stakeholder needs and constraints.

Output only a JSON array. Each element: {{"id": "SYS-<AREA>-<NNN>", "text": "<requirement>", "sources": ["<need or constraint ids>"], "verification_method": "test|analysis|inspection|demonstration"}}.

--- needs/stakeholder-needs.md ---
{needs}
--- needs/constraints.md ---
{constraints}
"""


def baseline(work: Path, out: Path) -> None:
    work = setup(work)
    prompt = BASELINE_PROMPT.format(needs=(work / "needs/stakeholder-needs.md").read_text(),
                                    constraints=(work / "needs/constraints.md").read_text())
    t0 = time.monotonic()
    r = subprocess.run(AUTHOR_CMD, input=prompt, cwd=work, capture_output=True, text=True, timeout=3600)
    wall = round(time.monotonic() - t0, 1)
    raw = last_json(r.stdout)
    arr = raw if isinstance(raw, list) else (raw or {}).get("items", []) if isinstance(raw, dict) else []
    items = []
    for it in arr:
        if not isinstance(it, dict):
            continue
        items.append({"id": str(it.get("id", "")), "level": "system", "text": str(it.get("text", "")),
                      "sources": [{"kind": "upstream", "id": str(s)} for s in it.get("sources") or []],
                      "derived": False, "verification_method": it.get("verification_method") or None,
                      "status": "proposed"})
        if items[-1]["verification_method"] is None:
            del items[-1]["verification_method"]
    write_json(work / "hi/sys-req/requirements.json", {
        "schema": "forge-c-hi/requirement-set@1", "stage": "sys-req", "baseline_id": "baseline", "status": "draft",
        "provenance": {"role": "author", "skill": "none (plain prompt)", "skill_version": "-", "harness": "claude-code",
                       "model": None, "model_family": "claude", "input_hashes": inputs_hash(work),
                       "created_utc": utc_now(), "run_id": "baseline"},
        "items": items, "open_points": []})
    write_json(out, {"arm": "baseline", "author_model": "claude (Claude Code default)", "inspector_model": None,
                     "inputs_hash": inputs_hash(work), "metrics": dict(metrics_for(work), wall_time_s=wall,
                                                                       model_calls=1, tokens=None,
                                                                       harness_exit=r.returncode),
                     "harness_versions": harness_versions(), "artefacts": [f"repos/{Path(work).name}"], "created_utc": utc_now()})


def with_package(project: Path, out: Path) -> None:
    events = []
    for f in sorted((project / ".hi" / "runs").glob("*/events.jsonl")):
        events += [json.loads(l) for l in f.read_text().splitlines()]
    roles = [e for e in events if e.get("step") == "role" and e.get("stage") == "sys-req"]
    wall = round(sum(e.get("duration_s") or 0 for e in roles), 1)
    ends = [e for e in events if e.get("step") == "stage-end" and e.get("stage") == "sys-req"]
    write_json(out, {"arm": "with_package", "author_model": "claude (Claude Code default)",
                     "inspector_model": "gpt (Codex CLI default)", "inputs_hash": inputs_hash(project),
                     "metrics": dict(metrics_for(project), wall_time_s_in_models=wall, model_calls=len(roles),
                                     model_calls_by_role=_count(f"{e['role']}:{e['phase']}" for e in roles),
                                     stage_outcome=ends[-1].get("outcome") if ends else None,
                                     gate_verdicts=ends[-1].get("gates") if ends else None, tokens=None),
                     "harness_versions": harness_versions(), "artefacts": [f"repos/{Path(project).name}"], "created_utc": utc_now()})


PLAIN_REVIEW = """Review the system requirements in hi/sys-req/requirements.json against the stakeholder needs in needs/.
List every defect you find. Output only a JSON array of {{"target_id": "<requirement id or SET>", "problem": "<one sentence>"}}.
Do not modify any file."""


def score(found: list[dict], key: list[dict]) -> dict:
    by_target: dict[str, list[dict]] = {}
    for f in found:
        by_target.setdefault(str(f.get("target_id")), []).append(f)
    hit, hit_class, misses = 0, 0, []
    for d in key:
        cands = by_target.get(d["target_id"], [])
        if cands:
            hit += 1
            if any(c.get("checklist_item") == d["class"] for c in cands):
                hit_class += 1
        else:
            misses.append(d["id"])
    return {"seeded_total": len(key), "seeded_detected": hit, "seeded_detected_same_class": hit_class,
            "detection_rate": round(100.0 * hit / max(1, len(key)), 1), "missed": misses,
            "findings_total": len(found)}


def seeded(work: Path, corpus: Path, key_file: Path, out: Path, plain: bool) -> None:
    work = setup(work)
    shutil.copyfile(corpus, work / "hi/sys-req/requirements.json")
    key = read_json(key_file)["defects"]
    t0 = time.monotonic()
    found: list[dict] = []
    calls = 0
    if plain:
        r = subprocess.run(INSPECTOR_CMD, input=PLAIN_REVIEW, cwd=work, capture_output=True, text=True, timeout=3600)
        calls = 1
        arr = last_json(r.stdout)
        found = [f for f in (arr if isinstance(arr, list) else []) if isinstance(f, dict)]
    else:
        import conduct  # the package conductor, used for its inspector call and finding normalisation
        c = conduct.Conductor(work, timeout=3600)
        ids = c.item_ids("sys-req")
        found += c.inspect("sys-req", "item", 1, ids, [])
        found += c.inspect("sys-req", "set", 1, [], [])
        calls = 2
        q = quality.check_items(read_json(work / "hi/sys-req/requirements.json")["items"], stage="sys-req")
        project = read_json(work / ".hi/project.json")
        tr, _, _ = trace.check(work, project, "sys-req")
        gate_map = {"IQ-03": "IQ-03", "IQ-05": "IQ-05", "IQ-06": "IQ-06", "IQ-11": "IQ-11", "IQ-12": "IQ-12"}
        for i in q:
            found.append({"target_id": i.get("target_id"), "checklist_item": gate_map.get(i["code"][:5], i["code"][:5]),
                          "source": "gate"})
        for i in tr:
            cls = "SQ-01" if i["code"] == "TR-UNCOVERED" else "IQ-12"
            tgt = "SET" if i["code"] == "TR-UNCOVERED" else i.get("target_id")
            found.append({"target_id": tgt, "checklist_item": cls, "source": "gate", "need": i.get("target_id")})
    wall = round(time.monotonic() - t0, 1)
    write_json(out, {"arm": "seeded_baseline" if plain else "seeded",
                     "inspector_model": "gpt (Codex CLI default)", "author_model": None,
                     "inputs_hash": dict(inputs_hash(work), corpus=sha256_file(corpus)),
                     "metrics": dict(score(found, key), wall_time_s=wall, model_calls=calls, tokens=None),
                     "harness_versions": harness_versions(), "artefacts": [f"repos/{Path(work).name}"], "created_utc": utc_now()})


def report(d: Path) -> None:
    rows = [read_json(p) for p in sorted(d.glob("*.json"))]
    for r in rows:
        m = r["metrics"]
        print(f"{r['arm']:16} items={m.get('items', '-'):>4} viol/100={m.get('rule_violations_per_100', '-'):>6} "
              f"trace={m.get('trace_coverage', '-'):>6}% detect={m.get('detection_rate', '-')}% "
              f"calls={m.get('model_calls')} wall={m.get('wall_time_s', m.get('wall_time_s_in_models'))}s")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--work", required=True)
    b.add_argument("--out", required=True)
    w = sub.add_parser("with-package")
    w.add_argument("--project", required=True)
    w.add_argument("--out", required=True)
    s = sub.add_parser("seeded")
    s.add_argument("--work", required=True)
    s.add_argument("--corpus", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--plain", action="store_true")
    r = sub.add_parser("report")
    r.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd == "baseline":
        baseline(Path(a.work), Path(a.out))
    elif a.cmd == "with-package":
        with_package(Path(a.project), Path(a.out))
    elif a.cmd == "seeded":
        seeded(Path(a.work), Path(a.corpus), Path(a.key), Path(a.out), a.plain)
    else:
        report(Path(a.dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
