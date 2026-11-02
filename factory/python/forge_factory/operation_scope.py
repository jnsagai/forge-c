"""Work-order operation subsets; shared peripheral defaults remain immutable.

Instance mode (optional `instance`, schema forge-c/ll-instance/1): the work order declares that the caller supplies the
peripheral instance. The structured LL pipeline then generates functions that take the instance pointer, with the
signatures of the declared API contract and the typed register layout of the declared device header (both pinned
inputs). Work orders without the declaration keep the register-block array unchanged.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

INSTANCE_SCHEMA = "forge-c/ll-instance/1"
INSTANCE_KEYS = {"schema", "parameter", "macro", "host_object", "register_interface"}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_PROTO = re.compile(r"^[ \t]*static\s+inline\s+(void|uint32_t)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;", re.M)
_PARAM = re.compile(r"^(const\s+)?([A-Za-z_]\w*)\s*(\*)?\s*([A-Za-z_]\w*)$")


def validate(scope, *, delivery=None):
    if not isinstance(scope, dict) or scope.get("schema") != "forge-c/operation-scope/1":
        raise ValueError("OPERATION_SCOPE_INVALID")
    functions = scope.get("functions")
    fields = scope.get("register_fields")
    sections = scope.get("primary_sections")
    if (not isinstance(functions, list) or not functions or len(set(functions)) != len(functions)
            or any(not isinstance(f, str) or not re.fullmatch(r"[A-Za-z_]\w*", f) for f in functions)
            or not isinstance(fields, list) or not fields
            or any(not isinstance(f, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*", f) for f in fields)
            or not isinstance(sections, list) or not sections
            or any(not isinstance(s, str) or not re.fullmatch(r"\d+(?:\.\d+)+", s) for s in sections)
            or not isinstance(scope.get("dependencies"), list)):
        raise ValueError("OPERATION_SCOPE_INVALID")
    if delivery is not None and functions != delivery.get("scope", {}).get("functions"):
        raise ValueError("OPERATION_SCOPE_DELIVERY_MISMATCH")
    if not isinstance(scope.get("prompt_overrides", {}), dict):
        raise ValueError("OPERATION_SCOPE_PROMPTS_INVALID")
    if "instance" in scope:
        validate_instance(scope["instance"], scope)
    return scope


def validate_instance(value, scope):
    """Structure of the instance declaration (no file access; the inputs are checked by instance_contract)."""
    if not isinstance(value, dict) or set(value) != INSTANCE_KEYS or value.get("schema") != INSTANCE_SCHEMA:
        raise ValueError("OPERATION_SCOPE_INSTANCE_SCHEMA_INVALID")
    for key in ("parameter", "macro", "host_object"):
        if not isinstance(value.get(key), str) or not _IDENT.fullmatch(value[key]):
            raise ValueError("OPERATION_SCOPE_INSTANCE_IDENTIFIER_INVALID:" + key)
    if len({value["parameter"], value["macro"], value["host_object"]}) != 3:
        raise ValueError("OPERATION_SCOPE_INSTANCE_IDENTIFIER_INVALID:distinct")
    iface = value.get("register_interface")
    if not isinstance(iface, dict) or iface.get("schema") != "forge-c/typed-register-interface/1":
        raise ValueError("OPERATION_SCOPE_INSTANCE_REGISTER_INTERFACE_INVALID")
    members = iface.get("members") if isinstance(iface.get("members"), list) else []
    mapped = {m.get("register") for m in members if isinstance(m, dict)}
    unmapped = sorted({f.split(".")[0] for f in scope["register_fields"]} - mapped)
    if unmapped:
        raise ValueError("OPERATION_SCOPE_INSTANCE_REGISTER_NOT_MAPPED:" + ",".join(unmapped))
    return value


def validate_instance_inputs(value, inputs: list[dict]):
    """The declared typed register interface names declared inputs (work-order preparation, before the workspace)."""
    from .inspection.typed_registers import validate_contract

    return validate_contract(value["register_interface"], {"inputs": inputs})


def _signature(proto: re.Match, inst: dict, type_name: str) -> dict:
    returns, name, raw = proto.group(1), proto.group(2), proto.group(3).strip()
    params = []
    for k, item in enumerate(p.strip() for p in raw.split(",")) if raw not in ("", "void") else []:
        m = _PARAM.fullmatch(" ".join(item.split()))
        if not m:
            raise ValueError("OPERATION_SCOPE_INSTANCE_API_PARAMETER_UNSUPPORTED:" + name)
        const, ctype, star, pname = m.groups()
        if k == 0:
            if ctype != type_name or not star or pname != inst["parameter"]:
                raise ValueError("OPERATION_SCOPE_INSTANCE_API_FIRST_PARAMETER:" + name)
            params.append({"name": pname, "type": f"{'const ' if const else ''}{ctype} *"})
        elif const or star or ctype != "uint32_t":
            raise ValueError("OPERATION_SCOPE_INSTANCE_API_PARAMETER_UNSUPPORTED:" + name)
        else:
            params.append({"name": pname, "type": "uint32_t"})
    if not params:
        raise ValueError("OPERATION_SCOPE_INSTANCE_API_FIRST_PARAMETER:" + name)
    return {"returns": returns, "params": params}


def instance_contract(ws, manifest: dict) -> dict:
    """The validated instance declaration of a prepared workspace with the function signatures of its API contract.
    A declared but invalid or changed contract raises; it never falls back to the register-block array."""
    from .common import sha256_file

    scope = validate(manifest.get("operation_scope"))
    inst = scope["instance"]
    if manifest.get("layer") != "LL":
        raise ValueError("OPERATION_SCOPE_INSTANCE_REQUIRES_LL_LAYER")
    if manifest.get("delivery_first") is not None or manifest.get("delivery"):
        raise ValueError("OPERATION_SCOPE_INSTANCE_EXCLUSIVE")
    iface = validate_instance_inputs(inst, manifest.get("inputs") or [])
    declared = {i["path"]: i for i in manifest.get("inputs") or []}
    ws = Path(ws)
    for key in ("device_header", "api_contract"):
        path = ws / iface[key]
        if not path.is_file() or sha256_file(path) != declared[iface[key]].get("sha256"):
            raise ValueError("OPERATION_SCOPE_INSTANCE_INPUT_CHANGED:" + iface[key])
    type_name = iface["type_name"]
    device = (ws / iface["device_header"]).read_text(errors="replace")
    if not re.search(rf"\bextern\s+{type_name}\s+{inst['host_object']}\s*;", device) or not re.search(
            rf"^\s*#\s*define\s+{inst['macro']}\b", device, re.M) or not all(
            re.search(rf"^\s*#\s*ifdef\s+{flag}\b", device, re.M)
            for flag in ("FORGE_HOST_BUILD", "FORGE_HOST_DEVICE_IMPLEMENTATION")):
        raise ValueError("OPERATION_SCOPE_INSTANCE_DEVICE_HEADER_MISMATCH")
    # the target definition of the instance macro is the peripheral's base address of the work order's profile (the
    # secure alias the profile names); the host definition (&<host object>) is not an address
    from .peripheral import load as load_profile

    targets = re.findall(rf"^\s*#\s*define\s+{re.escape(inst['macro'])}\s+\(\s*\(\s*{type_name}\s*\*\s*\)\s*"
                         r"(0x[0-9A-Fa-f]+)[uUlL]*\s*\)\s*$", device, re.M)
    base = int(str(load_profile(manifest.get("peripheral") or "rcc")["base_address"]), 16)
    if len(targets) != 1 or int(targets[0], 16) != base:
        raise ValueError("OPERATION_SCOPE_INSTANCE_BASE_MISMATCH")
    protos = list(_PROTO.finditer(re.sub(r"/\*.*?\*/|//[^\n]*", "", (ws / iface["api_contract"]).read_text(
        errors="replace"), flags=re.S)))
    names = [m.group(2) for m in protos]
    if sorted(names) != sorted(scope["functions"]) or len(set(names)) != len(names):
        raise ValueError("OPERATION_SCOPE_INSTANCE_API_MISMATCH")
    sigs = {m.group(2): _signature(m, inst, type_name) for m in protos}
    return {**inst, "type_name": type_name, "device_header": Path(iface["device_header"]).name,
            "api_contract": Path(iface["api_contract"]).name,
            "members": {m["register"]: m["member"] for m in iface["members"]},
            "signatures": {n: sigs[n] for n in scope["functions"]}}


def instance_of(ws) -> dict | None:
    """None without an instance declaration (every existing work order)."""
    try:
        manifest = json.loads((Path(ws) / ".forge-run/manifest.json").read_text())
    except (OSError, ValueError):
        return None
    if "instance" not in (manifest.get("operation_scope") or {}):
        return None
    return instance_contract(ws, manifest)


def scoped(profile, scope):
    if scope is None:
        return profile
    validate(scope)
    result = copy.deepcopy(profile)
    if not set(scope["primary_sections"]) <= set(profile["rm"]["key_sections"]):
        raise ValueError("OPERATION_SCOPE_UNKNOWN_PRIMARY_SECTION")
    result["rm"]["key_sections"] = list(scope["primary_sections"])
    overrides = scope.get("prompt_overrides") or {}
    if any(k not in profile.get("prompt", {}) or not isinstance(v, str) or not v.strip() for k, v in overrides.items()):
        raise ValueError("OPERATION_SCOPE_PROMPTS_INVALID")
    result["prompt"].update(overrides)
    result["operation_scope"] = scope
    return result
