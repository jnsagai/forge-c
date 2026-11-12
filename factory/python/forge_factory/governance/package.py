"""Feature 020 T012 (research R3 part 2, FR-001, FR-004..FR-006): the governance package of a functional-level order.

The first SWE.1 node (`swe1_governance`, role swe1-author) asks the model for the module's actors, use cases (each
naming the in-scope delivered functions it exercises), assumptions and open points, in ONE structured task over the
governance inventory and the input section index - never the delivered code or a chapter text. The answer is
validated deterministically (schema, known actors, in-scope functions/features, unique ids) and so is its coverage:
every in-scope delivered function and every in-scope RM feature must belong to a use case or an open point (a use case
that covers nothing in scope is reported as unused, not refused). Uncovered items go back to the model as findings for
a localized repair; what is still uncovered is COVERAGE_FAIL and the check node (`swe1_governance_check`) stops SWE.1
before the author. Owner use cases (work order `use_cases_owner`) are shown to the model and merged with origin
`owner`.

Outputs: `workproducts/SWE.1/governance/governance-package.json` (contracts/governance-package.schema.json) and `.md`;
`package_version` is the sha256 of the canonical package without itself; the run records it with the state in
`.forge-run/lrtx/SWE.1/governance/status.json` (GENERATED -> COVERAGE_PASS | COVERAGE_FAIL). Lessons are not offered
to this task (they are SWE.1 requirement-writing lessons; the packet stays a function of the order's inputs)."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, pretty_json, sha256_bytes, sha256_file, utc_now
from ..lrtx import structured as S
from ..lrtx import visit as V
from . import inventory as GI
from . import level as L

SCHEMA = "forge-c/governance-package/1"
TASK, ROLE, NODE = "governance", "swe1-author", "swe1_governance"
VISIT = "SWE.1/governance"  # visit state, checkpoint and visit log under .forge-run/lrtx/ (apart from the author's)
OUT_JSON = "workproducts/SWE.1/governance/governance-package.json"
OUT_MD = "workproducts/SWE.1/governance/governance-package.md"
STATUS = "SWE.1/governance/status.json"
REPLY = "SWE.1/governance-reply.json"
PASS, FAIL = "COVERAGE_PASS", "COVERAGE_FAIL"

_S = {"type": "string", "minLength": 1}
_IDS = {"type": "array", "items": _S}
ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["actors", "use_cases", "assumptions", "open_points"],
    "properties": {
        "actors": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False, "required": ["actor_id", "name", "description"],
            "properties": {"actor_id": _S, "name": _S, "description": {"type": "string"}}}},
        "use_cases": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["use_case_id", "title", "actor_id", "goal", "functions", "rm_features"],
            "properties": {"use_case_id": _S, "title": _S, "actor_id": _S, "goal": _S, "functions": _IDS,
                           "rm_features": _IDS}}},
        "assumptions": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["assumption_id", "text"],
            "properties": {"assumption_id": _S, "text": _S}}},
        "open_points": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["open_point_id", "text", "concerns"],
            "properties": {"open_point_id": _S, "text": _S, "concerns": _IDS}}},
    },
}
INSTRUCTIONS = (
    "Prepare the governance package of the module in the governance inventory, before any requirement is written. "
    "Name the actors that use the module's public API (application software, the interrupt context, the platform "
    "integration hooks, ...). Write the use cases of the driver: each names its actor, its goal and EVERY in-scope "
    "delivered function it exercises (exact names from the inventory 'api' entries with scope_class 'in') and the "
    "in-scope reference-manual features it relies on (section ids from the inventory 'rm_features' with scope_class "
    "'in'). Every in-scope function and every in-scope feature must belong to at least one use case; when the inputs "
    "do not describe one, record an open point whose 'concerns' name it instead of inventing behaviour. Record the "
    "assumptions you make. Use the inventory and the section index only: the delivered code is the implementation "
    "under analysis, never a source, and out-of-scope or not-delivered capabilities get no use case.")
CRITERIA = [
    "every use case names an actor_id from 'actors'",
    "use case functions are in-scope delivered functions of the inventory; rm_features are in-scope inventory features",
    "every in-scope function and in-scope feature is in a use case or in an open point's concerns",
    "ids are unique within actors, use cases, assumptions and open points",
]


def _manifest(ws: Path) -> dict:
    return json.loads((Path(ws) / ".forge-run/manifest.json").read_text())


def owner_use_cases(ws: Path) -> list[dict]:
    return [{**u, "origin": "owner"} for u in _manifest(ws).get("swe1_use_cases_owner") or []]


def skill_reference() -> dict:
    """The functional-level reference of the role's skill (T014, D15), bound by its hash like any source."""
    from ..registry.skillgen import FUNCTIONAL_REFERENCES

    rel = FUNCTIONAL_REFERENCES[ROLE]
    data = (REPO_ROOT / rel).read_bytes()
    return {"path": rel, "sha256": sha256_bytes(data), "text": data.decode("utf-8")}


