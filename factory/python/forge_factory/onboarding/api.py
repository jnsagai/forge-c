"""Feature 016 (OB-T031 input): the delivered API of the scope, read from the delivered headers without any model -
the scope functions' prototypes, the handle type with its members, the Init configuration type with its fields and
the handle state's reset constant. These are what the generated instructions name (FR-010: only declared names)."""
from __future__ import annotations

import re

from ..brownfield.scope import strip_comments
from .facts import Fact, Source, derived, not_derived
from .identity import Ctx, _declared_in, _headers_text


def _statement(lines: list[str], i: int) -> str:
    out = []
    for ln in lines[i - 1:i + 8]:
        out.append(ln.strip())
        if ln.rstrip().endswith(";"):
            break
    return re.sub(r"\s+", " ", " ".join(out)).rstrip(";").strip()


def _struct(text: str, name: str) -> tuple[list[tuple[str, str]], int] | None:
    """[(type, member)] of `typedef struct ... { ... } name;` and the line of its closing brace."""
    m = re.search(rf"}}\s*{re.escape(name)}\s*;", text)
    if not m:
        return None
    depth, i = 0, m.start()
    while i >= 0:
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                break
        i -= 1
    body = re.sub(r"#\s*(if|ifdef|ifndef|else|elif|endif)\b[^\n]*", "", text[i + 1:m.start()])
    members = []
    for decl in body.split(";"):
        d = " ".join(decl.split())
        mm = re.match(r"(?:__IO\s+|volatile\s+|const\s+)*([A-Za-z_]\w*(?:\s+\w+)*?)\s*(\*+)?\s*\(?\*?\s*([A-Za-z_]\w*)\)?"
                      r"(?:\s*\[[^\]]*\])?(?:\s*\(.*\))?$", d)
        if mm and mm.group(3) not in ("struct", "void"):
            members.append(((mm.group(1) + (mm.group(2) or "")).strip(), mm.group(3)))
    return members, text.count("\n", 0, m.start()) + 1


def api(ctx: Ctx, style: str) -> Fact:
    names = ctx.delivery["scope"]["functions"]
    hdrs = dict(_headers_text(ctx))
    protos, srcs = {}, []
    for n in names:
        decl = next(iter(_declared_in(ctx, n)), None)
        if decl:
            protos[n] = _statement(hdrs[decl[0]], decl[1])
            srcs.append(Source("file", decl[0], line=decl[1], value=n))
    if not protos:
        return not_derived("api", "delivered_header_declarations", "No delivered header declares the scope functions.")
    val: dict = {"prototypes": protos}
    handle = None
    for p in protos.values():
        m = re.search(r"\(\s*(?:const\s+)?(\w+_HandleTypeDef)\s*\*", p)
        if m:
            handle = m.group(1)
            break
    if handle:
        for rel, lines in hdrs.items():
            text = strip_comments("\n".join(lines))
            st = _struct(text, handle)
            if st:
                val["handle"] = {"type": handle, "members": [m for _, m in st[0]], "header": rel.split("/")[-1]}
                srcs.append(Source("file", rel, line=st[1], value=handle))
                init_t = next((t for t, m in st[0] if m == "Init"), None)
                break
        else:
            init_t = None
        if init_t:
            for rel, lines in hdrs.items():
                st = _struct(strip_comments("\n".join(lines)), init_t)
                if st:
                    val["init"] = {"type": init_t, "fields": [m for _, m in st[0]]}
                    srcs.append(Source("file", rel, line=st[1], value=init_t))
                    break
        pfx = re.match(r"(\w+)_HandleTypeDef", handle).group(1)
        for rel, lines in hdrs.items():
            for i, ln in enumerate(lines, 1):
                m = re.search(rf"\b(HAL_{pfx}_STATE_RESET)\b", ln)
                if m and ("#define" in ln or "=" in ln):
                    val["state_reset"] = m.group(1)
                    srcs.append(Source("file", rel, line=i, value=m.group(1)))
                    break
            if "state_reset" in val:
                break
    elif style == "HAL_STANDALONE":
        m = next((re.search(r"\(\s*(?:const\s+)?(\w+_TypeDef)\s*\*\s*(\w+)", p) for p in protos.values()
                  if re.search(r"\(\s*(?:const\s+)?\w+_TypeDef\s*\*", p)), None)
        if m:
            val["instance_param"] = {"type": m.group(1), "name": m.group(2)}
        init = next((re.search(r"(\w+_InitTypeDef)\s*\*", p) for p in protos.values()
                     if re.search(r"\w+_InitTypeDef\s*\*", p)), None)
        if init:
            for rel, lines in hdrs.items():
                st = _struct(strip_comments("\n".join(lines)), init.group(1))
                if st:
                    val["init"] = {"type": init.group(1), "fields": [mm for _, mm in st[0]]}
                    srcs.append(Source("file", rel, line=st[1], value=init.group(1)))
                    break
    return derived("api", val, "delivered_header_declarations", *srcs[:16])
