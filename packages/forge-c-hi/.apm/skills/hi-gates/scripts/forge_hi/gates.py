"""Stage gates: validate, doc-sources, independence, tool gates, and `hi gate <stage>` aggregation.

A required gate that cannot run is NOT_RUN and counts as a gap (FR-019). The aggregate verdict of a stage is FAIL if
any required gate failed, NOT_RUN if none failed but at least one did not run, and PASS only if all passed.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import code_gates, doc_index, gate_result, quality, scope, trace
from .config import REFS, effective_rigor, load_project, schema, stages
from .io import read_json, sha256_file
from .jsonschema_lite import validate as schema_validate

SCHEMA_ID = re.compile(r"^forge-c-hi/([a-z0-9-]+)@1$")
TOOL_GATES = ("build", "static-analysis", "unit-test", "coverage")


def _common(root: Path) -> tuple[dict, dict]:
    project = load_project(root)
    rigor = effective_rigor(project)
    return project, {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": Path(root)}


def validate_doc(doc) -> tuple[str | None, list[dict]]:
    """Schema-check one workproduct. Returns (schema name or None, issues)."""
    if not isinstance(doc, dict):
        return None, [gate_result.issue("VAL-NOT-OBJECT", "the workproduct is not a JSON object")]
    m = SCHEMA_ID.match(str(doc.get("schema", "")))
    if not m or not (REFS / "schemas" / f"{m.group(1)}.schema.json").is_file():
        return None, [gate_result.issue("VAL-NO-CONTRACT", f"no forge-c-hi contract for schema {doc.get('schema')!r}")]
    name = m.group(1)
    issues = [gate_result.issue("VAL-SCHEMA", e) for e in schema_validate(doc, schema(name))]
    ops = [o.get("id") for o in doc.get("open_points") or [] if isinstance(o, dict)]
    for dup in sorted({o for o in ops if ops.count(o) > 1}):
        issues.append(gate_result.issue("VAL-OPEN-POINT-ID", f"open point id {dup} is used twice", dup))
    return name, issues


def validate_file(root: Path, path: Path, *, stage: str | None = None, write: bool = True) -> dict:
    root = Path(root)
    _, common = _common(root)
    path = Path(path) if Path(path).is_absolute() else root / path
    try:
        doc = read_json(path)
    except (OSError, ValueError) as exc:
        res = gate_result.result("validate", [gate_result.issue("VAL-UNREADABLE", f"{path.name}: {exc}")], **common)
    else:
        _, issues = validate_doc(doc)
        if stage and isinstance(doc, dict) and doc.get("stage") not in (None, stage):
            issues.append(gate_result.issue("VAL-STAGE", f"workproduct stage {doc.get('stage')} is not {stage}"))
        res = gate_result.result("validate", issues, evidence=[path], **common)
        stage = stage or (doc.get("stage") if isinstance(doc, dict) else None)
    if write and stage in stages():
        gate_result.write(root, stage, res)
    return res


def validate_stage(root: Path, stage: str, *, write: bool = True) -> dict:
    root = Path(root)
    _, common = _common(root)
    issues, evidence = [], []
    for rel in stages()[stage]["outputs"]:
        p = root / rel
        if not p.is_file():
            issues.append(gate_result.issue("VAL-MISSING", f"{rel} does not exist"))
            continue
        evidence.append(p)
        one = validate_file(root, p, stage=stage, write=False)
        issues.extend(dict(i, message=f"{rel}: {i['message']}"[:300]) for i in one["issues"])
    res = gate_result.result("validate", issues, evidence=evidence, **common)
    if write:
        gate_result.write(root, stage, res)
    return res


def doc_sources(root: Path, stage: str, *, write: bool = True) -> dict:
    """Document sources must cite a declared document; with a local index, the section and page must exist in it."""
    root = Path(root)
    project, common = _common(root)
    declared = {i["doc_id"]: i for i in project.get("inputs", []) if i.get("doc_id")}
    issues, cited, unindexed = [], 0, set()
    items = trace.stage_items(root, stage) or []
    for it in items:
        for src in it.get("sources") or []:
            if not isinstance(src, dict) or src.get("kind") != "document":
                continue
            cited += 1
            did = src.get("doc_id")
            if did not in declared:
                issues.append(gate_result.issue("DOC-UNKNOWN", f"{it['id']} cites undeclared document {did}", it["id"]))
                continue
            idx = doc_index.load(root, did)
            if idx is None:
                unindexed.add(did)
                continue
            src_path = root / declared[did]["path"]
            if src_path.is_file() and idx.get("source_sha256") != sha256_file(src_path):
                issues.append(gate_result.issue("DOC-STALE-INDEX", f"the index of {did} was built from another file; "
                                                "rerun 'hi doc-index'", it["id"]))
                continue
            why = doc_index.resolve(idx, str(src.get("section")), int(src.get("page", 0)))
            if why:
                issues.append(gate_result.issue("DOC-UNRESOLVED", f"{it['id']} cites {did}: {why}", it["id"]))
    if unindexed and not issues:
        res = gate_result.result("doc-sources", [], not_run_reason=(
            f"no local index for {', '.join(sorted(unindexed))}; run 'hi doc-index'"), **common)
    else:
        res = gate_result.result("doc-sources", issues, **common)
    if write:
        gate_result.write(root, stage, res)
    return res


def independence(root: Path, stage: str, *, write: bool = True) -> dict:
    root = Path(root)
    project, common = _common(root)
    rule = effective_rigor(project)["independence"]
    author, insp = project["roles"]["author"], project["roles"]["inspector"]
    issues = []
    if rule != "same-session-ok":
        if insp.get("harness") != "manual" and insp.get("read_only") is not True:
            issues.append(gate_result.issue("IND-NOT-READ-ONLY", "the inspector binding is not read_only"))
    if rule == "separate-model-family" and insp.get("harness") != "manual":
        fa, fi = (author.get("model_family") or "").strip().lower(), (insp.get("model_family") or "").strip().lower()
        if not fa or not fi:
            issues.append(gate_result.issue("IND-FAMILY-UNKNOWN", "author and inspector model_family must both be declared"))
        elif fa == fi:
            issues.append(gate_result.issue(
                "IND-SAME-FAMILY", f"author and inspector are both model family '{fa}'; this level needs different families"))
    res = gate_result.result("independence", issues, tool={"name": f"forge-c-hi independence ({rule})",
                                                            "version": gate_result.__version__}, **common)
    if write:
        gate_result.write(root, stage, res)
    return res


def tool_gate_not_run(root: Path, stage: str, gate: str, *, write: bool = True) -> dict:
    _, common = _common(root)
    res = gate_result.result(gate, [], not_run_reason=f"the {gate} gate is not available in forge-c-hi "
                             f"{gate_result.__version__} for stage {stage}", **common)
    if write:
        gate_result.write(Path(root), stage, res)
    return res


def required_gates(project: dict, stage: str) -> list[str]:
    req = effective_rigor(project)["required_gates"]
    out = [g for g in stages()[stage]["gates"] if g in req]
    if "independence" in req:
        out.append("independence")
    return out


def _one_gate(root: Path, stage: str, g: str, scope_doc: dict | None) -> dict:
    if g == "validate":
        return validate_stage(root, stage)
    if g == "quality":
        return quality.run(root, stage)
    if g == "trace":
        return trace.run(root, stage)
    if g == "scope":
        if scope_doc is not None:
            gate_result.write(root, stage, scope_doc)
            return scope_doc
        return scope.run(root, "author", stage)
    if g == "doc-sources":
        return doc_sources(root, stage)
    if g == "independence":
        return independence(root, stage)
    if g == "build":
        return code_gates.build(root)
    if g == "static-analysis":
        return code_gates.static_analysis(root)
    if g == "unit-test":
        return code_gates.unit_test(root)[0]
    if g == "coverage":
        return code_gates.coverage(root)
    return tool_gate_not_run(root, stage, g)


def gate_stage(root: Path, stage: str, *, scope_doc: dict | None = None) -> dict:
    """Run every gate the profile requires for this stage and level. Returns a summary."""
    root = Path(root)
    if stage not in stages():
        raise ValueError(f"unknown stage {stage}")
    project, common = _common(root)
    results: dict[str, dict] = {}
    for g in required_gates(project, stage):
        try:
            results[g] = _one_gate(root, stage, g, scope_doc)
        except (OSError, ValueError) as exc:  # unreadable or invalid JSON input: the validate gate reports it as FAIL
            results[g] = gate_result.result(g, [], not_run_reason=f"an input is not readable: {exc}"[:300], **common)
            gate_result.write(root, stage, results[g])
    verdicts = {g: r["verdict"] for g, r in results.items()}
    if "FAIL" in verdicts.values():
        overall = "FAIL"
    elif "NOT_RUN" in verdicts.values():
        overall = "NOT_RUN"
    else:
        overall = "PASS"
    issues = [dict(i, gate=g) for g, r in results.items() for i in r["issues"]]
    return {"stage": stage, "verdict": overall, "gates": verdicts, "issues": issues,
            "profile": common["profile"], "integrity_level": common["integrity_level"]}


def recorded_gates(root: Path, stage: str) -> dict[str, str]:
    d = Path(root) / "hi" / stage / "gates"
    out = {}
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                out[f.stem] = read_json(f).get("verdict", "?")
            except (OSError, ValueError):
                out[f.stem] = "UNREADABLE"
    return out


STATE = Path(".hi") / "state.json"


def accepted_stages(root: Path) -> dict:
    p = Path(root) / STATE
    return read_json(p).get("stages", {}) if p.is_file() else {}


def findings(root: Path, stage: str) -> list[dict]:
    p = Path(root) / "hi" / stage / "inspection" / "findings.json"
    return read_json(p).get("findings", []) if p.is_file() else []


def status(root: Path) -> dict:
    root = Path(root)
    project, common = _common(root)
    rigor = effective_rigor(project)
    out_stages, nxt = [], None
    for s in trace.checked_stages(project, None):
        outputs = [root / p for p in stages()[s]["outputs"]]
        exists = all(p.is_file() for p in outputs)
        rec = recorded_gates(root, s)
        req = required_gates(project, s)
        fs = findings(root, s)
        open_f = [f for f in fs if f.get("status") in ("open", "carried")]
        ops = []
        for p in outputs:
            if p.is_file():
                ops += [o for o in read_json(p).get("open_points", []) if isinstance(o, dict)]
        state = "not-started"
        if exists:
            all_pass = all(rec.get(g) == "PASS" for g in req)
            blocking = any(f.get("severity") == "blocking" for f in open_f) or any(o.get("blocks") for o in ops)
            accepted = accepted_stages(root).get(s, {}).get("state") == "accepted"
            state = "accepted" if all_pass and not blocking and accepted else ("gated" if all_pass else "in-progress")
        if nxt is None and state != "accepted":
            nxt = s
        out_stages.append({
            "stage": s, "state": state, "gates": {g: rec.get(g, "-") for g in req},
            "open_findings": len(open_f), "open_points": len(ops),
            "blocking_open_points": sum(1 for o in ops if o.get("blocks")),
        })
    return {"project": project["project_id"], "profile": rigor["profile"], "level": rigor["level"],
            "level_name": rigor["level_name"], "next": nxt, "stages": out_stages}
