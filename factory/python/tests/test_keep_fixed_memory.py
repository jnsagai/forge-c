"""Owner change 2026-11-02: a structured author task repaired after an inspection also receives the findings of earlier
inspection rounds of the phase that the latest inspection no longer raises ("previously fixed - keep fixed"), full
text and separate from the current findings, routed by the phase's own rework routing. The inspector gets no memory.

Real-data fixture: the inspection records (verdicts and full item findings) of WO-F014-CMP-SWE2-IWDG-20261102-03
(SWE.2) and WO-F014-CMP-SWE1-RCC-20261102-06 (SWE.1)."""
from __future__ import annotations

import json
from pathlib import Path

from forge_factory.common import utc_now
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1, swe2
from forge_factory.lrtx import visit as V
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe1_rework_scope import _first_visit, _swr
from test_lrtx_swe2 import DESIGN, IFACE, ws1  # noqa: F401

DATA = json.loads((Path(__file__).parent / "fixtures/cloud-keep-fixed-rounds-20261102.json").read_text())


def _run(wo: str) -> dict:
    return next(r for r in DATA["runs"] if r["work_order"] == wo)


def _workspace(root: Path, run: dict) -> Path:
    (root / ".forge-run").mkdir(parents=True)
    (root / ".forge-run/manifest.json").write_text(json.dumps({"created_at": "2026-11-02T00:00:00Z"}))
    d = root / "inspection" / run["phase"]
    d.mkdir(parents=True)
    for n, rec in enumerate(run["inspections"], 1):
        (d / f"INS-{run['phase']}-{n:03d}.json").write_text(json.dumps({**rec, "recorded_at": f"2026-11-02T01:00:{n:02d}Z"}))
    return root


def _texts(run: dict, n: int, item: str) -> list[str]:
    return run["inspections"][n]["items"][item]["findings"]


def test_swe2_keep_fixed_lists_what_is_no_longer_raised_full_text_oldest_first(tmp_path):
    run = _run("WO-F014-CMP-SWE2-IWDG-20261102-03")
    keep = V.keep_fixed_findings(_workspace(tmp_path, run), "SWE.2")
    still = _texts(run, 2, "SWE2-06")[0]  # round 3: the PR width/mask status contradiction, raised in all rounds
    assert "PR field width and mask" in still
    assert not any("PR field width and mask" in k for k in keep)
    alloc = _texts(run, 1, "SWE2-06")[0]  # round 2: SWR-019/SWR-020 'outside the task requirement list', gone in 3
    assert "outside the task requirement list" in alloc and f"SWE2-06: {alloc}" in keep
    budget = [k for k in keep if k.startswith("SWE2-05: ")]
    assert budget == [f"SWE2-05: {_texts(run, 1, 'SWE2-05')[0]}"]  # one entry, the most recent wording
    assert keep[:3] == [f"SWE2-02: {t}" for t in _texts(run, 0, "SWE2-02")]  # oldest round first, record order
    assert [k for k in keep if k.startswith("SWE2-02: ")] == [f"SWE2-02: {t}" for t in _texts(run, 0, "SWE2-02")]
    routed = swe2.route(keep)  # CAPA-109 routing: each to the task owning the section it locates
    assert f"SWE2-06: {alloc}" in routed["interfaces"] and budget[0] in routed["design"]


def test_swe1_a_finding_still_raised_on_renumbered_requirements_is_not_called_fixed(tmp_path):
    run = _run("WO-F014-CMP-SWE1-RCC-20261102-06")
    keep = V.keep_fixed_findings(_workspace(tmp_path, run), "SWE.1")
    assert any("SWR-656" in t for t in _texts(run, 2, "SWE1-02"))  # round 3 raises the flash finding again
    assert not any("SWR-660" in k and "flash" in k for k in keep)  # round 2's wording of it is not 'fixed'
    first = _texts(run, 0, "SWE1-02")[1]  # round 1: serialization of read-modify-write, not raised in round 3
    assert f"SWE1-02: {first}" in keep
    assert len(keep) == len(set(keep)) and all(len(k) > 200 for k in keep)  # whole texts, never the 200-char detail


