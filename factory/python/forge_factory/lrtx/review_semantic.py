"""F011-T025..T027 (F011-FR-016..FR-019): evidence-grounded SWE.1 inspection for local-rtx-v2.

The inspector judges each required checklist item on the frozen baseline only, like the feature 010 structured
inspector. Its findings are atomic typed claims, not prose:
- an assertion from the item's closed list;
- a target from the frozen baseline (an SWR id, the document, or an upstream input);
- related SWR ids, a short detail and a remediation.

A deterministic adjudicator (`adjudicate`) decides each claim by fixed rules on the same baseline, with no
wording patterns:
- REFUTED: the baseline contradicts the claim, e.g. a requirement said to lack a pass criterion has one, or a
  recorded owner gap is judged as a failure;
- CONFIRMED: the baseline proves the claim;
- STANDS: the rules cannot decide (a judgement). It counts like CONFIRMED.

An item FAILs when at least one claim is CONFIRMED or STANDS. A FAIL whose claims are all REFUTED goes back to the
inspector once, with the refutations (selective reinspection, T027). If the inspector again returns only refuted
claims, the item is recorded as ADJUDICATED_PASS: the original verdict, every claim and every refutation are kept in
the inspection record and the reply. A refuted claim cannot authorize rework (FR-017).

Claim identity is (item, assertion, target, related ids), never the wording. A reworded claim keeps its identity
and its decision (F011-AT-022). Verdicts are recorded through the unchanged `check_inspection` operation and judged
by the unchanged inspect gate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import review as R
from . import structured as S
from . import visit as V

ASSERTIONS = {
    "SWE1-01": ["hsi_not_baselined", "safety_allocation_missing", "requirement_untraceable", "other"],
    "SWE1-02": ["requirement_not_atomic", "requirement_not_verifiable", "requirements_inconsistent",
                "requirement_infeasible", "other"],
    "SWE1-03": ["failure_handling_missing", "reset_startup_missing", "safe_state_missing", "other"],
    "SWE1-04": ["budget_missing", "budget_not_measurable", "other"],
    "SWE1-05": ["requirement_untraceable", "upstream_gap_not_recorded", "other"],
    "SWE1-06": ["requirement_not_verifiable", "ambiguity_not_documented", "other"],
}
INPUTS = ["HSI contract", "Safety allocation", "Budgets"]
_reply = R._reply  # the runner's error path writes the same compact inspect reply
STARTUP = re.compile(r"\*\*(SWR-\d{3})\*\*\s+While no .*after reset", re.I)
BOUND = re.compile(r"\b\d+(?:\.\d+)?\s*(?:bytes?|KiB|kB|MiB|%|ms|us|µs|ns|cycles|Hz|kHz|MHz)\b", re.I)
BUDGET = re.compile(r"\bat most \d+ bytes of (?:flash|static RAM|stack)\b|\buse 0 bytes of static RAM\b", re.I)
REQ_LINE = re.compile(r"^- \*\*(SWR-\d{3})\*\*\s+(.+)$")


def baseline_facts(ws: Path) -> dict:
    """What the adjudication rules read from the frozen SWE.1 work products (nothing from the author's context)."""
    ws = Path(ws)
    md = (ws / "workproducts/SWE.1/software_requirements.md").read_text()
    reqs, cur = {}, None
    for line in md.splitlines():
        m = REQ_LINE.match(line)
        if m:
            cur = m.group(1)
            reqs[cur] = {"statement": m.group(2).strip(), "verification": ""}
        elif cur and line.strip().startswith("- Verification:"):
            reqs[cur]["verification"] = line.split(":", 1)[1].strip()
    gaps_p, csv_p = ws / "traceability/upstream_gaps.md", ws / "traceability/requirements_to_tests.csv"
    gaps = gaps_p.read_text() if gaps_p.is_file() else ""
    csv = csv_p.read_text() if csv_p.is_file() else ""
    gap_rows = {i: re.search(rf"^\| {re.escape(i)} \| (.+?) \|", gaps, re.M) for i in INPUTS}
    up_to_sw = set(re.findall(r"^\| [^|]+ \| ((?:SWR-\d{3}(?:, )?)+) \|", gaps, re.M))
    traced_up = {s for row in up_to_sw for s in re.findall(r"SWR-\d{3}", row)}
    traced_sw = set(re.findall(r"^\| (SWR-\d{3}) \| [^|]+ \|$", gaps, re.M))
    return {"reqs": reqs, "startup": [m.group(1) for m in STARTUP.finditer(md)],
            "gap_rows": {i: (m.group(1) if m else None) for i, m in gap_rows.items()},
            "traced": traced_up & traced_sw, "tested": set(re.findall(r"^(SWR-\d{3}),", csv, re.M)),
            "budgets": {k: bool(re.search(rf"at most \d+ bytes of {k}", md, re.I)) for k in ("flash", "static RAM",
                                                                                            "stack")}}


def claim_schema(item: str, targets: list[str]) -> dict:
    claim = {"type": "object", "additionalProperties": False,
             "required": ["assertion", "target_id", "related_ids", "detail", "remediation"],
             "properties": {"assertion": {"type": "string", "enum": ASSERTIONS[item]},
                            "target_id": {"type": "string", "enum": targets},
                            "related_ids": {"type": "array", "maxItems": 5,
                                            "items": {"type": "string", "enum": [t for t in targets if
                                                                                 t.startswith("SWR-")] or ["none"]}},
                            "detail": {"type": "string", "minLength": 10, "maxLength": 300},
                            "remediation": {"type": "string", "minLength": 5, "maxLength": 200}}}
    return {"type": "object", "additionalProperties": False, "required": ["verdict", "claims", "evidence_checked"],
            "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                           "claims": {"type": "array", "maxItems": 10, "items": claim},
                           "evidence_checked": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}


def identity(item: str, c: dict) -> str:
    key = [item, c["assertion"], c["target_id"], *sorted(c.get("related_ids") or [])]
    return sha256_bytes(json.dumps(key).encode())[:16]


def adjudicate(ws: Path, item: str, claims: list[dict], facts: dict | None = None) -> list[dict]:
    """Each claim with its decision (REFUTED, CONFIRMED, STANDS) and the evidence that decided it."""
    from ..inspection.ears import Requirement, check_statement

    f = facts or baseline_facts(ws)
    m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    names = set(json.loads((Path(ws) / "configuration/system_names.json").read_text()))
    out = []
    for c in claims:
        a, t = c["assertion"], c["target_id"]
        r = f["reqs"].get(t)
        decision, why = "STANDS", "a judgement the deterministic rules do not decide"
        if t.startswith("SWR-") and r is None:
            decision, why = "REFUTED", f"{t} is not a requirement of the frozen baseline"
        elif a.startswith("requirement") and r is None:
            # policy: a requirement assertion is about a requirement; aimed at an input or the document it is mis-targeted
            decision, why = "REFUTED", f"'{a}' concerns a requirement, but the claim names '{t}', which is not one"
        elif a == "requirement_not_verifiable":
            # the author gate's own rule (lrtx.swe1.validate_group): a verification states a pass criterion
            if "pass" in r["verification"].lower():
                decision, why = "REFUTED", f"{t} states its pass criterion: '{r['verification'][:120]}'"
            else:
                decision, why = "CONFIRMED", f"{t} has no pass criterion in its verification"
        elif a == "budget_not_measurable" and r is not None:
            bound = BOUND.search(r["statement"])
            decision, why = ("REFUTED", f"{t} states a numeric bound with its unit: '{bound.group(0)}'") if bound else \
                ("CONFIRMED", f"{t} states no numeric bound with a unit")
        elif a == "requirement_infeasible" and r is not None and BUDGET.search(r["statement"]):
            # existing phase policy (feature 010 inspector notes): whether a constraint is MET is measured at
            # SWE.3-SWE.6; at SWE.1 the owner's work-order budget is judged as explicit and measurable
            decision, why = "REFUTED", (f"{t} is the owner's work-order budget (recorded in "
                                        "traceability/upstream_gaps.md); meeting it is measured at SWE.3-SWE.6, not "
                                        "judged at SWE.1")
        elif a == "requirement_not_atomic":
            ears = [x for x in check_statement(Requirement(t, r["statement"], 0), names).findings
                    if "NOT_ATOMIC" in x or "NO_SHALL" in x]
            decision, why = ("CONFIRMED", "; ".join(ears)) if ears else \
                ("REFUTED", f"{t} has exactly one 'shall' (EARS atomicity check passes)")
        elif a == "reset_startup_missing":
            if f["startup"]:
                decision, why = "REFUTED", f"{f['startup'][0]} specifies the reset/startup behaviour"
            else:
                decision, why = "CONFIRMED", "no reset/startup requirement in the document"
        elif a == "failure_handling_missing" and not t.startswith("SWR-") and m.get("layer") == "LL":
            # ADR-0009 (owner decision 2026-10-16): an LL work order is register access with no waiting; timeouts,
            # parameter checks and status codes belong to the HAL work order. A claim about one requirement stands.
            decision, why = "REFUTED", ("the work order is layer LL (ADR-0009): register access with no waiting, "
                                        "caller-bounded polling; timeouts, parameter checks and status codes are "
                                        "allocated to the HAL work order")
        elif a in ("safety_allocation_missing", "hsi_not_baselined", "upstream_gap_not_recorded") or \
                (a == "budget_missing" and t in INPUTS) or \
                (a == "safe_state_missing" and not t.startswith("SWR-")) or \
                (a == "failure_handling_missing" and t == "Safety allocation"):
            # F011-AT-020: safe states come from the software safety allocation; a PENDING allocation recorded by
            # the owner is the SWE.1 handling, neither approved nor a blocker. HAL failure handling stays a judgement.
            inp = {"safety_allocation_missing": "Safety allocation", "hsi_not_baselined": "HSI contract",
                   "safe_state_missing": "Safety allocation"}.get(a, t)
            row = f["gap_rows"].get(inp)
            if a == "upstream_gap_not_recorded" and inp not in INPUTS:
                decision, why = "STANDS", f"{inp} is not one of the recorded upstream inputs"
            elif row:
                decision, why = "REFUTED", (f"the owner-recorded state of '{inp}' is in traceability/upstream_gaps.md "
                                            f"('{row[:100]}'); a recorded gap is the specified handling at SWE.1")
            else:
                decision, why = "CONFIRMED", f"traceability/upstream_gaps.md has no row for '{inp}'"
        elif a == "budget_missing":
            if all(f["budgets"].values()) and f["gap_rows"].get("Budgets"):
                decision, why = "REFUTED", ("flash, static RAM and stack limits are requirements and the budget status "
                                            "is recorded in traceability/upstream_gaps.md")
        elif a == "requirement_untraceable":
            if t in f["traced"] and t in f["tested"]:
                decision, why = "REFUTED", (f"{t} is in both trace tables of traceability/upstream_gaps.md and in "
                                            "traceability/requirements_to_tests.csv")
            else:
                decision, why = "CONFIRMED", f"{t} is missing from a trace table or the test map"
        if decision == "REFUTED" and a in ("safety_allocation_missing", "safe_state_missing",
                                           "failure_handling_missing") and _mandatory_safety_missing(m):
            decision, why = "STANDS", "the work order targets an ASIL with a mandatory safety input missing"
        out.append({**c, "identity": identity(item, c), "decision": decision, "evidence": why})
    return out


def _mandatory_safety_missing(m: dict) -> bool:
    """F011-AT-023: a genuinely missing mandatory ASIL safety input is a real blocker, never refuted."""
    asil = str(m.get("safety_target") or "").upper().replace("ASIL", "").strip()  # workorder.prepare: target ASIL
    return asil in ("A", "B", "C", "D") and bool(m.get("owner_safety_document_issues"))


def item_packet(ws: Path, item: dict, bl: dict, srcs: list[dict], targets: list[str], model: str, findings=None,
                previous=None) -> dict:
    iid = item["id"]
    instr = (f"Inspect checklist item {iid} of SWE.1 on the frozen baseline {bl['baseline_id']} (hash "
             f"{bl['baseline_hash'][:16]}). Criterion (full text): {' '.join(str(item['criterion']).split())} "
             "Judge ONLY this criterion, ONLY from the SOURCES below (the frozen work products and the work-order "
             "context). verdict PASS only when the evidence satisfies the whole criterion; then claims is empty. "
             "Otherwise FAIL with one claim per problem: assertion is the kind of problem (from the list), "
             "target_id the requirement (SWR id), 'document' or the upstream input it concerns, related_ids other "
             "requirements involved (e.g. the other side of an inconsistency), detail the concrete evidence (quote "
             "the requirement or section), remediation what would fix it. A claim is checked against the baseline: a "
             "claim the baseline contradicts is refuted and does not count. evidence_checked lists the source paths "
             "you used. " + " ".join(R._notes(ws, "SWE.1", iid)))
    return S.packet(phase="SWE.1", task=f"inspect:{iid}", role="swe1-inspector", instructions=instr, sources=srcs,
                    criteria=[f"{iid}: {' '.join(str(item['criterion']).split())}"],
                    output_schema=claim_schema(iid, targets), model=model, findings=findings, previous=previous,
                    output_reserve=2048)


def validate(doc: dict, paths: set[str]) -> list[str]:
    out = []
    if doc["verdict"] == "FAIL" and not doc["claims"]:
        out.append("a FAIL verdict needs at least one claim")
    if doc["verdict"] == "PASS" and doc["claims"]:
        out.append("a PASS verdict carries no claims (use FAIL when a claim exists)")
    out += [f"evidence_checked names {p}, which is not a provided source" for p in doc["evidence_checked"]
            if R._norm_path(p) not in {R._norm_path(x) for x in paths}]
    return out


def render_claim(c: dict) -> str:
    rel = f" (with {', '.join(c['related_ids'])})" if c.get("related_ids") else ""
    return f"{c['assertion']} [{c['target_id']}{rel}]: {c['detail']} Remediation: {c['remediation']}"[:200]


def visit(ws: Path, phase: str, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    from ..registry.agents import load_agents

    if phase != "SWE.1":
        return R.visit(ws, phase, model, max_calls, resume, time_budget_s)
    budget, _f = V.open_visit(Path(ws), "SWE.1-inspect", resume, list,
                              max_calls or {a.id: a for a in load_agents()[0]}["swe1-inspector"].max_turns,
                              time_budget_s)
    try:
        return _visit(Path(ws), model, budget)
    except V.Continue as c:
        return R._reply(Path(ws), "SWE.1", "CONTINUE", [f"time box used; resumes at {c}"], budget)


def _visit(ws: Path, model: str, budget: dict) -> dict:
    from ..inspection.engine import Store
    from ..mcp.sdk import ToolContext
    from ..mcp.servers import evidence as EV

    st = Store(ws)
    try:
        bl, srcs = R.evidence(ws, "SWE.1")
    except (ValueError, S.PacketRefused) as exc:
        return R._reply(ws, "SWE.1", "FAILED", [str(exc)])
    items = [c for c in st.applicable(st.checklist("SWE.1"))["checks"]
             if c.get("required") and not c.get("deterministic_check")]
    paths = {s["path"] for s in srcs}
    facts = baseline_facts(ws)
    targets = sorted(facts["reqs"]) + ["document"] + INPUTS
    verdicts, issues, record = {}, [], {}
    for it in items:
        if it["id"] not in ASSERTIONS:
            issues.append(f"{it['id']}: no claim catalogue for this item (LRTX_SEMANTIC_INSPECTION_ITEM_UNKNOWN)")
            continue
        task = f"inspect:{bl['baseline_hash'][:16]}:{it['id']}"
        rec = V.run_task(ws, "SWE.1", task,
                         lambda fi, pr, it=it: item_packet(ws, it, bl, srcs, targets, model, fi, pr),
                         lambda d: validate(d, paths), budget)
        if rec["status"] != "VALID":
            issues += [f"{it['id']}: {e}" for e in rec["errors"][:3]]
            continue
        d = rec["doc"]
        judged = adjudicate(ws, it["id"], d["claims"], facts)
        rounds = [{"verdict": d["verdict"], "claims": judged}]
        if d["verdict"] == "FAIL" and all(c["decision"] == "REFUTED" for c in judged):
            # T027: one selective reinspection with the refutations; the inspector keeps what it can substantiate
            refut = [f"claim {c['assertion']} [{c['target_id']}] is refuted by the baseline: {c['evidence']}"
                     for c in judged]
            rec = V.run_task(ws, "SWE.1", task + ":reinspect",
                             lambda fi, pr, it=it: item_packet(ws, it, bl, srcs, targets, model, fi, pr),
                             lambda d2: validate(d2, paths), budget, refut)
            if rec["status"] == "VALID":
                d = rec["doc"]
                judged = adjudicate(ws, it["id"], d["claims"], facts)
                rounds.append({"verdict": d["verdict"], "claims": judged})
        standing = [c for c in judged if c["decision"] != "REFUTED"]
        verdict = "FAIL" if standing else "PASS"
        outcome = "ADJUDICATED_PASS" if d["verdict"] == "FAIL" and not standing else verdict
        record[it["id"]] = {"outcome": outcome, "rounds": rounds}
        verdicts[it["id"]] = {"verdict": verdict, "findings": [render_claim(c) for c in standing][:10],
                              "evidence_refs": [f"configuration/baselines/SWE.1/{bl['baseline_id']}.json",
                                                *d["evidence_checked"][:8]]}
    if issues:
        return R._reply(ws, "SWE.1", "FAILED", issues, budget)
    if st.latest_baseline("SWE.1")["baseline_hash"] != bl["baseline_hash"]:
        return R._reply(ws, "SWE.1", "FAILED", ["BASELINE_CHANGED_DURING_INSPECTION"], budget)
    ctx = ToolContext(server="forge-evidence-mcp", op="check_inspection", role="swe1-inspector", phase="SWE.1",
                      workspace=ws, run_id=json.loads((ws / ".forge-run/manifest.json").read_text())["work_order"])
    try:
        res = EV.check_inspection(ctx, EV.InspectIn(phase="SWE.1", baseline_id=bl["baseline_id"], verdicts=verdicts))
    except ValueError as exc:
        return R._reply(ws, "SWE.1", "FAILED", [f"LRTX_INSPECTION_RECORD_REFUSED:{' '.join(str(exc).split())[:240]}"],
                        budget)
    S.record(ws, "SWE.1/inspection-record.json", {"at": utc_now(), "baseline_id": bl["baseline_id"],
                                                  "result": res, "items": record, "inspector": "review_semantic"})
    notes = [f"LRTX_ADJUDICATED_PASS:{i}: {len(r['rounds'][-1]['claims'])} claim(s) refuted by the baseline"
             for i, r in record.items() if r["outcome"] == "ADJUDICATED_PASS"]
    status = "PASS" if res["status"] == "PASS" else "REWORK"
    return R._reply(ws, "SWE.1", status, list(res.get("issues") or []) + notes, budget,
                    list(res.get("artifact_refs") or []))
