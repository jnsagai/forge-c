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