def test_the_first_round_and_a_single_inspection_have_no_memory(tmp_path):
    run = _run("WO-F014-CMP-SWE2-IWDG-20261102-03")
    assert V.keep_fixed_findings(_workspace(tmp_path, {**run, "inspections": run["inspections"][:1]}), "SWE.2") == []


def _build(role="swe1-author"):
    def build(findings, previous):
        return S.packet(phase="SWE.1", task="requirements:crosscutting", role=role, with_skill=False, model="m",
                        instructions="x", sources=[], criteria=[], output_schema=S.PROBE_SCHEMA, output_reserve=64,
                        findings=findings, previous=previous)
    return build


KEEP = {"findings": ["SWE1-02: earlier finding one, fixed in round two.", "SWE1-03: earlier finding two."],
        "omitted": 0}


def test_a_repair_packet_carries_keep_fixed_separately_and_a_base_packet_does_not():
    base = _build()(None, None)
    token = S.KEEP_FIXED.set(KEEP)
    try:
        assert _build()(None, None)["input_hash"] == base["input_hash"]  # no findings: no memory, same identity
        p = _build()(["SWE1-02: the current finding."], {"answer": "a", "items": [1]})
        inspector = S.packet(phase="SWE.1", task="inspect:x:SWE1-02", role="swe1-inspector", with_skill=False,
                             model="m", instructions="x", sources=[], criteria=[], output_schema=S.PROBE_SCHEMA,
                             output_reserve=64, findings=["SWE1-02: the current finding."])
    finally:
        S.KEEP_FIXED.reset(token)
    assert "keep_fixed" not in base and p["keep_fixed"] == KEEP["findings"]
    user = p["_messages"][1]["content"]
    fix, kept = user.index("FINDINGS TO FIX:"), user.index("PREVIOUSLY FIXED - KEEP FIXED")
    assert fix < kept and "the current finding." not in user[kept:]
    assert all(f"- {f}" in user[kept:] for f in KEEP["findings"])
    assert "keep_fixed" not in inspector and "KEEP FIXED" not in inspector["_messages"][1]["content"]


def test_an_unfit_packet_drops_the_oldest_whole_keep_fixed_findings_and_counts_them(monkeypatch):
    long = [f"SWE1-02: finding {n} " + "word " * 400 for n in range(4)]
    fits = _build()(["SWE1-02: now"], {"answer": "a", "items": [1]})["accounting"]["estimated_prompt_tokens"]
    monkeypatch.setattr(S, "profile_context_tokens", lambda *_a, **_k: (fits + 64 + 1300, "test"))
    token = S.KEEP_FIXED.set({"findings": long, "omitted": 1})
    try:
        p = _build()(["SWE1-02: now"], {"answer": "a", "items": [1]})
    finally:
        S.KEEP_FIXED.reset(token)
    assert p["accounting"]["fits"] and 0 < len(p["keep_fixed"]) < len(long)
    assert p["keep_fixed"] == long[-len(p["keep_fixed"]):]  # the most recent are kept, each whole
    assert p["keep_fixed_omitted"]["count"] == 1 + len(long) - len(p["keep_fixed"])
    assert "older keep-fixed finding(s) omitted by count" in p["_messages"][1]["content"]


def test_run_task_gives_the_memory_to_the_author_repair_only(tmp_path, monkeypatch):
    seen = []

    def call(p, **_kw):
        seen.append(p)
        return {"doc": {"answer": "yes", "items": [len(seen), len(seen) + 1]}, "errors": [], "usage": None,
                "wall_ms": 1.0, "raw_chars": 1, "finish_reason": "stop", "format_note": None}

    monkeypatch.setattr(S, "call", call)
    budget = {"calls": 0, "max_calls": 10, "state": None, "deadline": None, "schema_mode": "json_schema",
              "visit": "v1", "execution": 0, "keep_fixed": {"requirements:crosscutting": KEEP}}
    first = V.run_task(tmp_path, "SWE.1", "requirements:crosscutting", _build(), lambda _d: [], budget)
    assert "keep_fixed" not in seen[-1]  # an authorship without findings
    V.run_task(tmp_path, "SWE.1", "requirements:crosscutting", _build(), lambda _d: [], budget, ["SWE1-02: now"])
    assert seen[-1]["keep_fixed"] == KEEP["findings"] and seen[-1]["findings"] == ["SWE1-02: now"]
    rec = json.loads(V._ckpt(tmp_path, "SWE.1", "requirements:crosscutting").read_text())
    assert rec["base_hash"] == first["base_hash"]  # the checkpoint identity is unchanged by the memory
    budget["keep_fixed"] = {"inspect:x": KEEP}
    V.run_task(tmp_path, "SWE.1", "inspect:x", _build("swe1-inspector"), lambda _d: [], budget, ["SWE1-02: now"])
    assert "keep_fixed" not in seen[-1]


