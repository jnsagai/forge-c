"""LRTX-T021 (LRTX-FR-019, spec acceptance 6): seeded semantic defects on independent frozen holdouts.

    python -m forge_factory.lrtx.seeded --holdout <READY workspace> --model qwen3-coder:30b --out <report.json>

The holdouts are complete work-order workspaces of the Codex/Claude line, for example the rc1 work orders. They are
independent of the local model and of this feature, and they are copied, never modified in place. For each case of
the frozen catalogue:
1. one defect of a named class is seeded into the phase's work products;
2. the phase is re-frozen through the UNCHANGED author gate (a gate rejection is a deterministic detection);
3. otherwise the structured local inspection judges the frozen baseline (an inspection FAIL whose findings name the
   seeded element is a semantic detection; a FAIL on other grounds is recorded as off-target).

The unmutated holdout runs through the same path, so a FAIL there is a false rejection. Deterministic detection,
semantic detection and false rejections are reported separately. The catalogue is versioned and hashed in the report
and is never adjusted to a model's results.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from ..common import pretty_json, sha256_bytes, utc_now

CATALOGUE_VERSION = "lrtx-seeded-1"


def _req_md(ws: Path) -> Path:
    return ws / "workproducts/SWE.1/software_requirements.md"


def omit_requirement(ws: Path) -> str:
    """Remove the first requirement that writes a field (statement, source and verification) and its effects."""
    md = _req_md(ws).read_text()
    eff = json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())
    target = next(e["swr"] for e in eff["effects"] if e.get("op") in ("write", "set", "clear"))
    md = re.sub(rf"^- \*\*{target}\*\*.*\n(?:  - .*\n)*", "", md, count=1, flags=re.M)
    _req_md(ws).write_text(md)
    eff["effects"] = [e for e in eff["effects"] if e["swr"] != target]
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(eff, indent=2))
    return target


def safety_scope_qm(ws: Path) -> str:
    (ws / "safety/software_safety_requirements.md").write_text(
        "# Software safety requirements\n\nQM development scope: no software safety requirements are allocated "
        "(work-order owner decision).\n")
    return "safety/software_safety_requirements.md"


def _header(ws: Path) -> Path:
    from ..layer import ll_header

    return ws / ll_header(ws)


def invert_behaviour(ws: Path) -> str:
    """The first key/flag write of the driver writes a different documented key (start <-> refresh) or the first set
    becomes a clear: the code still compiles and every trace tag stays in place."""
    h = _header(ws)
    t = h.read_text()
    for a, b in (("0x0000CCCCU", "0x0000AAAAU"), ("0xCCCCU", "0xAAAAU"), ("|=", "&= ~")):
        if a in t:
            h.write_text(t.replace(a, b, 1))
            fn = re.findall(r"\b(LL_\w+)\s*\(", t[:t.index(a)])
            return fn[-1] if fn else a
    raise ValueError("NO_MUTATION_SITE:invert_behaviour")


def comment_out_write(ws: Path) -> str:
    """The first register-array assignment of a function body is commented out (the function becomes a no-op)."""
    from ..layer import register_block

    h = _header(ws)
    t = h.read_text()
    m = re.search(rf"^(\s+)({re.escape(register_block(ws))}\[[^\]]+\]\s*=[^;]+;)", t, re.M)
    if not m:
        raise ValueError("NO_MUTATION_SITE:comment_out_write")
    h.write_text(t[:m.start()] + f"{m.group(1)}/* {m.group(2)} */" + t[m.end():])
    fn = re.findall(r"\b(LL_\w+)\s*\(", t[:m.start()])
    return fn[-1] if fn else m.group(2)


def vacuous_test(ws: Path) -> str:
    """The first unit-test CHECK condition becomes always true (the id, trace tags and test still exist)."""
    from ..workflow.scaffold import unit_test

    p = ws / unit_test(ws)
    t = p.read_text()
    m = re.search(r'CHECK\("(UT-\d+)",\s*(.+?)\);', t, re.S)
    if not m:
        raise ValueError("NO_MUTATION_SITE:vacuous_test")
    p.write_text(t[:m.start()] + f'CHECK("{m.group(1)}", 1U == 1U);' + t[m.end():])
    return m.group(1)


CATALOGUE = [
    {"id": "S1-OMIT", "phase": "SWE.1", "class": "omitted requirement", "apply": omit_requirement},
    {"id": "S1-QM", "phase": "SWE.1", "class": "safety-scope contradiction", "apply": safety_scope_qm},
    {"id": "S3-INVERT", "phase": "SWE.3", "class": "inverted behaviour", "apply": invert_behaviour},
    {"id": "S3-COMMENT", "phase": "SWE.3", "class": "commented-out code", "apply": comment_out_write},
    {"id": "S4-VACUOUS", "phase": "SWE.4", "class": "wrong test property", "apply": vacuous_test},
]


def catalogue_hash() -> str:
    import inspect

    return sha256_bytes("\n".join(f"{c['id']}|{c['phase']}|{c['class']}|{inspect.getsource(c['apply'])}"
                                  for c in CATALOGUE).encode())


def _refreeze(ws: Path, phase: str) -> dict:
    """Freeze the phase through the unchanged author gate; record its decision (rejection = deterministic catch)."""
    from ..inspection import gate
    from . import tools as T

    if phase == "SWE.4":  # the SWE.4 presence gate needs a run_unit PASS recorded after the code baseline
        T.call(ws, "forge-tests-mcp", "run_unit", {}, "swe4-author", phase)
    old = sys.stdin
    sys.stdin = io.StringIO('{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}')
    out = io.StringIO()
    try:
        import contextlib

        with contextlib.redirect_stdout(out):
            rc = gate.main(["--workspace", str(ws), "--phase", phase, "--step", "author"])
    finally:
        sys.stdin = old
    log = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    last = [d for d in log if d.get("step") == "author" and d.get("phase") == phase][-1]
    return {"rc": rc, "result": last.get("result"), "issues": (last.get("issues") or [])[:10]}


def evaluate(holdout: Path, case: dict | None, model: str, scratch: Path) -> dict:
    from . import review

    name = case["id"] if case else "BASELINE"
    ws = scratch / name / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(holdout, ws, symlinks=True, ignore=shutil.ignore_patterns("build"))
    for p in (ws / ".forge-run/lrtx").glob("*"):  # no checkpoints from any earlier evaluation
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    phase = case["phase"] if case else "SWE.1"
    target = case["apply"](ws) if case else None
    rec = {"case": name, "phase": phase, "class": case["class"] if case else "none", "target": target,
           "gate": _refreeze(ws, phase)}
    if rec["gate"]["result"] not in ("FROZEN", "FROZEN_BY_EVIDENCE", "FROZEN_BY_TOOL_EVIDENCE"):
        rec["detected_by"] = "deterministic gate" if case else "FALSE_REJECTION_BY_GATE"
        return rec
    rep = review.visit(ws, phase, model)
    ins = sorted((ws / "inspection" / phase).glob("INS-*.json"))
    rec_ins = json.loads(ins[-1].read_text()) if ins else None
    rec["inspection"] = {"reply": rep["status"], "verdict": (rec_ins or {}).get("verdict"),
                         "findings": [f"{f.get('id')}: {f.get('detail', '')[:240]}" for f in (rec_ins or {}).get(
                             "findings") or []]}
    text = " ".join(rec["inspection"]["findings"])
    on_target = bool(target) and (target in text or (target.startswith("SWR-") and re.search(rf"\b{target}\b", text)))
    if case is None:
        rec["detected_by"] = "FALSE_REJECTION_BY_INSPECTION" if rec["inspection"]["verdict"] == "FAIL" else "none"
    elif rec["inspection"]["verdict"] == "FAIL":
        rec["detected_by"] = "inspection (on target)" if on_target else "inspection (off target)"
    else:
        rec["detected_by"] = "MISSED" if rec_ins else f"NO_INSPECTION ({rep['status']})"
    return rec


def run(holdouts: list[Path], model: str, out: Path, cases: list[str] | None = None) -> dict:
    rows = []
    with tempfile.TemporaryDirectory(prefix="lrtx-seeded-", dir=out.parent) as td:
        for h in holdouts:
            for case in [None] + [c for c in CATALOGUE if not cases or c["id"] in cases]:
                try:
                    r = evaluate(h, case, model, Path(td) / h.parent.name)
                except ValueError as exc:  # a holdout without a site for this defect class
                    r = {"case": case["id"] if case else "BASELINE", "detected_by": f"NOT_APPLICABLE ({exc})"}
                rows.append({"holdout": h.parent.name, **r})
                out.write_text(pretty_json(_summary(rows, model)))
    return _summary(rows, model)


def _summary(rows: list[dict], model: str) -> dict:
    seeded = [r for r in rows if r["case"] != "BASELINE" and not r["detected_by"].startswith("NOT_APPLICABLE")]
    base = [r for r in rows if r["case"] == "BASELINE"]
    return {"schema": "forge-c/lrtx-seeded/1", "catalogue": CATALOGUE_VERSION, "catalogue_sha256": catalogue_hash(),
            "model": model, "generated_at": utc_now(),
            "deterministic_detection": sum(r["detected_by"] == "deterministic gate" for r in seeded),
            "semantic_detection_on_target": sum(r["detected_by"] == "inspection (on target)" for r in seeded),
            "inspection_fail_off_target": sum(r["detected_by"] == "inspection (off target)" for r in seeded),
            "missed": sum(r["detected_by"] == "MISSED" for r in seeded), "seeded": len(seeded),
            "false_rejections": sum(r["detected_by"].startswith("FALSE_REJECTION") for r in base),
            "baselines": len(base), "rows": rows,
            "note": "Pilot evidence on a small frozen catalogue; not a reliability or safety qualification."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", type=Path, action="append", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--case", action="append", default=None)
    a = ap.parse_args(argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    s = run([h.resolve() for h in a.holdout], a.model, a.out, a.case)
    print(json.dumps({k: v for k, v in s.items() if k != "rows"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
