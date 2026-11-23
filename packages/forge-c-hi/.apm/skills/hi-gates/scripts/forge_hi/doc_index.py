"""Section/page outline of a reference document the user supplies (`hi doc-index`), and citation resolution.

The index lives in `.hi/docs/<doc_id>.index.json` in the user's project and is never copied into a review package.
It holds only section numbers, short heading titles and page numbers, so that a citation `{doc_id, section, page}`
can be checked: the section must exist and the page must lie within that section's page range.

Text extraction uses poppler (`pdfinfo`, `pdftotext -layout`). Without poppler the result is NOT_RUN, never a pass.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import gate_result
from .io import read_json, sha256_file, write_json

# RM0486 sets headings with up to ~13 spaces between number and title (T052: 59.7.1 IWDG key register was missed)
HEADING = re.compile(r"^\s{0,8}(\d{1,3}(?:\.\d{1,3}){0,5})\.?\s{1,24}([A-Z][^\n]{1,110}?)\s*$")
LEADER = re.compile(r"(?:\. ?){4,}")          # dot leaders, also spaced ". . . ." as in vendor tables of contents
TOC_LEADER = re.compile(r"(?:\. ?){4,}|\s\d+\s*$")
INDEX_DIR = Path(".hi") / "docs"


def tools_available() -> bool:
    return bool(shutil.which("pdfinfo") and shutil.which("pdftotext"))


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise ValueError(f"pdfinfo cannot read {pdf.name}: {out.stderr.strip()[:200]}")
    m = re.search(r"^Pages:\s+(\d+)", out.stdout, re.M)
    if not m:
        raise ValueError(f"pdfinfo reports no page count for {pdf.name}")
    return int(m.group(1))


def page_texts(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=600)
    if out.returncode != 0:
        raise ValueError(f"pdftotext cannot read {pdf.name}: {out.stderr.decode(errors='replace').strip()[:200]}")
    return out.stdout.decode("utf-8", errors="replace").split("\f")


def _plausible(number: str, title: str) -> bool:
    if TOC_LEADER.search(title):
        return False
    first = int(number.split(".")[0])
    if first == 0 or first > 200:
        return False
    words = title.split()
    # a footnote or list item ("4. Private-key cryptography is protected ...") ends like a sentence; a heading does not
    return 1 <= len(words) <= 16 and not title.rstrip().endswith((",", ";", "."))


def outline(pages: list[str]) -> list[dict]:
    """First body occurrence of each numbered heading, with its start page and the page before the next heading.

    Pages that are part of a table of contents (5 or more dot-leader lines) are skipped, and headings must move forward
    through the chapters (the chapter of a heading is the current one or the next), so a wrapped contents entry, a
    numbered footnote or a table row cannot claim a section early."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    chapter = 0
    for pno, text in enumerate(pages, 1):
        lines = text.splitlines()
        if sum(1 for ln in lines if LEADER.search(ln)) >= 5:
            continue
        for line in lines:
            m = HEADING.match(line)
            if not m or not _plausible(m.group(1), m.group(2)):
                continue
            num, title = m.group(1), re.sub(r"\s{2,}.*$", "", m.group(2)).strip()
            first = int(num.split(".")[0])
            if chapter and not chapter <= first <= chapter + 1:
                continue
            if num not in seen:
                seen[num] = {"section": num, "title": title[:80], "page": pno}
                order.append(num)
                chapter = max(chapter, first)
    secs = [seen[n] for n in order]
    starts = sorted({s["page"] for s in secs})
    for s in secs:
        later = [p for p in starts if p > s["page"]]
        s["end_page"] = later[0] if later else len(pages)
    return secs


def build(root: Path, pdf: Path, doc_id: str, *, profile: str, integrity_level: str) -> dict:
    """Index a user-supplied PDF. Returns a gate-style result (gate 'doc-index')."""
    root, pdf = Path(root), Path(pdf)
    common = {"profile": profile, "integrity_level": integrity_level, "root": root}
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", doc_id):
        raise ValueError(f"invalid doc id {doc_id!r}")
    if not pdf.is_file():
        return gate_result.result("doc-index", [gate_result.issue("DOC-MISSING", f"{pdf} does not exist")], **common)
    if not tools_available():
        return gate_result.result("doc-index", [], not_run_reason="poppler (pdfinfo, pdftotext) is not installed",
                                  **common)
    try:
        n = page_count(pdf)
        pages = page_texts(pdf)[:n]
    except (ValueError, subprocess.TimeoutExpired) as exc:
        return gate_result.result("doc-index", [gate_result.issue("DOC-UNREADABLE", str(exc))], **common)
    secs = outline(pages)
    issues = [] if secs else [gate_result.issue("DOC-NO-SECTIONS", "no numbered section headings were found")]
    idx = {"schema": "forge-c-hi/doc-index@1", "doc_id": doc_id, "source_sha256": sha256_file(pdf), "pages": n,
           "sections": secs, "_note": "Local outline only (numbers, short headings, pages). Never redistributed."}
    out = write_json(root / INDEX_DIR / f"{doc_id}.index.json", idx)
    res = gate_result.result("doc-index", issues, **common)
    res["evidence"] = [{"path": out.relative_to(root).as_posix(), "sha256": sha256_file(out)}]
    return res


def load(root: Path, doc_id: str) -> dict | None:
    p = Path(root) / INDEX_DIR / f"{doc_id}.index.json"
    return read_json(p) if p.is_file() else None


def resolve(index: dict, section: str, page: int) -> str | None:
    """None if the citation resolves, else the reason it does not."""
    pages = int(index.get("pages", 0))
    if not 1 <= int(page) <= pages:
        return f"page {page} is outside 1..{pages}"
    sec = next((s for s in index.get("sections", []) if s.get("section") == section), None)
    if sec is None:
        return f"section {section} is not in the index"
    if not sec["page"] <= int(page) <= sec.get("end_page", sec["page"]):
        return f"page {page} is not within section {section} (pages {sec['page']}-{sec.get('end_page')})"
    return None
