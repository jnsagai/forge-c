"""Feature 020 T023b (SC-007, FR-013): the phase-2 SET inspection packets of a register-level order are unchanged.

The golden `fixtures/f020/register_identity_phase2.json` was captured on forge-c-020-base (303b46ea, the deployed
owner-lane commit) with FORGE_GOLDEN_WRITE=1: the feature 018 phase-2 packets (SQ-01..10 set-quality packets and the
SWE1-xx gate-item packets) of the IWDG LL order frozen by the unchanged register-level SWE.1 author and gate (scripted
model, git-ignored owner inputs; skipped when they are absent). Each packet is pinned by the hash of its prompt
messages and of its sources/criteria/schema, with the frozen baseline's id and hash (time-dependent) replaced by
placeholders. Self-contained on purpose (no feature 020 helper), so the same file runs on the base tree."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from forge_factory.common import canonical_json
from forge_factory.lrtx import review, structured, swe1
from test_lrtx_swe1 import ANSWERS, _gate, _scripted, pytestmark, ws  # noqa: F401

GOLDEN = Path(__file__).parent / "fixtures/f020/register_identity_phase2.json"
EVIDENCE = ["workproducts/SWE.1/software_requirements.md"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _model(calls):
    def call(p, **_k):
        calls.append(p)
        item = p["task"].split(":")[-1]
        doc = ({"findings": [], "evidence_checked": EVIDENCE} if item.startswith("SQ-") else
               {"verdict": "PASS", "findings": [], "evidence_checked": EVIDENCE})
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}
    return call


def test_register_level_phase2_set_packets_are_unchanged(ws, monkeypatch):  # noqa: F811
    from forge_factory.inspection.engine import Store

    monkeypatch.setattr(structured, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    assert _gate(ws, monkeypatch) == 0
    bl = Store(ws).latest_baseline("SWE.1")
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    calls: list = []
    monkeypatch.setattr(structured, "call", _model(calls))
    review.visit(ws, "SWE.1", "qwen3-coder:30b", max_calls=400)

    def norm(s: str) -> str:
        return s.replace(bl["baseline_id"], "<BASELINE_ID>").replace(bl["baseline_hash"][:16], "<BASELINE_HASH>")

    got = {}
    for p in calls:
        task = norm(p["task"])
        msgs = [{**m, "content": norm(m["content"])} for m in p["_messages"]]
        rest = {k: p[k] for k in ("role", "criteria", "output_schema", "output_reserve")}
        rest["sources"] = [s["path"] for s in p["sources"]]
        got[task] = [_sha(canonical_json(msgs)), _sha(canonical_json(rest))]
    assert len(got) >= 16
    data = json.loads(GOLDEN.read_text()) if GOLDEN.is_file() else {}
    if os.environ.get("FORGE_GOLDEN_WRITE") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps({"iwdg_register_level_phase2": got}, indent=1, sort_keys=True) + "\n")
        pytest.skip("golden recorded")
    assert got == data["iwdg_register_level_phase2"]
