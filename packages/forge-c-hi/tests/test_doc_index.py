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


def test_intake_refuses_a_missing_or_unreadable_reference_document(tmp_project):
    """US2-AS3 (T053): no document, or an unreadable one, stops the project at intake with the reason."""
    from forge_hi import api
    from forge_hi.config import ConfigError
    (tmp_project / "docs").mkdir()
    args = dict(level="HI-2", input_class="reference_document", inputs=["docs/rm.pdf:reference_document:RM0001"])
    with pytest.raises(ConfigError, match="does not exist"):
        api.init(tmp_project, **args)
    (tmp_project / "docs/rm.pdf").write_text("this is not a PDF\n")
    with pytest.raises(ConfigError, match="not a readable PDF"):
        api.init(tmp_project, **args)
    assert not (tmp_project / ".hi/project.json").exists()
    if POPPLER:
        (tmp_project / "docs/rm.pdf").write_bytes(b"%PDF-1.4\n% truncated\n")
        with pytest.raises(ConfigError, match="not a readable PDF"):
            api.init(tmp_project, **args)
    make_pdf(tmp_project / "docs/rm.pdf", ["1 Introduction\nText."])
    code, out = api.init(tmp_project, **args)
    assert code == 0 and out["status"] == "DONE"


def test_outline_handles_vendor_layout():
    """T052 on a real 4669-page reference manual found 1706 of about 3500 headings. The cases, rebuilt here with
    invented text: wide gaps between number and title, a contents page with spaced dot leaders and a wrapped entry,
    numbered footnotes, and a table row that looks like a heading."""
    toc = "\n".join([f"   {n}.{k}   Topic {k} . . . . . . . . . . . . {10 + k}" for n in (3, 4) for k in (1, 2, 3)]
                    + ["7        Unit with a long name that wraps"])
    pages = [
        toc,
        "3        Clock unit\n3.1      Clock overview\nBody text.\n",
        "1. Certified by an independent body.\n4. Secret keys are protected against probing.\n"
        "3.2                Clock registers\n12        Reserved\n",
        "4             Watchdog unit\n4.1           Watchdog overview\n4.1.1             Watchdog key register (WD_KR)\n",
    ]
    secs = doc_index.outline(pages)
    assert [s["section"] for s in secs] == ["3", "3.1", "3.2", "4", "4.1", "4.1.1"]
    assert {s["section"]: s["page"] for s in secs}["3.2"] == 3 and secs[-1]["title"] == "Watchdog key register (WD_KR)"


@pytest.mark.parametrize("stage", ["sys-arch", "sw-req", "sw-arch", "sw-design"])
def test_document_citations_are_a_required_gate_in_every_left_side_stage_that_may_cite(tmp_project, stage):
    # full-V attempt 3: the architecture needs hardware facts; a wrong citation there must not pass unseen
    from forge_hi.config import stages as all_stages
    project = {**json.loads((doc_project(tmp_project) / ".hi/project.json").read_text()), "integrity_level": "HI-2"}
    assert "doc-sources" in gates.required_gates(project, stage)
    name = all_stages()[stage]["outputs"][0]
    item = {"id": "SWC-SUP-001", "sources": [{"kind": "document", "doc_id": "NOPE", "section": "1", "page": 1}]}
    write(tmp_project / name, {"stage": stage, "items": [item]})
    res = gates.doc_sources(tmp_project, stage)
    assert res["verdict"] == "FAIL" and res["issues"][0]["code"] == "DOC-UNKNOWN"


def test_wrong_document_citations_go_back_to_the_author():
    sys.path.insert(0, str(SCRIPTS.parents[1] / "hi-conductor" / "scripts"))
    import conduct
    assert "doc-sources" in conduct.DET_GATES