def packet(ws: Path, model: str, findings: list[str] | None = None, previous: dict | None = None) -> dict:
    own = owner_use_cases(ws)
    instructions = INSTRUCTIONS + (
        "\nOWNER USE CASES (provided by the owner; they are merged into the package as they are - do not repeat "
        "them, but you may reference their actor_id):\n" + json.dumps(own, indent=1) if own else "")
    return S.packet(phase="SWE.1", task=TASK, role=ROLE, instructions=instructions,
                    sources=[S.source(ws, GI.OUT), S.source(ws, "inputs/index.md"), skill_reference()],
                    criteria=CRITERIA,
                    output_schema=ANSWER_SCHEMA, findings=findings, previous=previous, model=model, with_lessons=False)


def _scope(inv: dict) -> tuple[list[str], list[str], set[str]]:
    fns = [a["function"] for a in inv["api"] if a["scope_class"] == "in"]
    feats = [f["feature"] for f in inv["rm_features"] if f["scope_class"] == "in"]
    known = {a["function"] for a in inv["api"]} | {f["feature"] for f in inv["rm_features"]} | \
        {i["input_id"] for i in inv["inputs"]}
    return fns, feats, known


def validate_answer(ws: Path, doc: dict) -> list[str]:
    """Structural findings of a model answer (schema, actors, in-scope names, unique ids); coverage is separate."""
    errs = S.validate(doc, ANSWER_SCHEMA)
    if errs:
        return errs
    inv = GI.load(ws)
    fns, feats, known = _scope(inv)
    in_f, in_t = set(fns), set(feats)
    actors = {a["actor_id"] for a in doc["actors"]}
    own = {u["use_case_id"] for u in owner_use_cases(ws)}
    for key, idk in (("actors", "actor_id"), ("use_cases", "use_case_id"), ("assumptions", "assumption_id"),
                     ("open_points", "open_point_id")):
        ids = [x[idk] for x in doc[key]] + (sorted(own) if key == "use_cases" else [])
        errs += [f"{key}: {i} is a duplicate id" for i in dict.fromkeys(i for i in ids if ids.count(i) > 1)]
    for u in doc["use_cases"]:
        uc = u["use_case_id"]
        if u["actor_id"] not in actors:
            errs.append(f"{uc}: unknown actor {u['actor_id']} (declare it in 'actors')")
        errs += [f"{uc}: {f} is not an in-scope delivered function of the inventory" for f in u["functions"]
                 if f not in in_f]
        errs += [f"{uc}: {f} is not an in-scope RM feature of the inventory" for f in u["rm_features"]
                 if f not in in_t]
    for o in doc["open_points"]:
        errs += [f"{o['open_point_id']}: concern {c} is no delivered function, RM feature or input id of the inventory"
                 for c in o["concerns"] if c not in known]
    return errs


def coverage(inv: dict, use_cases: list[dict], open_points: list[dict]) -> dict:
    fns, feats, _known = _scope(inv)
    in_f, in_t = set(fns), set(feats)
    named = {x for u in use_cases for x in [*u.get("functions", []), *u.get("rm_features", [])]} | \
        {c for o in open_points for c in o.get("concerns", [])}
    return {"uncovered_functions": [f for f in fns if f not in named],
            "uncovered_features": [f for f in feats if f not in named],
            "unused_use_cases": [u["use_case_id"] for u in use_cases
                                 if not ({*u.get("functions", [])} & in_f or {*u.get("rm_features", [])} & in_t)]}


