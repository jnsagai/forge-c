"""Pin actual native/structured node→role→model and serve bindings for line products.

This is provenance, never a capability receipt or semantic complexity estimate.
Requests still pass the existing independent role/trial and finite mission gates.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from ..acp import _split_attrs, statements
from ..common import sha256_file
from .durable import Refused, immutable_json

SCHEMA = "forge-c/line-product-role-context/1"


def _attrs(raw):
    values = {}
    for part in _split_attrs(raw):
        key, sep, value = part.partition("=")
        if not sep or key.strip() in values:
            raise Refused("LINE_PRODUCT_GRAPH_ATTRIBUTE_INVALID")
        value = value.strip()
        # Workflow prompts carry real line breaks; only the string form differs from strict JSON.
        values[key.strip()] = json.loads(value, strict=False) if value.startswith('"') else value
    return values


def _command_model(script, module):
    try:
        args = shlex.split(script)
        if "-m" not in args or args[args.index("-m") + 1] != module or args.count("--model") != 1:
            return None
        return args[args.index("--model") + 1]
    except (ValueError, IndexError, TypeError):
        return None


def role_in_phase(role, phase):
    """Whether a role may act in a bound phase. Unphased roles such as release-manager always may."""
    if phase is None:
        return True
    if not isinstance(phase, str) or not re.fullmatch(r"SWE\.[0-9]+", phase):
        raise Refused("LINE_PRODUCT_PHASE_SCOPE_INVALID")
    numbered = re.fullmatch(r"swe([0-9]+)-.+", role)
    return numbered is None or "SWE." + numbered[1] == phase


def capture(workspace, job, profile, *, phase=None):
    """Freeze the graph's model nodes. Every node is validated; only in-phase roles may later obtain a model."""
    from .fault_observer import read_bytes, read_json

    ws = Path(workspace).resolve()
    paths = {name: ws / ".forge-run" / name for name in ("workflow.fabro", "binding.json", "model-profile.json")}
    if any(path.is_symlink() for path in paths.values()):
        raise Refused("LINE_PRODUCT_CONTEXT_SOURCE_SYMLINK")
    graph = read_bytes(paths["workflow.fabro"]).decode()
    binding = read_json(paths["binding.json"])
    recorded = read_json(paths["model-profile.json"])
    if binding.get("workspace") != str(ws) or recorded.get("default") != job["model"]:
        raise Refused("LINE_PRODUCT_CONTEXT_WORKSPACE_OR_DEFAULT_CHANGED")
    parsed = list(statements(graph))
    attrs = {name: _attrs(raw) for _, _, _, name, raw in parsed}
    if len(attrs) != len(parsed):
        raise Refused("LINE_PRODUCT_DUPLICATE_GRAPH_NODE")
    nodes, roles = {}, {}
    allowed = profile["models"]["allowed"]
    for name, value in attrs.items():
        native = "prompt" in value and value.get("backend") != "acp"
        if "prompt" in value and value.get("backend") == "acp":
            raise Refused("LINE_PRODUCT_NONLOCAL_NATIVE_BACKEND")
        structured = _command_model(value.get("script", ""), "forge_factory.lrtx.runner")
        if not native and structured is None:
            continue
        role = (binding.get("nodes", {}).get(name) or {}).get("role")
        if not role and structured is not None and name.endswith("_more"):
            parent = name.removesuffix("_more")
            parent_script = (attrs.get(parent) or {}).get("script", "")
            parent_args = [x for x in shlex.split(parent_script) if x != "--resume"]
            actual_args = [x for x in shlex.split(value["script"]) if x != "--resume"]
            if parent_args == actual_args:
                # The existing factory continuation repeats the same role/task;
                # arbitrary helpers never inherit this binding.
                role = (binding.get("nodes", {}).get(parent) or {}).get("role")
        if not role:
            raise Refused("LINE_PRODUCT_UNDECLARED_MODEL_NODE", name)
        model = value.get("model", job["model"]) if native else structured
        if model not in allowed:
            raise Refused("LINE_PRODUCT_UNDECLARED_MODEL", name)
        routing = (profile.get("structured") or {}).get("role_models") or {}
        expected = routing.get("inspector" if role.endswith("-inspector") else "author", job["model"])
        if routing and model != expected:
            raise Refused("LINE_PRODUCT_PROFILE_ROLE_MODEL_MISMATCH", name)
        served = _command_model((attrs.get(name + "_serve") or {}).get("script", ""), "forge_factory.lrtx.stack")
        edge = re.search(
            r"^\s*" + re.escape(name + "_serve") + r"\s*->\s*" + re.escape(name) + r'\s*\[condition="outcome=succeeded"\]\s*$',
            graph,
            re.M,
        )
        if served != model or not edge:
            raise Refused("LINE_PRODUCT_MODEL_SERVE_BINDING_MISMATCH", name)
        incoming = re.findall(r"^\s*(\w+)\s*->\s*" + re.escape(name) + r"(?:\s*\[|\s*$)", graph, re.M)
        if set(incoming) != {name + "_serve"}:
            raise Refused("LINE_PRODUCT_MODEL_SERVE_BYPASS", name)
        nodes[name] = {"role": role, "model": model, "served_model": served, "native": native}
        if role_in_phase(role, phase):
            roles.setdefault(role, set()).add(model)
    if not nodes or not roles:
        raise Refused("LINE_PRODUCT_MODEL_CONTEXT_EMPTY")
    value = {
        "schema": SCHEMA,
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "workspace": str(ws),
        "source_revision": job["factory_revision"]["commit"],
        "profile_sha256": profile["_sha256"],
        "sources": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in paths.items()},
        "nodes": nodes,
        "role_models": {role: sorted(models) for role, models in sorted(roles.items())},
    }
    path = ws / ".forge-run/line-product-role-context.json"
    immutable_json(path, value)
    return {"path": str(path), "sha256": sha256_file(path)}


