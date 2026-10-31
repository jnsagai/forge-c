"""Feature 010 LRTX-T021: seeded-defect harness mechanics on an independent holdout (the Codex/Claude rc1 IWDG LL
work order) with a scripted inspector that never fails: deterministic catches are attributed to the gate, everything
else is reported as MISSED, and the holdout itself is never modified."""
from __future__ import annotations

import json
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


def test_an_inspector_that_records_nothing_is_never_read_as_a_pass(tmp_path, monkeypatch):
    """F011 M4: the holdout keeps its original (PASS) inspection record. An inspector whose every call returns no JSON
    records nothing, so each row is NO_INSPECTION, never 'none' or MISSED from the stale record."""
    monkeypatch.setattr(S, "call", lambda p, **_k: {"doc": None, "errors": ["NOT_JSON:Expecting value: line 1 column 1 "
                                                                            "(char 0)"], "usage": None, "wall_ms": 1.0,
                                                     "finish_reason": "stop"})
    s = seeded.run([HOLDOUT], "m", tmp_path / "report.json", cases=["S3-INVERT"])
    by = {r["case"]: r["detected_by"] for r in s["rows"]}
    assert by["BASELINE"].startswith("NO_INSPECTION") and by["S3-INVERT"].startswith("NO_INSPECTION"), by
    assert s["no_inspection"] == 2 and s["false_rejections"] == 0 and s["missed"] == 0


def test_the_paired_swe1_mutations_seed_one_named_defect_each(tmp_path):
    """F011-T045: the lrtx-seeded-2 SWE.1 defects paired with the inspection lessons, each on a copy."""
    import shutil

    from forge_factory.lrtx import seeded as SD

    ws = tmp_path / "w"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "traceability").mkdir()
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "# Software requirements\n\n- **SWR-001** When X is called, the D shall set R.F.\n  - Verification: passes when F is 1.\n"
        "- **SWR-002** While no LL function has been called after reset, the D shall not write any register.\n"
        "  - Verification: passes when unchanged.\n"
        "- **SWR-003** The D shall use at most 128 bytes of stack for any public API call.\n  - Verification: passes.\n")
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps({"effects": [
        {"case": "A", "swr": "SWR-001", "register": "R", "field": "F", "op": "set"}]}))
    (ws / "traceability/upstream_gaps.md").write_text("| Input | Status | SWR |\n| Safety allocation | PENDING | SWR-001 |\n")
    base = ws.parent / "base"
    shutil.copytree(ws, base)
    cases = {c["id"]: c for c in SD.CATALOGUE}
    assert SD.CATALOGUE_VERSION == "lrtx-seeded-2"
    for cid, target, check in (
            ("S1-EFFECT", "SWR-001", lambda w: json.loads((w / "workproducts/SWE.1/register_effects.json").read_text())
             ["effects"][0]["op"] == "clear"),
            ("S1-NOSTART", "SWR-002", lambda w: "SWR-002" not in (
                w / "workproducts/SWE.1/software_requirements.md").read_text()),
            ("S1-GAPROW", "Safety allocation", lambda w: "Safety allocation" not in (
                w / "traceability/upstream_gaps.md").read_text()),
            ("S1-NOBUDGET", "SWR-003", lambda w: "SWR-003" not in (
                w / "workproducts/SWE.1/software_requirements.md").read_text())):
        shutil.rmtree(ws)
        shutil.copytree(base, ws)
        assert cases[cid]["apply"](ws) == target and check(ws), cid
    assert cases["S1-NOSTART"]["alt"] == "reset_startup_missing" and cases["S1-NOBUDGET"]["alt"] == "budget_missing"
    (ws / "workproducts/SWE.1/software_requirements.md").write_text("# Software requirements\n")
    with pytest.raises(ValueError, match="NO_MUTATION_SITE:omit_startup"):
        SD.omit_startup(ws)


