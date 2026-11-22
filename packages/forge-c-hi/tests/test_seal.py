"""T043: the sealed review package (READY or BLOCKED with gaps) and its independent verification."""
from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from conftest import PKG
from forge_hi import gate_result, seal, trace
from forge_hi.config import schema
from forge_hi.io import sha256_file, write_json
from forge_hi.jsonschema_lite import validate
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, reqset, write

VERIFY = PKG / ".apm" / "skills" / "hi-release" / "scripts" / "verify_package.py"


def accept(root, stage, *, findings=None, rebase=True):
    """Record what the conductor records on acceptance: state, findings, snapshot scope PASS."""
    wp = root / "hi" / stage / "requirements.json"
    state_p = root / ".hi/state.json"
    st = json.loads(state_p.read_text()) if state_p.exists() else {"schema": "forge-c-hi/state@1", "stages": {}}
    st["stages"][stage] = {"state": "accepted", "run_id": "r-test", "wp_sha256": sha256_file(wp)}
    write_json(state_p, st)
    write_json(root / "hi" / stage / "inspection" / "findings.json",
               {"schema": "forge-c-hi/findings@1", "stage": stage, "findings": findings or []})
    gate_result.write(root, stage, gate_result.result("scope", [], profile="generic", integrity_level="HI-1", root=root))
    if rebase:
        trace.rebaseline(root, stage)


def ready_project(root, level="HI-1"):
    make_project(root, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS, level=level)
    (root / ".hi/docs").mkdir(parents=True)
    (root / ".hi/docs/RM0486.index.json").write_text("{}")
    accept(root, "sys-req")
    accept(root, "sw-req")
    return root


def finding(sev="blocking", status="carried"):
    return {"id": "F-1", "phase": "item", "checklist_item": "IQ-02", "target_id": "SYS-SUP-001", "severity": sev,
            "description": "Wrong value.", "round": 1, "status": status}


def gap_codes(res):
    return {g["code"] for g in res["gaps"]}


