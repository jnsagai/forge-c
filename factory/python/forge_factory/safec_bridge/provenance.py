"""F011-T005 / F011-AT-005: the public/private boundary between public Forge-C and the private SafeC Forge.

    python -m forge_factory.safec_bridge.provenance scan --base <sha> [--private <safec checkout>] [--out <json>]

Two guards, both fail closed:
- `public_summary()` is the only way a SafeC record becomes repository content. It keeps allow-listed keys, accepts
  only bounded scalar values, and refuses (never truncates) a value that looks like a credential, an absolute path
  into the private checkout, or a line of private source.
- `scan_public_tree()` checks every line the public branch adds since `base` for credentials and, when the private
  checkout is given, for lines of its tracked files that public Forge-C did not already contain at `base`. Private
  lines are held in memory as hashes only; nothing from the private checkout is written anywhere. The shared wire
  contracts (published by Forge-C) are not private content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, pretty_json

# shapes of secrets, not their values; a match refuses the content
CREDENTIAL_PATTERNS = {  # group "s" is the secret part
    "PRIVATE_KEY": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?P<s>)"),
    "GITHUB_TOKEN": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_(?P<s>[A-Za-z0-9_]{20,})"),
    "API_KEY": re.compile(r"\bsk-(?:ant-)?(?P<s>[A-Za-z0-9_-]{20,})"),
    "AWS_KEY": re.compile(r"\bAKIA(?P<s>[0-9A-Z]{16})\b"),
    "BEARER": re.compile(r"\b[Bb]earer\s+(?P<s>[A-Za-z0-9._~+/=-]{20,})"),
    "ASSIGNED_SECRET": re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"]?(?P<s>[^\s'\"]{12,})"),
}
MIN_SECRET_VARIETY = 8  # distinct characters in the secret part of a credential shape
MIN_PRIVATE_LINE = 40  # shorter lines (braces, imports, common words) say nothing about origin
SHARED_PUBLIC = ("specs/011-safec-semantic-first/contracts/",)  # Forge-C publishes these; SafeC may mirror them
TEXT_SUFFIXES = {".rs", ".md", ".json", ".toml", ".yaml", ".yml", ".py", ".txt", ".sreq", ".lus", ".c", ".h", ".ps1",
                 ".sh", ".ebnf", ".ts", ".js"}
SUMMARY_MAX_CHARS = 512


class LeakRefused(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("PUBLIC_BOUNDARY_REFUSED: " + "; ".join(issues))
        self.issues = issues


def _norm(line: str) -> str:
    return " ".join(line.split())


def _digest(line: str) -> str:
    return hashlib.sha256(_norm(line).encode()).hexdigest()


def credentials(text: str) -> list[str]:
    """Credential shapes whose secret has real variety. A placeholder ('x' * 30, <redacted>, ${VAR}) is not a
    secret; a key or token whose longest alphanumeric run has 8+ distinct characters is."""
    out = []
    for name, rx in CREDENTIAL_PATTERNS.items():
        for m in rx.finditer(text):
            secret = m.group("s")
            runs = re.findall(r"[A-Za-z0-9]+", secret)
            longest = max(runs, key=len) if runs else ""
            if name == "PRIVATE_KEY" or (not secret.startswith(("<", "${", "$("))
                                         and len(set(longest)) >= MIN_SECRET_VARIETY):
                out.append(name)
                break
    return out


def private_fingerprints(private_root: Path) -> set[str]:
    """Hashes of the substantive lines of every tracked text file of the private checkout (memory only)."""
    files = subprocess.run(["git", "ls-files", "-z"], cwd=private_root, capture_output=True, check=True).stdout
    out: set[str] = set()
    for rel in filter(None, files.decode().split("\0")):
        p = private_root / rel
        if p.suffix.lower() not in TEXT_SUFFIXES or not p.is_file() or p.stat().st_size > 4 * 1024 * 1024:
            continue
        for line in p.read_text(errors="replace").splitlines():
            if len(_norm(line)) >= MIN_PRIVATE_LINE:
                out.add(_digest(line))
    return out


def public_fingerprints(repo: Path, rev: str) -> set[str]:
    """Hashes of the substantive lines the public repository already had at `rev`: a line that public Forge-C
    published before is not evidence of a private copy (common idioms, shared wording)."""
    blobs = []
    for entry in subprocess.run(["git", "ls-tree", "-r", "-l", "-z", rev], cwd=repo, capture_output=True,
                                check=True).stdout.decode(errors="replace").split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)  # "<mode> blob <object> <size>"
        _mode, kind, obj, size = meta.split()
        if kind == "blob" and Path(path).suffix.lower() in TEXT_SUFFIXES and int(size) <= 4 * 1024 * 1024:
            blobs.append(obj)
    data = subprocess.run(["git", "cat-file", "--batch"], cwd=repo, input="\n".join(blobs).encode(),
                          capture_output=True, check=True).stdout
    out: set[str] = set()
    pos = 0
    while pos < len(data):
        header_end = data.index(b"\n", pos)
        size = int(data[pos:header_end].split()[2])
        body = data[header_end + 1:header_end + 1 + size].decode(errors="replace")
        pos = header_end + 1 + size + 1
        out.update(_digest(line) for line in body.splitlines() if len(_norm(line)) >= MIN_PRIVATE_LINE)
    return out


def scan_lines(path: str, lines: list[tuple[int, str]], fingerprints: set[str] | None) -> list[dict]:
    findings = []
    shared = path.startswith(SHARED_PUBLIC)
    for no, line in lines:
        for kind in credentials(line):
            findings.append({"path": path, "line": no, "kind": f"CREDENTIAL:{kind}"})
        if fingerprints and not shared and len(_norm(line)) >= MIN_PRIVATE_LINE and _digest(line) in fingerprints:
            findings.append({"path": path, "line": no, "kind": "PRIVATE_SOURCE_LINE"})
    return findings


def added_lines(repo: Path, base: str) -> dict[str, list[tuple[int, str]]]:
    """Lines added since `base` in tracked changes, staged or not, plus untracked files (not ignored)."""
    diff = subprocess.run(["git", "diff", "-U0", "--no-color", "--no-ext-diff", base, "--"], cwd=repo,
                          capture_output=True, text=True, errors="replace", check=True).stdout
    out: dict[str, list[tuple[int, str]]] = {}
    path, no = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = None if line == "+++ /dev/null" else line[6:]
        elif line.startswith("@@"):
            no = int(re.search(r"\+(\d+)", line).group(1))
        elif line.startswith("+") and path is not None:
            out.setdefault(path, []).append((no, line[1:]))
            no += 1
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo,
                               capture_output=True, check=True).stdout.decode().split("\0")
    for rel in filter(None, untracked):
        p = repo / rel
        if p.is_file() and p.stat().st_size <= 4 * 1024 * 1024:
            out[rel] = list(enumerate(p.read_text(errors="replace").splitlines(), 1))
    return out


def scan_public_tree(repo: Path, base: str, private_root: Path | None = None) -> dict:
    fps = private_fingerprints(private_root) - public_fingerprints(repo, base) if private_root else None
    findings = []
    lines = added_lines(repo, base)
    for path, ls in sorted(lines.items()):
        findings += scan_lines(path, ls, fps)
    return {"schema": "forge-c/safec-public-boundary-scan/1", "base": base,
            "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                                   check=True).stdout.strip(),
            "files_scanned": len(lines), "lines_scanned": sum(len(v) for v in lines.values()),
            "private_checkout_compared": fps is not None, "private_line_hashes": len(fps or ()),
            "findings": findings, "status": "PASS" if not findings else "FAIL"}


def public_summary(record: dict, allowed: tuple[str, ...], *, private_root: Path | None = None,
                   fingerprints: set[str] | None = None) -> dict:
    """The repository-safe projection of a SafeC record: allow-listed keys, bounded scalars or lists of scalars."""
    issues: list[str] = []
    out: dict = {}
    priv = str(private_root.resolve()) if private_root else None

    def check(key: str, value) -> None:
        if isinstance(value, bool) or value is None or isinstance(value, int):
            return
        if not isinstance(value, str):
            issues.append(f"NOT_A_SCALAR:{key}")
            return
        if len(value) > SUMMARY_MAX_CHARS or "\n" in value:
            issues.append(f"VALUE_TOO_LARGE_OR_MULTILINE:{key}")
        issues.extend(f"CREDENTIAL:{key}:{kind}" for kind in credentials(value))
        if priv and priv in value:
            issues.append(f"PRIVATE_PATH:{key}")
        if fingerprints and len(_norm(value)) >= MIN_PRIVATE_LINE and _digest(value) in fingerprints:
            issues.append(f"PRIVATE_SOURCE_LINE:{key}")

    for key in allowed:
        if key not in record:
            continue
        value = record[key]
        for v in value if isinstance(value, list) else [value]:
            check(key, v)
        out[key] = value
    if issues:
        raise LeakRefused(sorted(set(issues)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--base", required=True)
    s.add_argument("--private", type=Path)
    s.add_argument("--repo", type=Path, default=REPO_ROOT)
    s.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    res = scan_public_tree(a.repo, a.base, a.private)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(pretty_json(res))
    print(json.dumps({k: res[k] for k in ("status", "files_scanned", "lines_scanned", "private_checkout_compared")}
                     | {"findings": res["findings"][:20]}))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
