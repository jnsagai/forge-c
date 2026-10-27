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
SAFETY_DOC = "safety/software_safety_requirements.md"
LESSONS = {"dir": None, "include_proposed": False}  # F011-T044: seeded harness (--lessons [--lessons-trial]);
# otherwise the profile flag decides (VALIDATED lessons only)
LESSON_SOURCE = "reference/inspection-lessons.md"
_reply = R._reply  # the runner's error path writes the same compact inspect reply
STARTUP = re.compile(r"\*\*(SWR-\d{3})\*\*\s+While no .*after reset", re.I)
# run 2 (2026-10-26): "at most HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations" is a measurable count bound
BOUND = re.compile(r"\b\d+(?:\.\d+)?\s*(?:bytes?|KiB|kB|MiB|%|ms|us|µs|ns|cycles|Hz|kHz|MHz|"
                   r"(?:polling\s+)?(?:iterations?|polls?|attempts?|retries|calls?))\b", re.I)
BUDGET = re.compile(r"\bat most \d+ bytes of (?:flash|static RAM|stack)\b|\buse 0 bytes of static RAM\b", re.I)
# measured (F011-T029 run 5, WO-0008C): the budget requirements say "use 0 bytes of persistent static RAM ... within
# the 64-byte static RAM budget"; a budget is a requirement naming the resource with a byte bound, in any phrasing
BYTES = re.compile(r"\b\d+(?:-| )bytes?\b", re.I)
REQ_LINE = re.compile(r"^- \*\*(SWR-\d{3})\*\*\s+(.+)$")
# a verification's criterion clause after the method: an asserted, observable outcome
CRITERION = re.compile(r";[^;]*\b(?:is|are|equals?|occurs?|returns?|remains?|reads?|holds?|contains?|matches|stays?)\b",
                       re.I)


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
    # a label may carry an explanation (WO-0008C: "HSI contract (hardware/software interface)")
    gap_rows = {i: re.search(rf"^\| (?:{input_label_pattern(i)}) \| (.+?) \|", gaps, re.M) for i in INPUTS}
    up_to_sw = set(re.findall(r"^\| [^|]+ \| ((?:SWR-\d{3}(?:, )?)+) \|", gaps, re.M))
    # learning set 2 (h005): the upstream table may carry more columns ('| Upstream id | Source | SWR IDs |'); a row whose
    # first cell is an upstream id and whose last cell lists SWR ids traces them
    for line in gaps.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 3 and not cells[0].startswith("SWR-") and re.fullmatch(r"SWR-\d{3}(?:,\s*SWR-\d{3})*", cells[-1]):
            up_to_sw.add(cells[-1])
    traced_up = {s for row in up_to_sw for s in re.findall(r"SWR-\d{3}", row)}
    traced_sw = set(re.findall(r"^\| (SWR-\d{3}) \| [^|]+ \|$", gaps, re.M))
    opened = re.search(r"^## Open points\s*\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    return {"reqs": reqs, "startup": [m.group(1) for m in STARTUP.finditer(md)],
            "open_points": " ".join(((opened.group(1) if opened else "") + " " + gaps).split()),
            "gap_rows": {i: (m.group(1) if m else None) for i, m in gap_rows.items()},
            # learning set 3 (USART1): 'USART_CR1.FIFOEN is 0 throughout verification', '(USART_CR1.FIFOEN = 0, reset
            # state)': fields the baseline or work-order scope fix as an environment state, not a driver obligation
            "fixed_state": fixed_state_fields(md + " " + " ".join(scope_items(ws))),
            "traced": traced_up & traced_sw, "tested": set(re.findall(r"^(SWR-\d{3}),", csv, re.M)),
            "budgets": {k: any(re.search(rf"\b{k}\b", r["statement"], re.I) and BYTES.search(r["statement"])
                               for r in reqs.values()) for k in ("flash", "static RAM", "stack")}}


def claim_schema(item: str, targets: list[str], paths: list[str] | None = None) -> dict:
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
                           "evidence_checked": {"type": "array", "minItems": 1,
                                                "items": {"type": "string", "enum": paths} if paths else
                                                {"type": "string"}}}}


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
            # the author gate's own rule (lrtx.swe1.validate_group): a verification states a pass criterion; learning
            # set 2 (h005): '<method>; <observable outcome>' states it too ('no IWDG register write ... occurs before
            # an initialisation request')
            if "pass" in r["verification"].lower() or CRITERION.search(r["verification"]):
                decision, why = "REFUTED", f"{t} states its pass criterion: '{r['verification'][:120]}'"
            else:
                decision, why = "CONFIRMED", f"{t} has no pass criterion in its verification"
        elif a == "budget_not_measurable" and r is None and all(f["budgets"].values()):
            # Omniverse2 learning run: the work-order budgets called unmeasurable while each is a requirement stating
            # its resource with a byte bound
            decision, why = "REFUTED", "flash, static RAM and stack are each a requirement with a byte bound"
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
        elif a == "ambiguity_not_documented" and t in INPUTS and f["gap_rows"].get(t):
            # run 2 (2026-10-26): a PENDING safety allocation called an undocumented ambiguity; the owner-recorded state
            # of the input is the documented ambiguity at SWE.1, as for the other upstream-input assertions
            decision, why = "REFUTED", (f"the owner-recorded state of '{t}' is in traceability/upstream_gaps.md "
                                        f"('{f['gap_rows'][t][:100]}')")
        elif a == "ambiguity_not_documented" and _quoted_open_point(c["detail"], f["open_points"]):
            # Omniverse2 2026-10-26 (stepwise smoke): the claim quoted the ambiguity from the document's own Open
            # points list; an ambiguity quotable from that list is documented, so the claim contradicts the baseline
            decision, why = "REFUTED", ("the baseline records it (Open points or upstream gaps): "
                                        f"'{_quoted_open_point(c['detail'], f['open_points'])[:120]}'")
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
                recorded = all(f["gap_rows"].get(i) for i in INPUTS)
                decision, why = ("REFUTED", "traceability/upstream_gaps.md records the state of every upstream input "
                                            f"({', '.join(INPUTS)})") if recorded else \
                    ("STANDS", f"{inp} is not one of the recorded upstream inputs")
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
        if decision == "STANDS" and RECORDED_UPSTREAM.search(c["detail"]) and all(f["gap_rows"].get(i) for i in INPUTS) \
                and not _mandatory_safety_missing(m):
            # run 10 (2026-10-26): a judgement whose objection is the owner-recorded upstream status (NOT_PROVIDED,
            # DRAFT_TEMPLATE) while every input's state is recorded; that record is the SWE.1 handling (F011-AT-020)
            decision, why = "REFUTED", ("the objection is the recorded upstream status; traceability/upstream_gaps.md "
                                        f"records the state of every upstream input ({', '.join(INPUTS)})")
        if decision == "REFUTED" and a in ("safety_allocation_missing", "safe_state_missing",
                                           "failure_handling_missing") and _mandatory_safety_missing(m):
            decision, why = "STANDS", "the work order targets an ASIL with a mandatory safety input missing"
        out.append({**c, "identity": identity(item, c), "decision": decision, "evidence": why})
    return out


RECORDED_UPSTREAM = re.compile(r"\bNOT_PROVIDED\b|\bDRAFT_TEMPLATE\b|upstream (?:status|inputs?) (?:is|are) (?:not provided|"
                               r"missing|absent)|\bPENDING\b", re.I)  # run 10: 0008B's recorded PENDING safety allocation


def _quoted_open_point(detail: str, open_points: str) -> str | None:
    """A phrase the claim quotes (8+ characters) that the document's Open points section contains verbatim."""
    for q in re.findall(r"'([^']{8,})'|\"([^\"]{8,})\"", detail):
        text = " ".join("".join(q).split()).rstrip(".")
        if text and text in open_points:
            return text
    return None


def _mandatory_safety_missing(m: dict) -> bool:
    """F011-AT-023: a genuinely missing mandatory ASIL safety input is a real blocker, never refuted."""
    asil = str(m.get("safety_target") or "").upper().replace("ASIL", "").strip()  # workorder.prepare: target ASIL
    return asil in ("A", "B", "C", "D") and bool(m.get("owner_safety_document_issues"))


INSPECTOR = {"seed": None, "coverage": None, "entries": None, "stepwise": None}  # F011-T048/T049/T054, F014: harness
FIELD = re.compile(r"^[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*$")
WILDCARD = re.compile(r"^[A-Z][A-Z0-9_]*\.\*$")  # F014 stepwise: a behaviour on any field of the register
NUMBER = re.compile(r"\b0x[0-9A-Fa-f]+\b|\b\d+\b")


