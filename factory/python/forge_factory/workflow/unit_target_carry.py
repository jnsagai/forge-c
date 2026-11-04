"""Normal-factory inheritance of passed SWE.4 target evidence.

Producer adapters remain byte-identical. A committed normal-resume receipt
binds a genuinely passed parent, the original creator, an unchanged semantic
contract and the exact new manifest. Only then may the unchanged adapter read
a private current-input view with its ORIGINAL creator manifest. No live
manifest, invocation, proof, phase verdict or policy is rewritten.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, pretty_json, sha256_file, state_dir
from ..inspection import swtrace
from ..inspection.engine import PHASES, Store
from . import unit_target_observation, unit_target_timing

PATH = ".forge-run/resume/target-proof-carry.json"
SCHEMA = "forge-c/swe4-target-proof-carry/1"
ADAPTERS = (unit_target_timing, unit_target_observation)
ADMIN = {"work_order", "created_at", "input_baseline_commit", "phase_scope", "resumed_from", "rework_context"}


class CarryRefused(ValueError):
    pass


def _require(ok, reason):
    if not ok:
        raise CarryRefused("TARGET_PROOF_CARRY_" + reason)


def _sha(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _read(ws, rel):
    return json.loads(unit_target_timing._safe_path(ws, rel).read_text())


def _manifest(ws):
    return _read(ws, ".forge-run/manifest.json")


def promotion_reference(path):
    """A bounded operator reference, never an imported/self-asserted decision."""
    path = Path(path)
    _require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4096,
             "MIGRATION_REFERENCE_FILE_INVALID")
    try:
        ref = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise CarryRefused("TARGET_PROOF_CARRY_MIGRATION_REFERENCE_INVALID") from exc
    _require(isinstance(ref, dict) and set(ref) == {"registry_path", "decision_id"}
             and isinstance(ref["registry_path"], str) and Path(ref["registry_path"]).is_absolute()
             and re.fullmatch(r"pd-[0-9a-f]{20}", str(ref["decision_id"])), "MIGRATION_REFERENCE_INVALID")
    return ref


def _source(wo):
    from ..common import safe_id

    safe_id(wo)
    path = state_dir() / "workorders" / wo / "workspace"
    _require(not any(p.is_symlink() for p in (path, path.parent))
             and path.is_dir() and path.resolve().is_relative_to((state_dir() / "workorders").resolve()), "SOURCE_UNSAFE")
    _require(_manifest(path).get("work_order") == wo, "SOURCE_IDENTITY_CHANGED")
    return path


def _record(ws):
    records = [r for r in swtrace._tool_records(Path(ws)) if r.get("op") == "run_unit"]
    _require(bool(records), "UNIT_RECORD_MISSING")
    record = records[-1]
    _require(record.get("phase") == "SWE.4" and record.get("server") == "forge-tests-mcp"
             and record.get("role") in ("swe4-author", "swe4-inspector")
             and record.get("result", {}).get("status") == "PASS", "UNIT_RECORD_NOT_PASSED_PHASE4")
    return record


def _attest(ws):
    """Recompute the normal baseline/independent-inspection chain, never a receipt's claimed PASS."""
    store = Store(Path(ws))
    phases = {}
    for phase in PHASES[:4]:
        _require(store.gate(phase)["decision"] == "PASS", "PARENT_PHASE_NOT_PASS:" + phase)
        baseline = store.latest_baseline(phase)
        inspection = store.inspections(phase)[-1]
        checklist = store.checklist(phase)
        _require(baseline["author_role"] == f"swe{phase[-1]}-author"
                 and inspection["inspector_role"] == f"swe{phase[-1]}-inspector"
                 and inspection["baseline_hash"] == baseline["baseline_hash"]
                 and inspection["checklist_sha256"] == checklist["sha256"]
                 and all(inspection.get("items", {}).get(c["id"], {}).get("verdict") == "PASS"
                         for c in store.applicable(checklist)["checks"] if c.get("required")),
                 "PARENT_INDEPENDENT_IDENTITY_CHANGED:" + phase)
        phases[phase] = {"baseline": baseline, "inspection": inspection}
    _require(not store.missing_outputs("SWE.4"), "PARENT_PHASE4_REQUIRED_OUTPUT_MISSING")
    return {"work_order": _manifest(ws)["work_order"], "phases_sha256": _sha(phases),
            "tool_record_sha256": _sha(_record(ws)),
            "phase_baseline_hashes": {phase: value["baseline"]["baseline_hash"] for phase, value in phases.items()}}