def coverage_findings(cov: dict) -> list[str]:
    return ([f"COVERAGE_FAIL: in-scope function {f} is in no use case and no open point - add it to the use case "
             "that exercises it, or record an open point naming it" for f in cov["uncovered_functions"]] +
            [f"COVERAGE_FAIL: in-scope RM feature {f} is in no use case and no open point - add it to the use case "
             "that relies on it, or record an open point naming it" for f in cov["uncovered_features"]])


def _use_cases(ws: Path, doc: dict) -> list[dict]:
    return [{**u, "origin": "generated"} for u in doc["use_cases"]] + owner_use_cases(ws)


def check_answer(ws: Path, doc: dict) -> list[str]:
    errs = validate_answer(ws, doc)
    return errs or coverage_findings(coverage(GI.load(ws), _use_cases(ws, doc), doc["open_points"]))


def assemble(ws: Path, doc: dict) -> dict:
    use_cases = _use_cases(ws, doc)
    pkg = {"schema": SCHEMA, "inventory_sha256": sha256_file(Path(ws) / GI.OUT), "actors": doc["actors"],
           "use_cases": use_cases, "assumptions": doc["assumptions"], "open_points": doc["open_points"],
           "coverage": coverage(GI.load(ws), use_cases, doc["open_points"])}
    return {**pkg, "package_version": version(pkg)}


def version(pkg: dict) -> str:
    return sha256_bytes(canonical_json({k: v for k, v in pkg.items() if k != "package_version"}))


def state_of(pkg: dict) -> str:
    c = pkg["coverage"]
    return FAIL if c["uncovered_functions"] or c["uncovered_features"] else PASS


def render_md(pkg: dict, inv: dict) -> str:
    c = pkg["coverage"]
    lines = [f"# Governance package - module {inv['module']}", "",
             f"- Package version: `{pkg['package_version']}`", f"- Inventory: `{pkg['inventory_sha256']}`",
             f"- Coverage: {state_of(pkg)}", "", "## Input register", "",
             "| Input | Name | Revision | Role | SHA-256 |", "|---|---|---|---|---|"]
    lines += [f"| {i['input_id']} | {i['name']} | {i.get('revision', '-')} | {i['role']} | `{i['sha256'][:16]}` |"
              for i in inv["inputs"]]
    lines += ["", "## Scope", "", "| Function | Component | Class | Group |", "|---|---|---|---|"]
    lines += [f"| {a['function']} | {a['component']} | {a['scope_class']} | {a['scope_group']} |" for a in inv["api"]]
    lines += ["", "RM features: " + (", ".join(f"{f['feature']} ({f['scope_class']})" for f in inv["rm_features"])
                                     or "none"), "", "Not delivered:"]
    lines += [f"- {n.get('capability')}: {n.get('note', '')}" for n in inv["not_delivered"]] or ["- none"]
    lines += ["", "## Actors", ""] + [f"- **{a['actor_id']}** {a['name']}: {a['description']}" for a in pkg["actors"]]
    lines += ["", "## Use cases", ""]
    for u in pkg["use_cases"]:
        lines += [f"### {u['use_case_id']} {u['title']} ({u['origin']})", "", f"- Actor: {u['actor_id']}",
                  f"- Goal: {u['goal']}", f"- Functions: {', '.join(u['functions']) or 'none'}",
                  f"- RM features: {', '.join(u.get('rm_features') or []) or 'none'}", ""]
    lines += ["## Assumptions", ""] + ([f"- **{a['assumption_id']}** {a['text']}" for a in pkg["assumptions"]]
                                       or ["- none"])
    lines += ["", "## Open points", ""] + ([f"- **{o['open_point_id']}** {o['text']} (concerns: "
                                            f"{', '.join(o['concerns']) or '-'})" for o in pkg["open_points"]]
                                           or ["- none"])
    lines += ["", "## Coverage", "", f"- Uncovered functions: {', '.join(c['uncovered_functions']) or 'none'}",
              f"- Uncovered RM features: {', '.join(c['uncovered_features']) or 'none'}",
              f"- Unused use cases: {', '.join(c['unused_use_cases']) or 'none'}", ""]
    return "\n".join(lines)