def _profile_structured(ws: Path) -> tuple[str | None, dict]:
    """The v2 profile of this work order (manifest binding, else the harness's FORGE_LRTX_PROFILE) and its
    `structured` block."""
    import os

    from .profile import load

    man = Path(ws) / ".forge-run/manifest.json"
    pid = (json.loads(man.read_text()).get("local_profile") or {}).get("id") if man.is_file() else None
    pid = pid or os.environ.get("FORGE_LRTX_PROFILE")
    return (pid, (load(pid).get("structured") or {})) if pid else (None, {})


def inspector_options(ws: Path, model: str) -> dict:
    """F011-T048/T049/T054: the sampling (temperature, top_p, seed), coverage and entry switches of the local inspector:
    the profile's per-model values over its default, then the harness overrides. None: model defaults (as before)."""
    pid, st = _profile_structured(ws)
    table = st.get("inspector_sampling") or {}
    sampling = {**(table.get("default") or {}), **(table.get(model) or {})}
    if INSPECTOR["seed"] is not None:
        sampling["seed"] = INSPECTOR["seed"]
    coverage = INSPECTOR["coverage"] if INSPECTOR["coverage"] is not None else bool(st.get("inspector_coverage"))
    entries = INSPECTOR["entries"] if INSPECTOR["entries"] is not None else bool(st.get("inspector_entries"))
    stepwise = INSPECTOR["stepwise"] if INSPECTOR["stepwise"] is not None else bool(st.get("inspector_stepwise"))
    if stepwise:  # F014: deterministic decoding for every question of the visit; per-fact questions replace entries
        sampling = {"temperature": 0, **({"seed": sampling["seed"]} if "seed" in sampling else {})}
        coverage, entries = True, False
    return {"profile": pid, "sampling": sampling or None, "coverage": coverage, "entries": entries,
            "stepwise": stepwise}


def scope_items(ws: Path) -> list[str]:
    """The owner's in-scope work-order scope items (an 'Out of scope' item is no coverage obligation)."""
    m = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    return [x for x in m.get("scope") or [] if not str(x).strip().lower().startswith("out of scope")]


def source_fields(srcs: list[dict]) -> list[str]:
    """F014 stepwise: the closed answer set of a coverage question, every REGISTER.FIELD the frozen sources name and
    REGISTER.* for each of their registers (Omniverse2 2026-10-26: a generic RCC scope item drew placeholder fields
    such as 'RCC_AHB2ENR.<field>' three times and the inspection recorded nothing)."""
    found = {m for s in srcs for m in re.findall(r"\b[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*\b", s.get("text") or "")}
    return sorted(found | {f.split(".")[0] + ".*" for f in found})


def coverage_schema(swrs: list[str], fields: list[str] | None = None) -> dict:
    field = {"type": "string", "enum": fields} if fields else {"type": "string", "minLength": 3, "maxLength": 60}
    row = {"type": "object", "additionalProperties": False,
           "required": ["behaviour", "register_field", "value", "covered_by"],
           "properties": {"behaviour": {"type": "string", "minLength": 5, "maxLength": 200},
                          "register_field": field,
                          "value": {"type": "string", "maxLength": 24},
                          "covered_by": {"type": "array", "maxItems": 5,
                                         "items": {"type": "string", "enum": swrs or ["none"]}}}}
    return {"type": "object", "additionalProperties": False, "required": ["behaviours"],
            "properties": {"behaviours": {"type": "array", "maxItems": 12, "items": row}}}


def coverage_packet(ws: Path, bl: dict, srcs: list[dict], scope: str, swrs: list[str], model: str, sampling,
                    findings=None, previous=None, fields: list[str] | None = None) -> dict:
    instr = (f"Coverage question on the frozen SWE.1 baseline {bl['baseline_id']}. Work-order scope item (written by "
             f"the owner): \"{' '.join(scope.split())}\". List each register behaviour this scope item requires the "
             "driver to perform or report: register_field is REGISTER.FIELD as the sources name it, value is the value "
             "written when the scope or the manual fixes one (else \"\"), covered_by lists the requirements of the "
             "baseline that specify exactly that behaviour (empty when none does). Only register behaviours: "
             "structure, style and API-shape constraints are not behaviours. Judge only from the SOURCES."
             + (" register_field is one of the offered names; REGISTER.* stands for a behaviour on any field of that "
                "register (for example a peripheral clock chosen by the caller)." if fields else ""))
    return S.packet(phase="SWE.1", task="inspect:coverage", role="swe1-inspector", instructions=instr, sources=srcs,
                    criteria=["SWE1-05: coverage gaps against the work-order scope"],
                    output_schema=coverage_schema(swrs, fields), model=model, findings=findings, previous=previous,
                    output_reserve=2048, sampling=sampling)


def validate_coverage(doc: dict, swrs: set[str]) -> list[str]:
    out = [f"register_field '{b['register_field']}' is not REGISTER.FIELD" for b in doc["behaviours"]
           if not (FIELD.match(b["register_field"]) or WILDCARD.match(b["register_field"]))]
    return out + [f"covered_by names {x}, not a requirement" for b in doc["behaviours"] for x in b["covered_by"]
                  if x not in swrs]


def _numbers(text: str) -> set[int]:
    return {int(n, 16) if n.lower().startswith("0x") else int(n) for n in NUMBER.findall(text)}


def coverage_claims(scope: str, doc: dict, facts: dict) -> list[dict]:
    """Every uncovered behaviour as an SWE1-05 claim, decided: REFUTED when a requirement states that register field
    (and that value, when one is given); otherwise it STANDS (the model's judgement)."""
    out = []
    for b in doc["behaviours"]:
        if b["covered_by"]:
            continue
        f, v = b["register_field"], b["value"].strip()
        want = _numbers(v) if v else set()
        wide = f.split(".")[0] if WILDCARD.match(f) else None  # register-wide: any requirement on that register
        hit = next((s for s, r in sorted(facts["reqs"].items()) if
                    (re.search(rf"\b{re.escape(wide)}\b", r["statement"]) if wide else f in r["statement"]) and
                    (not want or want & _numbers(r["statement"]))), None)
        c = {"assertion": "scope_behaviour_uncovered", "target_id": "document", "related_ids": [],
             "detail": (f"scope item '{' '.join(scope.split())[:60]}': {b['behaviour'][:120]} ({f}"
                        f"{' = ' + v if v else ''}) has no requirement")[:300],
             "remediation": f"add a requirement for {f}{' = ' + v if v else ''}"[:200]}
        c["identity"] = identity("SWE1-05", {**c, "target_id": f"{f}={v}"})
        c["decision"], c["evidence"] = ("REFUTED", f"{hit} states {f}" + (f" with {v}" if v else "")) if hit else \
            ("STANDS", "the requirements state no such register behaviour")
        out.append(c)
    return out


# F011-T054: per-entry questions. Measured (F011-T045 trials m8/m9): an effects entry contradicting its requirement
# was never found (0/14) and a removed budget requirement mostly missed (4/14) when judged inside a whole checklist item.
OPPOSITE = {"set": "clear", "clear": "set"}
WO_BUDGETS = {"flash_bytes": "flash", "static_ram_bytes": "static RAM", "stack_bytes": "stack"}


def effect_entries(ws: Path, facts: dict) -> list[dict]:
    """Each set/clear/write entry of the effects contract paired with the requirement it names (frozen baseline)."""
    p = Path(ws) / "workproducts/SWE.1/register_effects.json"
    out = []
    for e in (json.loads(p.read_text()).get("effects") or []) if p.is_file() else []:
        if e.get("op") not in ("set", "clear", "write") or e.get("swr") not in facts["reqs"] or \
                not e.get("register") or not e.get("field"):
            continue
        args = [x for c in e.get("api_calls") or [] for x in c.get("args") or [] if isinstance(x, int)]
        out.append({"entry": f"E{len(out) + 1:02d}", "case": str(e.get("case", "")), "swr": e["swr"],
                    "field": f"{e['register']}.{e['field']}", "op": e["op"], "value": e.get("value"), "args": args,
                    "statement": facts["reqs"][e["swr"]]["statement"]})
    return out


def budget_entries(ws: Path) -> list[dict]:
    """The owner's work-order resource budgets (manifest `budgets`), one question row each."""
    b = json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("budgets") or {}
    return [{"entry": f"B{i + 1}", "resource": res, "bytes": b[k]}
            for i, (k, res) in enumerate((k, r) for k, r in WO_BUDGETS.items() if isinstance(b.get(k), int))]


