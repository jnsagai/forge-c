"""Pure identity of provided LL code and a normally reviewed workspace-only correction.

Original approval is never repinned. A changed copy requires the existing CODE
defect/diff report and current independent SWE.3 approval chain. This module
does not write reports, advance defects, waive findings or grant write access.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path, PurePosixPath

from ..common import canonical_json, safe_id, sha256_bytes, sha256_file, state_dir
from ..inspection import defects
from ..inspection import provided_changes as PC
from ..inspection.engine import PHASES, Store


class ProvidedIdentityError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ProvidedIdentityError("PROVIDED_EFFECTIVE_" + reason)


def safe_path(ws, rel, *, missing=False):
    require(isinstance(rel, str) and bool(rel) and "\\" not in rel and "\x00" not in rel, "PATH_INVALID")
    root, rel = Path(ws).resolve(), PurePosixPath(rel)
    require(not rel.is_absolute() and ".." not in rel.parts and bool(rel.parts), "PATH_INVALID")
    p = root
    for part in rel.parts:
        p = p / part
        require(not p.is_symlink(), "PATH_SYMLINK")
    require(p.resolve().is_relative_to(root) and (p.is_file() or missing and not p.exists()), "PATH_INVALID")
    return p


def _original(ws, item):
    rel = PC.ORIGINALS + "/" + item["path"]
    own = safe_path(ws, rel, missing=True)
    if own.is_file():
        raw = own.read_bytes()
    else:
        source = item.get("source_work_order")
        require(isinstance(source, str) and safe_id(source) == source, "ORIGINAL_UNAVAILABLE")
        root = state_dir() / "workorders" / source / "workspace"
        require(root.is_dir() and not root.is_symlink() and not root.parent.is_symlink(), "ORIGINAL_UNAVAILABLE")
        raw = safe_path(root, item["path"]).read_bytes()
    require(sha256_bytes(raw) == item["sha256"], "ORIGINAL_CHANGED")
    return raw


def _phase3(ws):
    store = Store(Path(ws))
    for phase in PHASES[:3]:
        for root, pattern in (("configuration/baselines", "BL-*.json"), ("inspection", "INS-*.json")):
            for path in (Path(ws) / root / phase).glob(pattern):
                safe_path(ws, path.relative_to(ws).as_posix())
        require(store.gate(phase)["decision"] == "PASS", "PHASE_NOT_PASSED:" + phase)
        baseline = store.latest_baseline(phase)
        inspection = store.inspections(phase)[-1]
        checklist = store.checklist(phase)
        require(baseline["author_role"] == f"swe{phase[-1]}-author"
                and inspection["author_role"] == baseline["author_role"]
                and inspection["inspector_role"] == f"swe{phase[-1]}-inspector"
                and inspection["baseline_id"] == baseline["baseline_id"]
                and inspection["baseline_hash"] == baseline["baseline_hash"]
                and inspection["checklist_sha256"] == checklist["sha256"]
                and all(inspection["items"].get(c["id"], {}).get("verdict") == "PASS"
                        for c in store.applicable(checklist)["checks"] if c.get("required")),
                "INDEPENDENT_PHASE_APPROVAL_INVALID:" + phase)
    return baseline, inspection


def _without_lifecycle(value):
    if isinstance(value, dict):
        return {k: _without_lifecycle(v) for k, v in value.items() if not (k == "status" and "defect" in value)}
    return [_without_lifecycle(v) for v in value] if isinstance(value, list) else value


def historical_correction(ws, baseline, rel, current_file):
    """Historical PASS is context only: exactly the same LL bytes, diff hunks and reasons must be current."""
    require(baseline["files"].get(rel) == sha256_file(safe_path(ws, rel)), "HISTORICAL_EFFECTIVE_CODE_CHANGED")
    digest = baseline["files"].get(PC.REPORT_JSON)
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "HISTORICAL_REPORT_UNBOUND")
    path = safe_path(ws, PC.REPORT_JSON)
    if sha256_file(path) != digest:
        path = safe_path(ws, ".forge-run/provided/report-snapshots/" + digest + ".json")
    require(sha256_file(path) == digest, "HISTORICAL_REPORT_CHANGED")
    report = json.loads(path.read_text())
    require(report.get("schema") == PC.SCHEMA and report.get("human_review_required") is True
            and baseline["files"].get(PC.REPORT_MD) == sha256_bytes(PC.render_md(report).encode()),
            "HISTORICAL_REPORT_INVALID")
    rows = [r for r in report["files"] if r["path"] == rel]
    require(len(rows) == 1 and _without_lifecycle(rows[0]) == _without_lifecycle(current_file),
            "HISTORICAL_CORRECTION_CHANGED")
    return digest


def _defect(ws, row, baseline, inspection, file_row):
    require(isinstance(row.get("defect"), str) and re.fullmatch(r"DEF-[0-9]+", row["defect"]), "CODE_ID_INVALID")
    path = safe_path(ws, ".forge-run/defects/" + row["defect"] + ".json")
    d = json.loads(path.read_text())
    require(d.get("id") == row["defect"], "CODE_ID_CHANGED")
    require(d is not None and d.get("kind") == "CODE" and d.get("target_phase") == "SWE.3"
            and d.get("status") in ("FIXED", "VERIFIED"), "CODE_NOT_FIXED")
    texts = defects._requirement_texts(ws)
    quote = defects._norm(d.get("requirement_quote", ""))
    require(bool(d.get("requirement_ids")) and all(r in texts for r in d["requirement_ids"])
            and len(quote) >= 20 and any(quote in defects._norm(texts[r]) for r in d["requirement_ids"]),
            "CODE_REQUIREMENT_CHANGED")
    history = d.get("history", [])
    require(bool(history) and all(e.get("status") in ("OPEN", "IN_FIX", "FIXED", "VERIFIED") for e in history)
            and [e["ts"] for e in history] == sorted(e["ts"] for e in history)
            and history[-1]["status"] == d["status"], "CODE_HISTORY_INVALID")
    fixes = [e for e in history if e["status"] == "FIXED"]
    require(len(fixes) == 1, "CODE_FIX_APPROVAL_UNBOUND")
    fixed = fixes[0]
    fix_baseline = next((b for b in Store(Path(ws)).baselines("SWE.3")
                         if b["baseline_id"] == fixed.get("baseline_id")), None)
    require(fix_baseline is not None and any(e["status"] == "IN_FIX" and e["ts"] <= fix_baseline["frozen_at"]
                                           for e in history), "CODE_FIX_APPROVAL_UNBOUND")
    if fix_baseline["baseline_id"] != baseline["baseline_id"]:
        require(row["status"] in ("FIXED", "VERIFIED") and fixed["ts"] <= baseline["frozen_at"],
                "HISTORICAL_CODE_STATE_INVALID")
    historical_correction(ws, fix_baseline, file_row["path"], file_row)
    checks = Store(Path(ws)).applicable(Store(Path(ws)).checklist("SWE.3"))["checks"]
    approvals = [i for i in Store(Path(ws)).inspections("SWE.3") if i.get("baseline_id") == fix_baseline["baseline_id"]
                 and i.get("baseline_hash") == fix_baseline["baseline_hash"] and i.get("verdict") == "PASS"
                 and i.get("author_role") == "swe3-author" and i.get("inspector_role") == "swe3-inspector"
                 and i.get("checklist_sha256") == inspection["checklist_sha256"] and i["recorded_at"] <= fixed["ts"]
                 and all(i.get("items", {}).get(c["id"], {}).get("verdict") == "PASS" for c in checks if c.get("required"))]
    require(bool(approvals), "CODE_FIX_APPROVAL_UNBOUND")
    if d["status"] == "VERIFIED":
        verified = history[-1]
        require(verified["status"] == "VERIFIED" and verified["ts"] > fixed["ts"]
                and isinstance(verified.get("tools"), list) and bool(verified["tools"]), "CODE_VERIFICATION_UNBOUND")
        if verified["tools"] == ["gate-reverify"]:
            from ..inspection.reverify import validate_receipt

            validate_receipt(ws, d, verified, fixed, baseline, inspection, file_row)
        else:
            require(all(tool in defects.TEST_TOOLS for tool in verified["tools"]), "CODE_VERIFICATION_TOOL_UNKNOWN")
            safe_path(ws, "evidence/tool-results.jsonl")
            records = defects._tool_results(ws)
            for tool in verified["tools"]:
                require(any(r.get("phase") == d["detected_phase"] and r.get("op") == tool
                            and r.get("result", {}).get("status") == "PASS"
                            and fixed["ts"] < r.get("ts_utc", "") <= verified["ts"] for r in records),
                        "CODE_VERIFICATION_TOOL_MISSING")
            # A normal resume may retain historical verified test bytes only in
            # the protected snapshots. Those are context, never a new phase PASS.
            for rel, sha in d.get("test_files", {}).items():
                path = safe_path(ws, rel, missing=True)
                if not path.is_file() or sha256_file(path) != sha:
                    path = safe_path(ws, defects.SNAPSHOTS + "/" + sha)
                require(sha256_file(path) == sha, "CODE_VERIFICATION_TEST_CHANGED")
    require(row["status"] in ("IN_FIX", "FIXED", "VERIFIED"), "FROZEN_CODE_STATE_INVALID")
    if row["status"] == "IN_FIX":
        require(fixed["ts"] >= baseline["frozen_at"], "CODE_FIX_PRECEDES_FROZEN_REPORT")
    elif row["status"] == "VERIFIED":
        require(d["status"] == "VERIFIED", "CODE_STATE_REGRESSED")
    return {"id": d["id"], "core_sha256": sha256_bytes(canonical_json(
        {k: v for k, v in d.items() if k not in ("status", "history")})), "fixed_event": fixed,
        "fixed_inspection_sha256": sha256_bytes(canonical_json(approvals[-1])),
        "fixed_baseline_sha256": sha256_bytes(canonical_json(fix_baseline)),
        "fixed_report_sha256": fix_baseline["files"][PC.REPORT_JSON]}


def _report(ws, baseline, inspection):
    path = safe_path(ws, PC.REPORT_JSON)
    markdown = safe_path(ws, PC.REPORT_MD)
    require(baseline["files"].get(PC.REPORT_JSON) == sha256_file(path)
            and baseline["files"].get(PC.REPORT_MD) == sha256_file(markdown), "REPORT_NOT_FROZEN")
    frozen = json.loads(path.read_text())
    require(frozen.get("schema") == PC.SCHEMA and frozen.get("human_review_required") is True
            and markdown.read_text() == PC.render_md(frozen), "REPORT_INVALID")
    for record in (Path(ws) / ".forge-run/defects").glob("DEF-*.json"):
        safe_path(ws, record.relative_to(ws).as_posix())
    current = PC.report(ws)  # pure: never findings()/write() on frozen inputs
    bindings = {}

    def reconcile(a, b, file_row=None):
        if isinstance(a, dict) and "defect" in a and "status" in a:
            require(isinstance(b, dict) and {k: v for k, v in a.items() if k != "status"}
                    == {k: v for k, v in b.items() if k != "status"}, "REPORT_REASON_CHANGED")
            identity = _defect(ws, a, baseline, inspection, file_row)
            require(b["status"] in ("FIXED", "VERIFIED"), "CODE_STATE_INVALID")
            bindings[identity["id"]] = identity
            return copy.deepcopy(a)
        if isinstance(a, dict):
            require(isinstance(b, dict) and set(a) == set(b), "REPORT_CHANGED")
            if "path" in a and "original_sha256" in a and "hunks" in a:
                file_row = a
            return {k: reconcile(a[k], b[k], file_row) for k in a}
        if isinstance(a, list):
            require(isinstance(b, list) and len(a) == len(b), "REPORT_CHANGED")
            return [reconcile(x, y, file_row) for x, y in zip(a, b, strict=True)]
        require(a == b, "REPORT_CHANGED")
        return a

    require(reconcile(frozen, current) == frozen and bool(bindings), "REPORT_UNBOUND")
    return frozen, {"report_sha256": sha256_file(path), "report_md_sha256": sha256_file(markdown),
                    "phase3_baseline_sha256": sha256_bytes(canonical_json(baseline)),
                    "phase3_inspection_sha256": sha256_bytes(canonical_json(inspection)),
                    "defects": [bindings[k] for k in sorted(bindings)]}


def effective_identity(ws, rel):
    """Original approval + effective bytes; changed LL needs a passed normal approval chain. No bypass flag."""
    ws = Path(ws)
    manifest = json.loads(safe_path(ws, ".forge-run/manifest.json").read_text())
    require(isinstance(manifest, dict) and isinstance(manifest.get("provided", []), list)
            and all(isinstance(v, dict) for v in manifest.get("provided", [])), "INPUT_INVALID")
    candidates = [v for v in manifest.get("provided", []) if v.get("path") == rel]
    require(len(candidates) == 1, "INPUT_NOT_UNIQUE")
    item = candidates[0]
    require(item.get("role") == "provided_ll_driver" and rel.startswith("software/ll/")
            and PurePosixPath(rel).suffix == ".h" and re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256"))),
            "INPUT_INVALID")
    final_sha = sha256_file(safe_path(ws, rel))
    identity = {"schema": "forge-c/provided-effective-code/1", "path": rel,
                "validator_sha256": sha256_file(Path(__file__)),
                "original_sha256": item["sha256"], "effective_sha256": final_sha,
                "source_work_order": item.get("source_work_order"), "source_package": item.get("source_package"),
                "approval": None}
    if final_sha == item["sha256"]:
        return identity
    require(PC.enabled(ws), "CORRECTION_NOT_ENABLED")
    _original(ws, item)
    baseline, inspection = _phase3(ws)
    frozen, approval = _report(ws, baseline, inspection)
    changed = [r for r in frozen["files"] if r["path"] == rel]
    require(len(changed) == 1 and changed[0]["status"] == "CHANGED_LINKED"
            and changed[0]["original_sha256"] == item["sha256"] and changed[0]["final_sha256"] == final_sha
            and bool(changed[0].get("hunks")) and all(h.get("reasons") for h in changed[0]["hunks"]),
            "CORRECTION_REPORT_UNBOUND")
    identity["approval"] = approval
    return identity


def prepare_resume(src, dst, manifest, stable):
    """Normal controller only: import an independently approved corrected LL, retaining its original approval."""
    src, dst = Path(src), Path(dst)
    source_manifest = None
    imported = {}
    for item in manifest.get("provided", []):
        rel = item["path"]
        source = safe_path(src, rel)
        if sha256_file(source) == item["sha256"]:
            continue
        if "SWE.3" not in stable or not PC.enabled(src) or not PC.enabled(dst):
            continue  # existing normal resume mismatch guard retains the legacy refusal/code
        if source_manifest is None:
            source_manifest = json.loads(safe_path(src, ".forge-run/manifest.json").read_text())
        require(source_manifest.get("provided") == manifest.get("provided")
                and source_manifest.get("provided_build") == manifest.get("provided_build"), "RESUME_CONTRACT_CHANGED")
        identity = effective_identity(src, rel)
        require(identity["approval"] is not None and identity["original_sha256"] == item["sha256"],
                "RESUME_APPROVAL_MISSING")
        target = safe_path(dst, rel)
        require(sha256_file(target) in (identity["original_sha256"], identity["effective_sha256"]),
                "RESUME_DESTINATION_CHANGED")
        original = _original(src, item)
        pristine = safe_path(dst, PC.ORIGINALS + "/" + rel, missing=True)
        if pristine.is_file():
            require(pristine.read_bytes() == original, "RESUME_ORIGINAL_CHANGED")
        else:
            PC.save_original(dst, rel, original)  # same original identity, never the corrected bytes
        for defect in identity["approval"]["defects"]:
            ref = ".forge-run/defects/" + defect["id"] + ".json"
            source_record = safe_path(src, ref)
            destination = safe_path(dst, ref, missing=True)
            require(not destination.exists() or destination.read_bytes() == source_record.read_bytes(),
                    "RESUME_DEFECT_COLLISION")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_record, destination)
            _copy_reverify(src, dst, json.loads(source_record.read_text()))
            snapshot = ".forge-run/provided/report-snapshots/" + defect["fixed_report_sha256"] + ".json"
            original_report = safe_path(src, snapshot, missing=True)
            if original_report.is_file():
                target_report = dst / snapshot
                target_report.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original_report, target_report)
        target.chmod(0o644)
        target.write_bytes(source.read_bytes())
        target.chmod(0o444)
        require(sha256_file(target) == identity["effective_sha256"], "RESUME_COPY_CHANGED")
        imported[rel] = identity
    return imported


def validate_resumed(dst, imported):
    """After normal baselines/reports/inspections/evidence were copied, recompute the destination chain."""
    for rel, identity in imported.items():
        require(effective_identity(dst, rel) == identity, "RESUME_DESTINATION_APPROVAL_CHANGED")


def copy_validation_context(src, dst, *, manifest=True):
    """Controller-owned private verification view; no integrity history or unrelated phase state is copied."""
    from ..brownfield.resume import files

    src, dst = Path(src), Path(dst)
    require(src.resolve() != dst.resolve(), "PRIVATE_VIEW_REQUIRED")
    source_manifest = json.loads(safe_path(src, ".forge-run/manifest.json").read_text())
    identities = [effective_identity(src, item["path"]) for item in source_manifest.get("provided", [])]
    paths = [".forge-run/provided/original", ".forge-run/provided/report-snapshots", ".forge-run/test-snapshots", "traceability"]
    paths += [f"{root}/{phase}" for root in ("configuration/baselines", "inspection") for phase in PHASES[:3]]
    for rel in paths:
        if (src / rel).is_dir():
            files(src, rel)
            shutil.copytree(src / rel, dst / rel, dirs_exist_ok=True)
    for rel in ["configuration/system_names.json"] + ([".forge-run/manifest.json"] if manifest else []):
        if (src / rel).is_file():
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(src, rel), target)
    # All CODE reasons in the frozen report are validated by effective_identity;
    # their normal records and verification evidence are needed to recompute it.
    ids = {d["id"] for identity in identities if identity["approval"] for d in identity["approval"]["defects"]}
    records = []
    for defect in defects.all_defects(src):
        if defect["id"] not in ids:
            continue
        rel = ".forge-run/defects/" + defect["id"] + ".json"
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_path(src, rel), target)
        if defect["status"] != "VERIFIED":
            continue
        event = defect["history"][-1]
        if event["tools"] == ["gate-reverify"]:
            _copy_reverify(src, dst, defect)
        else:
            fixed = next(e for e in defect["history"] if e["status"] == "FIXED")
            records += [r for r in defects._tool_results(src) if r.get("phase") == defect["detected_phase"]
                        and r.get("op") in event["tools"] and r.get("result", {}).get("status") == "PASS"
                        and fixed["ts"] < r.get("ts_utc", "") <= event["ts"]]
    # Preserve exact selected protected evidence only. This is not test-integrity
    # history and cannot skip or replace the new execution in the private view.
    for record in records:
        copy_artifacts(src, dst, record["result"].get("artifact_refs", []))
    if records:
        target = dst / "evidence/tool-results.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(r) + "\n" for r in records))
    return records


def _copy_reverify(src, dst, defect):
    if defect["status"] != "VERIFIED" or defect["history"][-1].get("tools") != ["gate-reverify"]:
        return
    ref = defect["history"][-1].get("reverify_receipt") or {}
    path = safe_path(src, ref["path"])
    require(sha256_file(path) == ref["sha256"], "REVERIFY_RECEIPT_CHANGED")
    target = Path(dst) / ref["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    for result in json.loads(path.read_text())["tools"]:
        copy_artifacts(src, dst, result["result"].get("artifact_refs", []))


def artifact_paths(src, refs):
    out = []
    for ref in refs:
        require(isinstance(ref, str) and re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", ref), "ARTIFACT_REF_INVALID")
        paths = list((Path(src) / "evidence/raw").glob(ref.split(":")[-1] + ".*"))
        require(bool(paths), "ARTIFACT_MISSING")
        for path in paths:
            path = safe_path(src, path.relative_to(src).as_posix())
            require(sha256_file(path) == ref.split(":")[-1], "ARTIFACT_CHANGED")
            out.append(path)
    return out


def copy_artifacts(src, dst, refs):
    for path in artifact_paths(src, refs):
        target = Path(dst) / "evidence/raw" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
