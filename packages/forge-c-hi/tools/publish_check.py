#!/usr/bin/env python3
"""Content check before publishing the package (FR-003, SC-008). Standard library only.

    python3 publish_check.py <package-dir> [--denylist FILE] [--apm APM]

Violation classes:

- BINARY-DOC   PDF, office documents, or any file with NUL bytes (vendor documents are never shipped);
- PRIVATE      generic private identifiers: home or mount paths, private and CGNAT IPv4 addresses, plus every literal
               in a local denylist file that is NOT part of the package (default ~/.config/forge-c/publish-denylist.txt,
               one literal per line; for private project or host names);
- EMAIL        e-mail addresses (example domains such as example.com/.invalid are allowed);
- QUOTED-TEXT  a quoted or block-quoted passage of more than 25 words containing "shall" next to a standard or vendor
               reference (ISO, IEC, RTCA, DO-178, ASPICE, MISRA, RM/DS document ids, datasheet, reference manual);
- HIDDEN-UNICODE zero-width, bidirectional-control and tag characters (built in), plus `apm audit --file` on every
               Markdown primitive under .apm/ when an apm binary is available (otherwise that part is NOT_RUN).

Prints one JSON object; exit 0 when clean, 1 on any violation, 2 on usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "apm_modules"}
DOC_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".chm"}
PRIVATE = [
    ("home path", re.compile(r"/(?:home|Users)/[a-z_][a-z0-9_.-]*/")),
    ("mount path", re.compile(r"/media/[a-z_][a-z0-9_.-]*/")),
    ("private IPv4", re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01])|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))"
                                r"\.\d{1,3}\.\d{1,3}\b")),
]
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
ALLOWED_EMAIL_DOMAINS = re.compile(r"(^|\.)(example\.(com|org|net)|invalid|test|localhost|anthropic\.com)$", re.I)
STANDARD_REF = re.compile(r"\b(ISO|IEC|RTCA|DO-178|ASPICE|Automotive SPICE|MISRA|EN 5\d{4}|RM\d{4}|DS\d{4,5}|"
                          r"datasheet|reference manual)\b", re.I)
HIDDEN = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
QUOTE = re.compile(r"[\"“]([^\"”]{120,})[\"”]")


def files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def quoted_passages(text: str) -> list[str]:
    out = []
    for para in re.split(r"\n\s*\n", text):
        lines = para.splitlines()
        if lines and all(l.lstrip().startswith(">") for l in lines if l.strip()):
            out.append(" ".join(l.lstrip()[1:] for l in lines))
        out += [m.group(1) for m in QUOTE.finditer(para)]
    return out


def check(root: Path, denylist: list[str]) -> list[dict]:
    v: list[dict] = []
    for p in files(root):
        rel = p.relative_to(root).as_posix()
        data = p.read_bytes()
        if p.suffix.lower() in DOC_EXT or b"\0" in data[:8192]:
            v.append({"class": "BINARY-DOC", "file": rel, "detail": "binary or document file"})
            continue
        text = data.decode("utf-8", errors="replace")
        for name, rx in PRIVATE:
            for m in rx.finditer(text):
                v.append({"class": "PRIVATE", "file": rel, "detail": f"{name}: {m.group(0)[:60]}"})
        for m in HIDDEN.finditer(text):
            v.append({"class": "HIDDEN-UNICODE", "file": rel, "detail": f"U+{ord(m.group(0)):04X}"})
        low = text.lower()
        for lit in denylist:
            if lit.lower() in low:
                v.append({"class": "PRIVATE", "file": rel, "detail": "denylisted literal (see local denylist)"})
        for m in EMAIL.finditer(text):
            if not ALLOWED_EMAIL_DOMAINS.search(m.group(1)):
                v.append({"class": "EMAIL", "file": rel, "detail": "e-mail address"})
        for para in re.split(r"\n\s*\n", text):
            if not STANDARD_REF.search(para):
                continue
            for q in quoted_passages(para):
                if len(q.split()) > 25 and re.search(r"\bshall\b", q, re.I):
                    v.append({"class": "QUOTED-TEXT", "file": rel, "detail": q[:80] + "..."})
    return v


def apm_audit(root: Path, apm: str | None) -> dict:
    """`apm audit --file` on every Markdown primitive under .apm/ (skills, agents, instructions)."""
    exe = apm or shutil.which("apm")
    if not exe:
        return {"verdict": "NOT_RUN", "reason": "no apm binary; the built-in hidden-Unicode check still ran"}
    bad = []
    targets = sorted((root / ".apm").rglob("*.md")) if (root / ".apm").is_dir() else []
    for f in targets:
        r = subprocess.run([exe, "audit", "--file", str(f)], cwd=root, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            bad.append(f.relative_to(root).as_posix())
    return {"verdict": "FAIL" if bad else "PASS", "files": len(targets), "failed": bad[:20]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="publish_check")
    ap.add_argument("root")
    ap.add_argument("--denylist", default=os.path.expanduser("~/.config/forge-c/publish-denylist.txt"))
    ap.add_argument("--apm")
    ap.add_argument("--no-audit", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "ERROR", "error": f"{root} is not a directory"}))
        return 2
    deny_path = Path(a.denylist)
    denylist = [l.strip() for l in deny_path.read_text().splitlines()
                if l.strip() and not l.startswith("#")] if deny_path.is_file() else []
    if deny_path.is_file() and deny_path.resolve().is_relative_to(root):
        print(json.dumps({"status": "ERROR", "error": "the denylist must not live inside the package"}))
        return 2
    v = check(root, denylist)
    audit = {"verdict": "SKIPPED"} if a.no_audit else apm_audit(root, a.apm)
    ok = not v and audit["verdict"] in ("PASS", "SKIPPED")
    out = {"status": "PASS" if ok else "FAIL", "violations": len(v), "by_class": {},
           "first": v[:20], "denylist_entries": len(denylist), "hidden_unicode_audit": audit}
    for x in v:
        out["by_class"][x["class"]] = out["by_class"].get(x["class"], 0) + 1
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