def entries_schema(ids: list[str], swrs: list[str], kind: str) -> dict:
    row = {"type": "object", "additionalProperties": False,
           "required": ["entry", "agrees", "reason"] if kind == "effects" else ["entry", "covered_by", "reason"],
           "properties": {"entry": {"type": "string", "enum": ids},
                          "reason": {"type": "string", "minLength": 5, "maxLength": 200}}}
    if kind == "effects":
        row["properties"]["agrees"] = {"type": "boolean"}
    else:
        row["properties"]["covered_by"] = {"type": "array", "maxItems": 3,
                                           "items": {"type": "string", "enum": swrs or ["none"]}}
    return {"type": "object", "additionalProperties": False, "required": ["entries"],
            "properties": {"entries": {"type": "array", "minItems": len(ids), "maxItems": len(ids), "items": row}}}


def _effect_text(e: dict) -> str:
    return f"{e['op']} {e['field']}" + (f" = {e['value']}" if e["op"] == "write" else "")


def entries_packet(ws: Path, bl: dict, srcs: list[dict], kind: str, rows: list[dict], swrs: list[str], model: str,
                   sampling, findings=None, previous=None) -> dict:
    if kind == "effects":
        lines = "\n".join(f"{e['entry']}: effect entry '{e['case']}' performs {_effect_text(e)}; it names {e['swr']}: "
                          f"\"{e['statement']}\"" for e in rows)
        instr = (f"Entry question on the frozen SWE.1 baseline {bl['baseline_id']}. Each line pairs one entry of "
                 "workproducts/SWE.1/register_effects.json with the requirement it names:\n" + lines + "\n"
                 "For each entry answer agrees=true when the requirement states exactly this operation (set or clear, "
                 "or the written value) on this register field for this case, agrees=false when it states a "
                 "different operation or value for the field or does not state the field. The reason quotes the words "
                 "of the requirement that decide. Judge only from these lines and the SOURCES.")
        crit = ["SWE1-02: requirements consistent with the register effects contract"]
    else:
        lines = "\n".join(f"{b['entry']}: the work order fixes a {b['resource']} budget of {b['bytes']} bytes"
                          for b in rows)
        instr = (f"Entry question on the frozen SWE.1 baseline {bl['baseline_id']}. The owner's work order fixes these "
                 "resource budgets:\n" + lines + "\nFor each budget list in covered_by the requirements of the "
                 "baseline that state this resource with this byte bound (empty when none does). A requirement about "
                 "another resource does not cover it. Judge only from these lines and the SOURCES.")
        crit = ["SWE1-04: every work-order budget is an explicit, measurable requirement"]
    return S.packet(phase="SWE.1", task=f"inspect:{kind}", role="swe1-inspector", instructions=instr, sources=srcs,
                    criteria=crit, output_schema=entries_schema([r["entry"] for r in rows], swrs, kind), model=model,
                    findings=findings, previous=previous, output_reserve=2048, sampling=sampling)


def validate_entries(doc: dict, ids: list[str]) -> list[str]:
    got = [r["entry"] for r in doc["entries"]]
    return [f"entry {i} answered {got.count(i)} times (answer each entry once)" for i in ids if got.count(i) != 1]


PARAMETER = re.compile(r"\b(?:requested|configured|given|supplied|selected|caller[- ]supplied)\s+(?:value|prescaler|"
                       r"reload|key|divider|setting)\b", re.I)
RANGE = re.compile(r"\brange\s+(0x[0-9A-Fa-f]+|\d+)\s+(?:through|to|-|–)\s+(0x[0-9A-Fa-f]+|\d+)\b", re.I)


def in_stated_range(statement: str, value) -> bool:
    """Run 10 (IWDG-HAL rc4): 'write the configured prescaler in the inclusive range 0 through 7 to IWDG_PR.PR' states
    every in-range write the effects contract lists (PR = 0 ... 7)."""
    want = _numbers(value) if isinstance(value, str) else ({value} if isinstance(value, int) else set())
    for lo, hi in RANGE.findall(statement):
        a, b = (int(x, 16) if x.lower().startswith("0x") else int(x) for x in (lo, hi))
        if want and all(a <= w <= b for w in want):
            return True
    return False


def _states_effect(e: dict) -> bool:
    """The requirement text itself states the entry's operation on its field (the claim is then refuted)."""
    s, f = e["statement"], re.escape(e["field"])
    if not re.search(rf"\b{f}\b", s):
        return False
    if e["op"] in OPPOSITE:
        return bool(re.search(rf"\b{e['op']}\b[^.;]*\b{f}\b", s, re.I)) and \
            not re.search(rf"\b{OPPOSITE[e['op']]}\b[^.;]*\b{f}\b", s, re.I) or bit_written(s, e["field"], e["op"])
    if parameterised_write(s, e["field"]):
        return True
    v = e["value"]
    want = _numbers(v) if isinstance(v, str) else ({v} if isinstance(v, int) else set())
    if not want:
        return False
    return want <= _numbers(s) or (bool(re.search(r"\brequested value\b", s, re.I)) and want <= set(e["args"])) or \
        in_stated_range(s, v)


PARAMETER_VALUE = re.compile(r"\b(?:requested|configured|given|supplied|selected|caller[- ]supplied)\s+(?:[\w-]+\s+){0,3}?"
                             r"(?:values?|encodings?|arguments?|prescaler|reload|key|divider|setting|threshold|modes?|counts?|"
                             r"size|width|length|level|direction|order|polarity|phase|rate|selection|frame|data|byte|word)s?\b",
                             re.I)  # SPI1 'requested mode', 'requested frame'
# learning set 3 (Feature 015 SPI1/USART1): 'write that value to SPI_CFG1.MBR' (the supplied encoding) and 'write
# USART_BRR.BRR calculated from the supplied kernel clock ... and requested baud rate' (a computed write)
VALUE_REFERENCE = re.compile(r"\bwrit\w*\s+(?:that|this)\s+(?:[\w-]+\s+){0,2}?(?:value|encoding|argument)\b", re.I)
COMPUTED_FROM = re.compile(r"\b(?:calculated|computed|derived)\s+from\s+(?:the\s+)?(?:supplied|requested|given|configured)\b",
                           re.I)


def bit_written(statement: str, field: str, op: str) -> bool:
    """Learning set 3 (Feature 015 SPI1): 'shall write the requested master value 1 or slave value 0 to
    SPI_CFG2.MASTER' states both the set (1) and the clear (0) of that one-bit field. Only the clause naming the field."""
    bit = {"set": 1, "clear": 0}.get(op)
    f = re.escape(field)
    return bit is not None and any(re.search(rf"\b{f}\b", c) and re.search(r"\bwrit\w*\b", c, re.I) and bit in _numbers(c)
                                   for c in re.split(r"[.;](?=\s|$)", statement))


def parameterised_write(statement: str, field: str) -> bool:
    """Learning set 2 (2026-10-26, IWDG-HAL h003/rc1/rc3): 'shall write the configured prescaler (encoding) to
    IWDG_PR.PR' states the write of whatever value the caller configured, so every value the effects contract lists for
    that field is stated; so does 'with the configured values retained in IWDG_PR.PR' (the field holds the configured
    value). Learning set 3 adds 'write that value to FIELD' and 'write FIELD calculated from the supplied ...'. Only the
    clause that names the field counts, and it must write, or keep in the field, a parameter."""
    f = re.escape(field)
    for c in re.split(r"[.;](?=\s|$)", statement):  # sentence ends only: REG.FIELD keeps its dot
        if not re.search(rf"\b{f}\b", c):
            continue
        if re.search(r"\b(?:writ(?:e|es|ing)|retain(?:s|ed)?|hold(?:s)?|contain(?:s)?)\b", c, re.I) and PARAMETER_VALUE.search(c):
            return True
        if VALUE_REFERENCE.search(c) or (re.search(r"\bwrit\w*\b", c, re.I) and COMPUTED_FROM.search(c)):
            return True
    return False


