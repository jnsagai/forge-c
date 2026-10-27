"""Fixed-subject MCP model gate and the deterministic graph's snapshot step.

Agents choose neither the package nor source paths. The controller's inputs/case.json
binds the facts and platform. Author probes do not overwrite the graph's inspected
snapshot; inspector probes read that snapshot, never a mutable author file.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..common import canonical_json, sha256_bytes, sha256_file
from ..mcp.sdk import ToolContext, result
from . import facts
from .model_gate import SIM_DIR, check


def run(ctx: ToolContext, candidate: bool = True, *, freeze: bool = False) -> dict:
    root = ctx.workspace
    case = json.loads((root / "inputs/case.json").read_text())
    package = json.loads((root / "inputs/onboarding-package.json").read_text())
    if facts.canonical_hash(package) != case["package_sha256"] or package["sha256"] != case["package_sha256"]:
        raise ValueError("MODEL_INPUT_SUBJECT_CHANGED")
    for entry in case.get("input_files", []):
        path = ctx.path(entry["path"], kind="file")
        if not path.is_relative_to(root / "inputs") or sha256_file(path) != entry["sha256"]:
            raise ValueError("MODEL_INPUT_FILE_CHANGED")
    key = case["key"]
    if Path(key).name != key or key in (".", "..") or "/" in key or "\\" in key:
        raise ValueError("MODEL_CASE_KEY_INVALID")
    if package["work_order"] != key:
        raise ValueError("MODEL_CASE_KEY_MISMATCH")
    prefix = facts.value(package, "register_prefix")
    if not candidate:
        if case.get("hide_model"):
            raise ValueError("MODEL_HIDDEN_FROM_AUTHOR")
        source = SIM_DIR / f"{prefix.lower()}_model.py"
        gate = check(key, pkg=package, example=root / "inputs")
        digest = sha256_file(source)
    else:
        inspector = ctx.role == "onboard-model-inspector"
        source = root / ("onboarding/inspection-model.py" if inspector else "onboarding/model/model.py")
        source = ctx.path(str(source), kind="file")
        from .model_sandbox import MAX_SOURCE

        allowed = root / ("onboarding" if inspector else "onboarding/model")
        if not source.is_relative_to(allowed) or source.stat().st_size > MAX_SOURCE:
            raise ValueError("MODEL_CANDIDATE_SCOPE_OR_SIZE")
        blob = source.read_bytes()
        digest = sha256_bytes(blob)
        if inspector:
            prior = json.loads((root / "onboarding/gate.json").read_text())
            if prior["model_sha256"] != digest:
                raise ValueError("MODEL_INSPECTION_SNAPSHOT_CHANGED")
        platform = ctx.path("inputs/platform.repl", kind="file")
        with tempfile.TemporaryDirectory(prefix="forge-ob-candidate-") as temp:
            scratch = Path(temp)
            model, repl = scratch / "model.py", scratch / "platform.repl"
            model.write_bytes(blob)
            repl.write_bytes(platform.read_bytes())
            # Freeze the same bytes the source subset gate and Renode will read.
            model.chmod(0o444)
            repl.chmod(0o444)
            gate = check(key, pkg=package, example=root / "inputs", model_paths=(model, repl), isolated=True)
        if freeze and gate["verdict"] == "PASS":
            if inspector:
                raise ValueError("MODEL_INSPECTOR_CANNOT_FREEZE")
            (root / "onboarding/inspection-model.py").write_bytes(blob)
    gate = {**gate, "model_sha256": digest, "package_sha256": case["package_sha256"],
            "invocation_id": ctx.invocation_id}
    directory = root / "onboarding"
    directory.mkdir(exist_ok=True)
    name = "gate.json" if freeze else "gate.inspector.json" if ctx.role.endswith("-inspector") else "gate.author.json"
    (directory / name).write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n")
    return result(ctx, gate["verdict"], "RM model checks " + gate["verdict"],
                  [ctx.store(canonical_json(gate), "json")], gate["findings"],
                  {"model_sha256": digest, "limits": len(gate.get("limits", [])), **gate.get("stats", {})},
                  tool="forge-onboarding-model-gate", version=gate.get("version"))