def _phase_inputs(ws, attestation):
    """All inherited contracts remain passed/current, including SWE.1/2 outside producer-local seals."""
    store = Store(Path(ws))
    expected = attestation.get("phase_baseline_hashes", {})
    _require(set(expected) == set(PHASES[:4])
             and all(store.current_hash(phase) == expected[phase] and store.gate(phase)["decision"] == "PASS"
                     for phase in PHASES[:4]), "CURRENT_PHASE_INPUTS_CHANGED")


def _semantic(man):
    value = copy.deepcopy(man)
    for key in ADMIN:
        value.pop(key, None)
    # The source revision is compared separately, with an explicit exact CRE
    # decision required for a consumer-only revision migration.
    value.pop("factory_revision", None)
    historical = value.get("historical_safety_scope")
    if historical is not None:
        scope = historical.get("scope", {})
        _require(scope.get("work_order_id") == man.get("work_order"), "HISTORICAL_OWNER_IDENTITY_CHANGED")
        del scope["work_order_id"]
    return value


def _promotion(ref, creator, consumer, ws):
    from ..reliability.policy import load
    from ..reliability.promotion import schema_errors, tree_sha256

    _require(isinstance(ref, dict) and set(ref) == {"registry_path", "decision_id"}, "MIGRATION_REFERENCE_INVALID")
    path = Path(ref["registry_path"])
    _require(path.is_absolute() and path.is_file() and not path.is_symlink()
             and not path.resolve().is_relative_to(Path(ws).resolve())
             and not path.stat().st_mode & 0o022
             and re.fullmatch(r"pd-[0-9a-f]{20}", str(ref["decision_id"])), "MIGRATION_REGISTRY_UNTRUSTED")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3) as db:
        row = db.execute("SELECT candidate,baseline,decision,record FROM cre_promotion_decisions WHERE decision_id=?",
                         (ref["decision_id"],)).fetchone()
        triggers = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                                   "AND tbl_name='cre_promotion_decisions'"))
    _require(row is not None and all(
        re.search(r"BEFORE\s+" + operation + r"\s+ON\s+cre_promotion_decisions", triggers.get(
            "cre_promotion_decisions_no_" + operation.lower(), ""), re.I)
        and "RAISE(ABORT" in triggers.get("cre_promotion_decisions_no_" + operation.lower(), "").upper()
        for operation in ("UPDATE", "DELETE")), "MIGRATION_DECISION_MISSING_OR_MUTABLE")
    record = json.loads(row[3])
    gates = {g["name"]: g for g in record.get("hard_gates", [])}
    expected = {"protected_files", "policy_integrity", "reproducer", "prevention", "quality_process",
                "golden_benchmark", "holdout"}
    _require(set(gates) == expected and len(record["hard_gates"]) == len(expected)
             and all(g["result"] == "PASS" or (name == "reproducer" and g["result"] == "NOT_RUN"
                     and g.get("reason_code") == "NOT_APPLICABLE_FOR_CHANGE") for name, g in gates.items()),
             "MIGRATION_HARD_GATES_NOT_PASSED")
    _require(row[0] == consumer and row[1] == creator and row[2] == "ELIGIBLE_FOR_OFFLINE_REVIEW"
             and record.get("decision_id") == ref["decision_id"] and not schema_errors(record)
             and record.get("decision") == row[2]
             and record.get("evaluator_kind") == "INDEPENDENT_DETERMINISTIC_RUNNER"
             and record.get("allowed_auto_deployment") is False
             and record.get("policy_sha256") == load().sha256
             and record.get("candidate_sha256") == tree_sha256(consumer, REPO_ROOT)
             and record.get("baseline_sha256") == tree_sha256(creator, REPO_ROOT), "MIGRATION_DECISION_NOT_EXACT_ELIGIBLE")
    runtime = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
    _require(runtime == consumer, "MIGRATION_CONSUMER_NOT_CURRENT_SOURCE")
    return {"reference": ref, "row_sha256": _sha(list(row)), "creator_revision": creator, "consumer_revision": consumer}


