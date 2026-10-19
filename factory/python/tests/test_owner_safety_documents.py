"""OD-2026-10-19-11: owner-signed safety documents (software safety analysis, tool assurance assessment).

Only a document the owner signed - human approver and date, registered SHA-256, matching basis, draft marker gone -
enters an RCC work order, read-only; the package keeps it only while it still has the registered hash. Unsigned
drafts never count, so the package stays BLOCKED on them."""
import hashlib
import json

import pytest
import yaml
from forge_factory import workorder as WO
from forge_factory.assurance import package as P
from forge_factory.assurance import scope
from forge_factory.common import REPO_ROOT
from forge_factory.release import finalize as F

LL_EX = REPO_ROOT / "examples/0002a-arm_55_rcc_ll"
SIGNED = "# Software Safety Analysis\n\n| Status | Approved by the reviewer (section 11) |\n\nASIL B analysis.\n"
DRAFT = "# Software Safety Analysis\n\n| Status | **DRAFT — AI-drafted, not reviewed, not approved** |\n"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    return tmp_path


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _entry(path, text, basis="B0", who="Jefferson Nascimento", when="2026-10-20"):
    return {"path": str(path), "basis": basis, "sha256": _sha(text), "approved_by": who, "approved_at": when,
            "decision": "OD-TEST"}


def _docs(tmp_path, monkeypatch, texts: dict[str, str], **kw) -> dict:
    """A scope decision whose safety_documents register points at files under a temporary document directory."""
    d = tmp_path / "docs"
    d.mkdir(exist_ok=True)
    monkeypatch.setattr(scope, "DOC_DIR", str(d) + "/")
    reg = {}
    for key, text in texts.items():
        (d / f"{key}.md").write_text(text)
        reg[key] = _entry(d / f"{key}.md", text, **kw)
    return {"safety_documents": reg}


def test_signed_documents_with_matching_hash_and_basis_count(tmp_path, monkeypatch):
    dec = _docs(tmp_path, monkeypatch, {"software_safety_analysis": SIGNED, "tool_assurance_assessment": SIGNED})
    docs, issues = scope.owner_documents(dec, "B0", REPO_ROOT)
    assert issues == [] and [d["path"] for d in docs] == list(scope.DOC_FILES.values())
    assert docs[0]["approved_by"] == "Jefferson Nascimento" and docs[0]["sha256"] == _sha(SIGNED)


@pytest.mark.parametrize("change, issue", [
    (lambda e, f: e.update(approved_by=None), "SAFETY_DOC_NOT_SIGNED"),
    (lambda e, f: e.update(approved_by="agent-swe1"), "SAFETY_DOC_NOT_SIGNED"),
    (lambda e, f: e.update(approved_at=None), "SAFETY_DOC_NOT_SIGNED"),
    (lambda e, f: f.write_text(SIGNED + "edited after signing\n"), "SAFETY_DOC_HASH_MISMATCH"),
    (lambda e, f: e.update(basis="other-inputs"), "SAFETY_DOC_BASIS_CHANGED"),
    (lambda e, f: e.update(path="evidence/elsewhere.md"), "SAFETY_DOC_PATH_INVALID"),
    (lambda e, f: e.update(path=e["path"].replace("/docs/", "/docs/../")), "SAFETY_DOC_PATH_INVALID"),
])
def test_anything_but_an_intact_owner_signature_is_left_out(tmp_path, monkeypatch, change, issue):
    dec = _docs(tmp_path, monkeypatch, {"software_safety_analysis": SIGNED, "tool_assurance_assessment": SIGNED})
    e = dec["safety_documents"]["software_safety_analysis"]
    change(e, tmp_path / "docs/software_safety_analysis.md")
    docs, issues = scope.owner_documents(dec, "B0", REPO_ROOT)
    assert issues == [f"{issue}:software_safety_analysis"]
    assert [d["key"] for d in docs] == ["tool_assurance_assessment"]


def test_a_signed_file_that_still_says_draft_is_not_used(tmp_path, monkeypatch):
    dec = _docs(tmp_path, monkeypatch, {"software_safety_analysis": DRAFT, "tool_assurance_assessment": SIGNED})
    docs, issues = scope.owner_documents(dec, "B0", REPO_ROOT)
    assert issues == ["SAFETY_DOC_STILL_DRAFT:software_safety_analysis"] and len(docs) == 1


def test_unregistered_documents_are_issues():
    assert scope.owner_documents({}, "B0", REPO_ROOT) == (
        [], ["SAFETY_DOC_NOT_REGISTERED:software_safety_analysis", "SAFETY_DOC_NOT_REGISTERED:tool_assurance_assessment"])


def test_committed_rcc_register_is_either_an_unsigned_draft_or_an_intact_signature():
    dec = yaml.safe_load((REPO_ROOT / scope.DECISIONS).read_text())["decisions"][0]
    reg = dec["safety_documents"]
    assert set(reg) == set(scope.DOC_FILES)
    docs, issues = scope.owner_documents(dec, reg["software_safety_analysis"]["basis"], REPO_ROOT)
    signed = {d["key"] for d in docs}
    for key, e in reg.items():
        text = (REPO_ROOT / e["path"]).read_text()
        assert scope.claim_text_findings({"target_asil": "B"}, text) == []  # no compliance claim, ASIL B only
        if key in signed:
            assert not scope.DRAFT_MARK.search(text) and scope._human(e["approved_by"])
        else:
            assert e["approved_by"] is None and e["sha256"] is None and scope.DRAFT_MARK.search(text)
            assert f"SAFETY_DOC_NOT_SIGNED:{key}" in issues
    assert len(docs) + len(issues) == len(scope.DOC_FILES)