def entry_claims(kind: str, doc: dict, rows: list[dict], facts: dict) -> list[dict]:
    """A disagreeing effects entry as an SWE1-02 claim on its requirement, an uncovered budget as an SWE1-04 claim on
    the document; REFUTED only when the requirement text states that operation (budget: resource and bound)."""
    by, out = {r["entry"]: r for r in rows}, []
    for a in doc["entries"]:
        r = by[a["entry"]]
        if kind == "effects" and not a["agrees"]:
            c = {"assertion": "requirements_inconsistent", "target_id": r["swr"], "related_ids": [],
                 "detail": f"effects entry '{r['case']}' ({_effect_text(r)}) contradicts {r['swr']}: {a['reason']}"[:300],
                 "remediation": f"align {r['swr']} and the effects entry '{r['case']}'"[:200]}
            item, key, refuted = "SWE1-02", f"{r['swr']}:{r['case']}", _states_effect(r)
            why = f"{r['swr']} states {_effect_text(r)}"
        elif kind == "budgets" and not a["covered_by"]:
            c = {"assertion": "budget_missing", "target_id": "document", "related_ids": [],
                 "detail": f"the work-order {r['resource']} budget of {r['bytes']} bytes has no requirement: "
                           f"{a['reason']}"[:300],
                 "remediation": f"add a requirement bounding {r['resource']} to {r['bytes']} bytes"}
            hit = next((s for s, q in sorted(facts["reqs"].items()) if re.search(rf"\b{r['resource']}\b",
                        q["statement"], re.I) and r["bytes"] in _numbers(q["statement"])), None)
            item, key, refuted, why = "SWE1-04", f"budget:{r['resource']}", bool(hit), f"{hit} states the bound"
        else:
            continue
        c["identity"] = identity(item, {**c, "target_id": key})
        c["decision"], c["evidence"] = ("REFUTED", why) if refuted else \
            ("STANDS", "the requirement text does not state it")
        out.append(c)
    return out


# F014 (owner 2026-10-26, "Stepwise inspector in 014"): the split that took local diagnosis from 0 to 95/95. One
# small closed question per baseline fact (temperature 0), carrying only the source it needs; each answer that
# implies a problem becomes a typed claim decided by the unchanged adjudicator. The model still decides every claim.
def gap_labels(ws: Path) -> list[str]:
    """First cells of the rows of traceability/upstream_gaps.md (the closed answer set of an input question)."""
    p = Path(ws) / "traceability/upstream_gaps.md"
    cells = re.findall(r"^\| ([^|]+?) \|", p.read_text(), re.M) if p.is_file() else []
    return sorted({c.strip() for c in cells if not c.strip().startswith(("SWR-", "-", ":"))})


FIXED_STATE = re.compile(r"\b([A-Z][A-Z0-9]*_[A-Z0-9_]+\.[A-Z][A-Z0-9_]*)\s*(?:=|is|stays|remains)\s*(?:0|1|set|clear|cleared)"
                         r"(?:\s+throughout\b|\s*,\s*reset state\b|\s+\(reset state\))", re.I)


def fixed_state_fields(text: str) -> set[str]:
    return {m.group(1) for m in FIXED_STATE.finditer(text)}


def input_label_pattern(inp: str) -> str:
    """A gaps-table row label that records an upstream input: its name, optionally followed by an explanation in
    parentheses or after a colon. Learning set 2 (2026-10-26): 'Budgets: flash 4096 bytes, ...' (h005) and one row per
    resource ('Flash budget', 'Static RAM budget', 'Stack budget'; b009) record the Budgets input too."""
    pat = rf"{re.escape(inp)}(?: \([^|]*\)|:[^|]*)?"
    if inp == "Budgets":
        pat += r"|(?:Flash|Static RAM|RAM|Stack)(?: memory)? budget(?: \([^|]*\))?"
    return pat


def input_label(labels: list[str], inp: str) -> str | None:
    """The first gaps-table row label that records an upstream input (see input_label_pattern)."""
    return next((x for x in labels if input_recorded_by(x, inp)), None)


def input_recorded_by(label: str, inp: str) -> bool:
    return bool(re.fullmatch(input_label_pattern(inp), label.strip(), re.I if inp == "Budgets" else 0))


def step_schema(answers: list[str], value: bool = False) -> dict:
    props = {"quote": {"type": "string", "maxLength": 240}, "answer": {"type": "string", "enum": answers}}
    if value:
        props["value"] = {"type": "string", "maxLength": 24}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def step_questions(ws: Path, facts: dict) -> list[dict]:
    """Every fact question of the baseline: id, item, the text asked, its closed answers and the source it reads."""
    swrs, req = sorted(facts["reqs"]), "workproducts/SWE.1/software_requirements.md"
    qs = [{"id": "startup", "item": "SWE1-03", "source": req, "answers": swrs + ["NONE"],
           "text": "Which requirement states the driver's behaviour after reset, before it is initialised or first "
                   "called? answer is its SWR id, or NONE when no requirement states it; quote its words."}]
    asil = str(json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("safety_target") or "").upper()
    if asil in ("A", "B", "C", "D"):
        # learning set 3: the seeded QM scope claim was caught only by the gate's safety-scope check, which knows only
        # the scopes registered on this factory revision; the inspector now asks this fact itself
        qs.append({"id": "safety-scope", "item": "SWE1-01", "source": SAFETY_DOC, "asil": asil,
                   "answers": ["ASIL_TARGET_KEPT", "QM_CLAIMED"],
                   "text": f"The work order targets ASIL {asil}. Does {SAFETY_DOC} keep that ASIL target (software safety "
                           "allocation pending or allocated), or claim a QM development scope with no software safety "
                           "requirements? answer ASIL_TARGET_KEPT or QM_CLAIMED; quote the words that decide."})
    labels = gap_labels(ws)
    for inp in INPUTS:
        qs.append({"id": "input-" + inp.split()[0].lower(), "item": "SWE1-05", "input": inp,
                   "source": "traceability/upstream_gaps.md", "answers": labels + ["NONE"],
                   "text": f"Which row of traceability/upstream_gaps.md records the state of the upstream input "
                           f"'{inp}'? answer is that row's first cell, or NONE when no row records this input; quote "
                           "the row."})
    for b in budget_entries(ws):
        qs.append({"id": "budget-" + b["resource"].replace(" ", "-").lower(), "item": "SWE1-04", "row": b,
                   "source": req, "answers": swrs + ["NONE"],
                   "text": f"The owner's work order fixes a {b['resource']} budget of {b['bytes']} bytes. Which "
                           f"requirement states this {b['resource']} bound? answer is its SWR id, or NONE when no "
                           f"requirement states the {b['resource']} bound; quote its words. A requirement about "
                           "another resource does not count."})
    for f in startup_fields(facts):
        qs.append({"id": "startup-" + f.lower().replace(".", "-").replace("_", "-"), "item": "SWE1-03", "field": f,
                   "source": req, "answers": swrs + ["NONE"],
                   "text": f"Which requirement states the state of {f} after reset, before the driver is first called? "
                           "answer its SWR id, or NONE when no requirement states the after-reset state of this field; "
                           "quote its words."})
    for e in effect_entries(ws, facts):
        qs.append({"id": "effect-" + e["entry"].lower(), "item": "SWE1-02", "row": e, "source": None,
                   "answers": ["set", "clear", "set_then_clear", "write", "not_stated"], "value": True,
                   "text": f"Requirement {e['swr']} reads: \"{e['statement']}\" What does this requirement state "
                           f"for the register field {e['field']} in the case '{e['case']}'? answer set, clear, "
                           "set_then_clear (a pulse: asserted and then released) or write (value: the written "
                           "value as the requirement gives it, else \"\"), or not_stated when it does not state this "
                           "field; quote the words that decide."})
    return qs


FIELD_TOKEN = re.compile(r"\b([A-Z][A-Z0-9]*_[A-Z0-9_]+)\.([A-Z][A-Z0-9_]*)\b")


def startup_requirements(facts: dict) -> dict:
    return {x: r["statement"] for x, r in facts["reqs"].items() if re.search(r"\bafter reset\b", r["statement"], re.I)}


def startup_fields(facts: dict) -> list[str]:
    """Run 10 (2026-10-26, 0008B): startup requirements per field (HSION, HSEON); removing one left the other answering
    the general startup question. Only when startup requirements name fields: then every field of those registers
    that a requirement drives (an imposed set/clear/write) is asked. A register-wide startup requirement ('shall not
    write any IWDG register') makes no per-field question."""
    named = {f"{a}.{b}" for st in startup_requirements(facts).values() for a, b in FIELD_TOKEN.findall(st)}
    regs = {f.split(".")[0] for f in named}
    driven = set()
    for r in facts["reqs"].values():
        if any(v.startswith(ACTIONS["set"] + ACTIONS["clear"] + ACTIONS["write"]) for v in imposed_verbs(r["statement"])):
            driven |= {f"{a}.{b}" for a, b in FIELD_TOKEN.findall(r["statement"]) if a in regs}
    return sorted(named | driven) if named else []


def startup_hit(facts: dict, field: str) -> str | None:
    return next((x for x, st in sorted(startup_requirements(facts).items()) if field in st), None)


def step_packet(ws: Path, bl: dict, srcs: list[dict], q: dict, model: str, sampling, findings=None,
                previous=None) -> dict:
    sources = [s for s in srcs if R._norm_path(s["path"]) == q["source"]] if q["source"] else []
    return S.packet(phase="SWE.1", task=f"inspect:step-{q['id']}", role="swe1-inspector",
                    instructions=f"Fact question on the frozen SWE.1 baseline {bl['baseline_id']}. {q['text']} "
                                 "Judge only from this question" + (" and the SOURCES." if sources else "."),
                    sources=sources, criteria=[f"{q['item']}: one baseline fact"],
                    output_schema=step_schema(q["answers"], q.get("value", False)), model=model, findings=findings,
                    previous=previous, output_reserve=512, sampling=sampling)


