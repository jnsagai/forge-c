"""Feature 020 T023b (FR-022, research R6): the feature 018 phase-2 SET inspection of a functional-level order.

The set-quality packets (SQ-01..10) and the gate-item packets (SWE1-01..) of a functional order describe the
functional template (attributes and fixed lane values), the origin groups, the trace / derive / awaiting-traceability
links to the governance input register and the level rule, instead of the register-level wording (reference-manual
section and page per requirement, register fields); they carry the governance package as a source and not the
code-derived delivered interface (FR-003). The criteria are the unchanged ones (same SWE.1 checklist items, same
SQ criteria from the unchanged criteria file). The set step runs for a functional order under every local profile, as
its graph does (D21), and a profile's semantic SWE.1 inspector (register claims) hands a functional order to this
inspector. Register-level phase-2 packets are pinned by test_f020_set_identity.py (golden from forge-c-020-base).
Model calls are scripted."""
from __future__ import annotations

import hashlib
import io
import json
import sys

import pytest
from f020_swe1 import author, prepared
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import structured as S

CHECKLIST_SHA = "a5e46ac280ecc278a6f873191dc07fd1f2d18f3efc2ede3933847a70021ae8e9"  # forge-c-020-base, 303b46ea
EVIDENCE = ["workproducts/SWE.1/software_requirements.md"]
PLAIN_PROFILE = "local-rtx-v1"  # a local profile without the two-phase switch and without a semantic inspector
SEMANTIC_PROFILE = "local-rtx-v2"  # semantic_inspect_phases: [SWE.1] (register claims)
GOV_MD = "workproducts/SWE.1/governance/governance-package.md"
REGISTER_WORDING = ("cites its reference-manual section and page", "traces to a reference-manual section",
                    "its register and functional sections are the HSI", "REGISTER.FIELD")


def _gate(ws, monkeypatch) -> int:
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    return gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])


def _select(ws, profile: str) -> None:
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    m["local_profile"] = {"id": profile}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m, indent=1))


@pytest.fixture()
def frozen(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    assert _gate(ws, monkeypatch) == 0  # frozen by the functional SWE.1 author gate
    return ws


def _text(p) -> str:
    return " ".join(m["content"] for m in p["_messages"])


def _model(calls):
    def call(p, **_k):
        calls.append(p)
        item = p["task"].split(":")[-1]
        doc = ({"findings": [], "evidence_checked": EVIDENCE} if item.startswith("SQ-") else
               {"verdict": "PASS", "findings": [], "evidence_checked": EVIDENCE})
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}
    return call


def test_set_and_item_packets_of_a_functional_order_use_the_functional_wording(frozen, monkeypatch):
    from forge_factory.lrtx import review
    from forge_factory.lrtx import swe1_quality as Q

    assert hashlib.sha256((REPO_ROOT / Q.CHECKLIST).read_bytes()).hexdigest() == CHECKLIST_SHA
    _select(frozen, PLAIN_PROFILE)
    assert review.two_phase(frozen) is True  # the graph switches the two-phase inspection on for it (D21)
    calls: list = []
    monkeypatch.setattr(S, "call", _model(calls))
    out = review.visit(frozen, "SWE.1", "fake-model:q8", max_calls=400)
    assert out["status"] == "PASS", out
    sq = [p for p in calls if p["task"].split(":")[-1].startswith("SQ-")]
    items = [p for p in calls if p["task"].split(":")[-1].startswith("SWE1-")]
    assert [p["task"].split(":")[-1] for p in sq] == [f"SQ-{n:02d}" for n in range(1, 11)]
    assert items and {p["task"].split(":")[-1] for p in items} >= {"SWE1-01", "SWE1-02", "SWE1-05"}
    crit = {s["id"]: f"{s['id']} {s['property']}: {s['criterion']}" for s in Q.quality_checklist()["set"]}
    for p in sq:
        assert p["criteria"] == [crit[p["task"].split(":")[-1]]]  # the unchanged SQ criteria
    for p in sq + items:
        text = _text(p)
        assert "functional-level" in text and "swe1-functional-v1" in text, p["task"]
        for word in ("origin group", "awaiting_traceability", "derive", "trace", "input register",
                     "not applicable until SWE.2"):
            assert word in text, (p["task"], word)
        assert "never registers, bit fields, register addresses or reset values" in text
        assert not any(w in text for w in REGISTER_WORDING), p["task"]
        paths = [s["path"] for s in p["sources"]]
        assert GOV_MD in paths and "inputs/delivered-interface.json" not in paths, (p["task"], paths)
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert set(rec["set_quality"]) == set(crit)


def test_the_semantic_swe1_inspector_hands_a_functional_order_to_the_set_inspection(frozen, monkeypatch):
    from forge_factory.lrtx import review_semantic

    _select(frozen, SEMANTIC_PROFILE)
    calls: list = []
    monkeypatch.setattr(S, "call", _model(calls))
    out = review_semantic.visit(frozen, "SWE.1", "fake-model:q8", max_calls=400)
    assert out["status"] == "PASS", out
    tasks = [p["task"].split(":")[-1] for p in calls]
    assert tasks[:10] == [f"SQ-{n:02d}" for n in range(1, 11)]  # no register claims, coverage or effects questions
    assert all("REGISTER.FIELD" not in _text(p) and "register_effects" not in _text(p) for p in calls)

