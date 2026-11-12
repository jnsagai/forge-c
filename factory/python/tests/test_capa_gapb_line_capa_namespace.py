"""Maintainer gap (b), 2026-11-12: line maintainer CAPAs are LCAPA-NNN (never the owner store's CAPA-NNN), and the
owner CAPA the observer routed travels in the proposal so the deployer can link the imported fix to it."""
from forge_factory.afo import maintainer as M


class Reg:
    def __init__(self, ids):
        self.ids = ids

    def all(self):
        return [{"capa_id": i} for i in self.ids]


def test_line_capas_have_their_own_namespace():
    assert M._next_capa(Reg([])) == "LCAPA-001"  # an empty line store no longer yields the owner's CAPA-001
    assert M._next_capa(Reg(["CAPA-246", "LCAPA-002", "LCAPA-010"])) == "LCAPA-011"


def test_the_routed_owner_capa_is_read_from_the_run_evidence_and_validated():
    case = {"run_evidence": {"sha256": "x", "record": {"routed_capa": {"capa_id": "CAPA-244", "hypothesis": "h"}}}}
    assert M.owner_capa(case) == "CAPA-244"
    for bad in ({}, {"run_evidence": None}, {"run_evidence": {"record": {"routed_capa": None}}},
                {"run_evidence": {"record": {"routed_capa": {"capa_id": "LCAPA-001"}}}},
                {"run_evidence": {"record": {"routed_capa": {"capa_id": "CAPA-1;rm"}}}}):
        assert M.owner_capa(bad) is None


def test_the_proposal_record_carries_the_owner_capa(monkeypatch):
    seen = {}

    class Store:
        def record_proposal(self, rec, status, order_id=None):
            seen.update(rec=rec)
    monkeypatch.setattr(M, "changed_paths", lambda base, cand, repo: ["factory/python/forge_factory/lrtx/x.py"])
    case = {"repo": "/r", "proposal_id": "mnt-1-a1", "base": "a" * 40, "incident": {"order_id": "afo-1"},
            "run_evidence": {"record": {"routed_capa": {"capa_id": "CAPA-250"}}}}
    rec = M.record(Store(), case, {"candidate": "b" * 40, "staged": {"id": "AFO-1"}}, "ELIGIBLE_FOR_OFFLINE_REVIEW",
                   "ELIGIBLE_FOR_OFFLINE_REVIEW", capa_id="LCAPA-001", evidence=["promotion-decision:pd-1"])
    assert "owner-capa:CAPA-250" in rec["evidence_refs"] and rec["capa_id"] == "LCAPA-001"
    case.pop("run_evidence")
    assert not any(e.startswith("owner-capa:") for e in M.record(Store(), case, {"candidate": "b" * 40}, "REJECTED",
                                                                  "REJECTED")["evidence_refs"])
