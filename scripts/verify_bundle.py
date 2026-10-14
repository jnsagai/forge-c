#!/usr/bin/env python3
"""Check this packaged repository against the immutable SHA256SUMS file (stdlib only)."""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HASHES = ROOT / "SHA256SUMS.txt"

def main() -> int:
    if not HASHES.is_file():
        print("ERROR: SHA256SUMS.txt missing", file=sys.stderr)
        return 2
    failures = []
    verified = 0
    listed = set()
    for lineno, line in enumerate(HASHES.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            sha, path = line.split("  ", 1)
        except ValueError:
            failures.append(f"line {lineno}: invalid SHA256SUMS syntax")
            continue
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            failures.append(f"line {lineno}: invalid digest")
            continue
        target = ROOT / path
        if path in listed or Path(path).is_absolute() or ".." in Path(path).parts or not target.is_file():
            failures.append(f"line {lineno}: duplicate, unsafe or missing path {path}")
            continue
        listed.add(path)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != sha:
            failures.append(f"hash mismatch: {path}")
        verified += 1
    excluded={'SHA256SUMS.txt'}
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('__pycache__','.pytest_cache','build','.venv'))} - excluded
    if actual != listed:
        for path in sorted(actual - listed): failures.append(f"unlisted file: {path}")
        for path in sorted(listed - actual): failures.append(f"listed, not found: {path}")
    if failures:
        print(f"FAIL ({len(failures)}): " + "; ".join(failures[:30]), file=sys.stderr)
        return 1
    print(f"PASS: {verified} files SHA-256 validated, inventory complete")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