def resolve(job):
    from ..lrtx.profile import load
    from .fault_observer import bound_json

    ref = job.get("line_product_context")
    if not ref or Path(ref["path"]).resolve() != Path(job["workspace"]).resolve() / ".forge-run/line-product-role-context.json":
        raise Refused("LINE_PRODUCT_ROLE_CONTEXT_REQUIRED")
    value = bound_json(ref)
    profile = load(job["profile"])
    if (
        value.get("schema") != SCHEMA
        or value.get("job_id") != job["job_id"]
        or value.get("nonce") != job["nonce"]
        or value.get("source_revision") != job["factory_revision"]["commit"]
        or value.get("profile_sha256") != profile["_sha256"]
    ):
        raise Refused("LINE_PRODUCT_ROLE_CONTEXT_CHANGED")
    for source in value["sources"].values():
        path = Path(source["path"])
        if path.is_symlink() or sha256_file(path) != source["sha256"]:
            raise Refused("LINE_PRODUCT_ROLE_SOURCE_CHANGED")
    return value, profile


def request_job(job, role, model, eff):
    """One request's explicit model identity; the durable job/mission/lease remain unchanged."""
    value, profile = resolve(job)
    if not role or model not in value["role_models"].get(role, []):
        raise Refused("LINE_PRODUCT_REQUEST_MODEL_OR_ROLE_UNDECLARED")
    identity = profile["models"]["allowed"][model]
    selected = {**job, "model": model, "model_digest": identity["digest"], "precision": identity["quantization"]}
    if ref := (job.get("product_role_trials") or {}).get(model):
        from .product_role_trial import bind

        selected.pop("product_role_trial", None)
        bind(ref, selected, eff)
    elif model != job["model"]:
        selected.pop("product_role_trial", None)
    entry = (selected.get("role_capabilities") or {}).get(role)
    if not entry or entry.get("identity", {}).get("model_digest") != identity["digest"]:
        alternative = next((a for a in job.get("qualified_local_alternatives", []) if a.get("model_profile") == model), None)
        if alternative:
            selected["role_capabilities"] = alternative.get("role_capabilities") or {}
    return selected
