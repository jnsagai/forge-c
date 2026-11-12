"""Owner rule 2026-11-03: "every production backlog/order states up front its expected quality: structural analysis
coverage, requirements-based test coverage, MISRA checkings, if it's safety or ASPICE. The line should try to achieve,
for example, 100% of the metrics, but if it's not able, should progress at least with the minimum quality that the
order defined."

The work-order spec (examples/<name>/workorder.json, forge-c/work-order-spec/0.4) may carry a `quality` block:

    "quality": {
      "structural_coverage": {"line":   {"target": 100, "minimum": 90},
                              "branch": {"target": 100, "minimum": 90},
                              "mcdc":   {"target": 100, "minimum": 80}},          # safety purpose: required
      "requirements_coverage": {"uspec_tested":      {"target": 100, "minimum": 100},
                                "swr_verified_swe6": {"target": 100, "minimum": 100}},
      "misra": {"open_violations_max": 0, "undeviated_rules_max": 0, "deviation_owner_approval": true}
    }

The purpose (ASPICE_ONLY / QM / DEVELOPMENT / FORMAL_REVIEW) stays the manifest's `purpose`. Rules: minimum <= target
<= 100 (percent); MC/DC is required for a safety purpose and optional (only if the order asks) otherwise. Without the
block the previous owner defaults are BOTH target and minimum (100% line and branch, + 100% MC/DC for safety, 100%
requirement coverage, no open MISRA finding) and the manifest records quality_source "defaults".

The line works toward the TARGET (closure tasks while coverage progresses); a gate fails only below the MINIMUM, and every
shortfall below the target is reported ("Quality achieved vs target"), never claimed as met.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

SAFETY = ("DEVELOPMENT", "FORMAL_REVIEW")
STRUCTURAL = ("line", "branch", "mcdc")
REQUIREMENTS = ("uspec_tested", "swr_verified_swe6")
MISRA_KEYS = {"open_violations_max": int, "undeviated_rules_max": int, "deviation_owner_approval": bool}
LABELS = {"line": "statement/line coverage", "branch": "branch coverage", "mcdc": "MC/DC coverage",
          "uspec_tested": "USPEC items with a passing requirement-based test",
          "swr_verified_swe6": "SWRs verified at SWE.6"}


class QualityError(ValueError):
    pass


def defaults(purpose: str | None) -> dict:
    full = {"target": 100, "minimum": 100}
    sc = {"line": dict(full), "branch": dict(full)}
    if purpose in SAFETY:
        sc["mcdc"] = dict(full)
    return {"structural_coverage": sc,
            "requirements_coverage": {k: dict(full) for k in REQUIREMENTS},
            "misra": {"open_violations_max": 0, "undeviated_rules_max": 0, "deviation_owner_approval": True}}


def _pair(path: str, v) -> list[str]:
    if not isinstance(v, dict) or set(v) != {"target", "minimum"}:
        return [f"{path}: needs exactly target and minimum"]
    t, m = v["target"], v["minimum"]
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (t, m)):
        return [f"{path}: target and minimum are numbers (percent)"]
    if not 0 <= m <= t <= 100:
        return [f"{path}: needs 0 <= minimum <= target <= 100 (minimum {m}, target {t})"]
    return []


def validate(block, purpose: str | None) -> list[str]:
    if not isinstance(block, dict):
        return ["quality: must be an object"]
    out = [f"quality: unknown key {k}" for k in block if k not in ("structural_coverage", "requirements_coverage",
                                                                    "misra")]
    sc = block.get("structural_coverage")
    if not isinstance(sc, dict):
        out.append("quality.structural_coverage: required object")
    else:
        out += [f"quality.structural_coverage: unknown metric {k}" for k in sc if k not in STRUCTURAL]
        out += [f"quality.structural_coverage.{k}: required" for k in ("line", "branch") if k not in sc]
        if purpose in SAFETY and "mcdc" not in sc:
            out.append(f"quality.structural_coverage.mcdc: required for the safety purpose {purpose}")
        out += [e for k in STRUCTURAL if k in sc for e in _pair(f"quality.structural_coverage.{k}", sc[k])]
    rc = block.get("requirements_coverage")
    if not isinstance(rc, dict):
        out.append("quality.requirements_coverage: required object")
    else:
        out += [f"quality.requirements_coverage: unknown metric {k}" for k in rc if k not in REQUIREMENTS]
        out += [f"quality.requirements_coverage.{k}: required" for k in REQUIREMENTS if k not in rc]
        out += [e for k in REQUIREMENTS if k in rc for e in _pair(f"quality.requirements_coverage.{k}", rc[k])]
    mi = block.get("misra")
    if not isinstance(mi, dict):
        out.append("quality.misra: required object")
    else:
        for k, typ in MISRA_KEYS.items():
            v = mi.get(k)
            if not isinstance(v, typ) or (typ is int and (isinstance(v, bool) or v < 0)):
                out.append(f"quality.misra.{k}: required {'non-negative integer' if typ is int else 'boolean'}")
        out += [f"quality.misra: unknown key {k}" for k in mi if k not in MISRA_KEYS]
    return out


def resolve(spec: dict, purpose: str | None) -> tuple[dict, str]:
    """(quality, source) for workorder.prepare; an invalid block is refused, never repaired."""
    block = spec.get("quality")
    if block is None:
        return defaults(purpose), "defaults"
    errs = validate(block, purpose)
    if errs:
        raise QualityError("QUALITY_BLOCK_INVALID:" + "; ".join(errs[:6]))
    return copy.deepcopy(block), "order"


def for_workspace(ws: Path) -> tuple[dict, str]:
    """The order's quality from the manifest; older manifests (no block recorded) get the defaults."""
    try:
        m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    except (OSError, ValueError):
        m = {}
    q = m.get("quality")
    if isinstance(q, dict) and not validate(q, m.get("purpose")):
        return q, m.get("quality_source", "order")
    return defaults(m.get("purpose")), "defaults"


