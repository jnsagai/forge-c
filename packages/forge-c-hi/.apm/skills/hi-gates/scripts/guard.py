#!/usr/bin/env python3
"""PreToolUse write-scope guard for forge-c-hi roles (Claude Code and Codex hook input).

Reads the hook JSON on stdin and the active role from .hi/active-role.json (nearest ancestor of cwd).
Exit 0 allows the call. Exit 2 denies it, with the reason on stderr.

- No active role: the guard allows (the gate's scope backstop still applies).
- Active role: the guard fails closed. Unparseable input, or a write whose target paths cannot be
  determined, is denied.
- The .hi/ state directory is never writable by a role.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PATH_KEYS = ("file_path", "notebook_path", "path", "filename")
PATCH_HEADER = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$", re.M)


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


def find_role(start: Path) -> tuple[Path, dict] | None:
    for cand in (start, *start.parents):
        f = cand / ".hi" / "active-role.json"
        if f.is_file():
            return cand, json.loads(f.read_text(encoding="utf-8"))
    return None


def target_paths(payload: dict) -> list[str]:
    tin = payload.get("tool_input")
    if not isinstance(tin, dict):
        return []
    paths = [tin[k] for k in PATH_KEYS if isinstance(tin.get(k), str) and tin[k]]
    for val in tin.values():
        if isinstance(val, str) and "*** " in val:
            for m in PATCH_HEADER.finditer(val):
                paths.append(m.group(1) or m.group(2))
    return paths


def deny(msg: str) -> int:
    print(f"forge-c-hi guard: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    cwd = Path(os.getcwd()).resolve()
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        if isinstance(payload.get("cwd"), str) and payload["cwd"]:
            cwd = Path(payload["cwd"]).resolve()
    except (json.JSONDecodeError, AttributeError):
        payload = None
    try:
        found = find_role(cwd)
    except (OSError, json.JSONDecodeError) as exc:
        return deny(f"cannot read active role: {exc}")
    if not found:
        return 0
    root, role = found
    name = role.get("role", "?")
    if payload is None:
        return deny("hook input is not valid JSON while a role is active")
    paths = target_paths(payload)
    if not paths:
        return deny(f"cannot determine the files written by {payload.get('tool_name', '?')} (role {name})")
    scope = role.get("write_scope") or []
    for p in paths:
        full = Path(p) if os.path.isabs(p) else cwd / p
        full = Path(os.path.normpath(full))
        try:
            rel = full.relative_to(root).as_posix()
        except ValueError:
            return deny(f"{p} is outside the project; role {name} may only write {scope}")
        if rel == ".hi" or rel.startswith(".hi/"):
            return deny(f"{rel}: the .hi/ state directory is managed by the conductor, not by roles")
        if not in_scope(rel, scope):
            return deny(f"{rel} is outside the write scope of role {name} ({role.get('stage', '?')}): {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
