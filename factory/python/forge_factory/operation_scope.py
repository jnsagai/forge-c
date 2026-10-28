"""Work-order operation subsets; shared peripheral defaults remain immutable."""
from __future__ import annotations

import copy
import re


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
    return scope


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