def step_claims(ws: Path, q: dict, doc: dict, facts: dict) -> list[dict]:
    """The claim one fact answer implies (none when the answer finds the fact), decided like every other claim."""
    a, quote = doc["answer"], doc["quote"]
    if q["id"] == "startup":
        # learning set 2 round 2 (rc1 S1-NOSTART): with the startup requirement removed, an init requirement was cited;
        # only a requirement that states the after-reset behaviour answers this question
        if a != "NONE" and (a in facts["startup"] or a in startup_requirements(facts)):
            return []
        c = _claim("reset_startup_missing", "document",
                   "no requirement states the behaviour after reset (startup state): " + quote,
                   "add a requirement stating the register state after reset")
        return adjudicate(ws, "SWE1-03", [c], facts)
    if q["id"].startswith("startup-"):
        f = q["field"]
        if a != "NONE" and f in startup_requirements(facts).get(a, ""):
            return []
        c = _claim("reset_startup_missing", "document",
                   f"no requirement states the after-reset state of {f}"
                   + (f" ({a} does not)" if a != "NONE" else "") + (f": {quote}" if quote else ""),
                   f"add a requirement stating the after-reset state of {f}")
        c["identity"] = identity("SWE1-03", {**c, "target_id": f"startup:{f}"})
        hit = startup_hit(facts, f)
        c["decision"], c["evidence"] = ("REFUTED", f"{hit} states the after-reset state of {f}") if hit else \
            ("STANDS", f"no startup requirement names {f}")
        return [c]
    if q["id"] == "safety-scope":
        if a != "QM_CLAIMED":
            return []
        from ..assurance.scope import QM_CLAIM

        c = _claim("safety_allocation_missing", "Safety allocation",
                   f"{SAFETY_DOC} claims a QM development scope in an ASIL {q['asil']} work order: {quote}",
                   f"keep the ASIL {q['asil']} target in {SAFETY_DOC} (record the pending allocation, not a QM scope)")
        c["identity"] = identity("SWE1-01", {**c, "target_id": "safety-scope"})
        doc = Path(ws) / SAFETY_DOC
        claimed = doc.is_file() and QM_CLAIM.search(doc.read_text())
        c["decision"], c["evidence"] = ("CONFIRMED", f"{SAFETY_DOC} states a QM scope") if claimed else \
            ("REFUTED", f"{SAFETY_DOC} states no QM scope")
        return [c]
    if q["id"].startswith("input-"):
        if a != "NONE" and input_recorded_by(a, q["input"]):
            return []
        c = _claim("upstream_gap_not_recorded", q["input"],
                   f"traceability/upstream_gaps.md records no state for the upstream input '{q['input']}'",
                   f"record the state of '{q['input']}' in traceability/upstream_gaps.md")
        return adjudicate(ws, "SWE1-05", [c], facts)
    if q["id"].startswith("budget-"):
        # learning set 2 (0008A S1-NOBUDGET): the stack budget was answered with the static RAM requirement; a cited
        # requirement covers the budget only when it names the resource with its byte bound (like an effects entry)
        st, row = facts["reqs"].get(a, {}).get("statement", ""), q["row"]
        stated = re.search(rf"\b{re.escape(row['resource'])}\b", st, re.I) and row["bytes"] in _numbers(st)
        covered = [a] if a != "NONE" and stated else []
        return entry_claims("budgets", {"entries": [{"entry": q["row"]["entry"], "covered_by": covered,
                                                     "reason": quote or "no requirement states it"}]}, [q["row"]], facts)
    e = q["row"]
    # a pulse requirement states both the set and the clear entry it names
    pulse = a == "set_then_clear" and e["op"] in OPPOSITE
    ranged = a == "write" and e["op"] == "write" and in_stated_range(e["statement"], e["value"])
    # learning set 3 (SPI1): a one-bit set/clear answered as 'write 1'/'write 0' (or as the requested value)
    bit = a == "write" and e["op"] in OPPOSITE and (
        _numbers(doc.get("value") or "") == {1 if e["op"] == "set" else 0}
        or (not _numbers(doc.get("value") or "") and parameterised_write(e["statement"], e["field"])))
    agrees = pulse or ranged or bit or a == e["op"] and (a != "write" or bool(_numbers(doc.get("value") or "")) and
                                                         _numbers(doc.get("value") or "") == _numbers(str(e["value"])))
    return entry_claims("effects", {"entries": [{"entry": e["entry"], "agrees": agrees,
                                                 "reason": f"{e['swr']} states {a} {doc.get('value') or ''}: {quote}"}]},
                        [e], facts)


# F014 stepwise scope coverage (learning run 2: Qwen listed behaviours by walking the requirements, so a removed
# requirement never appeared). Behaviours come from the scope sentence alone; each is then one closed question.
ACTIONS = {"set": ("set", "enable", "assert", "start"), "clear": ("clear", "disable", "release", "stop"),
           "write": ("write", "set", "load", "program"),
           # a no-write behaviour (startup: 'shall leave RCC_CR.HSION at its reset value') observes like a read
           "read": ("read", "query", "return", "report", "check", "leave", "keep", "preserve", "retain")}
BEHAVIOURS: dict = {}  # question id -> behaviour of the current visit (read by the seeded harness preflight)


def behaviour_schema(fields: list[str]) -> dict:
    row = {"type": "object", "additionalProperties": False, "required": ["phrase", "action", "register_field", "value"],
           "properties": {"phrase": {"type": "string", "minLength": 5, "maxLength": 80},
                          "action": {"type": "string", "enum": sorted(ACTIONS)},
                          "register_field": {"type": "string", "enum": fields},
                          "value": {"type": "string", "maxLength": 24}}}
    return {"type": "object", "additionalProperties": False, "required": ["behaviours"],
            "properties": {"behaviours": {"type": "array", "maxItems": 16, "items": row}}}


def behaviour_packet(ws: Path, bl: dict, srcs: list[dict], scope: str, fields: list[str], model: str, sampling,
                     findings=None, previous=None) -> dict:
    # without the requirements and the effects contract derived from them: the scope is the reference here
    hidden = {"workproducts/SWE.1/software_requirements.md", "workproducts/SWE.1/register_effects.json"}
    sources = [x for x in srcs if R._norm_path(x["path"]) not in hidden]
    instr = (f"Scope question on the frozen SWE.1 baseline {bl['baseline_id']}. Work-order scope item (written by the "
             f"owner): \"{' '.join(scope.split())}\". List every separate register behaviour this sentence requires, "
             "one action on one object each: 'A and B enable/disable' is four behaviours. Derive them only from this "
             "sentence and the hardware sources; requirements are not shown and do not matter here. action: set "
             "(enable, assert, start), clear (disable, release), write (a value), read (query a flag or state); "
             "register_field: the field the behaviour acts on, REGISTER.* for any field of one register; value: the "
             "value a write uses when the hardware sources document it (for example a key), else \"\". Leave out "
             "structure, style and API-shape constraints; an empty list when the sentence names no register behaviour.")
    return S.packet(phase="SWE.1", task="inspect:behaviours", role="swe1-inspector", instructions=instr,
                    sources=sources, criteria=["SWE1-05: coverage gaps against the work-order scope"],
                    output_schema=behaviour_schema(fields), model=model, findings=findings, previous=previous,
                    output_reserve=1024, sampling=sampling)


def behaviour_question(qid: str, b: dict, swrs: list[str]) -> dict:
    q = {"id": qid, "item": "SWE1-05", "behaviour": b, "source": "workproducts/SWE.1/software_requirements.md",
         "answers": swrs + ["NONE"],
         "text": f"The work-order scope requires this behaviour: '{b['phrase']}' ({b['action']} {b['register_field']}). "
                 "Which requirement states it? answer its SWR id, or NONE when no requirement states this behaviour; "
                 "quote its words."}
    BEHAVIOURS[qid] = b
    return q


GENERIC = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by", "with", "from", "its", "their", "into",
           "write", "writing", "written", "read", "reading", "set", "setting", "clear", "clearing", "query", "querying",
           "value", "values", "bit", "bits", "field", "register", "registers", "flag", "flags", "documented", "key",
           "keys", "driver", "function", "status", "state", "via", "through", "using", "given", "requested"}