def _compatible(original, current, ws, promotion=None):
    _require(_semantic(original) == _semantic(current), "SEMANTIC_CONTRACT_CHANGED")
    a, b = original.get("factory_revision", {}), current.get("factory_revision", {})
    _require(a.get("dirty") is False and b.get("dirty") is False
             and all(re.fullmatch(r"[0-9a-f]{40}", str(r.get("commit"))) for r in (a, b)), "SOURCE_REVISION_UNBOUND")
    if a["commit"] == b["commit"]:
        _require({k: v for k, v in a.items() if k != "branch"} == {k: v for k, v in b.items() if k != "branch"},
                 "SOURCE_CONTEXT_CHANGED")
        return None
    _require(promotion is not None, "CONSUMER_REVISION_CHANGE_UNQUALIFIED")
    return _promotion(promotion, a["commit"], b["commit"], ws)


def _git_receipt(ws):
    """Normal factory resume commits protect the receipt and creator snapshot from agent-written substitutes."""
    out = subprocess.run(["git", "log", "-1", "--format=%H%n%an%n%ae%n%s", "--", PATH], cwd=ws,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    _require(len(out) == 4 and out[1:3] == ["forge-factory", "factory@forge-c.local"]
             and out[3].startswith(("forge: resume from ", "forge: validated brownfield resume from ",
                                    "forge: seal target evidence carry from ")), "NORMAL_RESUME_COMMIT_MISSING")
    raw = unit_target_timing._safe_path(ws, PATH).read_bytes()
    committed = subprocess.run(["git", "show", out[0] + ":" + PATH], cwd=ws,
                               capture_output=True, check=True).stdout
    _require(raw == committed, "RECEIPT_CHANGED_AFTER_NORMAL_COMMIT")
    receipt = json.loads(raw)
    _require(out[3] in ("forge: resume from " + receipt["source_work_order"] +
                       " (stable: " + ", ".join(receipt["stable_phases"]) + ")",
                       "forge: validated brownfield resume from " + receipt["source_work_order"],
                       "forge: seal target evidence carry from " + receipt["source_work_order"]),
             "NORMAL_RESUME_PARENT_CHANGED")
    return receipt


def _view(ws, creator_bytes, record, adapter):
    """Only a private CURRENT-input view receives the original creator manifest."""
    from ..brownfield.resume import files
    from .provided_input_identity import copy_validation_context, effective_identity

    with tempfile.TemporaryDirectory(prefix="forge-carried-target-proof-") as td:
        view = Path(td) / "workspace"
        for rel in ("software/hal", "software/ll", "software/src", "software/include", "software/tests/unit",
                    "inputs/vendor/include", "workproducts/SWE.1", "workproducts/SWE.2",
                    "workproducts/SWE.3", "workproducts/SWE.4"):
            if (Path(ws) / rel).is_dir():
                files(Path(ws), rel)  # reject original symlinks before copying, not only the private view
                shutil.copytree(Path(ws) / rel, view / rel)
        context_records = copy_validation_context(ws, view, manifest=False)
        manifest = json.loads(creator_bytes)
        items = manifest.get("inputs", []) + (manifest.get("provided_build") or {}).get("files", [])
        for item in items:
            path = unit_target_timing._safe_path(ws, item["path"])
            _require(sha256_file(path) == item["sha256"], "DECLARED_INPUT_CHANGED")
            target = view / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        provided = {item["path"]: effective_identity(ws, item["path"]) for item in manifest.get("provided", [])}
        if (Path(ws) / "configuration/system_names.json").is_file():
            target = view / "configuration/system_names.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(unit_target_timing._safe_path(ws, "configuration/system_names.json"), target)
        (view / ".forge-run").mkdir(parents=True, exist_ok=True)
        (view / ".forge-run/manifest.json").write_bytes(creator_bytes)
        (view / "evidence/raw").mkdir(parents=True, exist_ok=True)
        for ref in record["result"].get("artifact_refs", []):
            _require(re.fullmatch(r"artifact:sha256:[0-9a-f]{64}", ref) is not None, "ARTIFACT_REFERENCE_INVALID")
            found = list((Path(ws) / "evidence/raw").glob(ref.split(":")[-1] + ".*"))
            _require(bool(found), "ARTIFACT_MISSING")
            for path in found:
                path = unit_target_timing._safe_path(ws, path.relative_to(ws).as_posix())
                _require(sha256_file(path) == ref.split(":")[-1], "ARTIFACT_CHANGED")
                shutil.copyfile(path, view / "evidence/raw" / path.name)
        (view / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in context_records + [record]))
        for rel, identity in provided.items():
            _require(effective_identity(view, rel) == identity, "PRIVATE_PROVIDED_CONTEXT_CHANGED")
        return adapter.trace(view)