def judge(value: float | None, pair: dict) -> str:
    """MET / BELOW_TARGET (at or above the minimum: accepted, reported) / BELOW_MINIMUM / NOT_APPLICABLE."""
    if value is None:
        return "NOT_APPLICABLE"
    if float(value) >= float(pair["target"]):
        return "MET"
    return "BELOW_TARGET" if float(value) >= float(pair["minimum"]) else "BELOW_MINIMUM"


def requirement_coverage(ws: Path) -> dict:
    """Achieved requirements-based coverage from the generated matrices 4 and 6 (None when not yet produced)."""
    import csv
    import io

    def pct(path: str, key: str, total: list[str]) -> float | None:
        p = Path(ws) / path
        if not p.is_file() or not total:
            return None
        rows = list(csv.DictReader(io.StringIO(p.read_text())))
        ok = {r[key] for r in rows if r.get("status") == "VERIFIED"}
        return round(100.0 * len([x for x in total if x in ok]) / len(total), 2)

    from .inspection.swtrace import UNITS_MD, parse_units, requirement_ids

    units = parse_units((Path(ws) / UNITS_MD).read_text()) if (Path(ws) / UNITS_MD).is_file() else []
    specs = sorted({s["id"] for u in units for s in u["specs"]})
    m4 = pct("workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.csv", "uspec", specs)
    if m4 is None and specs:  # before the SWE.4 gate wrote Matrix 4: the same relation, computed without writing
        from .inspection.swtrace import build_all, latest_run

        if latest_run(Path(ws), "run_unit") is not None:
            mx = next((x for x in build_all(Path(ws), upto="SWE.4", render=False, doxygen=False, export=False,
                                           write=set())["matrices"] if x["matrix"] == 4), None)
            if mx is not None:
                m4 = round(100.0 * (len(specs) - len(mx["uncovered"])) / len(specs), 2)
    return {"uspec_tested": m4,
            "swr_verified_swe6": pct("workproducts/SWE.6/traceability/matrix_6_validationtest_to_swr.csv", "swr",
                                     requirement_ids(Path(ws)))}


def achieved_rows(ws: Path, structural: dict | None = None) -> list[dict]:
    """[{metric, label, target, minimum, achieved, status, reason}] for the report and the package."""
    q, _src = for_workspace(ws)
    rows = []
    for k, pair in q["structural_coverage"].items():
        v = (structural or {}).get(k)
        rows.append({"metric": k, "label": LABELS[k], **pair, "achieved": v, "status": judge(v, pair)})
    rc = requirement_coverage(ws)
    for k, pair in q["requirements_coverage"].items():
        rows.append({"metric": k, "label": LABELS[k], **pair, "achieved": rc.get(k),
                     "status": judge(rc.get(k), pair) if rc.get(k) is not None else "NOT_MEASURED"})
    return rows