def _ins(ws_, phase, n, items: dict[str, list[str]]):
    d = ws_ / "inspection" / phase
    d.mkdir(parents=True, exist_ok=True)
    rec = {"inspection_id": f"INS-{phase}-{n:03d}", "verdict": "FAIL", "recorded_at": utc_now(),
           "items": {k: {"verdict": "FAIL", "findings": v} for k, v in items.items()},
           "findings": [{"id": k, "detail": v[0][:200]} for k, v in items.items()]}
    (d / f"INS-{phase}-{n:03d}.json").write_text(json.dumps(rec))


def test_swe1_rework_routes_keep_fixed_to_the_owning_task(ws, monkeypatch):  # noqa: F811
    calls = []
    _first_visit(ws, monkeypatch, calls)
    kr, rlr = _swr(ws, "requirements:IWDG_KR"), _swr(ws, "requirements:IWDG_RLR")
    fixed_kr = f"Major - software_requirements.md, {kr[0]}: the key write lacks a caller access precondition."
    fixed_rlr = f"Major - software_requirements.md, {rlr[0]}: the reload value range is not bounded."
    now_kr = f"Major - software_requirements.md, {kr[0]}: verification does not state the expected reset value."
    _ins(ws, "SWE.1", 1, {"SWE1-02": [fixed_kr, fixed_rlr]})
    _ins(ws, "SWE.1", 2, {"SWE1-02": [now_kr]})
    assert swe1.visit(ws, "m")["status"] == "PASS"
    kr_packets = [p for p in calls if p["task"] == "requirements:IWDG_KR"]
    assert kr_packets and not any(p["task"] == "requirements:IWDG_RLR" for p in calls)
    assert any(f.endswith("verification does not state the expected reset value.") for f in kr_packets[0]["findings"])
    (kept,) = kr_packets[0]["keep_fixed"]  # the RLR finding went to the RLR task, which did not re-author
    assert kept.startswith(f"SWE1-02: Major - software_requirements.md, {kr[0]} [") and kept.endswith(
        "the key write lacks a caller access precondition.")
    record = json.loads((ws / ".forge-run/lrtx/SWE.1/keep-fixed.json").read_text())
    assert record["findings"] == [f"SWE1-02: {fixed_kr}", f"SWE1-02: {fixed_rlr}"]
    assert record["tasks"]["requirements:IWDG_KR"] == {"count": 1, "omitted_by_count": 0}


def test_swe2_rework_gives_the_design_task_its_keep_fixed_findings(ws1, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, calls))
    assert swe2.visit(ws1, "m")["status"] == "PASS"
    run = _run("WO-F014-CMP-SWE2-IWDG-20261102-03")
    budget_text = _texts(run, 1, "SWE2-05")[0]
    safety = _texts(run, 2, "SWE2-06")[0]
    _ins(ws1, "SWE.2", 1, {"SWE2-05": [budget_text], "SWE2-06": [safety]})
    _ins(ws1, "SWE.2", 2, {"SWE2-06": [safety]})
    fixed = {**DESIGN, "safety_and_dependencies": DESIGN["safety_and_dependencies"] + " The PR field is bits 3:0."}
    later = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": lambda p: fixed if p["findings"] else
                                              DESIGN}, later))
    swe2.visit(ws1, "m")
    design = [p for p in later if p["task"] == "design" and p["findings"]]
    assert design and design[0]["keep_fixed"] == [f"SWE2-05: {budget_text}"]
    assert f"SWE2-06: {safety}" in design[0]["findings"]