def _validated(ws, adapter):
    receipt = _git_receipt(ws)
    _require(receipt.get("schema") == SCHEMA and receipt.get("destination_manifest_sha256") ==
             sha256_file(unit_target_timing._safe_path(ws, ".forge-run/manifest.json")), "DESTINATION_FRAME_CHANGED")
    current = _manifest(ws)
    _require(current["work_order"] == receipt["destination_work_order"], "DESTINATION_IDENTITY_CHANGED")
    _require(_source(current["work_order"]).resolve() == Path(ws).resolve()
             and (current.get("resumed_from") or {}).get("source_work_order") == receipt["source_work_order"],
             "NORMAL_PARENT_BINDING_MISSING")
    source = _source(receipt["source_work_order"])
    _require(_attest(source) == receipt["parent_attestation"], "PARENT_PASS_CHANGED")
    entry = receipt["entries"].get(adapter.METRIC)
    _require(isinstance(entry, dict), "ADAPTER_RECEIPT_MISSING")
    creator = _source(entry["creator_work_order"])
    _require(_attest(creator) == entry["creator_attestation"], "CREATOR_PASS_CHANGED")
    creator_path = unit_target_timing._safe_path(ws, entry["creator_manifest_ref"])
    creator_bytes = creator_path.read_bytes()
    _require(hashlib.sha256(creator_bytes).hexdigest() == entry["creator_manifest_sha256"], "CREATOR_MANIFEST_CHANGED")
    _require(sha256_file(unit_target_timing._safe_path(creator, ".forge-run/manifest.json")) ==
             entry["creator_manifest_sha256"], "CREATOR_FRAME_CHANGED")
    original = json.loads(creator_bytes)
    _require(original["work_order"] == entry["creator_work_order"], "CREATOR_IDENTITY_CHANGED")
    migration = _compatible(original, current, ws, entry.get("promotion_ref"))
    _require(migration == entry.get("migration"), "MIGRATION_ROW_CHANGED")
    record = _record(ws)
    _require(_sha(record) == entry["tool_record_sha256"], "LATEST_UNIT_RECORD_CHANGED")
    _phase_inputs(ws, entry["creator_attestation"])
    return entry, creator_bytes, record


def trace(ws, adapter):
    """Shared trace hook. A fresh direct result, including FAIL, always takes precedence over inherited evidence."""
    direct = adapter.trace(ws)
    if not direct[2] or not (Path(ws) / PATH).exists():
        return direct
    try:
        _, original, record = _validated(Path(ws), adapter)
        inherited = _view(Path(ws), original, record, adapter)
        _require(not inherited[2], "CREATOR_PROOF_NO_LONGER_VALID")
        return inherited
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return [], {}, ["UT:TARGET_PROOF_CARRY_REFUSED:" + str(exc)[:200]]