def purpose_words(b: dict) -> set[str]:
    """What tells this behaviour apart from others on the same field ('start' vs 'refresh' for IWDG_KR.KEY writes)."""
    f = b["register_field"]
    named = {t.lower() for t in re.split(r"[._*]", f) if t}
    return {w for w in re.findall(r"[a-z][a-z0-9]{2,}", b["phrase"].lower())
            if w not in GENERIC and w not in named and not w.startswith(tuple(named))}


def behaviour_hit(facts: dict, b: dict) -> str | None:
    """A requirement that names the behaviour's field (register, for REG.*) with an action of the same kind and, when
    the phrase has them, one of its purpose words (run 3: every IWDG key write is 'write IWDG_KR.KEY'; only 'start'
    tells the start key from the refresh key). Any one word suffices: a looser match can only refute, never reject."""
    cands = candidates(facts, b)
    return next((x for x in cands if _decides(facts, cands, x, b)), None)


def _decides(facts: dict, cands: list[str], x: str, b: dict) -> bool:
    """A documented value always has to be stated; purpose words only choose among several candidates."""
    value, st = _documented_value(b), facts["reqs"][x]["statement"]
    if value:  # stated literally, inside a stated range, or supplied by a parameterised write (any value)
        return value <= _numbers(st) or in_stated_range(st, b.get("value") or "") or bool(PARAMETER.search(st)) or \
            parameterised_write(st, b["register_field"])
    if not _sequence(st, b) and _purpose_clash(st, b):  # a key sequence covers each keyed write (run 12)
        return False
    return len(cands) == 1 or _purposeful(st, b) or _sequence(st, b)


# learning set 2 (h003 S1-OMIT): with the start-key requirement removed, the refresh requirement was the one remaining
# write on IWDG_KR.KEY and was accepted for 'start key'. Key writes on one field have distinct purposes; a requirement
# that states only another purpose does not state this behaviour (a matching or unknown purpose still decides as before)
# '_' too: the API name HAL_IWDG_Start; not 'started' (a state: 'with the started watchdog running', h005 SWR-006)
KEY_PURPOSES = {"start": re.compile(r"(?:\b|_)start(?!ed\b)", re.I),
                "refresh": re.compile(r"(?:\b|_)(?:refresh|reload(?:s|ing)? the (?:watchdog )?counter)", re.I),
                "access": re.compile(r"\b(?:access|unlock|enabl\w* (?:\w+ )?(?:configuration|register) writ)", re.I),
                # round 2 (h005 S1-OMIT): the write-protect key (0x0000) was accepted for 'start key'
                "protect": re.compile(r"(?:\b|_)(?:write-protect|lock(?:s|ed|ing)?\b|no longer writable)", re.I)}


TIME_REFERENCE = re.compile(r"\b(?:after|before|until|following|once)\s+(?:the\s+)?(?:[\w-]+\s+){0,3}?key\b", re.I)


def _purpose_clash(statement: str, b: dict) -> bool:
    if b["action"] != "write":
        return False
    want = {k for k, r in KEY_PURPOSES.items() if r.search(b["phrase"])}
    # learning set 2 round 2 (h005 S1-OMIT): '... by writing 0x5555 ... after the start key' names the start key only
    # as a time reference; a reference ('after/before/until ... key') is not the requirement's own purpose
    done = TIME_REFERENCE.sub(" ", NOT_DONE.sub(" ", statement))
    have = {k for k, r in KEY_PURPOSES.items() if r.search(done)}
    return bool(want) and bool(have) and not want & have


def _sequence(statement: str, b: dict) -> bool:
    """Run 12 (IWDG-HAL rc4): SWR-001 writes 0xCCCC, then 0x5555, then 0xAAAA to IWDG_KR.KEY; purpose words cannot be
    judged against such a sequence ('register access key' is its 'enable configuration writes' step), so a requirement
    writing several distinct literal values covers each keyed write on the field. A single-write requirement (the
    IWDG-LL refresh key) still needs a purpose word, so an omitted start-key requirement stays detected. (A closed
    self-check of the citation was tried and withdrew that true S1-OMIT detection; it was removed.)"""
    written = re.findall(r"\bwrit\w*\s+(0x[0-9A-Fa-f]+)\b", statement, re.I)  # run 13: an omitted value is not written
    return b["action"] == "write" and len({int(v, 16) for v in written}) >= 2


# run 6 (2026-10-26): "clear the selected oscillator enable bit" names an action noun, not the action
NOUN_PHRASE = re.compile(r"\b(?:enable|disable|reset|ready|set|clear|start|update)\s+(?:bits?|flags?|fields?|registers?|"
                         r"values?|status)\b", re.I)


# run 7 (2026-10-26): "for an HSI enable request ... shall clear the enable bit it set" and "While no oscillator enable
# ... shall leave RCC_CR.HSION" name an action word but impose another; the imposed verbs follow "shall"
SHALL = re.compile(r"\bshall\s+(?:not\s+|only\s+|also\s+|then\s+|first\s+)?(\w+)"
                   r"(?:\s*,?\s*(?:and\s+)?then\s+(\w+)|\s+and\s+(\w+))?", re.I)  # 'assert then release' (0008B)


def imposed_verbs(statement: str) -> set[str]:
    """The verbs after 'shall' plus every 'and'/'then' verb of that clause (run 9: 'shall set RCC_CR.HSION and return
    HAL_OK upon observing RCC_SR.HSIRDY')."""
    out = {v.lower() for m in SHALL.finditer(statement) for v in m.groups() if v}
    for clause in re.findall(r"\bshall\b(.*?)(?=\.(?:\s|$)|;|$)", statement, re.I):  # a field's dot ends no clause
        out |= {v.lower() for v in re.findall(r"\b(?:and|then)\s+(?:then\s+)?(\w+)", clause, re.I)}
    return out


# learning set 2 (h005, rc1): 'shall start the watchdog by writing 0xCCCC to IWDG_KR.KEY' imposes that write; only the
# field the 'by ...ing' phrase writes to counts ('... before writing IWDG_PR.PR' in the same clause does not)
BY_GERUND = re.compile(r"\bby\s+(writing|setting|clearing|loading|programming)\s+(?:[^.;]{0,40}?\s)?(?:to|in|into)\s+"
                       r"([A-Z][A-Z0-9]*_[A-Z0-9_]+\.[A-Z][A-Z0-9_]*)", re.I)
GERUND_ACTION = {"writing": "write", "setting": "set", "clearing": "clear", "loading": "write", "programming": "write"}


def gerund_writes(statement: str) -> set[tuple[str, str]]:
    """(action, REGISTER.FIELD) pairs a 'shall ... by <verb>ing ... to FIELD' phrase imposes."""
    return {(GERUND_ACTION[g.lower()], f) for c in re.findall(r"\bshall\b(.*?)(?=\.(?:\s|$)|;|$)", statement, re.I)
            for g, f in BY_GERUND.findall(c)}


READ_WORDS = re.compile(r"\b(?:read|quer|return|report|check|observ|poll|wait|leave|keep|preserv|retain)\w*", re.I)


WAIT = re.compile(r"^\s*(?:wait|poll)\w*\b", re.I)  # the behaviour is the wait ('HSI enable with ready-flag wait' is not)
CONFIGURE = re.compile(r"\b(?:configur\w*|select\w*|choos\w*|word length|data width)\b", re.I)


def candidates(facts: dict, b: dict) -> list[str]:
    """Requirements naming the behaviour's field (register, for REG.*) and imposing an action of the same kind."""
    f = b["register_field"]
    name = f.split(".")[0] if WILDCARD.match(f) else f
    bare = name.split(".")[-1]
    if b["action"] in ("set", "clear") and WAIT.search(b["phrase"]):
        # replay of learning set 1 (rc4 'wait until PVU is cleared', answered as clear): a wait observes the flag the
        # hardware changes; it is stated where the requirement names the flag as a condition, like any read
        b = {**b, "action": "read"}
    # run 8: a register write is how a bit is set or cleared ('Enable write access to IWDG_PR' is SWR-003's
    # 'shall write 0x00005555 to IWDG_KR.KEY')
    kind = ACTIONS[b["action"]] + (ACTIONS["write"] if b["action"] in ("set", "clear") else ())
    # learning set 3 (USART1): 'Configure word length M0' is a configuration write whatever action the answer names, and
    # a configuration write is stated by a requirement that sets, clears or writes the field ('clear ... M0 ... to 0')
    if b["action"] in ("write", "set", "clear") and CONFIGURE.search(b["phrase"]):
        kind = ACTIONS["write"] + ("set", "clear")
    def acts(statement: str) -> bool:
        if b["action"] == "read":  # a read anywhere in the requirement (refuting a read claim can only cost a miss)
            return bool(READ_WORDS.search(NOUN_PHRASE.sub(" ", statement)))
        return any(v.startswith(kind) for v in imposed_verbs(statement))

    def by_gerund(statement: str) -> bool:
        return b["action"] in ("write", "set", "clear") and any(
            fld == f and (a == b["action"] or b["action"] == "write" or a == "write") for a, fld in gerund_writes(statement))

    def names(statement: str) -> bool:
        # learning set 3 (SPI1/USART1 S1-OMIT): 'while SPI_CR1.SPE is 0, ... shall write ... to SPI_CFG2.MASTER' names SPE
        # only as a precondition; a set/clear/write must name the field in what the requirement imposes (after 'shall')
        text = statement if b["action"] == "read" else statement[statement.lower().find("shall"):] \
            if "shall" in statement.lower() else statement
        return name in text or bool(re.search(rf"\b{re.escape(bare)}\b", text))

    return [x for x, r in sorted(facts["reqs"].items()) if (names(r["statement"]) and acts(r["statement"]))
            or by_gerund(r["statement"])]


