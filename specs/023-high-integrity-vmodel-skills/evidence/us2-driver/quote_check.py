#!/usr/bin/env python3
"""Check that driver-demo evidence quotes no text from the reference manual before it is committed.

    python3 quote_check.py <manual.pdf> <file.json|.md> ...

Every string in the files is split into words, and every run of N=8 consecutive words is looked up in the
manual's text (pdftotext). Prints one JSON line with the number of shared runs per file and up to 5 examples (their
first 3 words only, so the report itself quotes nothing). Exit 1 if any file shares a run. Register and field
names alone are short and never reach 8 words; runs with fewer than 4 words containing a letter are ignored.
"""
import json
import re
import subprocess
import sys

N = 8


def words(text):
    return re.findall(r"[a-z0-9_]+", text.lower())


def shingles(ws):
    """Runs of N words with at least 4 words that contain a letter: a list of numbers ("0 1 2 3 4 5 6 7") is not a
    quotation (driver demo pass 4: encoded prescaler values)."""
    out = set()
    for i in range(len(ws) - N + 1):
        run = ws[i:i + N]
        if sum(1 for w in run if re.search(r"[a-z]", w)) >= 4:
            out.add(" ".join(run))
    return out


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def main():
    pdf, files = sys.argv[1], sys.argv[2:]
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, check=True).stdout.decode(
        "utf-8", "replace")
    manual = shingles(words(text))
    worst = 0
    out = {}
    for f in files:
        raw = open(f, encoding="utf-8").read()
        try:
            parts = list(strings(json.loads(raw)))
        except ValueError:
            parts = raw.splitlines()
        hits = set()
        for p in parts:
            hits |= shingles(words(p)) & manual
        out[f] = {"shared_runs": len(hits), "examples": sorted(" ".join(h.split()[:3]) + " ..." for h in hits)[:5]}
        worst = max(worst, len(hits))
    print(json.dumps({"n": N, "files": out}))
    return 1 if worst else 0


if __name__ == "__main__":
    sys.exit(main())