def _reply(ws: Path, status: str, issues: list[str], budget: dict | None = None, artifacts: list[str] | None = None):
    doc = {"status": status, "artifacts": artifacts or [], "issues": [i[:V.ISSUE_MAX] for i in issues[:20]],
           "next_action": "next" if status == "PASS" else "rework"}
    S.record(ws, REPLY, doc)
    if status != "CONTINUE":
        V.close_visit(budget)
    p = Path(ws) / ".forge-run/lrtx" / VISIT / "visits.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"at": utc_now(), "status": status, "calls": (budget or {}).get("calls", 0),
                            "issues": [i[:300] for i in issues[:10]]}, sort_keys=True) + "\n")
    return doc


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """The governance node: one structured task, then the package, its coverage state and the run record."""
    from ..registry.agents import load_agents

    ws = Path(ws)
    if L.of_workspace(ws) != L.FUNCTIONAL:
        return _reply(ws, "FAILED", ["GOVERNANCE_NOT_A_FUNCTIONAL_ORDER"])
    if not (ws / GI.OUT).is_file():
        return _reply(ws, "FAILED", [f"GOVERNANCE_INVENTORY_MISSING:{GI.OUT}"])
    role = {a.id: a for a in load_agents()[0]}[ROLE]
    budget, _ = V.open_visit(ws, VISIT, resume, lambda: [], V.author_call_limit(ws, "SWE.1", role.max_turns, max_calls),
                             time_budget_s)
    try:
        rec = V.run_task(ws, VISIT, TASK, lambda fi, pr: packet(ws, model, fi, pr), lambda d: check_answer(ws, d),
                         budget)
    except V.Continue as c:
        return _reply(ws, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    doc = rec.get("doc")
    invalid = ["GOVERNANCE_ANSWER_MISSING"] if doc is None else validate_answer(ws, doc)
    if invalid:
        S.record(ws, STATUS, {"state": "ANSWER_INVALID", "package_version": None,
                              "inventory_sha256": sha256_file(ws / GI.OUT), "uncovered": []})
        return _reply(ws, "FAILED", ["GOVERNANCE_ANSWER_INVALID: " + e for e in invalid] +
                      [str(e) for e in (rec.get("errors") or []) if e not in invalid][:5], budget)
    pkg = assemble(ws, doc)
    state = state_of(pkg)
    V.write_scoped(ws, {OUT_JSON: pretty_json(pkg), OUT_MD: render_md(pkg, GI.load(ws))}, NODE)
    uncovered = [f"function:{f}" for f in pkg["coverage"]["uncovered_functions"]] + \
        [f"feature:{f}" for f in pkg["coverage"]["uncovered_features"]]
    S.record(ws, STATUS, {"state": state, "package_version": pkg["package_version"],
                          "inventory_sha256": pkg["inventory_sha256"], "uncovered": uncovered})
    if state == PASS:
        return _reply(ws, "PASS", [], budget, [OUT_JSON, OUT_MD])
    return _reply(ws, "FAILED", [f"COVERAGE_FAIL: uncovered {u}" for u in uncovered], budget, [OUT_JSON, OUT_MD])


def status(ws: Path) -> dict | None:
    p = Path(ws) / ".forge-run/lrtx" / STATUS
    return json.loads(p.read_text()) if p.is_file() else None


def check(ws: Path) -> int:
    """The check node: 0 when the recorded package passes coverage and is the current, unchanged package for the
    current inventory (SWE.1 may start), else 1 with the reason (SWE.1 stops before the author)."""
    ws = Path(ws)
    st = status(ws)
    if st is None:
        reason = ["GOVERNANCE_NOT_GENERATED"]
    elif st["state"] != PASS:
        reason = [f"{st['state']}: uncovered {u}" for u in st.get("uncovered") or []] or [st["state"]]
    else:
        try:
            pkg = json.loads((ws / OUT_JSON).read_text())
        except (OSError, ValueError):
            pkg = None
        reason = []
        if pkg is None or pkg.get("package_version") != st["package_version"] or version(pkg) != st["package_version"]:
            reason.append("GOVERNANCE_PACKAGE_CHANGED: the package differs from the recorded version")
        elif sha256_file(ws / GI.OUT) != pkg["inventory_sha256"] or state_of(pkg) != PASS:
            reason.append("GOVERNANCE_PACKAGE_STALE: the inventory changed after the package was generated")
    print(json.dumps({"governance_check": "PASS" if not reason else "FAIL", "issues": reason[:20]}))
    return 0 if not reason else 1
