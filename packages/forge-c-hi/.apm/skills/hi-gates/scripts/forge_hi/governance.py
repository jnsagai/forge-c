"""The `governance` gate: scope and coverage of the entry stage, checked before and after the requirements are written.

Ported from Forge-C feature 020 (the SWE.1 governance package and its deterministic coverage check), generalised from
driver API functions to the inputs of any project. Before the first requirement is written, the author records in
``hi/<entry stage>/governance.json`` the actors, the use cases (each naming the stakeholder needs it serves and, for a
reference document, the sections it relies on), what is deliberately out of scope, the assumptions and the open points.
The gate then checks, without a model:

- GOV-MISSING / GOV-UNREADABLE / GOV-SCHEMA   the package exists and matches contracts/governance.schema.json;
- GOV-DUPLICATE-ID                            ids are unique;
- GOV-ACTOR-UNKNOWN                           every use case names a declared actor;
- GOV-REF-UNKNOWN                             every need, constraint or section named exists in the inputs or the
                                              document scope (constraints may be named but need no use case);
- GOV-NEED-UNCOVERED                          every stakeholder need is in a use case, out of scope, or an open point;
- GOV-SECTION-UNCOVERED                       every in-scope document section is in a use case or an open point;
- GOV-SCOPE-CONFLICT                          a need is both out of scope and served by a use case;
- GOV-UC-EMPTY                                a use case serves no need and relies on no section;
- GOV-UC-UNREALIZED                           (requirements written) a use case no requirement names in
                                              ``attributes.use_cases``;
- GOV-UC-UNKNOWN                              (requirements written) a requirement names a use case that does not exist;
- GOV-SECTION-UNREALIZED                      (requirements written) an in-scope section no requirement cites;
- IQ-12.open-point-owner                      the open-point classification rule of the quality gate.

The gate applies to the project's entry stage only; later stages trace to the entry stage's requirements.
"""
from __future__ import annotations

from pathlib import Path

from . import gate_result, quality, trace
from .config import effective_rigor, load_project, schema, stages
from .io import read_json
from .jsonschema_lite import validate as schema_validate

NAME = "governance.json"


def path(root: Path, stage: str) -> Path:
    return Path(root) / "hi" / stage / NAME


def applies(project: dict, stage: str) -> bool:
    return stage == project.get("entry_stage")


def _section_refs(project: dict, doc: dict) -> tuple[list[str], set[str]]:
    declared = {i.get("doc_id") for i in project.get("inputs", []) if i.get("doc_id")}
    scope = [d for d in doc.get("document_scope") or [] if isinstance(d, dict)]
    in_scope = [d["ref"] for d in scope if d.get("scope") == "in" and d.get("ref", "#").split("#")[0] in declared]
    return in_scope, {d.get("ref") for d in scope}


def _cited(ref: str, items: list[dict]) -> bool:
    doc_id, section = ref.split("#", 1)
    for it in items:
        for s in it.get("sources") or []:
            if isinstance(s, dict) and s.get("kind") == "document" and s.get("doc_id") == doc_id:
                sec = str(s.get("section", ""))
                if sec == section or sec.startswith(section + "."):
                    return True
    return False


