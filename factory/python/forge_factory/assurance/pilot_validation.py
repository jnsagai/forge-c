"""ENFORCING precondition (policy.mode_preconditions): a validated pilot record - pilot PASS, measured false-positive
and false-negative rates, and an independent human review. Nothing here switches the mode or approves safety.

  measure   per pilot package (copied, never modified): seeded defects for the false-negative rate (generic rules
            applied to the package's own LL/HAL code, one defect per copy; detector = the EASA register checks, the
            requirement/RM oracle, the analyzers and CBMC/Eva - corpus.py), plus the EASA findings to review: the
            detector findings on the unmodified copy and the package's blocking EASA findings.
  worksheet one row per finding with an empty disposition; ONLY the human reviewer fills CORRECT / INCORRECT and signs.
  record    from a signed worksheet: false-positive rate = INCORRECT / reviewed findings, false-negative rate = seeded
            defects missed / seeded defects applied, pilot_status PASS only if every pilot package passed the pilot
            check and the worksheet is complete; appended to the assurance store as kind 'mode' (the record
            policy.request_mode reads). An agent cannot sign: the reviewer must be a human name (policy._human).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from ..common import pretty_json, sha256_file, utc_now
from . import corpus, pilot, shadow
from .policy import _human

LL, HAL = corpus.LL, corpus.HAL
# id, file, regex, replacement (first match only), defect class - generic forms of the corpus.py classes
SEEDS = [
    ("S01", LL, r"(#define LL_RCC_CR_HSEON_MSK\s+)0x00000010U", r"\g<1>0x00000020U", "wrong bit in a register definition"),
    ("S02", LL, r"(ll_rcc_regs\[\s*LL_RCC_AHB1ENR_OFFSET\s*/\s*4U?\s*\]\s*)\|=", r"\g<1>=",
     "write clobbers other bits (= for |=)"),
    ("S03", LL, r"(ll_rcc_regs\[\s*LL_RCC_AHB1)ENR(_OFFSET\s*/\s*4U?\s*\]\s*\|=\s*LL_RCC_AHB1ENR_GPDMA1EN_MSK)",
     r"\g<1>RSTR\g<2>", "wrong register (RSTR for ENR)"),
    ("S04", HAL, r"\b(LL_RCC_)HSE(_Enable\s*\(\s*\))", r"\g<1>HSI\g<2>", "swapped oscillator (HSI for HSE)"),
    ("S05", HAL, r"(<)(\s*timeout\b)", r"<=\g<2>", "polling bound off by one"),
    ("S06", HAL, r"\(\s*timeout\s*==\s*0U?\s*\)\s*\|\|\s*", "", "missing parameter check (timeout 0 accepted)"),
    ("S07", HAL, r"(hal_status_t\s+\w+)\s*=\s*HAL_TIMEOUT\s*;", r"\g<1>;", "uninitialised status variable"),
    ("S08", LL, r"(&=\s*~\s*\(?\s*)LL_RCC_AHB1RSTR_GPDMA1RST_MSK", r"\g<1>LL_RCC_AHB1RSTR_ADC12RST_MSK",
     "release clears the wrong reset bit"),
]


def _detect(ws: Path) -> dict[str, list[str]]:
    return {**corpus._easa(ws), "formal": corpus._formal(ws)}


def measure(zip_path: Path, inputs_from: Path) -> dict:
    zip_path = Path(zip_path)
    before = sha256_file(zip_path)
    chk = pilot.check(zip_path)
    with tempfile.TemporaryDirectory() as td:
        x = Path(td) / "x"
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(x)
            summary = json.loads(z.read("evidence/assurance/summary.json")) \
                if "evidence/assurance/summary.json" in z.namelist() else {}
        base = shadow._workspace_from_package(x, inputs_from)
        ref = _detect(base)
        seeds = []
        for sid, rel, rx, new, cls in SEEDS:
            p = base / rel
            t = p.read_text(errors="replace") if p.is_file() else ""
            if not re.search(rx, t):
                seeds.append({"id": sid, "class": cls, "status": "NOT_APPLICABLE", "reason": "pattern absent"})
                continue
            ws = Path(td) / sid
            shutil.copytree(base, ws)
            (ws / rel).write_text(re.sub(rx, new, t, count=1))
            got = {k: [f for f in v if f not in ref.get(k, [])] for k, v in _detect(ws).items()}
            seeds.append({"id": sid, "class": cls, "status": "APPLIED", "detected": any(got.values()),
                          "detected_by": sorted(k for k, v in got.items() if v),
                          "evidence": {k: v[:3] for k, v in got.items() if v}})
    findings = [{"source": f"detector:{k}", "finding": f} for k, v in ref.items() for f in v]
    findings += [{"source": "package:blocking", "finding": f} for f in summary.get("blocking_findings", [])]
    applied = [s for s in seeds if s["status"] == "APPLIED"]
    return {"schema": "forge-c/easa-pilot-validation-measure/0.1", "package": zip_path.name, "archive_sha256": before,
            "archive_unchanged": sha256_file(zip_path) == before, "pilot_check": chk["status"],
            "pilot_check_failing": chk["failing_relations"][:10], "seeds": seeds,
            "seeded_applied": len(applied), "seeded_missed": [s["id"] for s in applied if not s["detected"]],
            "findings_to_review": findings, "measured_at": utc_now()}


def worksheet(measurements: list[dict]) -> dict:
    rows = []
    for m in measurements:
        for i, f in enumerate(m["findings_to_review"], 1):
            rows.append({"row": f"{m['package'].split('-review')[0]}#{i:03d}", "package": m["package"], **f,
                         "disposition": "", "reviewer_note": ""})
    return {"schema": "forge-c/easa-pilot-review-worksheet/0.1", "created_at": utc_now(),
            "instructions": "For each row write disposition CORRECT (the finding is a real gap or defect) or INCORRECT "
                            "(false positive), with a short note for INCORRECT. Then fill reviewer and reviewed_at. "
                            "Only the named human reviewer fills this; an agent must not.",
            "reviewer": "", "reviewed_at": "", "rows": rows,
            "measurements": [{k: m[k] for k in ("package", "archive_sha256", "pilot_check", "seeded_applied",
                                                "seeded_missed")} for m in measurements]}


def record(ws_doc: dict, store=None) -> dict:
    """Validated pilot record from a reviewer-signed worksheet; refuses an unsigned or incomplete worksheet."""
    from .store import AssuranceStore

    issues = []
    if not _human(ws_doc.get("reviewer")) or not ws_doc.get("reviewed_at"):
        issues.append("REVIEW_NOT_SIGNED_BY_A_HUMAN")
    rows = ws_doc.get("rows") or []
    open_rows = [r["row"] for r in rows if r.get("disposition") not in ("CORRECT", "INCORRECT")]
    if open_rows:
        issues.append(f"REVIEW_INCOMPLETE:{len(open_rows)} rows without disposition")
    ms = ws_doc.get("measurements") or []
    applied = sum(m["seeded_applied"] for m in ms)
    missed = sum(len(m["seeded_missed"]) for m in ms)
    if not ms or applied == 0:
        issues.append("FALSE_NEGATIVES_NOT_MEASURED")
    if issues:
        return {"decision": "REFUSED", "issues": issues}
    fp = sum(r["disposition"] == "INCORRECT" for r in rows)
    pilots_pass = all(m["pilot_check"] == "PASS" for m in ms)
    rec = {"pilot_status": "PASS" if pilots_pass else "FAIL",
           "false_positive_rate": round(fp / len(rows), 4) if rows else 0.0,
           "false_negative_rate": round(missed / applied, 4),
           "reviewed_findings": len(rows), "false_positives": fp, "seeded_applied": applied, "seeded_missed": missed,
           "packages": [m["package"] for m in ms], "independent_review_by": ws_doc["reviewer"],
           "reviewed_at": ws_doc["reviewed_at"]}
    store = store or AssuranceStore()
    rid = store.append("mode", "pilot_validation", rec, actor=ws_doc["reviewer"])
    return {"decision": "RECORDED", "record_id": rid, "record": rec}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.assurance.pilot_validation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("worksheet")
    m.add_argument("zips", nargs="+", type=Path)
    m.add_argument("--inputs-from", type=Path, required=True)
    m.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("record")
    r.add_argument("worksheet", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "worksheet":
        doc = worksheet([measure(z, a.inputs_from) for z in a.zips])
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(doc))
        print(json.dumps({"rows": len(doc["rows"]), "measurements": doc["measurements"]}))
        return 0
    out = record(json.loads(a.worksheet.read_text()))
    print(json.dumps(out))
    return 0 if out["decision"] == "RECORDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
