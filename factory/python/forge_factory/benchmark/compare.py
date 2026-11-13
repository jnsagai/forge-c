"""Feature 020 FR-024/FR-025 (SC-008): side-by-side comparison of a functional SWE.1 with a benchmark, metrics only.

The pilot side is computed from the work products of a functional-level SWE.1 workspace
(workproducts/SWE.1/requirement_attributes.json, inputs/governance-inventory.json, the governance package). The
benchmark side is a numbers-and-generic-categories file kept outside the repository; it is validated against
contracts/benchmark-metrics.schema.json and refused when missing or invalid. Nothing here reads benchmark text.

An attribute counts as present when it holds a value: not empty and not a "no value" marker (N/A, none, TBD, or a
"not applicable ..." placeholder) - the rule the benchmark extraction applies to N/A.

    python -m forge_factory.benchmark.compare --pilot <workspace> --benchmark <metrics.json> --out <dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jsonschema
import yaml

REPO = Path(__file__).resolve().parents[4]
CONTRACT = REPO / "specs/020-usart-benchmark-pilot/contracts/benchmark-metrics.schema.json"
TEMPLATE = REPO / "config/factory/swe1-functional-template.yaml"
ATTRS = "workproducts/SWE.1/requirement_attributes.json"
INVENTORY = "inputs/governance-inventory.json"
PACKAGE = "workproducts/SWE.1/governance/governance-package.json"
SCHEMA = "forge-c/benchmark-comparison/1"
METRICS = ("requirement_count", "by_type", "attribute_completeness", "by_origin_group", "link_kinds",
           "verification_methods", "test_levels", "scope_coverage")
NO_VALUE = re.compile(r"^(n/?a|none|tbd|-+|not applicable\b.*)$", re.I)


class Refused(Exception):
    pass


def _present(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and not NO_VALUE.match(v.strip())
    if isinstance(v, (list, dict)):
        return bool(v)
    return True


def _template(template_id: str | None = None) -> dict:
    """The template the workspace was assembled with (v1 file when none is named)."""
    if template_id:
        for p in sorted(TEMPLATE.parent.glob("swe1-functional-template*.yaml")):
            t = yaml.safe_load(p.read_text())
            if t.get("template_id") == template_id:
                return t
    return yaml.safe_load(TEMPLATE.read_text())


ALLOCATION = ("allocated_interface", "allocated_operation")


def _load(ws: Path, rel: str) -> dict:
    p = ws / rel
    if not p.is_file():
        raise Refused(f"PILOT_SWE1_MISSING: {rel} not in {ws}")
    return json.loads(p.read_text())


def pilot_metrics(ws: Path) -> dict:
    ws = Path(ws)
    adoc = _load(ws, ATTRS)
    reqs = adoc["requirements"]
    inv, pkg, tpl = _load(ws, INVENTORY), _load(ws, PACKAGE), _template(adoc.get("template"))
    n = len(reqs)
    attrs = [a for a in tpl["attributes"] if a != "key"] + list(tpl["fixed"])
    attrs += [a for a in ALLOCATION if a not in attrs]  # template v2 derives them; v1 fixes them
    links = Counter(l["kind"] for r in reqs for l in r.get("links") or [])
    awaiting = sum(r.get("origin_group") == "awaiting_traceability" for r in reqs)
    groups = Counter(r.get("origin_group") for r in reqs)
    # scope: an in-scope function is covered when a requirement names it or a use case a requirement serves holds it
    ucs = {u["use_case_id"]: u for u in pkg.get("use_cases") or []}
    used = {u for r in reqs for u in r.get("use_cases") or []}
    text = "\n".join(" ".join(str(r.get(k, "")) for k in ("title", "statement", "precondition")) for r in reqs)
    in_fns = [a["function"] for a in inv.get("api") or [] if a["scope_class"] == "in"]
    covered = {f for u in used if u in ucs for f in ucs[u].get("functions") or []}
    covered |= {f for f in in_fns if re.search(rf"\b{re.escape(f)}\b", text)}
    in_rm = [f["feature"] for f in inv.get("rm_features") or [] if f["scope_class"] == "in"]
    rm_cov = {f for u in used if u in ucs for f in ucs[u].get("rm_features") or []}

    def share(k: int, d: int) -> float:
        return k / d if d else 0.0

    return {
        "side": "pilot",
        "requirement_count": n,
        "by_type": dict(Counter(r["type"] for r in reqs)),
        "attribute_completeness": {a: round(share(sum(_present(r.get(a)) for r in reqs), n), 3) for a in attrs},
        "by_origin_group": {**{g: groups[g] for g in tpl["enums"]["origin_group"] if groups[g]},
                            "groups_defined": len(tpl["enums"]["origin_group"])},
        "link_kinds": {"trace": links["trace"], "derive": links["derive"], "awaiting": awaiting},
        "verification_methods": dict(Counter(r["verification_method"] for r in reqs)),
        "test_levels": dict(Counter(r["test_level"] for r in reqs)),
        "scope_coverage": {
            "in_scope_functions": len(in_fns),
            "in_scope_functions_covered_share": share(len(covered & set(in_fns)), len(in_fns)),
            "out_of_scope_functions": sum(a["scope_class"] == "out" for a in inv.get("api") or []),
            "in_scope_rm_features": len(in_rm),
            "in_scope_rm_features_covered_share": share(len(rm_cov & set(in_rm)), len(in_rm)),
            "not_delivered_capabilities": len(inv.get("not_delivered") or []),
            "traced_share": share(sum(any(l["kind"] == "trace" for l in r.get("links") or []) for r in reqs), n),
            "derived_share": share(sum(any(l["kind"] == "derive" for l in r.get("links") or []) for r in reqs), n),
            "awaiting_share": share(awaiting, n),
        },
    }


def load_benchmark(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise Refused(f"BENCHMARK_METRICS_MISSING: {path}")
    try:
        doc = json.loads(path.read_text())
        jsonschema.validate(doc, json.loads(CONTRACT.read_text()))
    except (ValueError, jsonschema.ValidationError) as e:
        raise Refused(f"BENCHMARK_METRICS_INVALID: {path}: {getattr(e, 'message', e)}") from None
    if doc["side"] != "benchmark":
        raise Refused(f"BENCHMARK_METRICS_INVALID: {path}: side is {doc['side']!r}, not 'benchmark'")
    return doc


def rows(pilot: dict, bench: dict) -> list[dict]:
    out = []
    for key in METRICS:
        p, b = pilot.get(key), bench.get(key)
        if not isinstance(p, dict) and not isinstance(b, dict):
            out.append({"metric": key, "category": "", "pilot": p, "benchmark": b})
            continue
        p, b = p or {}, b or {}
        cats = list(p) + [c for c in b if c not in p]
        out += [{"metric": key, "category": c, "pilot": p.get(c), "benchmark": b.get(c)} for c in cats] or [
            {"metric": key, "category": "", "pilot": None, "benchmark": None}]
    return out


def _cell(v) -> str:
    if v is None:
        return "not reported"
    return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


VERDICTS = ".forge-run/lrtx/SWE.1/phase1/verdicts.jsonl"
GOV_STATUS = ".forge-run/lrtx/SWE.1/governance/status.json"
# D34 (owner 2026-11-12 "in the new runs, preserve what is already good compared to the benchmark"): the metrics a
# rerun must not lose against its baseline run. Higher is better for each; a drop beyond TOLERANCE is REGRESSED.
GUARDED = ([("attribute_completeness", a) for a in ("statement", "type", "verification_method", "test_level",
                                                     "status", "asil", "cal")]
           + [("scope_coverage", k) for k in ("traced_share", "in_scope_functions_covered_share",
                                              "in_scope_rm_features_covered_share")]
           + [("quality", "iq_first_pass_share"), ("quality", "governance_pass")])
TOLERANCE = 0.01


def quality(ws: Path) -> dict:
    """Run-quality numbers outside the benchmark contract: per-requirement inspection first-pass share (first verdict
    of each requirement passed; a carried PASS counts) and governance coverage (1 = COVERAGE_PASS)."""
    ws = Path(ws)
    first: dict[str, bool] = {}
    p = ws / VERDICTS
    for line in (p.read_text().splitlines() if p.is_file() else []):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        first.setdefault(v.get("tk"), bool(v.get("passed")))
    g = ws / GOV_STATUS
    state = (json.loads(g.read_text()) if g.is_file() else {}).get("state")
    return {"iq_first_pass_share": (sum(first.values()) / len(first)) if first else None,
            "iq_judged": len(first), "governance_pass": 1.0 if state == "COVERAGE_PASS" else 0.0}


def preserve(current: dict, baseline: dict) -> list[dict]:
    """D34: every guarded metric of the rerun against its baseline comparison (PRESERVED / REGRESSED / NOT_MEASURED)."""
    out = []
    for metric, cat in GUARDED:
        b = (baseline.get("pilot", {}).get(metric) if metric != "quality" else baseline.get("quality") or {}).get(cat)
        c = (current.get("pilot", {}).get(metric) if metric != "quality" else current.get("quality") or {}).get(cat)
        if b is None or c is None:
            status = "NOT_MEASURED"
        else:
            status = "PRESERVED" if c >= b - TOLERANCE else "REGRESSED"
        out.append({"metric": metric, "category": cat, "baseline": b, "current": c, "status": status})
    return out


def report(ws: Path, bench_path: Path, baseline: Path | None = None) -> tuple[dict, str]:
    bench = load_benchmark(bench_path)
    pilot = pilot_metrics(ws)
    jsonschema.validate(pilot, json.loads(CONTRACT.read_text()))
    inv = _load(Path(ws), INVENTORY)
    doc = {"schema": SCHEMA, "pilot": pilot, "benchmark": bench, "rows": rows(pilot, bench),
           "quality": quality(ws),
           "not_delivered": [n.get("capability") for n in inv.get("not_delivered") or []]}
    if baseline is not None:
        if not Path(baseline).is_file():
            raise Refused(f"BASELINE_COMPARISON_MISSING: {baseline}")
        doc["preserve"] = preserve(doc, json.loads(Path(baseline).read_text()))
    md = ["# SWE.1 comparison: pilot vs benchmark (metrics only)", "",
          "Numbers and generic categories only; the benchmark itself is private and not in the repository.", "",
          "| metric | category | pilot | benchmark |", "|---|---|---|---|"]
    md += [f"| {r['metric']} | {r['category']} | {_cell(r['pilot'])} | {_cell(r['benchmark'])} |" for r in doc["rows"]]
    md += ["", "## Not delivered (capabilities with no delivered equivalent)", ""]
    md += [f"- {c}" for c in doc["not_delivered"]] or ["- none"]
    q = doc["quality"]
    md += ["", "## Run quality", "", f"- per-requirement inspection first-pass share: {_cell(q['iq_first_pass_share'])}"
           f" ({q['iq_judged']} requirements judged)", f"- governance coverage pass: {_cell(q['governance_pass'])}"]
    if "preserve" in doc:
        md += ["", "## Preserved against the baseline run (D34)", "", "| metric | category | baseline | current | status |",
               "|---|---|---|---|---|"]
        md += [f"| {p['metric']} | {p['category']} | {_cell(p['baseline'])} | {_cell(p['current'])} | {p['status']} |"
               for p in doc["preserve"]]
    md += ["", "Present = a value that is not empty and not a no-value marker (N/A, none, TBD, not applicable ...).", ""]
    return doc, "\n".join(md)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.benchmark.compare")
    ap.add_argument("--pilot", required=True, type=Path)
    ap.add_argument("--benchmark", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--preserve", type=Path, default=None, help="baseline comparison.json (D34 guarded metrics)")
    a = ap.parse_args(argv)
    try:
        doc, md = report(a.pilot, a.benchmark, a.preserve)
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "comparison.json").write_text(json.dumps(doc, indent=1) + "\n")
    (a.out / "comparison.md").write_text(md)
    print(json.dumps({"status": "OK", "out": str(a.out), "requirements": doc["pilot"]["requirement_count"],
                      **({"regressed": [f"{p['metric']}/{p['category']}" for p in doc["preserve"]
                                        if p["status"] == "REGRESSED"]} if "preserve" in doc else {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