def bind_resume(src, ws, stable, promotion=None):
    """Called only by normal resume before its factory commit; never from trace or a model tool."""
    src, ws = Path(src), Path(ws)
    if "SWE.4" not in stable:
        return False
    active = [a for a in ADAPTERS if (src / a.DECLARATION).exists()]
    if not active:
        return False
    parent = _attest(src)
    old, current = _manifest(src), _manifest(ws)
    _require(_source(old["work_order"]).resolve() == src.resolve()
             and _source(current["work_order"]).resolve() == ws.resolve()
             and old["work_order"] != current["work_order"], "NORMAL_WORKSPACE_IDENTITY_REQUIRED")
    _require((current.get("resumed_from") or {}).get("source_work_order") == old["work_order"], "NORMAL_PARENT_BINDING_MISSING")
    record, entries = _record(src), {}
    for adapter in active:
        direct = adapter.trace(src)
        if not direct[2]:
            _require(bool(direct[1]) and all(v == "PASS" for v in direct[1].values()), "SOURCE_TARGET_NOT_PASS")
            creator_bytes = (src / ".forge-run/manifest.json").read_bytes()
            creator_attestation = parent
            old_entry = {}
        else:
            old_entry, creator_bytes, _ = _validated(src, adapter)
            inherited = _view(src, creator_bytes, record, adapter)
            _require(bool(inherited[1]) and not inherited[2] and all(v == "PASS" for v in inherited[1].values()),
                     "SOURCE_TARGET_NOT_PASS")
            creator_attestation = old_entry["creator_attestation"]
        original = json.loads(creator_bytes)
        promotion_ref = promotion or old_entry.get("promotion_ref")
        migration = _compatible(original, current, ws, promotion_ref)
        _require(_sha(_record(ws)) == _sha(record), "COPIED_UNIT_RECORD_CHANGED")
        _phase_inputs(ws, creator_attestation)
        manifest_sha = hashlib.sha256(creator_bytes).hexdigest()
        rel = ".forge-run/resume/target-proof-origins/" + manifest_sha + ".json"
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(creator_bytes)
        entries[adapter.METRIC] = {"creator_work_order": original["work_order"], "creator_manifest_ref": rel,
                                  "creator_manifest_sha256": manifest_sha, "creator_attestation": creator_attestation,
                                  "tool_record_sha256": _sha(record), "promotion_ref": promotion_ref, "migration": migration}
    receipt = {"schema": SCHEMA, "source_work_order": old["work_order"], "parent_attestation": parent,
               "stable_phases": stable,
               "destination_work_order": current["work_order"],
               "destination_manifest_sha256": sha256_file(ws / ".forge-run/manifest.json"),
               "entries": entries}
    path = ws / PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(receipt))
    return True


def seal_after_setup(ws):
    """Normal run has finished setting its administrative context; seal the final exact destination frame."""
    ws = Path(ws)
    if not (ws / PATH).exists():
        return
    receipt = _git_receipt(ws)
    original = receipt["destination_manifest_sha256"]
    if original == sha256_file(ws / ".forge-run/manifest.json"):
        return
    # Rebuild solely from normal parent PASS and unchanged creator inputs.
    refs = {json.dumps(e.get("promotion_ref"), sort_keys=True) for e in receipt["entries"].values()}
    _require(len(refs) == 1, "MIXED_MIGRATION_REFERENCES")
    promotion = json.loads(next(iter(refs)))
    bind_resume(_source(receipt["source_work_order"]), ws, receipt["stable_phases"], promotion)
    subprocess.run(["git", "add", "--", PATH, ".forge-run/resume/target-proof-origins"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.name=forge-factory", "-c", "user.email=factory@forge-c.local", "commit",
                    "--allow-empty", "-qm", "forge: seal target evidence carry from " + receipt["source_work_order"]],
                   cwd=ws, check=True)
