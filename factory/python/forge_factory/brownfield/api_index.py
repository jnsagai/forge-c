"""CAPA-242: a bounded view of a brownfield work order for the native SWE.2 author.

The native author's conversation must stay under the qualified context allowance minus its output cap (about 114,688
tokens on the Ornith author profile). ST's delivered headers are large (SPI LL 121 kB, TIM larger) and the work-order
manifest carries a 15 kB resume identity no author needs. Written when the delivered code is injected:
- api-index.md: every in-scope delivered function (from delivery/scope.json) with its signature and the line range of its
  doc comment and body, so the author reads the code by ranges;
- swe2-brief.json: the manifest without resume_identity (compact JSON).
Both are derived deterministically from files already in the workspace; nothing else changes."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import DELIVERY_DIR
from . import scope as S

INDEX = DELIVERY_DIR + "/api-index.md"
BRIEF = DELIVERY_DIR + "/swe2-brief.json"
DROP = ("resume_identity",)


def _range(lines: list[str], code: list[str], line: int) -> tuple[int, int, str]:
    """(first, last, signature) of the definition at 1-based `line`: its doc comment (when directly above) to its
    closing brace; `code` is the comment-stripped text (same line numbers)."""
    i = line - 1
    sig, depth, end, opened = [], 0, i, False
    for k in range(i, len(code)):
        if not opened:
            sig.append(lines[k].strip())
        for ch in code[k]:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            end = k
            break
    signature = " ".join(s for s in sig if s and s != "{").split("{")[0].strip()
    start = i
    j = i - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j >= 0 and lines[j].strip().endswith("*/"):
        while j >= 0 and "/*" not in lines[j]:
            j -= 1
        if j >= 0:
            start = j
    return start + 1, end + 1, signature


def index_text(ws: Path) -> str:
    try:
        funcs = json.loads((ws / DELIVERY_DIR / "scope.json").read_text()).get("functions") or []
    except (OSError, ValueError):
        funcs = []
    rows, cache = [], {}
    for f in funcs:
        rel, line = f.get("file"), f.get("line")
        if not isinstance(rel, str) or not isinstance(line, int):
            continue
        if rel not in cache:
            try:
                text = (ws / rel).read_text(errors="replace")
            except OSError:
                continue
            cache[rel] = (text.splitlines(), S.strip_comments(text).splitlines())
        lines, code = cache[rel]
        if not 0 < line <= len(lines):
            continue
        a, b, sig = _range(lines, code, line)
        rows.append(f"| {f.get('name')} | `{sig}` | {rel} | {a}-{b} |")
    head = ["# Delivered API index (factory-generated, CAPA-242)", "",
            "Every in-scope delivered function: read its lines with read_file offset/limit (offset = first line).", ""]
    if not rows:
        return "\n".join(head + ["no in-scope delivered function was found in .forge-run/delivery/scope.json", ""])
    return "\n".join(head + ["| function | signature | file | lines |", "|---|---|---|---|", *rows, ""])


def write(ws, manifest: dict) -> None:
    ws = Path(ws)
    (ws / DELIVERY_DIR).mkdir(parents=True, exist_ok=True)
    (ws / INDEX).write_text(index_text(ws))
    brief = {k: v for k, v in manifest.items() if k not in DROP}
    (ws / BRIEF).write_text(json.dumps(brief, sort_keys=True, separators=(",", ":")))


# CAPA-243 (SPI HAL L46: the HAL SWE.2 author read the whole provided ST LL header, 121 kB, then parts of it again, and
# 2 of 3 author cycles were refused CAPABILITY_LIMIT at ~115k input tokens): the same bounded view for a HAL designed
# on a PROVIDED CMSIS LL - its constant groups and functions by line range.
PROVIDED_INDEX = ".forge-run/provided-ll-api.md"
_DEF = re.compile(r"\b(?:__STATIC_(?:FORCE)?INLINE|static\s+inline)\b[^;{(]*?\b(LL_\w+)\s*\(")
_GROUP = re.compile(r"@defgroup\s+(\w+)\s*(.*?)\s*(?:\*/)?\s*$")


def provided_text(header_rel: str, text: str) -> str:
    lines = text.splitlines()
    code = S.strip_comments(text).splitlines()
    groups = [(i + 1, m.group(1), m.group(2)) for i, ln in enumerate(lines) for m in [_GROUP.search(ln)] if m]
    grows = [f"- {name} ({title}): {a}-{(groups[k + 1][0] - 1) if k + 1 < len(groups) else len(lines)}"
             for k, (a, name, title) in enumerate(groups)]
    frows = []
    for i, c in enumerate(code):
        m = _DEF.search(c)
        if m:
            a, b, sig = _range(lines, code, i + 1)
            sig = re.sub(r"^(?:__STATIC_(?:FORCE)?INLINE|static\s+inline)\s+", "", sig)
            frows.append(f"- `{sig}`: {a}-{b}")
    head = ["# Provided LL API index (factory-generated, CAPA-243)", "",
            f"{header_rel} is PROVIDED and frozen. Read it only with read_file offset/limit on these ranges "
            "(offset = first line); never read the whole header.", ""]
    return "\n".join(head + ["## Groups (constants and functions, by line range)", *(grows or ["none"]), "",
                             "## Functions (signature: lines of comment and body)", *(frows or ["none"]), ""])


def write_provided(ws) -> str | None:
    """Writes PROVIDED_INDEX for a HAL work order on a provided CMSIS LL; None (no file) for every other work order."""
    from ..layer import ll_header
    from .cmsis import provided_api

    ws = Path(ws)
    if not provided_api(ws):
        return None
    rel = ll_header(ws)
    (ws / PROVIDED_INDEX).parent.mkdir(parents=True, exist_ok=True)
    (ws / PROVIDED_INDEX).write_text(provided_text(rel, (ws / rel).read_text(errors="replace")))
    return PROVIDED_INDEX
