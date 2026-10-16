"""CRE-T001 — capability matrix is evidence-backed and drift-free; historical inventory compared, never rewritten."""
import subprocess

from forge_factory.common import REPO_ROOT, sha256_bytes
from forge_factory.reliability import audit as A


def test_every_claim_cites_existing_modules_and_recorded_pass_evidence():
    assert A.consistency_issues() == []
    assert {c["status"] for c in A.CAPABILITIES} <= set(A.STATUSES)
    assert any(c["status"] == "MISSING" for c in A.CAPABILITIES)  # the audit reports gaps, not only successes


def test_published_matrix_matches_the_data():
    assert (REPO_ROOT / "docs/cre-capability-matrix.md").read_text() == A.render_markdown()


def test_unbacked_claim_is_detected(monkeypatch):
    fake = [{"id": "CX", "component": "x", "status": "IMPLEMENTED", "modules": ["no/such/module.py"],
             "evidence": ["T999"], "finding": ""}]
    monkeypatch.setattr(A, "CAPABILITIES", fake)
    assert A.consistency_issues() == ["CX:MODULE_MISSING:no/such/module.py", "CX:EVIDENCE_NOT_PASS:T999"]


def test_source_inventory_classifies_against_the_historical_sums_without_touching_them(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    (r / "same.txt").write_text("a")
    (r / "changed.txt").write_text("new")
    (r / "added.txt").write_text("c")
    sums = (f"{sha256_bytes(b'a')}  same.txt\n{sha256_bytes(b'old')}  changed.txt\n"
            f"{sha256_bytes(b'gone')}  removed.txt\n")
    (r / "SHA256SUMS.txt").write_text(sums)
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    subprocess.run(["git", "add", "-A"], cwd=r, check=True)
    inv = A.source_inventory(r)
    assert inv["counts"] == {"UNCHANGED": 1, "CHANGED": 1, "ADDED_SINCE_HISTORICAL": 2, "MISSING_FROM_TREE": 1}
    assert inv["historical_inventory"]["status"] == "STALE" and inv["missing_from_tree"] == ["removed.txt"]
    assert (r / "SHA256SUMS.txt").read_text() == sums


def test_live_facts_report_unknown_not_zero_when_state_is_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DATA_ROOT", str(tmp_path))
    f = A.live_facts(tmp_path / "state")
    assert f["supervisor"] == "UNKNOWN" and f["incidents_by_state"] == "UNKNOWN" and f["lessons_by_state"] == "UNKNOWN"
    assert f["work_orders"] == 0 and f["archives"] == "UNKNOWN"
