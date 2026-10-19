"""Reviewer worksheet: identifiers and rating symbols only, OCR layouts, annex tables never leak into Table 15,
and only a named human reviewer's sign-off of whole tables changes the catalog."""
import json

import pytest
from forge_factory.assurance import catalog, normative
from forge_factory.assurance import norm_worksheet as W
from forge_factory.assurance.store import AssuranceStore

SRC = """Table 9 — x
ASIL
Methods
A B C D
1a Statement coverage ++ ++ + +
1b Branch coverage + ++ ++ ++
1c MC/DC (Modified Condition/Decision Coverage) + + + ++
Table 12 — y
1a Function coverage + + ++ ++
1b Call coverage + + ++ ++
Table 15 — z
| 1a Analysis of requirements | ++ ++ | ++ ++ |
| 1b Generation and analysis of equivalence classes | + ++ | ++ ++ |
Table C.1 — annex
1a Plausibility checks ++ ++ ++ ++
1b Redundant storage + + + ++
"""


def test_parse_reads_plain_and_markdown_rows_and_stops_at_annex_tables():
    p = W.parse(SRC)
    assert p[9]["1c"] == {"A": "+", "B": "+", "C": "+", "D": "++"}
    assert p[15]["1b"] == {"A": "+", "B": "++", "C": "++", "D": "++"}          # not overwritten by Table C.1
    assert set(p) == {9, 12, 15} and W.DUPLICATES == []


def test_worksheet_flags_mismatch_and_stores_no_text():
    cat = catalog.load(catalog.contracts.CATALOG)
    ws = W.worksheet(cat, W.parse(SRC.replace("1b Branch coverage + ++", "1b Branch coverage + +")), "s" * 64)
    assert "CATALOG_ROW_NOT_B_HIGHLY_RECOMMENDED:ISO6-T09-1B:B=+" in ws["tables"][9]["findings"]
    assert "coverage" not in json.dumps(ws).lower().replace("structural coverage", "")  # no row text kept


def test_sign_requires_registered_source_matching_worksheet_and_human_reviewer(tmp_path, monkeypatch):
    src = tmp_path / "part6.md"
    src.write_text(SRC)
    monkeypatch.setenv(normative.ENV, str(src))
    monkeypatch.setattr(catalog, "DERIVED_DIR", tmp_path / "derived")
    store = AssuranceStore(tmp_path / "easa.sqlite3")
    acc = normative.standard_access()
    ws = W.worksheet(catalog.load(), W.parse(SRC), acc["sha256"])
    assert ws["tables"][9]["state"] == "MATCHES_CATALOG" and ws["tables"][12]["state"] == "MATCHES_CATALOG"
    ws = json.loads(json.dumps(ws))                                              # as read back from disk
    assert W.sign(ws, "agent:swe-inspector", "x", [9], store)[0]["issues"] == ["REVIEWER_IS_AGENT"]
    assert W.sign({**ws, "source_sha256": "0" * 64}, "Jefferson Nascimento", "c", [9], store)[0]["issues"] == \
        ["WORKSHEET_FROM_OTHER_SOURCE"]
    d = W.sign(ws, "Jefferson Nascimento", "owner competence statement", [9, 12], store)
    assert [x["decision"] for x in d] == ["ACCEPTED", "ACCEPTED"]
    cat = catalog.load()
    assert cat["document_status"] == "PARTIALLY_RECONCILED" and cat["reconciled_against_sha256"] == acc["sha256"]
    t9 = [m for m in cat["methods"] if m["table"] == 9]
    assert all(m["normative_checked"] and m["verified_reviewer_id"] == "Jefferson Nascimento" for m in t9)
    assert len(list((tmp_path / "derived").glob("catalog-v*.json"))) == 2


@pytest.mark.parametrize("table", [7])
def test_sign_refuses_a_table_with_open_worksheet_findings(tmp_path, monkeypatch, table):
    src = tmp_path / "part6.md"
    src.write_text(SRC)
    monkeypatch.setenv(normative.ENV, str(src))
    monkeypatch.setattr(catalog, "DERIVED_DIR", tmp_path / "derived")
    ws = json.loads(json.dumps(W.worksheet(catalog.load(), W.parse(SRC), normative.standard_access()["sha256"])))
    assert W.sign(ws, "Jefferson Nascimento", "c", [table])[0]["issues"] == [f"WORKSHEET_FINDINGS_OPEN:T{table}"]