def _scope_with(tmp_path, monkeypatch, register: dict):
    """Point the scope decisions at a copy of the committed file whose RCC decision has the given register."""
    real = yaml.safe_load((REPO_ROOT / scope.DECISIONS).read_text())
    real["decisions"][0]["safety_documents"] = register
    p = tmp_path / "safety-scope.yaml"
    p.write_text(yaml.safe_dump(real))
    monkeypatch.setattr(scope, "DECISIONS", str(p))


def test_prepare_copies_only_signed_documents_read_only(tmp_path, monkeypatch):
    unsigned = {k: {"path": f"{scope.DOC_DIR}SC-T/{k}.md", "basis": "x", "sha256": None, "approved_by": None,
                    "approved_at": None} for k in scope.DOC_FILES}
    _scope_with(tmp_path, monkeypatch, unsigned)
    _ws0, man0 = WO.prepare(LL_EX, "WO-LL-UNSIGNED")
    assert man0["owner_safety_documents"] == [] and not (_ws0 / "safety/software_safety_analysis.md").exists()
    assert "SAFETY_DOC_NOT_SIGNED:software_safety_analysis" in man0["owner_safety_document_issues"]
    basis = json.loads((_ws0 / ".forge-run/safety_scope.json").read_text())["scope"]["source_requirements_hash"]

    texts = {"software_safety_analysis": SIGNED, "tool_assurance_assessment": DRAFT}
    _scope_with(tmp_path, monkeypatch, _docs(tmp_path, monkeypatch, texts, basis=basis)["safety_documents"])
    ws, man = WO.prepare(LL_EX, "WO-LL-SIGNED")
    f = ws / "safety/software_safety_analysis.md"
    assert f.read_text() == SIGNED and (f.stat().st_mode & 0o222) == 0
    assert not (ws / "safety/tool_assurance_assessment.md").exists()
    assert [d["key"] for d in man["owner_safety_documents"]] == ["software_safety_analysis"]
    assert man["owner_safety_document_issues"] == ["SAFETY_DOC_STILL_DRAFT:tool_assurance_assessment"]


def _stage(tmp_path, texts: dict[str, str]):
    stage = tmp_path / "stage"
    for rel, text in texts.items():
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        (stage / rel).write_text(text)
    return stage


def test_package_keeps_only_the_signed_version(tmp_path):
    ssa, taa = scope.DOC_FILES["software_safety_analysis"], scope.DOC_FILES["tool_assurance_assessment"]
    wo = {"owner_safety_documents": [{"key": "software_safety_analysis", "path": ssa, "sha256": _sha(SIGNED),
                                      "approved_by": "Jefferson Nascimento", "approved_at": "2026-10-20"}],
          "owner_safety_document_issues": ["SAFETY_DOC_NOT_SIGNED:tool_assurance_assessment"]}
    stage = _stage(tmp_path, {ssa: SIGNED, taa: "written by someone else\n"})
    lines = F.owner_safety_documents(wo, stage)
    assert (stage / ssa).read_text() == SIGNED and not (stage / taa).exists()
    assert any("signed by Jefferson Nascimento" in x and "not a safety approval" in x for x in lines)
    assert any(taa in x and "removed" in x for x in lines)
    assert any("SAFETY_DOC_NOT_SIGNED:tool_assurance_assessment" in x for x in lines)

    stage2 = _stage(tmp_path / "t", {ssa: SIGNED + "tampered\n"})
    F.owner_safety_documents(wo, stage2)
    assert not (stage2 / ssa).exists()


def test_work_orders_without_the_register_are_unchanged(tmp_path):
    ssa = scope.DOC_FILES["software_safety_analysis"]
    stage = _stage(tmp_path, {ssa: "synthetic\n"})
    assert F.owner_safety_documents({}, stage) == [] and (stage / ssa).is_file()


def test_assurance_scope_counts_only_signed_documents(tmp_path):
    ssa, taa = scope.DOC_FILES["software_safety_analysis"], scope.DOC_FILES["tool_assurance_assessment"]
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    rec = {"scope": {"scope_id": "SC-T", "work_order_id": "WO-T", "target_asil": "B", "source_requirements_hash": "B0",
                     "hsi_hash": "h", "allocation_review_ref": "r", "product_asil_source": "approved:test"}, "na": {}}
    (ws / P.SCOPE_FILE).write_text(json.dumps(rec))
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"owner_safety_documents": [
        {"key": k, "path": rel, "sha256": _sha(SIGNED)} for k, rel in scope.DOC_FILES.items()]}))
    out = P.scope_dispositions(ws, _stage(tmp_path, {ssa: SIGNED, taa: SIGNED}))
    assert out["dispositions"] == {"software_safety_analysis": "PRESENT", "tool_assurance_assessment": "PRESENT"}
    out = P.scope_dispositions(ws, _stage(tmp_path / "x", {ssa: SIGNED, taa: "unsigned\n"}))
    assert out["dispositions"]["tool_assurance_assessment"] == "MISSING"
    assert "SAFETY_EVIDENCE_MISSING:tool_assurance_assessment" in out["issues"]
