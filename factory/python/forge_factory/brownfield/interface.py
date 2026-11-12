"""CAPA-112 (runs WO-F014-CMP-SWE1-CRCL-20261102-05/-06): the delivered interface vocabulary for SWE.1.

A FROZEN delivery fixes the API, including the constants its value arguments take (ST: `LL_CRC_POLYLENGTH_16B`,
`LL_CRC_INDATA_REVERSE_BIT_BYBYTE`, ...). SWE.1 is written without the delivered code (FR-007), so the requirements of
a parameterised scoped function could name a polynomial size or reversal mode but never the argument that selects it;
the inspector failed SWE1-02 (not feasible / not objectively verifiable against the frozen interface) three times.

This module extracts, at intake, only that vocabulary: for each scoped function, the constant names its parameters
accept and its queries return (the header's `@arg` lists of that function, kept only when the name is an object-like
macro of the delivered code) and their integer values (evaluated through the delivered code and its dependencies).
No function body, declaration text or comment text is copied; the register field values a requirement states still
come from the reference manual. The result is a declared, hash-bound work-order input (inputs/delivered-interface.json)
that the SWE.1 author and inspector receive; nothing is written when no scoped function has such constants."""
from __future__ import annotations

import json
import re

from ..common import sha256_bytes
from . import scope as S

OUT = "inputs/delivered-interface.json"
ROLE = "delivered_interface"
SCHEMA = "forge-c/delivered-interface/1"
RULE = ("Delivered interface vocabulary of a brownfield work order: for each scoped delivered function, the constants "
        "each value argument accepts and a query returns, with their integer values, extracted deterministically from "
        "the delivered headers. It contains no function body and no implementation; the register field values a "
        "requirement states come from the reference manual.")
AUTHOR_NOTE = (f" Delivered interface ({OUT}, a provided source): it lists, for the scoped delivered functions, the "
               "constants each value argument accepts (and a query returns) with their values. A requirement on such a "
               "function names its argument by that constant (with its value) and states the register field values "
               "the call gives; take those field values from the reference manual, and record a constant whose value "
               "contradicts the reference manual as an open point.")
_TAG = re.compile(r"@(param|retval)\b[ \t]*(\w*)(.*?)(?=@(?:param|retval|note|brief|rmtoll|warning)\b|\Z)", re.S)
_ARG = re.compile(rf"@arg\s+(?:@ref\s+)?({S.IDENT})")


def _doc_block(raw: str, line: int) -> str:
    """The /** ... */ comment directly above the definition whose name is on `line` (1-based), else ''."""
    head = "\n".join(raw.split("\n")[: line - 1])
    end = head.rfind("*/")
    if end < 0 or re.search(r"[;{}#]", head[end + 2:]):
        return ""
    start = head.rfind("/**", 0, end)
    return head[start:end] if start >= 0 else ""


def extract(files: dict[str, bytes], records: list[dict], functions: list[str]) -> dict | None:
    """`files`: {workspace path: bytes} of the delivery (code and dependencies); `records`: the intake file records
    (path, role, sha256). None when no scoped function documents argument or return constants."""
    text = {p: b.decode("utf-8", errors="replace") for p, b in files.items()}
    code = [r["path"] for r in records if r.get("role") == "delivered_code" and r["path"] in text]
    own = S.constant_macros([text[p] for p in code])
    macros = S.constant_macros([text[p] for p in code] + [text[r["path"]] for r in records
                                                          if r.get("role") != "delivered_code" and r["path"] in text])
    defs: dict[str, tuple[S.Definition, str]] = {}
    for p in code:
        for d in S.index(text[p], p):
            defs.setdefault(d.name, (d, text[p]))

    def constants(section: str) -> list[dict]:
        names = list(dict.fromkeys(n for n in _ARG.findall(section) if n in own))
        out = []
        for n in names:
            v = S.evaluate(own[n], macros)
            out.append({"name": n, "value": None if v is None else f"0x{v:08X}"})
        return out

    rows = []
    for fn in functions:
        if fn not in defs:
            continue
        d, raw = defs[fn]
        params, returns = [], []
        for m in _TAG.finditer(_doc_block(raw, d.line)):
            consts = constants(m.group(3))
            if not consts:
                continue
            if m.group(1) == "param" and m.group(2) in d.params:
                params.append({"name": m.group(2), "constants": consts})
            elif m.group(1) == "retval":
                returns.extend(c for c in consts if c not in returns)
        if params or returns:
            rows.append({"function": fn, "parameters": params, **({"returns": returns} if returns else {})})
    if not rows:
        return None
    return {"schema": SCHEMA, "rule": RULE,
            "source_files": [{"path": p, "sha256": sha256_bytes(files[p])} for p in code], "functions": rows}


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def declared(manifest: dict) -> str | None:
    """The workspace path of the declared delivered-interface input, else None (greenfield, or no constants)."""
    return next((i["path"] for i in manifest.get("inputs") or [] if i.get("role") == ROLE), None)
