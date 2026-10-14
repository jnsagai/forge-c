"""Deterministic PDF -> Markdown conversion for authoritative input documents (datasheets, RMs).

Uses poppler `pdftotext -layout` (GPL tool, invoked only, not shipped). Output keeps a page anchor
for every page (`<a id="p-N"></a>` + `<!-- source: DOC p.N -->`) so every requirement and design
decision can cite an exact source page; numbered section titles become Markdown headings; register
tables / bit-field diagrams are kept verbatim inside fenced blocks (never "summarised").
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from ..common import pretty_json, sha256_bytes, sha256_file, utc_now

HEADING = re.compile(r"^(?P<num>\d{1,2}(?:\.\d{1,2}){0,4})\s{1,24}(?P<title>[A-Z][^.]{2,110}?)\s*$")
NOISE = re.compile(r"^\s*(RM\d{4}|DS\d{5})\s+Rev\s+\d+\s*\d*\s*/?\s*\d*\s*$|^\s*\d+/\d+\s+RM\d{4}|^\s*$")


def page_texts(pdf: Path, first: int, last: int) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(pdf), "-"],
                         check=True, capture_output=True, text=True, errors="replace").stdout
    pages = out.split("\f")
    return pages[: last - first + 1]


def convert_page(text: str, doc: str, page: int) -> str:
    lines = [ln.rstrip() for ln in text.splitlines()]
    md = [f'<a id="p-{page}"></a>', f"<!-- source: {doc} p.{page} -->", ""]
    block: list[str] = []

    def flush() -> None:
        if any(x.strip() for x in block):
            md.extend(["```text", *block, "```", ""])
        block.clear()

    for ln in lines:
        if NOISE.match(ln) and ln.strip():
            continue
        stripped = ln.strip()
        m = HEADING.match(stripped)
        if m and len(ln) - len(ln.lstrip()) < 4 and "  " not in m.group("title").strip():
            flush()
            depth = min(6, m.group("num").count(".") + 2)
            md.extend([f"{'#' * depth} {m.group('num')} {m.group('title').strip()}", ""])
        else:
            block.append(ln)
    flush()
    return "\n".join(md)


def convert(pdf: Path, out: Path, doc: str, first: int, last: int, title: str, provenance: dict) -> dict:
    pages = page_texts(pdf, first, last)
    header = [f"# {title}", "", f"> Converted from `{pdf.name}` (sha256 `{sha256_file(pdf)}`), pages {first}–{last}.",
              f"> Source: {provenance.get('source_url', 'unknown')} — retrieved via {provenance.get('retrieved_via')}.",
              "> Authoritative content © STMicroelectronics; converted verbatim for offline engineering use. "
              "Cite as `" + doc + " p.N`.", ""]
    body = [convert_page(t, doc, first + i) for i, t in enumerate(pages)]
    text = "\n".join(header + body) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return {"doc": doc, "pdf": pdf.name, "pdf_sha256": sha256_file(pdf), "pages": [first, last],
            "markdown": out.name, "markdown_sha256": sha256_bytes(text.encode()), "converted_at": utc_now(),
            "converter": "forge_factory.docs.pdf2md + pdftotext -layout", **provenance}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, required=True)
    ap.add_argument("--source-url", default="")
    ap.add_argument("--retrieved-via", default="")
    ap.add_argument("--manifest", type=Path)
    a = ap.parse_args(argv)
    rec = convert(a.pdf, a.out, a.doc, a.first, a.last, a.title,
                  {"source_url": a.source_url, "retrieved_via": a.retrieved_via})
    if a.manifest:
        man = json.loads(a.manifest.read_text()) if a.manifest.is_file() else {"documents": []}
        man["documents"] = [d for d in man["documents"] if d["markdown"] != rec["markdown"]] + [rec]
        a.manifest.write_text(pretty_json(man))
    print(json.dumps({k: rec[k] for k in ("doc", "markdown", "pages", "markdown_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
