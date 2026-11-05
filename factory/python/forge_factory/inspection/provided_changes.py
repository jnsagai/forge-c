"""Owner decision 2026-11-03 (revised): "If the provided code is not able to implement 100% of the proposed requirements
and uspec, the code is allowed to be changed, but a diff report with the reasons needs to be documented for human
inspection in the end".

Provided code = the delivered code of a FROZEN brownfield work order and the provided read-only LL of a HAL work order
(--provided-from). In work orders with unit_verification it may be changed - only in this work order's own workspace
copy, never in the source work order, its baselines, the stored archive or the delivered inputs - when a CODE defect
names the file (a failing requirement-based/negative test, a closure task or an unreachable-code finding sent it to
SWE.3). Every change is linked to that defect: a changed provided file without a linked defect is refused at the SWE.3
gate. The originals stay byte-identical and hash-bound (manifest sha256; pristine copies in .forge-run/provided/original
and the delivery store).

The diff report (workproducts/SWE.3/provided_code_changes.{md,json}, frozen with the SWE.3 baseline, shown to the SWE.3-6
inspectors and carried into the offline review package) holds the unified diff, original and final sha256, and per hunk
the reasons: defect id, failing test id, SWR/USPEC and what was required versus what the original did.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from ..common import sha256_bytes

REPORT_MD = "workproducts/SWE.3/provided_code_changes.md"
REPORT_JSON = "workproducts/SWE.3/provided_code_changes.json"
ORIGINALS = ".forge-run/provided/original"
SCHEMA = "forge-c/provided-code-changes/1"
TITLE = "Changes to provided code (for human inspection)"
LINK_STATES = ("OPEN", "IN_FIX", "FIXED", "VERIFIED")


def enabled(ws: Path) -> bool:
    from ..layer import uspec_gtest

    return uspec_gtest(ws)


def save_original(ws: Path, rel: str, data: bytes) -> None:
    """workorder.prepare: the pristine provided bytes, kept beside the workspace copy (read-only)."""
    p = Path(ws) / ORIGINALS / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.chmod(0o644)
    p.write_bytes(data)
    p.chmod(0o444)


def items(ws: Path) -> list[dict]:
    """Provided files of this work order: {path, kind, source, original_sha256, original (bytes|None)}."""
    from ..brownfield import code_mode, delivered_paths, is_brownfield, manifest_of
    from ..layer import provided

    ws = Path(ws)
    out = []
    for rec in provided(ws):
        p = ws / ORIGINALS / rec["path"]
        data = p.read_bytes() if p.is_file() else None
        if data is None and rec.get("source_work_order"):  # older work orders: the source workspace, if unchanged
            from ..common import state_dir

            src = state_dir() / "workorders" / rec["source_work_order"] / "workspace" / rec["path"]
            data = src.read_bytes() if src.is_file() else None
        if data is not None and sha256_bytes(data) != rec["sha256"]:
            data = None
        out.append({"path": rec["path"], "kind": "provided_ll", "source": rec.get("source_work_order"),
                    "original_sha256": rec["sha256"], "original": data})
    m = manifest_of(ws)
    if is_brownfield(m) and code_mode(m) == "FROZEN":
        from ..brownfield import delivery as D

        store = D.stored(m["work_order"])
        shas = {d["path"]: d["sha256"] for d in m.get("delivered") or []}
        for rel in delivered_paths(m):
            data = store.get(rel)
            out.append({"path": rel, "kind": "frozen_delivery", "source": m.get("work_order"),
                        "original_sha256": shas.get(rel),
                        "original": data if data is not None and sha256_bytes(data) == shas.get(rel) else None})
    return out


def _code_defects(ws: Path) -> list[dict]:
    from ..brownfield.verify import _code_defects as cd

    return cd(ws)


def linked_defects(ws: Path, rel: str) -> list[dict]:
    """CODE defects that name this provided file explicitly (evidence 'file:line', location or summary path)."""
    out = []
    for d in _code_defects(ws):
        txt = json.dumps({k: d.get(k) for k in ("location", "evidence_refs", "summary", "files")})
        if d.get("status") in LINK_STATES and rel in txt:
            out.append(d)
    return out


def _reason(d: dict) -> dict:
    s = d.get("summary") or ""
    return {"defect": d["id"], "status": d.get("status"), "tests": sorted(set(re.findall(r"\bUT-\d{3}\b", s))),
            "requirements": list(d.get("requirement_ids") or []),
            "uspecs": sorted(set(re.findall(r"\bUSPEC-[A-Z]+-\d{2,}-\d{2,}\b", s))),
            "required_vs_original": s[:400], "evidence": list(d.get("evidence_refs") or [])[:6]}


def _hunks(diff: str) -> list[dict]:
    out = []
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$", diff, re.M):
        a, n = int(m.group(1)), int(m.group(2) or 1)
        out.append({"header": m.group(0), "original_lines": [a, a + max(n, 1) - 1]})
    return out


def report(ws: Path) -> dict:
    ws = Path(ws)
    files, changes = [], 0
    for it in items(ws):
        p = ws / it["path"]
        final = p.read_bytes() if p.is_file() else b""
        fsha = sha256_bytes(final)
        row = {k: it[k] for k in ("path", "kind", "source", "original_sha256")} | {"final_sha256": fsha}
        if fsha == it["original_sha256"]:
            files.append({**row, "status": "UNCHANGED", "hunks": [], "diff": ""})
            continue
        defs = linked_defects(ws, it["path"])
        if it["original"] is None:
            files.append({**row, "status": "CHANGED_ORIGINAL_UNAVAILABLE", "hunks": [], "diff": "",
                          "reasons": [_reason(d) for d in defs]})
            continue
        diff = "".join(difflib.unified_diff(it["original"].decode("utf-8", errors="replace").splitlines(keepends=True),
                                            final.decode("utf-8", errors="replace").splitlines(keepends=True),
                                            f"original/{it['path']}", f"final/{it['path']}"))
        hunks = _hunks(diff)
        for h in hunks:  # a defect citing a line inside the hunk is its reason; otherwise every linked defect
            lo, hi = h["original_lines"]
            near = [d for d in defs if any(re.search(rf"{re.escape(it['path'])}:(\d+)", e) and
                                           lo - 3 <= int(re.search(rf"{re.escape(it['path'])}:(\d+)", e).group(1)) <= hi + 3
                                           for e in d.get("evidence_refs") or [])]
            h["reasons"] = [_reason(d) for d in (near or defs)]
        changes += len(hunks)
        files.append({**row, "status": "CHANGED_LINKED" if defs else "CHANGED_WITHOUT_DEFECT", "hunks": hunks,
                      "diff": diff, "reasons": [_reason(d) for d in defs]})
    return {"schema": SCHEMA, "title": TITLE, "files": files, "changes": changes,
            "modified_files": sum(f["status"] != "UNCHANGED" for f in files),
            "human_review_required": any(f["status"] != "UNCHANGED" for f in files)}


def render_md(rep: dict) -> str:
    md = [f"# {TITLE}", "",
          "Generated deterministically from the workspace copy of the provided code, the pristine originals (sha256 "
          "bound in the work-order manifest) and the CODE defects that sent each change to SWE.3. The source work order, "
          "its baselines, the stored archive and the delivered inputs are unchanged. Human inspection is required for "
          "every change below; nothing here claims conformance.", "",
          f"- provided files: {len(rep['files'])}; modified: {rep['modified_files']}; changes (hunks): {rep['changes']}",
          f"- human review required: {'YES' if rep['human_review_required'] else 'no (provided code used unchanged)'}", ""]
    for f in rep["files"]:
        md += [f"## {f['path']} ({f['kind']}, from {f['source']})", "",
               f"- original sha256: {f['original_sha256']}", f"- final sha256: {f['final_sha256']}",
               f"- status: {f['status']}", ""]
        for i, h in enumerate(f.get("hunks") or [], 1):
            md.append(f"### Change {i}: `{h['header']}` (original lines {h['original_lines'][0]}-{h['original_lines'][1]})")
            md.append("")
            for r in h.get("reasons") or []:
                md.append(f"- reason {r['defect']} ({r['status']}): tests {', '.join(r['tests']) or '-'}; "
                          f"requirements {', '.join(r['requirements']) or '-'}; USPEC {', '.join(r['uspecs']) or '-'}; "
                          f"required vs original: {r['required_vs_original']}")
            if not h.get("reasons"):
                md.append("- reason: NONE - change without a linked CODE defect (refused at the SWE.3 gate)")
            md.append("")
        if f.get("diff"):
            md += ["```diff", f["diff"].rstrip("\n"), "```", ""]
    return "\n".join(md) + "\n"


def write(ws: Path) -> dict:
    rep = report(ws)
    for rel, text in ((REPORT_JSON, json.dumps(rep, indent=1, sort_keys=True) + "\n"), (REPORT_MD, render_md(rep))):
        p = Path(ws) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    if rep["human_review_required"]:
        from ..workflow.provided_input_identity import safe_path

        raw = (Path(ws) / REPORT_JSON).read_bytes()
        rel = ".forge-run/provided/report-snapshots/" + sha256_bytes(raw) + ".json"
        target = safe_path(ws, rel, missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError("PROVIDED_REPORT_SNAPSHOT_CHANGED")
        else:
            target.write_bytes(raw)
            target.chmod(0o444)
    return rep


def findings(ws: Path) -> list[str]:
    """SWE.3 gate: a changed provided file needs a linked CODE defect and an available original."""
    if not enabled(ws):
        return []
    rep = write(ws)
    out = []
    for f in rep["files"]:
        if f["status"] == "CHANGED_WITHOUT_DEFECT":
            out.append(f"PROVIDED_CODE_CHANGED_WITHOUT_DEFECT:{f['path']} (provided code changes only for a CODE "
                       "defect that names this file; restore it or link the change)")
        elif f["status"] == "CHANGED_ORIGINAL_UNAVAILABLE":
            out.append(f"PROVIDED_CODE_ORIGINAL_UNAVAILABLE:{f['path']} (no hash-bound original for the diff report)")
    return out


def allowed(ws: Path, rel: str) -> bool:
    """A provided file may be changed in this workspace: unit_verification and a linked CODE defect in fix."""
    return enabled(ws) and any(d.get("status") in ("OPEN", "IN_FIX") for d in linked_defects(ws, rel))


def unlock(ws: Path) -> list[str]:
    """Make the workspace copy of each provided file with an open linked CODE defect writable (never the original)."""
    out = []
    for it in items(ws):
        p = Path(ws) / it["path"]
        if p.is_file() and allowed(ws, it["path"]):
            p.chmod(0o644)
            out.append(it["path"])
    return out


def stage_into(ws: Path, stage: Path) -> dict | None:
    """Release Manager staging: the report as quality/provided-code-changes.{md,json} and the section in the
    package's known limitations; None for work orders without unit_verification."""
    if not enabled(ws):
        return None
    rep = report(ws)
    q = Path(stage) / "quality"
    q.mkdir(parents=True, exist_ok=True)
    (q / "provided-code-changes.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    (q / "provided-code-changes.md").write_text(render_md(rep))
    kl = Path(stage) / "safety/known_limitations.md"
    kl.parent.mkdir(parents=True, exist_ok=True)
    with kl.open("a", encoding="utf-8") as f:
        f.write(f"\n## {TITLE}\n\n" + (
            f"- PROVIDED CODE WAS MODIFIED in this work order: {rep['modified_files']} file(s), {rep['changes']} "
            "change(s); HUMAN REVIEW REQUIRED - quality/provided-code-changes.md (diffs, original/final sha256, reasons "
            "per change). The provided code was NOT used unchanged; no conformance is claimed.\n"
            if rep["human_review_required"] else
            "- The provided code was used unchanged (final sha256 equals the hash-bound original).\n"))
    return rep