def _documented_value(b: dict) -> set[int]:
    return _numbers(b.get("value") or "") if b["action"] == "write" else set()


# run 10 (IWDG-HAL rc4): purpose words fail on synonyms ('register access key' is 'enable configuration writes'); a
# documented value is exact: the start key 0xCCCC is stated only by the start requirement
def _purposeful(statement: str, b: dict) -> bool:
    # run 4 (2026-10-26): purpose words decide only between several candidates; SWR-006 'write the requested value to
    # IWDG_RLR.RL' is the one requirement on that field, although it never says 'reload'. Run 5: and only for writes
    # (different values on one field are different behaviours); reading a flag is one behaviour however many
    # requirements split it by value ('query the PVU update flag': SWR-007/SWR-008 return 1U/0U)
    if b["action"] != "write":
        return True
    purpose = purpose_words(b)
    done = NOT_DONE.sub(" ", statement)  # run 13: 'leaving the already started watchdog running' starts nothing
    return not purpose or any(re.search(rf"\b{w}", done, re.I) for w in purpose)


NOT_DONE = re.compile(r"\b(?:leav(?:e|es|ing)|omit(?:s|ting)?|without|except)\b[^,;]*?(?=,|;|\band\b|\.(?:\s|$)|$)", re.I)


def states_behaviour(facts: dict, cited: str, b: dict) -> bool:
    cands = candidates(facts, b)
    return cited in cands and _decides(facts, cands, cited, b)


def relevant(b: dict) -> bool:
    """Run 11 (IWDG-HAL rc4): 'The LL header is provided read-only ... not modified' became the behaviour 'LL header is
    not modified' on IWDG_KR.KEY. A register behaviour's phrase shares a word with its register or field name (the
    peripheral prefix aside): 'register access key' (KEY), 'HSI oscillator enable' (HSION), 'AHB1 clock' (AHB1ENR)."""
    parts = [t.lower() for t in re.split(r"[._]", b["register_field"]) if t and t != "*"]
    names = [t for t in parts[1:] if len(t) >= 2]  # without the peripheral prefix (RCC, IWDG)
    words = re.findall(r"[a-z][a-z0-9]+", b["phrase"].lower())
    return any(w.startswith(n) or n.startswith(w) for w in words if len(w) >= 2 for n in names)


def behaviour_claims(b: dict, doc: dict, facts: dict) -> list[dict]:
    """A cited requirement must itself state the behaviour (run 3: 'enable HSI' was answered with a requirement on the
    same field that clears it, and the omitted requirement went unnoticed); an unsupported citation counts as NONE."""
    cited = doc["answer"]
    if cited != "NONE" and states_behaviour(facts, cited, b):
        return []
    f, act = b["register_field"], b["action"]
    why = f"{cited} does not state it" if cited != "NONE" else doc["quote"]
    c = _claim("scope_behaviour_uncovered", "document",
               f"scope behaviour '{b['phrase']}' ({act} {f}) has no requirement: {why}",
               f"add a requirement for {act} {f}")
    c["identity"] = identity("SWE1-05", {**c, "target_id": f"{f}:{act}"})
    hit = behaviour_hit(facts, b)
    c["decision"], c["evidence"] = ("REFUTED", f"{hit} states {act} on {f}") if hit else \
        ("STANDS", "no requirement states this behaviour")
    if not hit and f in facts.get("fixed_state", ()):  # learning set 3 (USART1 FIFOEN): an assumption, not a write
        c["decision"], c["evidence"] = "REFUTED", f"the baseline records {f} as a fixed state assumption"
    return [c]


def check_question(iid: str, c: dict, facts: dict) -> dict:
    """Run 10 (IWDG-HAL rc4): a broad item's judgement no rule decides ('SWR-007 is inconsistent with SWR-002',
    'SWR-009 is infeasible') stood and rejected a clean baseline. Stepwise: one closed check per such claim."""
    ids = [x for x in [c["target_id"], *(c.get("related_ids") or [])] if x in facts["reqs"]]
    texts = " ".join(f"{x}: \"{facts['reqs'][x]['statement']}\"" for x in ids)
    return {"id": f"check-{iid.lower()}-{c['identity']}", "item": iid, "source": "workproducts/SWE.1/software_requirements.md",
            "answers": ["TRUE", "FALSE"],
            "text": f"A reviewer claims about checklist item {iid}: \"{render_claim(c)}\" {texts} Is this claim true of the "
                    "baseline? answer TRUE only when the requirement texts themselves show the problem; FALSE when they do "
                    "not (requirements for different conditions are not inconsistent; a requirement a test can check is not "
                    "infeasible; a recorded open point is documented). Quote the decisive words."}


def withdraw_unconfirmed(c: dict, doc: dict) -> dict:
    if doc["answer"] == "FALSE":
        return {**c, "decision": "WITHDRAWN", "evidence": f"closed check found it false: {doc['quote'][:160]}"}
    return c


def _claim(assertion: str, target: str, detail: str, remediation: str) -> dict:
    return {"assertion": assertion, "target_id": target, "related_ids": [], "detail": detail[:300],
            "remediation": remediation[:200]}


def lessons_dir(ws: Path) -> Path | None:
    """The inspection lesson set for this work order: the harness setting, else the profile flag
    structured.inspection_lessons (the Codex/Claude line never reaches this inspector)."""
    from ..knowledge import inspection as IL
    from .swe2 import _structured_flag

    if LESSONS["dir"]:
        return Path(LESSONS["dir"])
    return IL.LESSON_DIR if _structured_flag(ws, "inspection_lessons") else None


def item_lessons(ws: Path, item_id: str, srcs: list[dict]) -> list[dict]:
    """F011-T044: the validated lessons for one item, by phase, item, layer and the work products in the packet."""
    from ..knowledge import inspection as IL
    from ..layer import layer_of

    d = lessons_dir(ws)
    return IL.select("SWE.1", item_id, layer_of(ws), {s["path"] for s in srcs}, d,
                     include_proposed=bool(LESSONS["dir"] and LESSONS["include_proposed"])) if d else []


def lesson_source(lessons: list[dict]) -> dict | None:
    from ..knowledge import inspection as IL

    text = IL.render(lessons)
    return {"path": LESSON_SOURCE, "sha256": sha256_bytes(text.encode()), "text": text} if text else None


