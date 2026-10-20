"""Deterministic brownfield workflow nodes (invoked through `inspection.gate --step verify --check <name>`):

* `delivery_inject` (after the SWE.1 inspection gate): inject.py - exit 0 only when the code is in the workspace;
* `delivery_check` (SWE.3 entry, before the SWE.3 author): fingerprints unchanged (FROZEN), trace-map seed and
  delivered-code facts written for the author;
* `delivery` (SWE.3 verify, replacing the greenfield HAL guideline node): fingerprints, the existing guideline /
  register-map / implementation checks run on the delivered code, and conformance. In FROZEN mode a problem in the
  delivered code is a recorded finding (a package gap for the owner), not a rework of the author; a fingerprint
  mismatch always fails."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import pretty_json
from . import DELIVERY_DIR, code_mode, manifest_of

FINDINGS = f"{DELIVERY_DIR}/code_findings.json"


def run(store, phase: str, check: str, state, fail_code) -> int:
    ws = Path(store.workspace)
    if check == "delivery_inject":
        from .inject import inject

        r = inject(ws)
        state(ws, phase, {"step": "delivery_inject", "result": r["status"], "issues": r["issues"][:10],
                          "swe1_baseline_id": r.get("swe1_baseline_id")})
        print(json.dumps({k: r.get(k) for k in ("status", "issues", "swe1_baseline_id")}))
        return 0 if r["status"] in ("INJECTED", "ALREADY_INJECTED") else fail_code(ws, phase, "delivery_inject")
    if check == "delivery_check":
        from .trace import seed
        from .verify import verify

        v = verify(ws, "swe3_entry")
        s = seed(ws) if v["status"] != "MISMATCH" else {"rows": 0}
        claimed = []
        if code_mode(manifest_of(ws)) == "FIX_ALLOWED":
            from ..inspection.defects import claim_delivered_fixes

            claimed = claim_delivered_fixes(ws)
        state(ws, phase, {"step": "delivery_check", "result": v["status"], "issues": v["issues"][:10],
                          "trace_seed_rows": s["rows"], "claimed_defects": claimed})
        print(json.dumps({"delivery": v["status"], "issues": v["issues"][:10], "trace_seed_rows": s["rows"],
                          "seed": "workproducts/SWE.3/code_trace_map.seed.json",
                          "facts": "workproducts/SWE.3/delivered_code_facts.json"}))
        return 0 if v["status"] != "MISMATCH" else fail_code(ws, phase, "delivery_check")
    if check == "delivery":
        return _verify_swe3(store, phase, state, fail_code)
    print(json.dumps({"error": f"unknown brownfield check {check}"}))
    return 2


def code_checks(ws: Path) -> dict:
    """The greenfield SWE.3 code checks, run on the delivered code (style forge); NOT_APPLICABLE for other styles."""
    m = manifest_of(ws)
    style = (m.get("delivery") or {}).get("build", {}).get("style", "forge")
    if style != "forge":
        return {"style": style, "guideline": "NOT_APPLICABLE", "register_map": "NOT_APPLICABLE",
                "implementation": "NOT_APPLICABLE", "findings": []}
    from ..inspection.guideline import check_workspace
    from ..inspection.implementation import check_implementation
    from ..inspection.regmap import check_regmap

    rep, reg, imp = check_workspace(ws), check_regmap(ws), check_implementation(ws)
    out = ws / "verification/static"
    out.mkdir(parents=True, exist_ok=True)
    (out / "hal_guideline_conformance.json").write_text(pretty_json(rep))
    (out / "register_map_conformance.json").write_text(pretty_json(reg))
    (out / "implementation_completeness.json").write_text(pretty_json(imp))
    findings = [f"GUIDELINE:{v.get('rule')}:{v.get('file', '')}:{v.get('line', '')}" for v in rep["violations"]][:20] + \
        [f"REGISTER_MAP:{x}" for x in reg["major_findings"]][:20] + \
        [f"IMPLEMENTATION:{x}" for x in imp["major_findings"]][:20]
    return {"style": style, "guideline": rep["verdict"], "register_map": reg["verdict"],
            "implementation": imp["verdict"], "findings": findings}


def file_contradictions(ws: Path, findings: list[dict]) -> list[str]:
    """FIX_ALLOWED: one CODE defect (IN_FIX) per contradicted requirement of a delivered function, unless one is
    already open or in fix; evidence = the function's delivered location and the requirement text."""
    from ..inspection import defects
    from ..inspection.swtrace import swr_texts

    texts = swr_texts(ws)
    scope = {f["name"]: f for f in json.loads((ws / DELIVERY_DIR / "scope.json").read_text()).get("functions", [])}
    busy = {(r, d.get("target_kind")) for d in defects.all_defects(ws) if d["kind"] == "CODE"
            and d["status"] in ("OPEN", "IN_FIX") for r in d["requirement_ids"]}
    out = []
    for f in findings:
        req, fn = f.get("requirement"), f.get("function")
        if f["kind"] != "CONTRADICTION" or not req or fn not in scope or (req, "DELIVERED_CODE") in busy:
            continue
        quote = " ".join(texts.get(req, "").split())[:200]
        try:
            rec = defects.report(ws, detected_phase="SWE.3", reported_by="brownfield-conformance", kind="CODE",
                                 summary=f"{fn}: {f['evidence']}"[:400], requirement_ids=[req], test_files=[],
                                 evidence_refs=[f"{scope[fn]['file']}:{scope[fn]['line']}"], requirement_quote=quote)
        except defects.DefectError as exc:
            out.append(f"NOT_FILED:{req}:{exc}"[:120])
            continue
        busy.add((req, "DELIVERED_CODE"))
        out.append(rec["id"])
    return out


def _verify_swe3(store, phase: str, state, fail_code) -> int:
    from ..inspection.misra_matrix import build as misra_matrix
    from .conformance import check as conformance
    from .verify import verify

    ws = Path(store.workspace)
    mode = code_mode(manifest_of(ws))
    v = verify(ws, "swe3_verify")
    cc = code_checks(ws)
    cf = conformance(ws, phase)
    misra_matrix(ws)  # coverage record (not compliance) for the release policy
    (ws / FINDINGS).write_text(pretty_json({"schema": "forge-c/delivered-code-findings/0.1", "code_mode": mode,
                                            "code_checks": cc, "conformance": cf["status"],
                                            "delivery": v["status"]}))
    # FROZEN: the author cannot change the code, so code problems are owner findings (package gaps), never rework.
    # FIX_ALLOWED: a conformance contradiction becomes a CODE defect in fix and SWE.3 reworks (b002).
    filed = file_contradictions(ws, cf["findings"]) if mode == "FIX_ALLOWED" else []
    verdict = "FAIL" if v["status"] == "MISMATCH" or (mode == "FIX_ALLOWED" and any(
        f["kind"] == "CONTRADICTION" for f in cf["findings"])) else "PASS"
    state(ws, phase, {"step": "verify", "check": "delivery", "verdict": verdict, "code_mode": mode,
                      "delivery": v["status"], "code_findings": len(cc["findings"]),
                      "conformance_findings": len(cf["findings"]), "defects_filed": filed})
    print(json.dumps({"verdict": verdict, "delivery": v["status"], "issues": v["issues"][:10],
                      "code_findings": cc["findings"][:10], "conformance": cf["status"],
                      "conformance_findings": [f"{f['kind']}:{f['function']}:{f['requirement']}"
                                               for f in cf["findings"]][:10],
                      "report": FINDINGS}))
    return 0 if verdict == "PASS" else fail_code(ws, phase, "verify")