def test_ready_package(tmp_project):
    root = ready_project(tmp_project)
    res = seal.seal(root)
    assert res["status"] == seal.READY, res["gaps"]
    pkg = root / res["package"]
    m = json.loads((pkg / "manifest.json").read_text())
    assert validate(m, schema("review-manifest")) == []
    assert m["status"] == "READY_FOR_OFFLINE_REVIEW" and m["gaps"] == []
    assert "not a certification" in m["disclaimer"]
    for f in m["files"]:
        assert sha256_file(pkg / f["path"]) == f["sha256"]
    names = {f["path"] for f in m["files"]}
    assert {"files/hi/sys-req/requirements.json", "files/hi/sw-req/inspection/findings.json", "files/hi/trace.json",
            "findings.md", "gates.md", "trace-matrix.md", "files/needs/stakeholder-needs.md"} <= names
    assert not any(".hi/docs" in n for n in names)
    assert "not a certification" in (pkg / "gates.md").read_text()
    r = subprocess.run([sys.executable, str(VERIFY), str(pkg)], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["verified"] is True


@pytest.mark.parametrize("case,code", [
    ("fail", "GATE-FAIL"),
    ("not_run", "GATE-NOT-RUN"),
    ("missing_scope", "GATE-MISSING"),
    ("blocking_open_point", "OPEN-POINT-BLOCKING"),
    ("blocking_finding", "FINDING-BLOCKING"),
    ("suspect", "TRACE-SUSPECT"),
    ("independence", "INDEPENDENCE"),
    ("not_accepted", "NOT-ACCEPTED"),
    ("changed", "CHANGED-AFTER-INSPECTION"),
    ("missing_stage", "STAGE-MISSING"),
])
def test_each_gap_blocks(tmp_project, case, code):
    root = ready_project(tmp_project, level="HI-3" if case == "independence" else "HI-1")
    sw = root / "hi/sw-req/requirements.json"
    if case == "fail":
        doc = json.loads(sw.read_text())
        doc["items"][0]["text"] = "The monitor reacts quickly."
        write(sw, doc)
        accept(root, "sw-req")
    elif case == "not_run":
        doc = json.loads(sw.read_text())
        doc["items"][0]["sources"].append({"kind": "document", "doc_id": "RM9", "section": "1", "page": 1})
        write(sw, doc)
        proj = json.loads((root / ".hi/project.json").read_text())
        proj["inputs"].append({"path": "needs/constraints.md", "kind": "reference_document", "doc_id": "RM9"})
        write(root / ".hi/project.json", proj)
        accept(root, "sw-req")
    elif case == "missing_scope":
        (root / "hi/sys-req/gates/scope.json").unlink()
    elif case == "blocking_open_point":
        doc = json.loads(sw.read_text())
        doc["open_points"] = [{"id": "OP-SWR-001", "text": "Time split missing.", "blocks": True}]
        write(sw, doc)
        accept(root, "sw-req")
    elif case == "blocking_finding":
        accept(root, "sys-req", findings=[finding()])
    elif case == "suspect":
        items = copy.deepcopy(SYS_ITEMS)
        items[1]["text"] = "The supervisor shall detect a late task within 5 ms of its deadline."
        write(root / "hi/sys-req/requirements.json", reqset("sys-req", items))
        accept(root, "sys-req", rebase=False)
    elif case == "independence":
        proj = json.loads((root / ".hi/project.json").read_text())
        proj["roles"]["inspector"].update(harness="codex", model_family="fake-a")
        write(root / ".hi/project.json", proj)
    elif case == "not_accepted":
        st = json.loads((root / ".hi/state.json").read_text())
        st["stages"]["sw-req"] = {"state": "blocked", "reason": "rework limit"}
        write(root / ".hi/state.json", st)
    elif case == "changed":
        doc = json.loads(sw.read_text())
        doc["items"][0]["verification_method"] = "analysis"
        write(sw, doc)
    elif case == "missing_stage":
        sw.unlink()
    res = seal.seal(root)
    assert res["status"] == seal.BLOCKED
    assert code in gap_codes(res), res["gaps"]
    pkg = root / res["package"]
    m = json.loads((pkg / "manifest.json").read_text())
    assert validate(m, schema("review-manifest")) == []
    assert m["status"] == "BLOCKED" and m["gaps"]
    r = subprocess.run([sys.executable, str(VERIFY), str(pkg)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout  # a BLOCKED package is still a complete, verifiable package


def test_package_produced_when_nothing_was_inspected(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    res = seal.seal(tmp_project)
    assert res["status"] == seal.BLOCKED and {"NOT-ACCEPTED", "STAGE-MISSING"} <= gap_codes(res)
    assert (tmp_project / res["package"] / "review.tar.gz").is_file()


def test_tampering_is_detected(tmp_project):
    root = ready_project(tmp_project)
    pkg = root / seal.seal(root)["package"]
    (pkg / "files/hi/sys-req/requirements.json").write_text("{}")
    r = subprocess.run([sys.executable, str(VERIFY), str(pkg)], capture_output=True, text=True)
    assert r.returncode == 1 and any("hash mismatch" in e for e in json.loads(r.stdout)["errors"])


def test_archive_is_deterministic(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a/x.txt").write_text("x")
    (tmp_path / "a/y.txt").write_text("y")
    seal.deterministic_tar(tmp_path / "a", tmp_path / "one.tar.gz", ["y.txt", "x.txt"])
    seal.deterministic_tar(tmp_path / "a", tmp_path / "two.tar.gz", ["x.txt", "y.txt"])
    assert (tmp_path / "one.tar.gz").read_bytes() == (tmp_path / "two.tar.gz").read_bytes()


def test_cli_seal_exit_codes(tmp_project):
    root = ready_project(tmp_project)
    hi = PKG / ".apm/skills/hi-gates/scripts/hi.py"
    r = subprocess.run([sys.executable, str(hi), "seal"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "READY_FOR_OFFLINE_REVIEW"
    (root / "hi/sys-req/gates/scope.json").unlink()
    r = subprocess.run([sys.executable, str(hi), "seal"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "BLOCKED"