def item_packet(ws: Path, item: dict, bl: dict, srcs: list[dict], targets: list[str], model: str, findings=None,
                previous=None, lessons: list[dict] | None = None, sampling: dict | None = None,
                paths: list[str] | None = None) -> dict:
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
    ref = lesson_source(lessons or [])
    if ref:  # reference data with provenance, after the frozen work products; never part of the instructions
        srcs = [*srcs, ref]
    return S.packet(phase="SWE.1", task=f"inspect:{iid}", role="swe1-inspector", instructions=instr, sources=srcs,
                    criteria=[f"{iid}: {' '.join(str(item['criterion']).split())}"],
                    output_schema=claim_schema(iid, targets, paths), model=model, findings=findings, previous=previous,
                    output_reserve=2048, sampling=sampling)


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
    opts = inspector_options(Path(ws), model)
    extra = 2 * len(scope_items(Path(ws))) if opts["coverage"] else 0  # one call and one repair per scope item
    extra += 4 if opts["entries"] else 0  # the effects and budget questions
    if opts["stepwise"]:  # one call and one repair per fact question, per scope sentence and per scope behaviour
        extra += 2 * len(step_questions(Path(ws), baseline_facts(Path(ws)))) + 2 * 17 * len(scope_items(Path(ws)))
        extra += 2 * 10 * len(ASSERTIONS)  # at most ten claims per item, one closed check (and a repair) each
    budget, _f = V.open_visit(Path(ws), "SWE.1-inspect", resume, list,
                              (max_calls or {a.id: a for a in load_agents()[0]}["swe1-inspector"].max_turns) + extra,
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
    opts = inspector_options(ws, model)
    smp = opts["sampling"]
    cov_claims, cov_record = [], []
    if opts["stepwise"]:  # F014: behaviours from each scope sentence, then one closed question per behaviour
        swrs, fields, asked = sorted(facts["reqs"]), source_fields(srcs), set()
        BEHAVIOURS.clear()
        for i, sc in enumerate(scope_items(ws)):
            brec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:behaviours-{i}",
                              lambda fi, pr, sc=sc: behaviour_packet(ws, bl, srcs, sc, fields, model, smp, fi, pr),
                              lambda d: [], budget)
            if brec["status"] != "VALID":
                issues += [f"behaviours-{i}: {e}" for e in brec["errors"][:3]]
                continue
            got, answers = [], []
            for j, b in enumerate(brec["doc"]["behaviours"]):
                key = (b["register_field"], b["action"], frozenset(purpose_words(b)))
                if key in asked:
                    continue
                asked.add(key)
                if not relevant(b):  # a non-register sentence mapped onto a field: not asked, recorded
                    answers.append({"question": f"behaviour-{i}-{j}", "skipped": "NOT_A_REGISTER_BEHAVIOUR"})
                    continue
                q = behaviour_question(f"behaviour-{i}-{j}", b, swrs)
                qrec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:step-{q['id']}",
                                  lambda fi, pr, q=q: step_packet(ws, bl, srcs, q, model, smp, fi, pr), lambda d: [],
                                  budget)
                if qrec["status"] != "VALID":
                    issues += [f"step-{q['id']}: {e}" for e in qrec["errors"][:3]]
                    continue
                got += behaviour_claims(b, qrec["doc"], facts)
                answers.append({"question": q["id"], "answer": qrec["doc"]})
            cov_claims += got
            cov_record.append({"scope": sc, "behaviours": brec["doc"]["behaviours"], "answers": answers, "claims": got})
    elif opts["coverage"]:  # F011-T049: one decomposed coverage question per in-scope work-order scope item
        swrs = sorted(facts["reqs"])
        for i, sc in enumerate(scope_items(ws)):
            crec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:coverage-{i}",
                              lambda fi, pr, sc=sc: coverage_packet(ws, bl, srcs, sc, swrs, model, smp, fi, pr,
                                                                    source_fields(srcs) if opts["stepwise"] else None),
                              lambda d: validate_coverage(d, set(swrs)), budget)
            if crec["status"] != "VALID":
                issues += [f"coverage-{i}: {e}" for e in crec["errors"][:3]]
                continue
            got = coverage_claims(sc, crec["doc"], facts)
            cov_claims += got
            cov_record.append({"scope": sc, "behaviours": crec["doc"]["behaviours"], "claims": got})
    ent_claims, ent_record = {}, []
    if opts["entries"]:  # F011-T054: one effects question and one budget question, each judged entry by entry
        swrs = sorted(facts["reqs"])
        for kind, rows, item in (("effects", effect_entries(ws, facts), "SWE1-02"),
                                 ("budgets", budget_entries(ws), "SWE1-04")):
            if not rows:
                continue
            ids = [r["entry"] for r in rows]
            erec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:{kind}",
                              lambda fi, pr, kind=kind, rows=rows: entries_packet(ws, bl, srcs, kind, rows, swrs, model,
                                                                                  smp, fi, pr),
                              lambda d, ids=ids: validate_entries(d, ids), budget)
            if erec["status"] != "VALID":
                issues += [f"{kind}: {e}" for e in erec["errors"][:3]]
                continue
            got = entry_claims(kind, erec["doc"], rows, facts)
            ent_claims[item] = ent_claims.get(item, []) + got
            ent_record.append({"kind": kind, "answers": erec["doc"]["entries"], "claims": got})
    step_record = []
    if opts["stepwise"]:  # F014: one closed question per baseline fact; answers join their item's claims
        for q in step_questions(ws, facts):
            srec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:step-{q['id']}",
                              lambda fi, pr, q=q: step_packet(ws, bl, srcs, q, model, smp, fi, pr), lambda d: [], budget)
            if srec["status"] != "VALID":
                issues += [f"step-{q['id']}: {e}" for e in srec["errors"][:3]]
                continue
            got = step_claims(ws, q, srec["doc"], facts)
            ent_claims[q["item"]] = ent_claims.get(q["item"], []) + got
            step_record.append({"question": q["id"], "answer": srec["doc"], "claims": got})
    for it in items:
        if it["id"] not in ASSERTIONS:
            issues.append(f"{it['id']}: no claim catalogue for this item (LRTX_SEMANTIC_INSPECTION_ITEM_UNKNOWN)")
            continue
        task = f"inspect:{bl['baseline_hash'][:16]}:{it['id']}"
        les = item_lessons(ws, it["id"], srcs)
        ipaths = paths | ({LESSON_SOURCE} if les else set())
        # F014 stepwise: evidence_checked is a closed list (Omniverse2 learning run: bare or misplaced paths made three
        # inspections record nothing)
        offered = sorted(ipaths) if opts["stepwise"] else None
        rec = V.run_task(ws, "SWE.1", task,
                         lambda fi, pr, it=it, les=les, offered=offered: item_packet(ws, it, bl, srcs, targets, model,
                                                                                     fi, pr, les, smp, offered),
                         lambda d, ipaths=ipaths: validate(d, ipaths), budget)
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
                             lambda fi, pr, it=it, les=les, offered=offered: item_packet(ws, it, bl, srcs, targets,
                                                                                         model, fi, pr, les, smp,
                                                                                         offered),
                             lambda d2, ipaths=ipaths: validate(d2, ipaths), budget, refut)
            if rec["status"] == "VALID":
                d = rec["doc"]
                judged = adjudicate(ws, it["id"], d["claims"], facts)
                rounds.append({"verdict": d["verdict"], "claims": judged})
        if opts["stepwise"]:  # F014: every standing judgement of this item gets one closed check
            checked = []
            for c in judged:
                if c["decision"] != "STANDS":
                    checked.append(c)
                    continue
                q = check_question(it["id"], c, facts)
                crec = V.run_task(ws, "SWE.1", f"inspect:{bl['baseline_hash'][:16]}:step-{q['id']}",
                                  lambda fi, pr, q=q: step_packet(ws, bl, srcs, q, model, smp, fi, pr), lambda d: [],
                                  budget)
                checked.append(withdraw_unconfirmed(c, crec["doc"]) if crec["status"] == "VALID" else c)
            if checked != judged:
                rounds.append({"checks": [c for c in checked if c["decision"] == "WITHDRAWN"]})
            judged = checked
        if it["id"] == "SWE1-05" and cov_claims:  # the coverage answers join the coverage item, decided the same way
            judged = judged + cov_claims
            rounds.append({"coverage": cov_claims})
        if ent_claims.get(it["id"]):  # the entry answers join their item, decided the same way
            judged = judged + ent_claims[it["id"]]
            rounds.append({"entries": ent_claims[it["id"]]})
        standing = [c for c in judged if c["decision"] not in ("REFUTED", "WITHDRAWN")]
        verdict = "FAIL" if standing else "PASS"
        outcome = "ADJUDICATED_PASS" if d["verdict"] == "FAIL" and not standing else verdict
        record[it["id"]] = {"outcome": outcome, "rounds": rounds,
                            "lessons": [{k: x[k] for k in ("id", "version", "sha256")} for x in les]}
        verdicts[it["id"]] = {"verdict": verdict, "findings": [render_claim(c) for c in standing][:10],
                              "evidence_refs": [f"configuration/baselines/SWE.1/{bl['baseline_id']}.json",
                                                *[e for e in d["evidence_checked"]  # lessons are no work product
                                                  if R._norm_path(e) != LESSON_SOURCE][:8]]}
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
                                                  "result": res, "items": record, "inspector": "review_semantic",
                                                  "options": opts, "coverage": cov_record,
                                                  "entries": ent_record, "steps": step_record})
    # the last verdict round: coverage, entry and fact answers are appended as rounds without their own verdict
    notes = [f"LRTX_ADJUDICATED_PASS:{i}: {len(next(x for x in reversed(r['rounds']) if 'claims' in x)['claims'])} "
             "claim(s) refuted by the baseline" for i, r in record.items() if r["outcome"] == "ADJUDICATED_PASS"]
    status = "PASS" if res["status"] == "PASS" else "REWORK"
    return R._reply(ws, "SWE.1", status, list(res.get("issues") or []) + notes, budget,
                    list(res.get("artifact_refs") or []))
