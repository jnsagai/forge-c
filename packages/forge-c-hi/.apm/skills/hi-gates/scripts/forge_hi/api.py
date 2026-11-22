"""Command functions shared by the `hi` CLI and the forge-c-hi MCP server.

Each function returns ``(exit_code, payload)``: exit 0 PASS/DONE, 1 FAIL/BLOCKED/NOT_RUN gap, 2 usage or configuration
error (raised as ConfigError or ValueError and mapped by the callers). The payload is compact; full results are on disk.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import __version__, gates, quality as _quality, scope as _scope, trace as _trace
from .config import ConfigError, REFS, effective_rigor, load_project, schema, stages
from .io import read_json, sha256_file, write_json
from .jsonschema_lite import validate as schema_validate
from .provenance import utc_now

MAX_OUT = 2048
PRESETS = REFS.parents[1] / "hi-conductor" / "references" / "harness-presets.json"
CLASS_ALIASES = {"nl": "natural_language", "natural-language": "natural_language", "doc": "reference_document",
                 "reference-document": "reference_document"}
PRIVACY = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]", re.I)


def compact(payload: dict) -> dict:
    """Trim a payload until its JSON is at most 2 KB."""
    out = dict(payload)
    while len(json.dumps(out, separators=(",", ":"))) > MAX_OUT:
        lists = [k for k, v in out.items() if isinstance(v, list) and v]
        if not lists:
            out = {k: out[k] for k in ("cmd", "verdict", "status") if k in out} | {"truncated": True}
            break
        k = max(lists, key=lambda key: len(json.dumps(out[key])))
        out[k] = out[k][: max(0, len(out[k]) // 2)]
        out["truncated"] = True
    return out


def _gate_payload(cmd: str, doc: dict, written: str | None) -> tuple[int, dict]:
    payload = {
        "cmd": cmd, "gate": doc["gate"], "verdict": doc["verdict"], "issues": len(doc["issues"]),
        "top": [{k: i[k] for k in ("code", "target_id") if k in i} for i in doc["issues"][:8]],
    }
    if doc.get("not_run_reason"):
        payload["not_run_reason"] = doc["not_run_reason"]
    if written:
        payload["written"] = written
    return (0 if doc["verdict"] == "PASS" else 1), payload


def _load_presets() -> dict:
    if not PRESETS.is_file():
        raise ConfigError(f"harness presets not found at {PRESETS}; is the hi-conductor skill installed?")
    return read_json(PRESETS)


def role_binding(preset: str, role: str, model: str | None = None, family: str | None = None) -> dict:
    presets = _load_presets()["presets"]
    if preset not in presets:
        raise ConfigError(f"unknown harness preset '{preset}' (known: {sorted(presets)})")
    p = presets[preset]
    cmd = list(p[role]["command"])
    if model:
        cmd += list(p.get("model_flag") or []) + ([model] if p.get("model_flag") else [])
    fam = family or p.get("model_family")
    if not fam:
        raise ConfigError(f"preset '{preset}' needs an explicit model family for the {role} (e.g. --{role}-family qwen)")
    return {"harness": p["harness"], "command": cmd, "model": model, "model_family": fam,
            "read_only": bool(p[role]["read_only"])}


def init(
    root: Path,
    *,
    level: str | None = None,
    profile: str | None = None,
    input_class: str | None = None,
    entry: str | None = None,
    inputs: list[str] | None = None,
    project_id: str | None = None,
    author: str | None = None,
    inspector: str | None = None,
    author_model: str | None = None,
    inspector_model: str | None = None,
    author_family: str | None = None,
    inspector_family: str | None = None,
    from_file: str | None = None,
    stages_list: list[str] | None = None,
    force: bool = False,
) -> tuple[int, dict]:
    root = Path(root)
    path = root / ".hi" / "project.json"
    if path.exists() and not force:
        raise ConfigError(f"{path} exists; use --force to replace it")
    if from_file:
        src = Path(from_file) if Path(from_file).is_absolute() else root / from_file
        doc = read_json(src)
    else:
        doc = {"schema": "forge-c-hi/project@1", "inputs": [], "roles": {}}
    if project_id or "project_id" not in doc:
        doc["project_id"] = project_id or re.sub(r"[^a-z0-9-]+", "-", root.name.lower()).strip("-")[:64] or "project"
    if profile:
        doc["profile"] = profile
    doc.setdefault("profile", "generic")
    if level:
        doc["integrity_level"] = level
    if input_class:
        doc["input_class"] = CLASS_ALIASES.get(input_class, input_class)
    doc.setdefault("input_class", "natural_language")
    if entry:
        doc["entry_stage"] = entry
    doc.setdefault("entry_stage", "sys-req" if doc["input_class"] == "natural_language" else "sw-req")
    if stages_list:
        doc["stages"] = stages_list
    for spec in inputs or []:
        parts = spec.split(":")
        if len(parts) < 2:
            raise ConfigError(f"--input must be PATH:KIND[:DOC_ID], got {spec!r}")
        ref = {"path": parts[0], "kind": parts[1]}
        if len(parts) > 2:
            ref["doc_id"] = parts[2]
        doc["inputs"] = [i for i in doc.get("inputs", []) if i.get("path") != ref["path"]] + [ref]
    roles = doc.setdefault("roles", {})
    if author or "author" not in roles:
        roles["author"] = role_binding(author or _load_presets()["reference"]["author"], "author", author_model, author_family)
    if inspector or "inspector" not in roles:
        roles["inspector"] = role_binding(inspector or _load_presets()["reference"]["inspector"], "inspector",
                                          inspector_model, inspector_family)
    if "integrity_level" not in doc:
        raise ConfigError("--level HI-n is required (no default integrity level)")
    errors = schema_validate(doc, schema("project"))
    if errors:
        raise ConfigError(f"invalid project configuration: {errors[:3]}")
    effective_rigor(doc)  # refuses unknown profiles and unmapped levels
    lock, warnings = {}, []
    for inp in doc["inputs"]:
        p = root / inp["path"]
        if not p.is_file():
            raise ConfigError(f"input {inp['path']} does not exist")
        lock[inp["path"]] = sha256_file(p)
        if inp["kind"] in ("needs", "constraints") and PRIVACY.search(p.read_text(encoding="utf-8", errors="replace")):
            warnings.append(f"{inp['path']} may contain personal data or a secret; remove it before running")
    write_json(path, doc)
    write_json(root / ".hi" / "inputs.lock.json", {"schema": "forge-c-hi/inputs-lock@1", "created_utc": utc_now(),
                                                   "inputs": lock})
    rigor = effective_rigor(doc)
    return 0, {"cmd": "init", "status": "DONE", "project": doc["project_id"], "profile": rigor["profile"],
               "level": rigor["level"], "level_name": rigor["level_name"], "entry": doc["entry_stage"],
               "inputs": len(lock), "warnings": warnings, "written": ".hi/project.json"}


def validate(root: Path, file: str) -> tuple[int, dict]:
    doc = gates.validate_file(root, Path(file))
    stage = None
    try:
        stage = read_json(Path(root) / file if not Path(file).is_absolute() else Path(file)).get("stage")
    except (OSError, ValueError, AttributeError):
        pass
    return _gate_payload("validate", doc, f"hi/{stage}/gates/validate.json" if stage in stages() else None)


def quality(root: Path, stage: str) -> tuple[int, dict]:
    _stage_ok(stage)
    return _gate_payload("quality", _quality.run(root, stage), f"hi/{stage}/gates/quality.json")


def trace(root: Path, stage: str | None = None) -> tuple[int, dict]:
    if stage:
        _stage_ok(stage)
    doc = _trace.run(root, stage)
    code, payload = _gate_payload("trace", doc, "hi/trace-matrix.md" if doc["verdict"] != "NOT_RUN" else None)
    return code, payload


def scope(root: Path, role: str, stage: str, snapshot: str | None = None) -> tuple[int, dict]:
    _stage_ok(stage)
    if role not in ("author", "inspector", "release", "intake"):
        raise ValueError(f"unknown role {role}")
    snap = None if snapshot is None else (Path(snapshot) if Path(snapshot).is_absolute() else Path(root) / snapshot)
    return _gate_payload("scope", _scope.run(root, role, stage, snapshot_file=snap), f"hi/{stage}/gates/scope.json")


def gate(root: Path, stage: str) -> tuple[int, dict]:
    _stage_ok(stage)
    summ = gates.gate_stage(root, stage)
    payload = {"cmd": "gate", "stage": stage, "verdict": summ["verdict"], "gates": summ["gates"],
               "issues": len(summ["issues"]),
               "top": [{k: i[k] for k in ("gate", "code", "target_id") if k in i} for i in summ["issues"][:8]],
               "written": f"hi/{stage}/gates/"}
    return (0 if summ["verdict"] == "PASS" else 1), payload


def status(root: Path) -> tuple[int, dict]:
    return 0, dict(gates.status(root), cmd="status")


def role_set(root: Path, role: str, stage: str, run_id: str | None = None) -> tuple[int, dict]:
    _stage_ok(stage)
    load_project(root)
    scope_list = _scope.write_scope(role, stage)
    write_json(Path(root) / ".hi" / "active-role.json", {
        "role": role, "stage": stage, "write_scope": scope_list, "run_id": run_id or "manual", "set_utc": utc_now()})
    return 0, {"cmd": "role set", "status": "DONE", "role": role, "stage": stage, "write_scope": scope_list}


def role_clear(root: Path) -> tuple[int, dict]:
    p = Path(root) / ".hi" / "active-role.json"
    existed = p.exists()
    p.unlink(missing_ok=True)
    return 0, {"cmd": "role clear", "status": "DONE", "cleared": existed}


def seal(root: Path) -> tuple[int, dict]:
    from . import seal as _seal
    res = _seal.seal(root)
    return (0 if res["status"] == _seal.READY else 1), {
        "cmd": "seal", "status": res["status"], "package": res["package"], "files": res["files"],
        "gaps": len(res["gaps"]), "top": [{"code": g["code"], "source": g["source"]} for g in res["gaps"][:8]]}


def not_available(cmd: str, task: str) -> tuple[int, dict]:
    return 1, {"cmd": cmd, "verdict": "NOT_RUN", "not_run_reason": f"'{cmd}' is not available in forge-c-hi "
               f"{__version__} yet ({task})"}


def _stage_ok(stage: str) -> None:
    if stage not in stages():
        raise ValueError(f"unknown stage '{stage}' (known: {list(stages())})")
