"""Deferred normal CODE ownership for a HAL's supplied LL; never a new input approval or phase PASS."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import canonical_json, pretty_json, sha256_bytes, sha256_file, state_dir, utc_now
from ..rework_context import read_file
from . import provided_changes as PC
from .engine import Store

SCHEMA = "forge-c/provided-code-reference/1"
FIELD = "provided_code_reference"
KIND = "PROVIDED_CODE"
RECEIPT = ".forge-run/provided/early-code-handoff.json"


def require(ok, code):
    if not ok:
        raise ValueError("EARLY_PROVIDED_CODE_" + code)


def manifest(ws):
    value = json.loads(read_file(Path(ws), ".forge-run/manifest.json"))
    require(isinstance(value, dict), "MANIFEST_INVALID")
    return value


def enabled(ws):
    value = manifest(ws)
    return (PC.enabled(ws) and value.get("layer") == "HAL" and not value.get("delivery")
            and any(isinstance(item, dict) and item.get("role") == "provided_ll_driver"
                    for item in value.get("provided", [])))


def _reference(ws, item):
    rel, digest = item.get("path"), item.get("sha256")
    require(item.get("role") == "provided_ll_driver" and isinstance(rel, str)
            and rel.startswith("software/ll/") and rel.endswith(".h")
            and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "INPUT_INVALID")
    read_file(Path(ws), rel)  # the exact supplied workspace copy, never a vendor dependency or another file
    original = Path(ws) / PC.ORIGINALS / rel
    if original.exists() or original.is_symlink():
        raw = read_file(Path(ws), PC.ORIGINALS + "/" + rel)
    else:
        source = item.get("source_work_order")
        require(isinstance(source, str) and re.fullmatch(r"WO-[A-Za-z0-9_-]{1,180}", source), "ORIGINAL_UNAVAILABLE")
        root = state_dir() / "workorders" / source / "workspace"
        require(not root.is_symlink() and not root.parent.is_symlink(), "ORIGINAL_UNAVAILABLE")
        raw = read_file(root, rel)
    require(sha256_bytes(raw) == digest, "ORIGINAL_CHANGED")
    return {"schema": SCHEMA, "path": rel, "original_sha256": digest,
            "provided_item_sha256": sha256_bytes(canonical_json(item))}


def reference(ws, evidence_refs):
    """Return the exact existing provided-input binding named by a source location, or no early exception."""
    try:
        if not enabled(ws) or not isinstance(evidence_refs, list):
            return None
        values = manifest(ws).get("provided", [])
        matches = []
        for item in values:
            if not isinstance(item, dict) or item.get("role") != "provided_ll_driver":
                continue
            rel = item.get("path")
            if any(isinstance(ref, str) and re.fullmatch(re.escape(str(rel)) + r":[1-9][0-9]*", ref)
                   for ref in evidence_refs):
                matches.append(_reference(ws, item))
        return matches[0] if len(matches) == 1 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def validate(ws, record):
    from . import defects as D

    require(record.get("schema") == "forge-c/defect/0.5" and record.get("kind") == "CODE"
            and record.get("target_kind") == KIND and record.get("target_phase") == "SWE.3"
            and record.get("detected_phase") in ("SWE.1", "SWE.2", "SWE.3"), "DEFECT_INVALID")
    require(isinstance(record.get("id"), str) and re.fullmatch(r"DEF-[0-9]{3,6}", record["id"]), "ID_INVALID")
    phase = record["detected_phase"]
    require(record.get("reported_by") in ("swe" + phase[-1] + "-author", "swe" + phase[-1] + "-inspector"),
            "REPORTER_INVALID")
    bound = reference(ws, record.get("evidence_refs"))
    require(bound is not None and record.get(FIELD) == bound, "INPUT_BINDING_CHANGED")
    texts = D._requirement_texts(ws)
    ids, quote = record.get("requirement_ids"), D._norm(record.get("requirement_quote", ""))
    require(isinstance(ids, list) and bool(ids) and all(value in texts for value in ids)
            and len(quote) >= 20 and any(quote in D._norm(texts[value]) for value in ids), "REQUIREMENT_CHANGED")
    history = record.get("history")
    require(isinstance(history, list) and bool(history) and history[-1].get("status") == record.get("status"),
            "HISTORY_INVALID")
    return bound


def pending(ws):
    from . import defects as D

    values = [record for record in D.all_defects(ws) if record.get("target_kind") == KIND
              and record.get("kind") == "CODE" and record.get("status") == "OPEN"
              and record.get("detected_phase") in ("SWE.1", "SWE.2")]
    require(len(values) <= D.MAX_OPEN, "TOO_MANY_PENDING")
    for record in values:
        bound = validate(ws, record)
        require(sha256_bytes(read_file(Path(ws), bound["path"])) == bound["original_sha256"],
                "PENDING_CODE_CHANGED_BEFORE_OWNER")
    return values


def claim(ws):
    """Controller SWE.3 entry only; no phase or inspection result is created or copied."""
    from . import defects as D

    values = pending(ws)
    if not values:
        return []
    store = Store(Path(ws))
    for phase in ("SWE.1", "SWE.2"):
        require(store.gate(phase)["decision"] == "PASS", "PREFIX_NOT_PASSED:" + phase)
        baseline = store.latest_baseline(phase)
        require(baseline is not None and baseline["baseline_hash"] == store.current_hash(phase),
                "PREFIX_CHANGED:" + phase)
    for record in values:
        D._event(record, "IN_FIX", note="normal SWE.3 entry: supplied LL correction remains workspace-only "
                 "and independently reviewed")
        D._save(ws, record)
    return [record["id"] for record in values]


def carry(src, dst, stable):
    """Carry only pending normal early CODE, with intact passed requirements/design; never old INPUT or closure."""
    src, dst = Path(src), Path(dst)
    values = pending(src)
    if not values:
        return []
    require(enabled(dst) and "SWE.2" in stable and "SWE.3" not in stable, "RESUME_PREFIX_INVALID")
    origin, target = manifest(src), manifest(dst)
    require(origin.get("provided") == target.get("provided"), "RESUME_INPUT_CHANGED")
    for key in ("driver", "layer", "peripheral", "purpose", "target", "scope", "operation_scope"):
        require(origin.get(key) == target.get(key), "RESUME_SCOPE_CHANGED:" + key)
    prefix = {}
    for phase in ("SWE.1", "SWE.2"):
        a, b = Store(src), Store(dst)
        require(a.gate(phase)["decision"] == b.gate(phase)["decision"] == "PASS", "PREFIX_NOT_PASSED:" + phase)
        before, after = a.latest_baseline(phase), b.latest_baseline(phase)
        require(before["baseline_hash"] == after["baseline_hash"] == a.current_hash(phase) == b.current_hash(phase),
                "RESUME_PREFIX_CHANGED:" + phase)
        prefix[phase] = before["baseline_hash"]
    snapshots = []
    for record in values:
        validate(dst, record)
        rel = ".forge-run/defects/" + record["id"] + ".json"
        raw = read_file(src, rel)
        require(json.loads(raw) == record and not (dst / rel).exists() and not (dst / rel).is_symlink(),
                "RESUME_DEFECT_COLLISION")
        snapshots.append((rel, raw))
    receipt = {"schema": "forge-c/provided-early-code-handoff/1", "created_at": utc_now(),
               "source_work_order": origin["work_order"], "source_manifest_sha256": sha256_file(src / ".forge-run/manifest.json"),
               "work_order": target["work_order"], "prefix": prefix,
               "defects": [{"path": rel, "sha256": sha256_bytes(raw)} for rel, raw in snapshots],
               "inherited_verdict": False, "next_owner": "SWE.3", "intended_next_step": "CLAIM_AT_ENTRY"}
    require(not (dst / RECEIPT).exists() and not (dst / RECEIPT).is_symlink(), "RESUME_RECEIPT_EXISTS")
    for rel in [RECEIPT, *(rel for rel, _raw in snapshots)]:
        path = dst / rel
        require(not any(p.is_symlink() for p in path.parents if p.is_relative_to(dst)), "RESUME_SYMLINK")
    for rel, raw in snapshots:
        path = dst / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    path = dst / RECEIPT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(receipt))
    path.chmod(0o444)
    return [record["id"] for record in values]
