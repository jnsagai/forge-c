"""Opt-in typed register layout/signature checks in the existing SWE.3 verifier.

Hardware offsets come from a frozen declared primary manual. Compiler profiles,
input identity, artifact storage and process limits reuse the current services.
This checks the declared C interface, not its behavioral correctness or release.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import pretty_json, sha256_bytes, sha256_file
from ..mcp.sdk import ToolDenied, run_argv, tool_version

SCHEMA = "forge-c/typed-register-interface/1"
REPORT = "verification/static/typed_register_layout.json"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")


def validate_contract(value, manifest):
    keys = {"schema", "device_header", "api_contract", "manual", "type_name", "members"}
    if not isinstance(value, dict) or set(value) != keys or value.get("schema") != SCHEMA:
        raise ValueError("TYPED_REGISTER_INTERFACE_SCHEMA_INVALID")
    if not isinstance(value.get("type_name"), str) or not IDENT.fullmatch(value["type_name"]):
        raise ValueError("TYPED_REGISTER_INTERFACE_TYPE_INVALID")
    inputs = {item["path"]: item for item in manifest.get("inputs", [])}
    for key, suffix in (("device_header", ".h"), ("api_contract", ".h"), ("manual", ".md")):
        path = value.get(key)
        if (not isinstance(path, str) or not path.startswith("inputs/") or not path.endswith(suffix)
                or path not in inputs or ".." in Path(path).parts):
            raise ValueError("TYPED_REGISTER_INTERFACE_INPUT_NOT_DECLARED:" + key)
    if not str(inputs[value["manual"]].get("role", "")).startswith("reference_manual"):
        raise ValueError("TYPED_REGISTER_INTERFACE_PRIMARY_MANUAL_REQUIRED")
    members = value.get("members")
    if not isinstance(members, list) or not 1 <= len(members) <= 64:
        raise ValueError("TYPED_REGISTER_INTERFACE_MEMBERS_REQUIRED")
    names, fields = set(), set()
    for member in members:
        if (not isinstance(member, dict) or set(member) != {"register", "member", "width_bits"}
                or any(not isinstance(member.get(k), str) or not IDENT.fullmatch(member[k])
                       for k in ("register", "member"))
                or type(member.get("width_bits")) is not int or member["width_bits"] not in (8, 16, 32)
                or member["register"] in names or member["member"] in fields):
            raise ValueError("TYPED_REGISTER_INTERFACE_MEMBER_INVALID")
        names.add(member["register"])
        fields.add(member["member"])
    return value


def selected(ws):
    from ..delivery_first import selected as delivery_selected

    cfg, _ = delivery_selected(ws)
    return cfg.get("register_interface") if cfg else None


def check_selected(ws):
    """None preserves the legacy path. A selected invalid contract never falls back."""
    from ..delivery_first import selected as delivery_selected

    try:
        cfg, manifest = delivery_selected(ws)
        if not cfg or "register_interface" not in cfg:
            return None
        return _check(Path(ws).resolve(), cfg, manifest)
    except (OSError, ValueError, ToolDenied) as exc:
        return {"verdict": "FAIL", "major_findings": ["TYPED_REGMAP:" + str(exc)[:160]], "stats": {}}


def _check(ws, cfg, manifest):
    from ..delivery_first import checked_paths, context
    from ..development_demonstration import validate_inputs
    from ..layer import ll_header, profile
    from ..mcp.servers.build import ALLOW, PROFILES, WARN
    from ..workorder import split_sections
    from .regmap import architecture_registers, check_defines, parse_section

    validate_inputs(ws)
    manifest_path = ws / ".forge-run/manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    adapter = cfg["register_interface"]
    ctx = context(ws)
    paths = checked_paths(ws, cfg)
    header = ctx.path(ll_header(ws), kind="file")
    tracked = {**paths, ll_header(ws): header}
    before = {name: sha256_file(path) for name, path in tracked.items()}
    for item in manifest.get("provided") or []:
        if sha256_file(ctx.path(item["path"], kind="file")) != item["sha256"]:
            raise ValueError("PROVIDED_COMPONENT_CHANGED:" + item["path"])
    manual = ctx.path(adapter["manual"], kind="file")
    sections, _ = split_sections(manual.read_text(), manual.stem.split("-")[0])
    prof = profile(ws)
    registers = {}
    for source, text in sections.items():
        reg = parse_section(text, prof["register_prefix"])
        if reg:
            if reg["name"] in registers and reg != registers[reg["name"]]["definition"]:
                raise ValueError("PRIMARY_MANUAL_REGISTER_AMBIGUOUS:" + reg["name"])
            registers[reg["name"]] = {"definition": reg, "section": source, "sha256": sha256_bytes(text.encode())}
    findings, members, assertions = [], [], []
    mapped = {m["register"] for m in adapter["members"]}
    architectural = architecture_registers(ws)
    if not architectural:
        findings.append("TYPED_REGMAP:NO_ARCHITECTURE_REGISTER_TABLE")
    scoped = {field.split(".")[0] for field in (manifest.get("operation_scope") or {}).get("register_fields", [])}
    findings += ["TYPED_REGMAP:REGISTER_NOT_MAPPED:" + name for name in sorted((set(architectural) | scoped) - mapped)]
    ctype = adapter["type_name"]
    for m in adapter["members"]:
        source = registers.get(m["register"])
        if source is None:
            findings.append("TYPED_REGMAP:REGISTER_NOT_IN_PRIMARY_MANUAL:" + m["register"])
            continue
        reg, field, width = source["definition"], m["member"], m["width_bits"]
        if any(msb >= width for msb, _ in reg["fields"].values()):
            findings.append("TYPED_REGMAP:FIELD_OUTSIDE_DECLARED_WIDTH:" + m["register"])
        label = m["register"]
        assertions += [f'_Static_assert(offsetof({ctype}, {field}) == {reg["offset"]}U, "offset {label}");',
                       f'_Static_assert(sizeof((({ctype} *)0)->{field}) * CHAR_BIT == {width}U, "width {label}");',
                       f'_Static_assert(_Generic(&(({ctype} *)0)->{field}, volatile uint{width}_t *: 1, '
                       f'const volatile uint{width}_t *: 1, default: 0), "volatile {label}");']
        members.append({**m, "offset": reg["offset"], "primary_section": source["section"],
                        "primary_section_sha256": source["sha256"]})
    numeric = check_defines(header.read_text(), {name.split("_", 1)[1]: rec["definition"]
                           for name, rec in registers.items()}, prof["ll"]["function_prefix"], require_defines=False)
    findings += numeric["major_findings"]
    directory = ws / "verification/static/typed-register-layout"
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / "probe.c"
    includes = [ctx.path(adapter[key], kind="file") for key in ("device_header", "api_contract")]
    includes += [path for path in paths.values() if path.suffix == ".h"]
    includes.append(header)
    text = "#include <stddef.h>\n#include <stdint.h>\n#include <limits.h>\n" + "".join(
        "#include " + json.dumps(str(path)) + "\n" for path in dict.fromkeys(includes)) + "\n".join(assertions) + "\n"
    probe.write_text(text)
    compiler = PROFILES[cfg["compiler_profiles"]["target"]]
    argv = [compiler["cc"], *compiler["flags"], *WARN, *[arg for raw in cfg["include_dirs"]
            for arg in ("-I", str(ctx.path(raw)))], "-fsyntax-only", str(probe)]
    execution = run_argv(argv, directory, 120, ALLOW) if not findings else None
    status = "NOT_RUN" if execution is None else "PASS" if execution.exit_code == 0 else "FAIL"
    if status == "FAIL":
        findings.append("TYPED_REGMAP:LAYOUT_OR_API_COMPILE_FAILED")
    validate_inputs(ws)
    if manifest_path.read_bytes() != manifest_bytes or before != {name: sha256_file(path) for name, path in tracked.items()}:
        findings.append("TYPED_REGMAP:CONTRACT_OR_CANDIDATE_CHANGED_DURING_CHECK")
    proof = {"schema": SCHEMA, "manifest_sha256": sha256_bytes(manifest_bytes), "adapter": adapter,
             "candidate_sha256": {name: before[name] for name in paths}, "checked_header_sha256": before,
             "manual_sha256": sha256_file(manual), "members": members, "probe_sha256": sha256_file(probe),
             "compiler_profile": cfg["compiler_profiles"]["target"], "argv": argv,
             "compiler_version": tool_version(compiler["cc"]), "layout_compile": status,
             "exit_code": execution.exit_code if execution else None,
             "stdout_ref": ctx.store(execution.stdout) if execution else None,
             "stderr_ref": ctx.store(execution.stderr) if execution else None,
             "functional_verification": "NOT_ESTABLISHED_BY_LAYOUT_CHECK", "findings": findings}
    (ws / REPORT).write_text(pretty_json(proof))
    return {"verdict": "FAIL" if findings or status != "PASS" else "PASS", "major_findings": findings,
            "evidence_ref": ctx.store(pretty_json(proof).encode(), kind="json"),
            "stats": {"members_checked": len(members), "layout_compile": status,
                      "defines_checked": numeric["stats"]["defines_checked"]}}
