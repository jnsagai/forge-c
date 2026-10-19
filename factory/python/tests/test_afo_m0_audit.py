"""AFO-T002 (AFO-FR-001): the capability matrix is derived from code checks; it cites only code that exists and the
committed document matches the generator (no invented capability)."""
from forge_factory.afo import audit


def test_matrix_is_derived_and_the_document_is_current():
    rows = audit.matrix()
    assert audit.DOC.read_text() == audit.markdown(rows)
    for r in rows:
        if r["status"] == "IMPLEMENTED":
            assert r["gap"] == "" and r["checks_passed"].split("/")[0] == r["checks_passed"].split("/")[1], r
        if r["status"] == "PARTIAL":
            assert r["gap"], r                         # a partial row always says what is missing
    st = {r["id"]: r["status"] for r in rows}
    assert st["A21"] == "IMPLEMENTED" and st["A22"] == "PARTIAL"   # M6 built; M7 lacks real soak/pilot evidence
    assert st["A14"] == "PARTIAL" and st["A20"] == "PARTIAL"       # units not installed; agent runs not enabled


def test_a_row_citing_absent_code_cannot_be_implemented(monkeypatch):
    monkeypatch.setattr(audit, "ROWS", [("X1", "need", "-", [("factory/python/forge_factory/nope.py", "")], None, "-")])
    assert audit.matrix()[0]["status"] == "MISSING"
