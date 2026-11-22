"""Minimal, dependency-free JSON Schema (draft 2020-12 subset) validator.

Supports exactly the keywords the forge-c-hi contracts use. Any other validation keyword raises
SchemaError, so a schema can never be silently under-checked.
"""
from __future__ import annotations

import re
from typing import Any

ANNOTATIONS = {"$schema", "$id", "title", "description", "default", "examples", "$comment"}
KEYWORDS = {
    "type", "enum", "const", "pattern", "minLength", "maxLength", "minimum", "maximum",
    "minItems", "maxItems", "items", "required", "properties", "additionalProperties",
    "propertyNames", "oneOf", "allOf", "if", "then", "else",
}

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


class SchemaError(ValueError):
    """The schema itself uses an unsupported keyword or is malformed."""


def _ptr(path: str, key: Any) -> str:
    return f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"


def _check(inst: Any, schema: Any, path: str, out: list[str]) -> None:
    if schema is True or schema == {}:
        return
    if schema is False:
        out.append(f"{path or '/'}: not allowed")
        return
    if not isinstance(schema, dict):
        raise SchemaError(f"schema at {path or '/'} is not an object")
    unknown = set(schema) - KEYWORDS - ANNOTATIONS
    if unknown:
        raise SchemaError(f"unsupported keyword(s) {sorted(unknown)} at {path or '/'}")
    where = path or "/"

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](inst) for t in types):
            out.append(f"{where}: expected type {'|'.join(types)}")
            return
    if "enum" in schema and inst not in schema["enum"]:
        out.append(f"{where}: not one of {schema['enum']}")
    if "const" in schema and inst != schema["const"]:
        out.append(f"{where}: must equal {schema['const']!r}")

    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            out.append(f"{where}: does not match {schema['pattern']}")
        if "minLength" in schema and len(inst) < schema["minLength"]:
            out.append(f"{where}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(inst) > schema["maxLength"]:
            out.append(f"{where}: longer than {schema['maxLength']}")
    if _TYPES["number"](inst):
        if "minimum" in schema and inst < schema["minimum"]:
            out.append(f"{where}: below minimum {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            out.append(f"{where}: above maximum {schema['maximum']}")
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            out.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            out.append(f"{where}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(inst):
                _check(v, schema["items"], _ptr(path, i), out)
    if isinstance(inst, dict):
        for key in schema.get("required", []):
            if key not in inst:
                out.append(f"{_ptr(path, key)}: required property missing")
        props = schema.get("properties", {})
        for key, val in inst.items():
            if key in props:
                _check(val, props[key], _ptr(path, key), out)
            elif "additionalProperties" in schema:
                _check(val, schema["additionalProperties"], _ptr(path, key), out)
        if "propertyNames" in schema:
            for key in inst:
                sub: list[str] = []
                _check(key, schema["propertyNames"], _ptr(path, key), sub)
                if sub:
                    out.append(f"{_ptr(path, key)}: invalid property name")

    if "allOf" in schema:
        for sub_schema in schema["allOf"]:
            _check(inst, sub_schema, path, out)
    if "oneOf" in schema:
        matches = 0
        for sub_schema in schema["oneOf"]:
            sub = []
            _check(inst, sub_schema, path, sub)
            matches += not sub
        if matches != 1:
            out.append(f"{where}: must match exactly one alternative (matched {matches})")
    if "if" in schema:
        probe: list[str] = []
        _check(inst, schema["if"], path, probe)
        branch = schema.get("then") if not probe else schema.get("else")
        if branch is not None:
            _check(inst, branch, path, out)


def validate(instance: Any, schema: dict) -> list[str]:
    """Return a list of error strings (JSON-pointer prefixed); empty means valid."""
    out: list[str] = []
    _check(instance, schema, "", out)
    return out
