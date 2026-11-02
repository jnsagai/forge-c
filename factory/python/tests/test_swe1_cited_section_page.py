"""CAPA-114 (run WO-F014-SWE1-CRCL-20261102-L12, SWR-006): a SWE.1 requirement whose text cites an RM section takes its
source_page from that section (its pages and its subsections' pages); otherwise the author gets a finding before the
baseline freezes, instead of a page-derived trace row that names another section than the text."""
from forge_factory import layer
from forge_factory.lrtx import swe1

SECTIONS = {"26.4": ("CRC registers", 1172, []), "26.4.3": ("CRC control register (CRC_CR)", 1173, [1174]),
            "26.4.4": ("CRC initial value (CRC_INIT)", 1174, []), "26.4.5": ("CRC polynomial (CRC_POL)", 1174, [1175]),
            "26.4.6": ("CRC register map", 1175, [])}
ST = ("When LL_CRC_SetOutputDataReverseMode is called, the CRC LL driver shall write the mode to CRC_CR.REV_OUT, per "
      "RM0486 26.4.3.")


def _ws(tmp_path, monkeypatch):
    rows = []
    for i, (num, (title, page, more)) in enumerate(SECTIONS.items()):
        rel = f"inputs/s{i}.md"
        (tmp_path / "inputs").mkdir(exist_ok=True)
        (tmp_path / rel).write_text(f"<!-- source: RM0486 section {num} starting p.{page} -->\n"
                                    + "".join(f'<a id="p-{p}"></a>\n' for p in more))
        rows.append(f"{num} | {title} | p.{page} | {rel}")
    (tmp_path / "inputs/index.md").write_text("\n".join(rows) + "\n")
    monkeypatch.setattr(layer, "profile", lambda _ws=None: {"register_prefix": "CRC", "rm": {"doc": "RM0486"}})
    return tmp_path


def _req(page, st=ST):
    return {"key": "set_out", "statement": st, "source_page": page}


def test_cited_section_pages_include_subsections(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    assert swe1.section_pages(ws, "26.4.3") == [1173, 1174]
    assert swe1.section_pages(ws, "26.4") == [1172, 1173, 1174, 1175]
    assert swe1.section_pages(ws, "99.1") == []
    assert swe1.cited_sections(ws, "per RM0486 section 26.4.3 and 26.4.5; see section 26.4.4, version 1.5") == [
        "26.4.3", "26.4.5", "26.4.4"]
    assert swe1.cited_sections(ws, "per RM0486 99.9.9 and Rev 4") == []  # not an indexed section


def test_page_outside_the_cited_section_is_a_finding(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    found = swe1.cited_page_findings(ws, _req(1175))
    assert len(found) == 1 and "source_page 1175" in found[0] and "section 26.4.3: pages 1173-1174" in found[0]
    assert swe1.cited_page_findings(ws, _req(1174)) == []
    assert swe1.cited_page_findings(ws, _req(1175, ST.replace("26.4.3.", "26.4.3 and 26.4.5."))) == []  # any cited
    assert swe1.cited_page_findings(ws, _req(1175, ST.replace("per RM0486 26.4.3", "per the RM"))) == []  # no cite
    assert swe1.cited_page_findings(ws, _req(1175, ST.replace("26.4.3", "26.4"))) == []  # parent section


def test_the_author_gate_reports_it(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    monkeypatch.setattr(swe1, "_manifest", lambda _ws: {"scope": ["CRC_CR.REV_OUT output reversal."]})
    g = {"id": "CRC_CR", "register": "CRC_CR", "section": "26.4.3", "pages": [1173, 1174],
         "fields": {"REV_OUT": {"msb": 8, "lsb": 7, "access": ["rw"]}}}
    doc = {"requirements": [{**_req(1175), "verification": "Host unit test; passes when CRC_CR.REV_OUT is 0x1.",
                             "verified_by": "host_unit_test", "effects": [
                                 {"case": "REV_OUT_ONE", "register": "CRC_CR", "field": "REV_OUT", "op": "write",
                                  "value": "0x1"}]}], "not_covered": [], "open_points": []}
    idx = {"CRC_CR": {"fields": g["fields"]}}
    found = swe1.validate_group(ws, doc, g, "CRC LL driver", idx)
    assert [f for f in found if "source_page" in f] == [swe1.cited_page_findings(ws, doc["requirements"][0])[0]]
    doc["requirements"][0]["source_page"] = 1174
    assert not [f for f in swe1.validate_group(ws, doc, g, "CRC LL driver", idx) if "source_page" in f]
