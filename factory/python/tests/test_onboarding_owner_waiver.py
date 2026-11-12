"""Owner 2026-11-11 ~04:15Z: "revoke the sign off requirement, i dont want to sign off things, move ahead without it
for everything from now on". On the owner lane an onboarding package needs no signed approval: an unchanged package
with no CONFLICT fact and no blocking gap is approved under the owner's recorded waiver, its assumptions taking their
proposed values. A signed approval, when present, still decides; nothing is signed for the owner."""
import json

from forge_factory.onboarding import approval as A
from forge_factory.onboarding import facts as F


def _pkg(root, *, facts=(), gaps=(), assumptions=()):
    pkg = {"schema": "x", "work_order": "0011m-spi-hal", "status": "READY_FOR_OWNER", "facts": list(facts),
           "gaps": list(gaps), "assumptions": list(assumptions), "inputs": [], "texts": {}, "authored": {}}
    pkg["sha256"] = F.canonical_hash(pkg)
    d = root / "onboarding"
    d.mkdir(parents=True)
    (d / "package.json").write_text(json.dumps(pkg))
    return pkg


def _no_artifacts(monkeypatch):
    from forge_factory.onboarding import authoring

    monkeypatch.setattr(authoring, "artifact_paths", lambda pkg: {})


ASM = {"id": "ASM-BUDGET-FLASH", "proposed_value": 4096, "symbol": "budgets.flash_bytes"}
UNCONF = {"id": "GAP-OB-001", "kind": "ASSUMPTION_UNCONFIRMED", "blocks_approval": True, "ref": "ASM-BUDGET-FLASH"}


def test_a_ready_package_is_approved_under_the_owner_waiver(tmp_path, monkeypatch):
    _no_artifacts(monkeypatch)
    pkg = _pkg(tmp_path, gaps=[UNCONF], assumptions=[ASM])
    r = A.verify(tmp_path)
    assert r["code"] == "APPROVAL_OK" and r["reason"] == pkg["sha256"]
    a = r["approval"]
    assert a["decided_by"] == A.OWNER_WAIVER["decided_by"] and a["decision"] == "APPROVED"
    assert a["assumption_confirmations"] == [{"id": "ASM-BUDGET-FLASH", "value": 4096}]
    assert "revoke the sign off requirement" in a["waiver"]["quote"]


def test_conflicts_and_blocking_gaps_still_hold_the_package(tmp_path, monkeypatch):
    _no_artifacts(monkeypatch)
    _pkg(tmp_path / "c", facts=[{"name": "base_address", "status": "CONFLICT"}])
    assert A.verify(tmp_path / "c")["code"] == "APPROVAL_INCOMPLETE:conflict"
    _pkg(tmp_path / "g", gaps=[{"id": "GAP-OB-001", "kind": "MISSING_INPUT", "blocks_approval": True, "ref": "file_map"}])
    assert A.verify(tmp_path / "g")["code"] == "APPROVAL_INCOMPLETE:blocking_gap"


def test_a_missing_package_is_still_missing(tmp_path):
    assert A.verify(tmp_path)["code"] == "APPROVAL_MISSING"
