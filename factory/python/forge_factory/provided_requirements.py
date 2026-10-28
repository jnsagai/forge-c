"""Hash-bound externally prepared SWE.1 inputs; no model authorship or human review is invented."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .afo.durable import digest, immutable_json
from .common import sha256_file


def scope_identity(man):
    return digest({k: man.get(k) for k in ("peripheral", "operation_scope", "scope", "budgets", "target", "layer")})


def payload(doc):
    return {k: v for k, v in doc.items() if k != "review"}


def validate(ws):
    ws = Path(ws)
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    binding = man.get("provided_requirements")
    if binding is None:
        return None, man
    if binding.get("path") != "inputs/provided-requirements.json":
        raise ValueError("PROVIDED_REQUIREMENTS_PATH_INVALID")
    path = ws / binding["path"]
    if path.is_symlink() or not path.is_file() or sha256_file(path) != binding["sha256"]:
        raise ValueError("PROVIDED_REQUIREMENTS_HASH_CHANGED")
    doc = json.loads(path.read_text())
    if doc.get("schema") != "forge-c/provided-requirements/1" or doc.get("scope_sha256") != scope_identity(man):
        raise ValueError("PROVIDED_REQUIREMENTS_SCOPE_CHANGED")
    review = doc.get("review") or {}
    who = str(review.get("reviewed_by") or "")
    if (review.get("status") != "REVIEWED" or not who.strip() or
            who.lower().startswith(("codex", "claude", "qwen", "gpt", "agent", "ai", "llm", "swe", "fabro"))
            or not review.get("reviewed_at") or not review.get("record_ref")
            or review.get("payload_sha256") != digest(payload(doc))):
        raise ValueError("PROVIDED_REQUIREMENTS_REVIEW_MISSING_OR_UNBOUND")
    if not doc.get("origin", {}).get("prepared_by") or not doc.get("sources"):
        raise ValueError("PROVIDED_REQUIREMENTS_PROVENANCE_MISSING")
    declared = {r["path"]: r["sha256"] for r in man["inputs"]
                if r.get("role", "").startswith(("reference_manual", "datasheet"))}
    for source in doc["sources"]:
        if (declared.get(source["path"]) != source["sha256"] or
                sha256_file(ws / source["path"]) != source["sha256"]):
            raise ValueError("PROVIDED_REQUIREMENTS_PRIMARY_SOURCE_CHANGED")
    return doc, man


def materialize(ws):
    from .assurance.hardware import index
    from .lrtx import swe1
    from .lrtx.visit import write_scoped

    ws = Path(ws)
    doc, man = validate(ws)
    if doc is None:
        raise ValueError("PROVIDED_REQUIREMENTS_NOT_SELECTED")
    inv = swe1.inventory(ws)
    if inv["missing_sections"]:
        raise ValueError("PROVIDED_REQUIREMENTS_PRIMARY_SECTION_MISSING")
    groups = swe1.groups(inv)
    supplied = doc.get("groups") or {}
    if set(supplied) != {g["id"] for g in groups}:
        raise ValueError("PROVIDED_REQUIREMENTS_COVERAGE_MISMATCH")
    idx = index(ws / "inputs/sections/RM0486")
    results = []
    for group in [*groups, None]:
        value = supplied[group["id"]] if group else doc.get("crosscutting")
        jsonschema.validate(value, swe1.GROUP_SCHEMA)
        errors = swe1.validate_group(ws, value, group, swe1.system_name(ws), idx)
        if errors:
            raise ValueError("PROVIDED_REQUIREMENTS_INVALID:" + ";".join(errors[:6]))
        if group:
            results.append((group, {"task": "provided:" + group["id"], "doc": value, "status": "VALID"}))
        else:
            cross = {"task": "provided:crosscutting", "doc": value, "status": "VALID"}
    errors = swe1.consistency(results, cross)
    if errors:
        raise ValueError("PROVIDED_REQUIREMENTS_INCONSISTENT:" + str(errors[:5]))
    swe1.assemble(ws, inv, results, cross)
    errors = swe1.self_check(ws)
    if errors:
        raise ValueError("PROVIDED_REQUIREMENTS_CHECK_FAILED:" + ";".join(errors[:5]))
    paths = [swe1.REQS, swe1.EFFECTS, swe1.CSV, swe1.GAPS, swe1.SAFETY]
    receipt = {"schema": "forge-c/provided-requirements-receipt/1", "authorship": "EXTERNALLY_PREPARED",
               "qwen_authored": False, "scope_sha256": scope_identity(man), "input": man["provided_requirements"],
               "origin": doc["origin"], "review_as_supplied": doc["review"],
               "files": {p: sha256_file(ws / p) for p in paths}}
    write_scoped(ws, {"traceability/assisted_requirements.json": json.dumps(receipt, indent=2) + "\n"}, "swe1_author")
    immutable_json(ws / ".forge-run/provided-requirements-receipt.json", receipt)
    return swe1.reply(ws, "PASS", [])  # Import-stage status; not a Qwen authorship or inspection receipt.


def findings(ws):
    path = Path(ws) / ".forge-run/manifest.json"
    if not path.is_file() or not json.loads(path.read_text()).get("provided_requirements"):
        return []
    try:
        doc, man = validate(ws)
        receipt = json.loads((Path(ws) / "traceability/assisted_requirements.json").read_text())
        if (receipt["input"] != man["provided_requirements"] or receipt["scope_sha256"] != scope_identity(man)
                or receipt["review_as_supplied"] != doc["review"]):
            raise ValueError("PROVIDED_REQUIREMENTS_RECEIPT_CHANGED")
        if any(sha256_file(Path(ws) / p) != sha for p, sha in receipt["files"].items()):
            raise ValueError("PROVIDED_REQUIREMENTS_IMPORTED_CONTENT_CHANGED")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["ASSISTED_REQUIREMENTS:" + str(exc)[:200]]
    return []
