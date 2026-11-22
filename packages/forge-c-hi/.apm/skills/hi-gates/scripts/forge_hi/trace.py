"""Bidirectional traceability gate (FR-013, FR-022).

The idea of a structural trace gate comes from Forge-C tools/trace_gate.py (Apache-2.0); this version is rewritten for
the neutral V-model. Links are not written twice: they are derived from each item's upstream ``sources``. The gate
writes them to ``hi/trace.json`` with a status, renders ``hi/trace-matrix.md`` and checks:

- TR-DANGLING      an upstream source names an id that exists nowhere;
- TR-ORPHAN       a system or software item has no upstream source and is not marked derived;
- TR-UNCOVERED    a stakeholder need has no system requirement, or a system requirement allocated to software has no
                  software requirement;
- TR-SUSPECT      a link whose end changed since the stage that owns it was last accepted;
- TR-DOC-UNKNOWN  a document source cites a document id the project does not declare.

Suspect links: when a stage is accepted, ``rebaseline`` records the content hash of both ends of every link that
enters that stage (``.hi/trace-baseline.json``). A later change to either end makes the link suspect until the owning
stage is inspected and accepted again.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import doc_index, gate_result
from .config import effective_rigor, load_project, stage_order, stages
from .io import canonical, read_json, sha256_bytes, write_json, write_text

INPUT_ID = re.compile(r"\b((?:STK|CON)-[A-Z0-9_]+-[0-9]{3})\b")
LINK_TYPE = {
    "sys-req": "derives", "sw-req": "derives", "sys-arch": "allocates", "sw-arch": "realises",
    "sw-design": "implements", "unit-verif": "verifies", "sw-integ": "verifies", "sw-qual": "verifies",
    "sys-integ": "verifies", "sys-qual": "verifies",
}
BASELINE = Path(".hi") / "trace-baseline.json"
TRACE = Path("hi") / "trace.json"
MATRIX = Path("hi") / "trace-matrix.md"


def item_hash(item: dict) -> str:
    return sha256_bytes(canonical({"text": item.get("text"), "sources": item.get("sources")}))


def input_nodes(root: Path, project: dict) -> dict[str, dict]:
    """Ids declared in needs and constraints inputs (STK-*, CON-*), hashed by the line that states them."""
    nodes: dict[str, dict] = {}
    for inp in project.get("inputs", []):
        if inp.get("kind") not in ("needs", "constraints"):
            continue
        path = Path(root) / inp["path"]
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            for m in INPUT_ID.finditer(line):
                nodes.setdefault(m.group(1), {
                    "id": m.group(1), "stage": "input", "kind": inp["kind"], "file": inp["path"],
                    "hash": sha256_bytes(line.strip().encode("utf-8")),
                })
    return nodes


def stage_items(root: Path, stage: str) -> list[dict] | None:
    out = []
    found = False
    for rel in stages()[stage]["outputs"]:
        p = Path(root) / rel
        if p.is_file():
            found = True
            doc = read_json(p)
            out.extend(i for i in doc.get("items", []) if isinstance(i, dict) and i.get("id"))
    return out if found else None


def checked_stages(project: dict, until: str | None) -> list[str]:
    order = stage_order()
    wanted = project.get("stages") or order[order.index(project["entry_stage"]):]
    wanted = [s for s in order if s in wanted]
    if until:
        if until not in order:
            raise ValueError(f"unknown stage {until}")
        wanted = [s for s in wanted if order.index(s) <= order.index(until)]
    return wanted


LEVEL_STAGE = {"driver_interface": "sw-req", "software": "sw-req", "system": "sys-req"}


def linked_nodes(root: Path, project: dict) -> tuple[dict[str, dict], list[dict]]:
    """Items of the requested level from linked projects (e.g. driver interface requirements of a driver project)."""
    nodes, issues = {}, []
    for ln in project.get("links", []):
        other = (Path(root) / ln["project_path"]).resolve()
        wp = other / stages()[LEVEL_STAGE[ln["level"]]]["outputs"][0]
        if not wp.is_file():
            issues.append(gate_result.issue("TR-LINK-MISSING", f"linked project {ln['project_path']} has no {wp.name} "
                                            f"for level {ln['level']}"))
            continue
        for it in read_json(wp).get("items", []):
            if isinstance(it, dict) and it.get("level") == ln["level"] and it.get("id"):
                nodes[it["id"]] = {"id": it["id"], "stage": "linked", "level": it["level"], "hash": item_hash(it),
                                   "project": ln["project_path"]}
    return nodes, issues


def build(root: Path, project: dict, until: str | None = None) -> dict:
    """Collect nodes and derived links for the checked stages."""
    root = Path(root)
    nodes = input_nodes(root, project)
    linked, link_issues = linked_nodes(root, project)
    nodes.update(linked)
    present: dict[str, list[dict]] = {}
    for s in checked_stages(project, until):
        items = stage_items(root, s)
        if items is None:
            continue
        present[s] = items
        for it in items:
            nodes[it["id"]] = {"id": it["id"], "stage": s, "level": it.get("level"), "hash": item_hash(it), "item": it}
    links = []
    for s, items in present.items():
        for it in items:
            for src in it.get("sources") or []:
                if isinstance(src, dict) and src.get("kind") == "upstream" and src.get("id"):
                    parent = src["id"]
                    drv_use = parent.startswith("DRV-") and not it["id"].startswith("DRV-")
                    ltype = "interfaces" if drv_use else LINK_TYPE[s]
                    links.append({"from": parent, "to": it["id"], "type": ltype, "stage": s})
    return {"nodes": nodes, "present": present, "links": links, "link_issues": link_issues}


def _key(link: dict) -> str:
    return f"{link['from']}|{link['to']}|{link['type']}"


def _load_baseline(root: Path) -> dict:
    p = Path(root) / BASELINE
    return read_json(p) if p.is_file() else {"schema": "forge-c-hi/trace-baseline@1", "links": {}}


def check(root: Path, project: dict, until: str | None = None) -> tuple[list[dict], list[dict], dict]:
    graph = build(root, project, until)
    nodes, present = graph["nodes"], graph["present"]
    baseline = _load_baseline(root)["links"]
    issues: list[dict] = list(graph["link_issues"])
    links_out: list[dict] = []
    for ln in graph["links"]:
        rec = {"from": ln["from"], "to": ln["to"], "type": ln["type"], "status": "valid"}
        if ln["from"] not in nodes:
            issues.append(gate_result.issue(
                "TR-DANGLING", f"{ln['to']} cites {ln['from']}, which exists in no input or stage", ln["to"]))
            continue
        base = baseline.get(_key(rec))
        if base:
            changed = [end for end in ("from", "to") if base.get(end) != nodes[rec[end]]["hash"]]
            if changed:
                rec["status"] = "suspect"
                rec["suspect_reason"] = " and ".join(f"{rec[e]} changed" for e in changed) + " since acceptance"
                issues.append(gate_result.issue(
                    "TR-SUSPECT", f"{rec['from']} -> {rec['to']}: {rec['suspect_reason']}", rec["to"]))
        links_out.append(rec)

    declared_docs = {i.get("doc_id") for i in project.get("inputs", []) if i.get("doc_id")}
    ref_doc_project = project.get("input_class") == "reference_document"
    for s, items in present.items():
        for it in items:
            srcs = [x for x in it.get("sources") or [] if isinstance(x, dict)]
            ups = [x for x in srcs if x.get("kind") == "upstream"]
            docs = [x for x in srcs if x.get("kind") == "document"]
            for d in docs:
                if d.get("doc_id") not in declared_docs:
                    issues.append(gate_result.issue(
                        "TR-DOC-UNKNOWN", f"{it['id']} cites document {d.get('doc_id')}, not declared in the project inputs",
                        it["id"]))
                    continue
                idx = doc_index.load(root, d["doc_id"])
                why = doc_index.resolve(idx, str(d.get("section")), int(d.get("page", 0))) if idx else None
                if why:
                    issues.append(gate_result.issue("TR-DOC-UNRESOLVED", f"{it['id']} cites {d['doc_id']}: {why}", it["id"]))
            doc_ok = bool(docs) and (ref_doc_project or it.get("level") == "driver_interface")
            if not ups and not it.get("derived") and not doc_ok and it.get("level") in ("system", "software"):
                issues.append(gate_result.issue("TR-ORPHAN", f"{it['id']} has no upstream source and is not derived", it["id"]))

    children: dict[str, set[str]] = {}
    for ln in links_out:
        children.setdefault(ln["from"], set()).add(ln["to"])

    def covered_in(parent: str, stage: str) -> bool:
        return any(nodes.get(c, {}).get("stage") == stage for c in children.get(parent, ()))

    if "sys-req" in present:
        for nid, n in sorted(nodes.items()):
            if n["stage"] == "input" and n["kind"] == "needs" and not covered_in(nid, "sys-req"):
                issues.append(gate_result.issue("TR-UNCOVERED", f"need {nid} is not covered by any system requirement", nid))
    if "sw-req" in present and "sys-req" in present:
        for it in present["sys-req"]:
            alloc = (it.get("attributes") or {}).get("allocation")
            if alloc is not None and "software" not in alloc:
                continue
            if not covered_in(it["id"], "sw-req"):
                issues.append(gate_result.issue(
                    "TR-UNCOVERED", f"{it['id']} is allocated to software but no software requirement covers it", it["id"]))
    return issues, links_out, graph


def _level_label(project: dict) -> str:
    from . import report
    from .config import load_profile
    try:
        return report.level_label(load_profile(project.get("profile", "generic")), project["integrity_level"])
    except Exception:  # noqa: BLE001 - the matrix header must never fail the gate
        return project["integrity_level"]


def render_matrix(project: dict, graph: dict, links: list[dict], issues: list[dict]) -> str:
    nodes = graph["nodes"]
    by_from: dict[str, list[dict]] = {}
    for ln in links:
        by_from.setdefault(ln["from"], []).append(ln)
    uncovered = {i["target_id"] for i in issues if i["code"] == "TR-UNCOVERED"}
    lines = [
        f"# Trace matrix: {project['project_id']}",
        "",
        f"Profile `{project.get('profile', 'generic')}`, level `{_level_label(project)}`. "
        "Generated by `hi trace`; do not edit.",
        "",
        "| Upstream | Downstream | Link | Status |",
        "|---|---|---|---|",
    ]
    def rank(i: str) -> int:
        st = nodes[i]["stage"]
        return 0 if st == "input" else 1 if st == "linked" else 2 + stage_order().index(st)

    ordered = sorted(nodes, key=lambda i: (rank(i), i))
    for nid in ordered:
        outs = by_from.get(nid, [])
        if not outs:
            if nid in uncovered:
                lines.append(f"| {nid} | **NOT COVERED** | | |")
            continue
        for ln in sorted(outs, key=lambda x: x["to"]):
            lines.append(f"| {nid} | {ln['to']} | {ln['type']} | {ln['status']} |")
    if issues:
        lines += ["", "## Issues", ""]
        lines += [f"- `{i['code']}` {i['message']}" for i in issues]
    return "\n".join(lines) + "\n"


def run(root: Path, stage: str | None = None, *, write: bool = True) -> dict:
    root = Path(root)
    project = load_project(root)
    rigor = effective_rigor(project)
    issues, links, graph = check(root, project, stage)
    present = list(graph["present"])
    target_stage = stage or (present[-1] if present else None)
    common = {"profile": rigor["profile"], "integrity_level": rigor["level"], "root": root}
    if not present:
        doc = gate_result.result("trace", [], not_run_reason="no stage workproduct exists yet", **common)
    else:
        if write:
            write_json(root / TRACE, {"schema": "forge-c-hi/trace@1", "links": links})
            write_text(root / MATRIX, render_matrix(project, graph, links, issues))
        evidence = [root / TRACE, root / MATRIX] + [root / p for s in present for p in stages()[s]["outputs"]]
        doc = gate_result.result("trace", issues, evidence=evidence, **common)
    if write and target_stage:
        gate_result.write(root, target_stage, doc)
    return doc


def rebaseline(root: Path, stage: str, only: set[str] | None = None) -> int:
    """Record both end hashes of every link entering `stage` (or only those entering the items in `only`).

    Called for items the inspector judged against their current upstream, and when the stage is accepted.
    Returns the number of links recorded."""
    root = Path(root)
    project = load_project(root)
    _, links, graph = check(root, project, None)
    nodes = graph["nodes"]
    base = _load_baseline(root)
    n = 0
    for ln in links:
        if nodes.get(ln["to"], {}).get("stage") == stage and (only is None or ln["to"] in only):
            base["links"][_key(ln)] = {"from": nodes[ln["from"]]["hash"], "to": nodes[ln["to"]]["hash"]}
            n += 1
    write_json(root / BASELINE, base)
    return n
