"""Owner factory rule 2026-11-13 (D36): a rerun preserves every artifact already inspected and validated unless a
dependency changed - first application, functional SWE.1 at requirement granularity (lrtx/swe1_carry.py).

Source: a v1 order whose author set passed and whose per-requirement inspection judged every requirement (one failed).
Rerun: a template-v2 order of the same module with `swe1.carry_from`. Expected: the governance answer is carried (no
model call); tasks whose migrated requirements still validate are kept as is (no call); only the requirements the new
rules or findings name are reworked and every other requirement comes back byte-identical even when the answer
touched it; PASS verdicts of unchanged requirements are carried, everything changed or failed is judged again; a
changed inventory (inputs) carries nothing. Scripted model only."""
from __future__ import annotations

import copy
import json

import pytest
import test_f020_two_phase as two
from f020_fixtures import ser_spec
from f020_swe1 import MODEL, answers, author, prepared, scripted
from forge_factory.lrtx import structured as S
from test_f020_template_v2 import PRE, answers_v2

SRC, DST = "WO-F020-SRC", "WO-F020-DST"


def _source_answers() -> dict:
    """v1 answers with real preconditions on every functional requirement except transmit_blocking."""
    a = copy.deepcopy(answers())
    for t in a.values():
        for r in t["requirements"]:
            if r["type"] == "functional" and r["key"] != "transmit_blocking":
                r["precondition"] = PRE
    return a


@pytest.fixture()
def pair(tmp_path, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q

    src = prepared(tmp_path, monkeypatch, wo=SRC)
    rep, _ = author(src, monkeypatch, _source_answers())
    assert rep["status"] == "PASS", rep
    seen: list = []
    monkeypatch.setattr(S, "call", two.judge({"ll_enable": "name the enable condition"}, seen))
    assert Q.iq_inspect(src, MODEL)["status"] == "PASS"
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-GONE", SRC]}
    dst = prepared(tmp_path, monkeypatch, spec=spec, wo=DST)
    return src, dst


def test_the_rerun_names_its_source_and_carries_the_governance_answer(pair):
    from forge_factory.governance import package as GP
    from forge_factory.lrtx import swe1_carry as C
    from forge_factory.lrtx import visit as V

    src, dst = pair
    man = json.loads((dst / ".forge-run/manifest.json").read_text())
    assert man["swe1_carry_from"] == ["WO-F020-GONE", SRC]
    p, meta = C.source(dst)
    assert p == src and meta["source_work_order"] == SRC
    rec = json.loads(V._ckpt(dst, GP.VISIT, GP.TASK).read_text())
    assert rec["carried_from"]["source_work_order"] == SRC and rec["status"] == "VALID"
    assert GP.status(dst)["state"] == GP.PASS


def _author_dst(dst, monkeypatch):
    v2 = answers_v2(dst)
    changed = copy.deepcopy(v2["requirements:g_blocking_transfer"])
    for r in changed["requirements"]:
        if r["key"] == "receive_blocking":
            r["title"] = "a title the second answer changed"  # must come back byte-identical (kept); D40: no process words
    calls: list = []
    monkeypatch.setattr(S, "call", scripted({**v2, "requirements:g_blocking_transfer": changed}, calls))
    from forge_factory.lrtx import swe1_functional as F

    return F.visit(dst, MODEL), calls


def test_only_what_the_new_rules_name_is_reworked_and_the_rest_is_kept(pair, monkeypatch):
    from forge_factory.lrtx import swe1_carry as C
    from forge_factory.lrtx import swe1_functional as F
    from forge_factory.lrtx import visit as V

    src, dst = pair
    rep, calls = _author_dst(dst, monkeypatch)
    assert rep["status"] == "PASS", rep
    called = {p["task"] for p in calls}
    # transmit_blocking has no precondition (D33); the state requirements name no delivered function (D32)
    assert called == {"requirements:g_blocking_transfer", "requirements:state_behaviour"}, called
    ctx = F.context(dst)
    tasks = {t["id"]: t for t in F.plan(dst)}
    old = json.loads(V._ckpt(src, "SWE.1", "requirements:g_blocking_transfer").read_text())["doc"]["requirements"]
    new = json.loads(V._ckpt(dst, "SWE.1", "requirements:g_blocking_transfer").read_text())
    by = {r["key"]: r for r in new["doc"]["requirements"]}
    want = {r["key"]: C.migrate(r, tasks["requirements:g_blocking_transfer"], ctx) for r in old}
    assert by["receive_blocking"] == want["receive_blocking"]  # kept byte-identical despite the answer's change
    assert by["tx_complete_callback"] == want["tx_complete_callback"]
    assert by["transmit_blocking"]["precondition"] == PRE  # the reworked one
    assert "receive_blocking" in new["carry_merge"]["restored"]
    ll = json.loads(V._ckpt(dst, "SWE.1", "requirements:g_ll_configuration").read_text())
    assert ll["carried_from"]["source_work_order"] == SRC and not ll["attempts"]
    assert all(r["operations"] for r in ll["doc"]["requirements"])
    dc = json.loads(V._ckpt(dst, "SWE.1", "requirements:design_constraints").read_text())
    assert dc["carried_from"]["kept"] == len(dc["doc"]["requirements"])


def test_unchanged_requirements_keep_their_pass_verdict(pair, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q

    src, dst = pair
    rep, _ = _author_dst(dst, monkeypatch)
    assert rep["status"] == "PASS", rep
    seen: list = []
    monkeypatch.setattr(S, "call", two.judge({}, seen))
    assert Q.iq_inspect(dst, MODEL)["status"] == "PASS"
    judged = {p["task"].split(":")[3] for p in seen}
    # reworked (transmit_blocking, the two state requirements) and failed in the source (ll_enable): judged again
    assert judged == {"transmit_blocking", "busy_refusal", "invalid_parameter", "ll_enable"}, judged
    lines = [json.loads(x) for x in (dst / ".forge-run/lrtx/SWE.1/phase1/verdicts.jsonl").read_text().splitlines()]
    carried = [v for v in lines if v.get("carried_from")]
    assert carried and all(v["passed"] for v in carried)
    assert {v["key"] for v in carried} >= {"receive_blocking", "tx_complete_callback", "ll_disable"}


def test_a_changed_input_carries_nothing(pair):
    from forge_factory.governance import inventory as GI
    from forge_factory.lrtx import swe1_carry as C

    src, dst = pair
    inv = src / GI.OUT
    inv.write_text(inv.read_text().replace('"module"', '"module" ', 1))
    p, meta = C.source(dst)
    assert p is None and f"{SRC}:INPUT_CHANGED" in meta["reason"]


def test_a_later_finding_releases_a_kept_requirement(pair, monkeypatch):
    from forge_factory.lrtx import swe1_carry as C

    _src, dst = pair
    rep, _ = _author_dst(dst, monkeypatch)
    assert rep["status"] == "PASS"
    tid = "requirements:g_blocking_transfer"
    assert "receive_blocking" in C._kept(dst, tid)
    C.release(dst, tid, ["[receive_blocking] DUPLICATE_STATEMENT: duplicates another task"])
    assert "receive_blocking" not in C._kept(dst, tid)
