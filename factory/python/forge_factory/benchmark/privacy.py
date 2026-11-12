"""Feature 020 FR-025 (SC-008): find benchmark names in the repository without storing them.

Forbidden tokens are kept outside the repository; the repository holds only their salted SHA-256 digests
(`sha256(salt + token)`, token lower-cased). A scan lower-cases and word-splits every tracked file and reports a hit as
file + digest, never the token. The salt defeats precomputed name tables; a guessed name can still be confirmed, which
is accepted for programme and people names (decision log D29).

    python -m forge_factory.benchmark.privacy hash --tokens <private list> --salt <salt> --out <fixture.json>
    python -m forge_factory.benchmark.privacy scan --hashes <fixture.json> [--repo <dir>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "forge-c/forbidden-token-hashes/1"
NORMALISE = "lower-case; split on characters outside [0-9a-zà-ÿ]"
SPLIT = re.compile(r"[^0-9a-zà-ÿ]+")


def digest(salt: str, token: str) -> str:
    return hashlib.sha256((salt + token.lower()).encode()).hexdigest()


def tokens(text: str) -> set[str]:
    return {t for t in SPLIT.split(text.lower()) if t}


def load(path: Path) -> dict:
    doc = json.loads(Path(path).read_text())
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} file: {path}")
    return {"salt": doc["salt"], "hashes": set(doc["hashes"])}


def scan_paths(paths, hashes: dict) -> list[dict]:
    salt, want, hits = hashes["salt"], hashes["hashes"], []
    for p in paths:
        try:
            text = Path(p).read_bytes().decode("utf-8", "ignore")
        except OSError:
            continue
        found = sorted({h for h in (digest(salt, t) for t in tokens(text)) if h in want})
        hits += [{"file": str(p), "hash": h} for h in found]
    return hits


def tracked(repo: Path) -> list[Path]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [repo / f for f in out.decode().split("\0") if f and (repo / f).is_file()]


def scan_repo(repo: Path, hashes: dict) -> list[dict]:
    repo = Path(repo)
    return [{**h, "file": str(Path(h["file"]).relative_to(repo))} for h in scan_paths(tracked(repo), hashes)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="forge_factory.benchmark.privacy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hash")
    h.add_argument("--tokens", required=True, type=Path)
    h.add_argument("--salt", required=True)
    h.add_argument("--out", required=True, type=Path)
    s = sub.add_parser("scan")
    s.add_argument("--hashes", required=True, type=Path)
    s.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[4])
    a = ap.parse_args(argv)
    if a.cmd == "hash":
        toks = {t.strip().lower() for t in a.tokens.read_text().splitlines() if t.strip()}
        doc = {"schema": SCHEMA, "salt": a.salt, "normalise": NORMALISE,
               "hashes": sorted({digest(a.salt, t) for t in toks})}
        a.out.write_text(json.dumps(doc, indent=1) + "\n")
        print(json.dumps({"status": "OK", "hashes": len(doc["hashes"])}))
        return 0
    hits = scan_repo(a.repo, load(a.hashes))
    print(json.dumps({"status": "CLEAN" if not hits else "FORBIDDEN_TOKENS", "hits": hits}))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