def render(ws: Path, rows: list[dict], reasons: list[str] | None = None) -> list[str]:
    q, src = for_workspace(ws)
    out = ["## Quality achieved vs target", "",
           "Quality of the order: " + ("stated by the work order" if src == "order" else
                                       "quality: defaults (no quality block: the owner defaults are target and minimum)")
           + ". "
           "The line works toward the target; a gate fails only below the minimum. A shortfall is reported here, never "
           "claimed as met.", "", "| metric | target | minimum | achieved | status |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        a = "n/a" if r["achieved"] is None else f"{r['achieved']}%"
        out.append(f"| {r['label']} | {r['target']}% | {r['minimum']}% | {a} | {r['status']} |")
    mi = q["misra"]
    out += ["", f"MISRA: at most {mi['open_violations_max']} open violation(s) and {mi['undeviated_rules_max']} undeviated "
            f"rule(s); deviations need owner approval: {'yes' if mi['deviation_owner_approval'] else 'no'}."]
    if reasons:
        out += ["", "Reasons the target was missed:", ""] + [f"- {x}" for x in reasons]
    return out


def accept_requirement_findings(ws: Path, phase: str, findings: list[str]) -> tuple[list[str], list[str]]:
    """Author gate (cheap): requirement-coverage findings (SWE.4 UT:SPEC_NOT_VERIFIED / UT:PLANNED_TEST_MISSING, SWE.6
    VT:SWR_NOT_VERIFIED) are accepted while the achieved share stays at or above the order's minimum; they are then
    returned as reported shortfall, never dropped silently. Work orders without unit_verification: unchanged."""
    from .layer import uspec_gtest

    if phase not in ("SWE.4", "SWE.6") or not uspec_gtest(ws):
        return findings, []
    q, _src = for_workspace(ws)
    key, codes = (("uspec_tested", ("UT:SPEC_NOT_VERIFIED:", "UT:PLANNED_TEST_MISSING:")) if phase == "SWE.4" else
                  ("swr_verified_swe6", ("VT:SWR_NOT_VERIFIED:",)))
    from .inspection.swtrace import UNITS_MD, parse_units, requirement_ids

    if phase == "SWE.4":
        units = parse_units((Path(ws) / UNITS_MD).read_text()) if (Path(ws) / UNITS_MD).is_file() else []
        total = len({s["id"] for u in units for s in u["specs"]})
        missing = len({f.split(":")[2].split()[0] for f in findings if f.startswith(codes[0])})
    else:
        total = len(requirement_ids(Path(ws)))
        missing = len({f.split(":")[2] for f in findings if f.startswith(codes[0])})
    if not total or not missing:
        return findings, []
    achieved = round(100.0 * (total - missing) / total, 2)
    pair = q["requirements_coverage"][key]
    if judge(achieved, pair) == "BELOW_MINIMUM":
        return findings, []
    hit = [f for f in findings if f.startswith(codes)]
    return [f for f in findings if not f.startswith(codes)], [
        f"REQUIREMENT_COVERAGE_BELOW_TARGET:{key}:{achieved}% (target {pair['target']}%, minimum {pair['minimum']}% "
        f"met): " + "; ".join(hit)[:400]]


def misra_allows(ws: Path, open_findings: int) -> bool:
    """SWE.3 freeze with open coding-rule findings up to the order's open_violations_max (default 0)."""
    from .layer import uspec_gtest

    return uspec_gtest(ws) and open_findings <= for_workspace(ws)[0]["misra"]["open_violations_max"]


def stage_into(ws: Path, stage: Path) -> dict | None:
    """Release Manager: 'Quality achieved vs target' in the package (quality/quality-achieved.{md,json} and a section
    in safety/known_limitations.md), from the latest llvm_coverage and the generated matrices."""
    from .layer import uspec_gtest

    if not uspec_gtest(ws):
        return None
    from .release.finalize import latest, tool_results

    rec = latest(tool_results(Path(ws)), "forge-tests-mcp", "llvm_coverage")
    m = (rec or {}).get("result", {}).get("metrics") or {}
    if "scope_functions" in m:
        m = {"line_pct": m.get("scope_region_pct"), "branch_pct": m.get("scope_branch_pct"), "mcdc_pct": m.get("mcdc_pct")}
    rows = achieved_rows(ws, {"line": m.get("line_pct"), "branch": m.get("branch_pct"), "mcdc": m.get("mcdc_pct")})
    q, src = for_workspace(ws)
    plan_p = Path(ws) / "workproducts/SWE.4/unit_test_plan.json"
    reasons = []
    if plan_p.is_file():
        plan = json.loads(plan_p.read_text())
        st = plan.get("closure_status") or {}
        reasons += list(st.get("shortfall") or [])
        reasons += [f"{u['gap']['file']}:{u['gap']['line']} `{u['gap']['text']}`: CODE defect {u['defect']}"
                    for u in plan.get("closure_unreachable", [])]
    rep = {"schema": "forge-c/quality-achieved/1", "source": src, "quality": q, "rows": rows,
           "target_met": all(r["status"] in ("MET", "NOT_APPLICABLE") for r in rows),
           "below_minimum": [r["metric"] for r in rows if r["status"] == "BELOW_MINIMUM"], "reasons": reasons}
    qd = Path(stage) / "quality"
    qd.mkdir(parents=True, exist_ok=True)
    (qd / "quality-achieved.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    md = render(ws, rows, reasons)
    (qd / "quality-achieved.md").write_text("\n".join(md) + "\n")
    kl = Path(stage) / "safety/known_limitations.md"
    kl.parent.mkdir(parents=True, exist_ok=True)
    with kl.open("a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(md) + "\n")
    return rep