def check(root: Path, stage: str, *, realization: bool = True) -> list[dict]:
    """All governance issues of the entry stage. `realization=False` checks the package alone (before writing)."""
    root = Path(root)
    project = load_project(root)
    p = path(root, stage)
    rel = p.relative_to(root).as_posix()
    if not p.is_file():
        return [gate_result.issue("GOV-MISSING", f"{rel} does not exist: write the governance package (actors, use "
                                  "cases, scope, assumptions, open points) before the requirements")]
    try:
        doc = read_json(p)
    except (OSError, ValueError) as exc:
        return [gate_result.issue("GOV-UNREADABLE", f"{rel} is not valid JSON: {exc}", rel)]
    errs = schema_validate(doc, schema("governance"))
    if errs:
        return [gate_result.issue("GOV-SCHEMA", f"{rel}: {e}"[:300], rel) for e in errs[:20]]
    issues: list[dict] = []

    def add(code: str, msg: str, tid: str | None = None) -> None:
        issues.append(gate_result.issue(code, msg[:300], tid))

    for key in ("actors", "use_cases", "assumptions", "open_points"):
        ids = [x["id"] for x in doc[key]]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            add("GOV-DUPLICATE-ID", f"{key}: {dup} is used twice", dup)
    nodes = trace.input_nodes(root, project)
    needs = sorted(n for n, v in nodes.items() if v["kind"] == "needs")
    # constraints may be named (a driver project's scope is stated as constraints) but need no use case
    constraints = {n for n, v in nodes.items() if v["kind"] == "constraints"}
    sections, known_sections = _section_refs(project, doc)
    known = set(needs) | constraints | known_sections
    actors = {a["id"] for a in doc["actors"]}
    out = {o["ref"] for o in doc["out_of_scope"]}
    served: set[str] = set()
    for uc in doc["use_cases"]:
        if uc["actor"] not in actors:
            add("GOV-ACTOR-UNKNOWN", f"{uc['id']} names actor {uc['actor']}, which is not in 'actors'", uc["id"])
        refs = list(uc["needs"]) + list(uc.get("sections") or [])
        for r in refs:
            if r not in known:
                add("GOV-REF-UNKNOWN", f"{uc['id']} names {r}, which is no need or constraint of the inputs and no "
                    "section of the document scope", uc["id"])
        if not refs:
            add("GOV-UC-EMPTY", f"{uc['id']} serves no need and relies on no section", uc["id"])
        served |= set(refs)
    for r in sorted(out):
        if r not in known:
            add("GOV-REF-UNKNOWN", f"out_of_scope names {r}, which is no stakeholder need of the inputs", r)
        elif r in served:
            add("GOV-SCOPE-CONFLICT", f"{r} is out of scope and also served by a use case", r)
    concerned = {c for o in doc["open_points"] for c in o["concerns"]}
    for o in doc["open_points"]:
        for c in o["concerns"]:
            if c not in known:
                add("GOV-REF-UNKNOWN", f"{o['id']} concerns {c}, which is no need, constraint or section", o["id"])
    for n in needs:
        if n not in served | out | concerned:
            add("GOV-NEED-UNCOVERED", f"stakeholder need {n} is in no use case, not declared out of scope and in no "
                "open point: add it to the use case that serves it, or record why it is out of scope", n)
    for s in sections:
        if s not in served | concerned:
            add("GOV-SECTION-UNCOVERED", f"in-scope section {s} is in no use case and no open point", s)
    issues += quality.check_open_points(doc["open_points"], stage=stage)
    if realization:
        wp = Path(root) / stages()[stage]["outputs"][0]
        if wp.is_file():
            items = [i for i in read_json(wp).get("items", []) if isinstance(i, dict)]
            ucs = {u["id"] for u in doc["use_cases"]}
            named: set[str] = set()
            for it in items:
                for u in (it.get("attributes") or {}).get("use_cases") or []:
                    named.add(u)
                    if u not in ucs:
                        add("GOV-UC-UNKNOWN", f"{it.get('id')} names use case {u}, which is not in {rel}", it.get("id"))
            for u in sorted(ucs - named):
                add("GOV-UC-UNREALIZED", f"use case {u} is realised by no requirement: name it in attributes.use_cases "
                    "of the requirements that realise it, or add one", u)
            for s in sections:
                if s in served and not _cited(s, items):
                    add("GOV-SECTION-UNREALIZED", f"in-scope section {s} is cited by no requirement source", s)
    return issues


def open_points(root: Path, stage: str) -> list[dict]:
    """The governance package's open points (empty when there is none or it cannot be read)."""
    try:
        return [o for o in read_json(path(root, stage)).get("open_points", []) if isinstance(o, dict)]
    except (OSError, ValueError, AttributeError):
        return []


def blocking_open_points(root: Path, stage: str) -> list[dict]:
    return [o for o in open_points(root, stage) if o.get("blocks")]


def run(root: Path, stage: str, *, write: bool = True) -> dict:
    root = Path(root)
    project = load_project(root)
    rigor = effective_rigor(project)
    common = {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": root}
    if not applies(project, stage):
        doc = gate_result.result("governance", [], not_run_reason=(
            f"the governance package belongs to the entry stage {project.get('entry_stage')}"), **common)
    else:
        p = path(root, stage)
        doc = gate_result.result("governance", check(root, stage), evidence=[p] if p.is_file() else [],
                                 tool={"name": "forge-c-hi governance", "version": gate_result.__version__}, **common)
    if write:
        gate_result.write(root, stage, doc)
    return doc
