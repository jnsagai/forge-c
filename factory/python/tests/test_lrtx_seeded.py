"""Feature 010 LRTX-T021: seeded-defect harness mechanics on an independent holdout (the Codex/Claude rc1 IWDG LL
work order) with a scripted inspector that never fails: deterministic catches are attributed to the gate, everything
else is reported as MISSED, and the holdout itself is never modified."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from forge_factory.common import sha256_file
from forge_factory.lrtx import seeded
from forge_factory.lrtx import structured as S

HOLDOUT = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / \
    "state/workorders/WO-0009A-STM32N6-IWDG-LL-rc1/workspace"
pytestmark = pytest.mark.skipif(not (HOLDOUT / ".forge-run/manifest.json").is_file(), reason="rc1 holdout not present")


def test_seeded_cases_are_attributed_and_the_holdout_is_untouched(tmp_path, monkeypatch):
    before = {p: sha256_file(p) for p in HOLDOUT.rglob("*") if p.is_file() and "build" not in p.parts}

    def never_fails(p, **_k):
        doc = {"verdict": "PASS", "findings": [], "evidence_checked": [p["sources"][0]["path"]]}
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 1.0, "finish_reason": "stop"}
    monkeypatch.setattr(S, "call", never_fails)
    s = seeded.run([HOLDOUT], "m", tmp_path / "report.json")
    by = {r["case"]: r["detected_by"] for r in s["rows"]}
    assert by["BASELINE"] == "none" and s["false_rejections"] == 0
    assert by["S1-QM"] == "deterministic gate"  # SAFETY_SCOPE rejection by the unchanged SWE.1 gate
    assert by["S3-INVERT"] == "MISSED" and by["S4-VACUOUS"] == "MISSED"  # an always-PASS inspector misses them
    assert s["catalogue_sha256"] == seeded.catalogue_hash() and (tmp_path / "report.json").is_file()
    after = {p: sha256_file(p) for p in HOLDOUT.rglob("*") if p.is_file() and "build" not in p.parts}
    assert before == after