def test_preflight_passes_clean_baselines_with_truthful_answers_and_no_model_call(tmp_path, monkeypatch):
    """F014 (owner 2026-10-26): before any inference the run script inspects every clean baseline with scripted
    truthful answers; every question's schema must accept its true answer and the adjudication must pass."""
    from forge_factory.lrtx import review_semantic as RS

    monkeypatch.setitem(RS.INSPECTOR, "stepwise", True)
    monkeypatch.setattr(S, "call", lambda *a, **k: pytest.fail("the preflight made a model call"))
    pf = seeded.preflight([HOLDOUT], "qwen3.6:35b-a3b", tmp_path, "semantic")
    assert pf["status"] == "PASS" and pf["model_calls"] == 0, pf
    assert S.call is not seeded._truthful_call  # the real client is restored


def test_preflight_fails_on_a_harness_defect_and_the_run_stops_at_the_no_inspection_limit(tmp_path, monkeypatch):
    from forge_factory.lrtx import review_semantic as RS

    monkeypatch.setitem(RS.INSPECTOR, "stepwise", True)
    real = RS.step_questions
    # a defect a scripted answer exposes: a question whose closed answers exclude the true one
    monkeypatch.setattr(RS, "step_questions", lambda ws, f: [{**q, "answers": ["NONE"]} if q["id"] == "startup" else q
                                                             for q in real(ws, f)])
    pf = seeded.preflight([HOLDOUT], "qwen3.6:35b-a3b", tmp_path / "pf", "semantic")
    assert pf["status"] == "FAIL" and pf["rows"][0]["detected_by"] != "none", pf
    monkeypatch.setattr(RS, "step_questions", real)
    monkeypatch.setattr(S, "call", lambda p, **_k: {"doc": None, "errors": ["NOT_JSON"], "usage": None, "wall_ms": 1.0,
                                                     "finish_reason": "stop"})
    s = seeded.run([HOLDOUT], "m", tmp_path / "report.json", cases=["S3-INVERT", "S4-VACUOUS"], inspector="semantic",
                   max_no_inspection=1)
    assert s["aborted"].startswith("NO_INSPECTION_LIMIT") and len(s["rows"]) == 2


def test_on_target_counts_a_detection_listed_only_under_its_item(tmp_path, monkeypatch):
    """Run 2 (2026-10-26): S1-EFFECT raised the standing SWR-001 claim, but the record's capped top-level findings showed
    only another SWE1-02 claim and the case was scored off target."""
    from forge_factory.lrtx import review_semantic as RS

    monkeypatch.setitem(RS.INSPECTOR, "stepwise", True)
    # long enough to fill the item's 200-character top-level entry on its own (engine.record_inspection)
    other = {"assertion": "other", "target_id": "document", "related_ids": [], "detail": "an unrelated judgement " * 12,
             "remediation": "fix it"}

    def call(p, **k):
        item = p["task"].split(":")[-1]
        if item == "step-effect-e01":  # the requirement's own value, against the seeded (flipped) entry
            doc = {"quote": "write 0x0000CCCC", "answer": "write", "value": "0x0000CCCC"}
            return {"doc": doc, "errors": [], "usage": None, "wall_ms": 1.0, "finish_reason": "stop"}
        if item == "SWE1-02":
            doc = {"verdict": "FAIL", "claims": [other],
                   "evidence_checked": p["output_schema"]["properties"]["evidence_checked"]["items"]["enum"][:1]}
            return {"doc": doc, "errors": [], "usage": None, "wall_ms": 1.0, "finish_reason": "stop"}
        return seeded._truthful_call(p, **k)

    monkeypatch.setattr(S, "call", call)
    case = next(c for c in seeded.CATALOGUE if c["id"] == "S1-EFFECT")
    seeded.PREFLIGHT["ws"] = tmp_path / "h" / "S1-EFFECT" / "workspace"
    try:
        r = seeded.evaluate(HOLDOUT, case, "qwen3.6:35b-a3b", tmp_path / "h", "semantic")
    finally:
        seeded.PREFLIGHT["ws"] = None
    assert r["target"] == "SWR-001" and r["detected_by"] == "inspection (on target)", r["inspection"]
