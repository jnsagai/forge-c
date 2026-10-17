"""CRE-T041 (AT-038): requirement -> task -> test -> evidence matrix is complete and drift-free; the runbook covers
setup, restart, rollback, escalation and approval restrictions with commands that exist."""
import importlib
import re

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import trace


def test_traceability_matrix_is_generated_from_evidence_and_complete():
    assert (trace.FEATURE / "traceability.csv").read_text() == trace.render_csv()
    rows = trace.rows()
    assert len(rows) == 40
    unmet = [r["requirement_id"] for r in rows if r["priority"] == "P0" and r["status"] != "COVERED"]
    assert unmet == []
    for r in rows:
        if r["status"] == "COVERED":
            assert r["evidence"] and r["tests"], r["requirement_id"]
    assert (trace.FEATURE / "planned-traceability.csv").is_file()  # the planned crosswalk is kept unchanged


def test_runbook_covers_operations_and_every_command_exists():
    text = (REPO_ROOT / "docs/cre-runbook.md").read_text()
    for section in ("Reproducible setup", "Routine operation", "Restart", "Rollback", "Escalation",
                    "Approval restrictions", "Data-quality audit"):
        assert section in text, section
    mods = sorted(set(re.findall(r"python -m (forge_factory\.[\w.]+)", text)))
    assert len(mods) >= 9
    for m in mods:
        assert hasattr(importlib.import_module(m), "main"), m
    assert "No AI or CRE component signs off safety" in text
