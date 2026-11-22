"""T047: reference-document outline and citation resolution. The PDF fixture is generated here (no vendor content)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from conftest import SCRIPTS
from forge_hi import doc_index, gates, trace
from hi_helpers import PROV, SYS_ITEMS, make_project, req, write

HI = SCRIPTS / "hi.py"
POPPLER = bool(shutil.which("pdfinfo") and shutil.which("pdftotext"))
needs_poppler = pytest.mark.skipif(not POPPLER, reason="poppler not installed")

PAGES = [
    ["Contents", "1 Introduction . . . . . . . . . . 2", "2 Watchdog . . . . . . . . . . 3"],
    ["1 Introduction", "This made-up manual describes a fictional timer block.", "1.1 Conventions",
     "Values are hexadecimal."],
    ["2 Watchdog", "2.1 Functional description", "The counter counts down from the reload value."],
    ["2.2 Registers", "2.2.1 Key register", "Writing the key starts the counter."],
    ["2.2.2 Reload register", "The reload value is 12 bits wide."],
]


def make_pdf(path, pages):
    """A minimal, valid multi-page PDF with Helvetica text lines."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        body = "BT /F1 11 Tf 14 TL 72 760 Td " + " ".join(f"({esc(l)}) Tj T*" for l in lines) + " ET"
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream")
        content_no = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_no} 0 R "
                    "/Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def doc_project(root):
    make_project(root, sys_items=SYS_ITEMS, stages=("sw-req",), input_class="reference_document")
    (root / "docs").mkdir()
    make_pdf(root / "docs" / "fm.pdf", PAGES)
    proj = json.loads((root / ".hi/project.json").read_text())
    proj["inputs"] = [{"path": "docs/fm.pdf", "kind": "reference_document", "doc_id": "FM0001"}]
    proj["entry_stage"] = "sw-req"
    write(root / ".hi/project.json", proj)
    return root


def drv(section, page):
    return req("DRV-WDG-001", "The driver shall start the counter by writing the start key.",
               [{"kind": "document", "doc_id": "FM0001", "section": section, "page": page}])


def test_outline_skips_table_of_contents():
    secs = doc_index.outline(["\n".join(p) for p in PAGES])
    got = {s["section"]: (s["page"], s["end_page"]) for s in secs}
    assert got["1"] == (2, 3) and got["2"] == (3, 4) and got["2.2.1"] == (4, 5) and got["2.2.2"] == (5, 5)


@needs_poppler
def test_doc_index_builds_from_pdf(tmp_project):
    root = doc_project(tmp_project)
    r = subprocess.run([sys.executable, str(HI), "doc-index", "docs/fm.pdf", "--doc-id", "FM0001"], cwd=root,
                       capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert r.returncode == 0, out
    assert out["pages"] == 5 and out["written"] == ".hi/docs/FM0001.index.json"
    idx = json.loads((root / ".hi/docs/FM0001.index.json").read_text())
    secs = {s["section"]: s["page"] for s in idx["sections"]}
    assert secs == {"1": 2, "1.1": 2, "2": 3, "2.1": 3, "2.2": 4, "2.2.1": 4, "2.2.2": 5}


def test_without_poppler_is_not_run(tmp_project, monkeypatch):
    root = doc_project(tmp_project)
    monkeypatch.setattr(doc_index.shutil, "which", lambda _: None)
    res = doc_index.build(root, root / "docs/fm.pdf", "FM0001", profile="generic", integrity_level="HI-2")
    assert res["verdict"] == "NOT_RUN" and "poppler" in res["not_run_reason"]


def test_missing_document_fails(tmp_project):
    root = doc_project(tmp_project)
    res = doc_index.build(root, root / "docs/nope.pdf", "FM0001", profile="generic", integrity_level="HI-2")
    assert res["verdict"] == "FAIL" and res["issues"][0]["code"] == "DOC-MISSING"


@needs_poppler
@pytest.mark.parametrize("section,page,ok", [("2.2.1", 4, True), ("2.2.1", 5, True), ("2.2.1", 2, False),
                                              ("9.9", 4, False), ("2.2.1", 99, False)])
def test_citations_resolve_or_fail(tmp_project, section, page, ok):
    root = doc_project(tmp_project)
    doc_index.build(root, root / "docs/fm.pdf", "FM0001", profile="generic", integrity_level="HI-2")
    write(root / "hi/sw-req/requirements.json",
          {"schema": "forge-c-hi/requirement-set@1", "stage": "sw-req", "baseline_id": "b", "status": "draft",
           "provenance": PROV, "items": [drv(section, page)],
           "open_points": []})
    ds = gates.doc_sources(root, "sw-req")
    tr = trace.run(root, "sw-req")
    assert (ds["verdict"] == "PASS") is ok, ds["issues"]
    assert (tr["verdict"] == "PASS") is ok, tr["issues"]
    if not ok:
        assert ds["issues"][0]["code"] == "DOC-UNRESOLVED"
        assert any(i["code"] == "TR-DOC-UNRESOLVED" for i in tr["issues"])


@needs_poppler
def test_doc_sources_not_run_without_index_and_stale_index(tmp_project):
    root = doc_project(tmp_project)
    write(root / "hi/sw-req/requirements.json",
          {"schema": "forge-c-hi/requirement-set@1", "stage": "sw-req", "baseline_id": "b", "status": "draft",
           "provenance": PROV, "items": [drv("2.2.1", 4)], "open_points": []})
    assert gates.doc_sources(root, "sw-req")["verdict"] == "NOT_RUN"
    doc_index.build(root, root / "docs/fm.pdf", "FM0001", profile="generic", integrity_level="HI-2")
    assert gates.doc_sources(root, "sw-req")["verdict"] == "PASS"
    make_pdf(root / "docs/fm.pdf", PAGES + [["3 Appendix"]])
    res = gates.doc_sources(root, "sw-req")
    assert res["verdict"] == "FAIL" and res["issues"][0]["code"] == "DOC-STALE-INDEX"
