"""Write-scope glob matching shared by the guard hook and the scope gate.

Supported: `**/` (zero or more directories), `**` (anything), `*` (within one path segment), `?` (one character).
"""
from __future__ import annotations

import re
from functools import lru_cache


# Written only by the deterministic gates and the conductor; no role may write them, whatever its scope says.
PROTECTED = ["hi/*/gates/**", "hi/*/inspection/**", "hi/trace.json", "hi/trace-matrix.md"]


@lru_cache(maxsize=None)
def glob_to_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def in_scope(rel: str, scope: list[str]) -> bool:
    return any(glob_to_regex(p).match(rel) for p in scope)


def protected(rel: str) -> bool:
    return rel == ".hi" or rel.startswith(".hi/") or in_scope(rel, PROTECTED)
