"""Feature 021 US1 (T007): the SWE.1 functional carry on the generic validated-item store. A run's PASS requirements
are published to the store when its per-requirement inspection ends; a rerun whose named sources are not available on
this machine still finds the earlier run that validated the same inputs (same governance inventory) through the
store; a different inventory finds nothing (INPUT_CHANGED stays the rule). Scripted answers only."""
import json
import shutil

import pytest
from f020_fixtures import ser_spec
from f020_swe1 import MODEL, prepared
from test_f020_carry import SRC, _author_dst, pair  # noqa: F401 - the two-run fixture
from test_f020_two_phase import judge


@pytest.mark.parametrize("legacy_workspace", [False, True])
def test_retry_keeps_inspected_requirements_after_interrupted_author_rework(pair, monkeypatch, legacy_workspace):  # noqa: F811
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe1_carry as C
    from forge_factory.lrtx import swe1_quality as Q
    from forge_factory.lrtx import visit as V

    src, dst = pair
    if legacy_workspace:
        Store(src).freeze("SWE.1", "swe1-author")
        shutil.rmtree(src / C.SNAPSHOTS)
    task = "requirements:g_blocking_transfer"
    checkpoint = V._ckpt(src, "SWE.1", task)
    before = json.loads(checkpoint.read_text())
    draft = {**before, "doc": {**before["doc"], "requirements": before["doc"]["requirements"][:1]}}
    checkpoint.write_text(json.dumps(draft))

    reply, _ = _author_dst(dst, monkeypatch)
    assert reply["status"] == "PASS", reply
    target = json.loads(V._ckpt(dst, "SWE.1", task).read_text())
    assert "receive_blocking" in target["carry_merge"]["restored"]
    seen = []
    monkeypatch.setattr(S, "call", judge({}, seen))
    assert Q.iq_inspect(dst, MODEL)["status"] == "PASS"
    assert "receive_blocking" not in {packet["task"].split(":")[3] for packet in seen}
    verdict = next(v for v in Q.verdicts(dst).values() if v["key"] == "receive_blocking")
    assert verdict["passed"] and verdict["carried_from"]["source_work_order"] == SRC


def test_rework_does_not_accept_a_draft_that_conflicts_with_unreleased_requirements(pair, monkeypatch):  # noqa: F811
    from forge_factory.lrtx import swe1_carry as C
    from forge_factory.lrtx import swe1_functional as F
    from forge_factory.lrtx import visit as V

    _, dst = pair
    reply, _ = _author_dst(dst, monkeypatch)
    assert reply["status"] == "PASS"
    task = next(task for task in F.plan(dst) if task["id"] == "requirements:g_blocking_transfer")
    checkpoint = V._ckpt(dst, "SWE.1", task["id"])
    rec = json.loads(checkpoint.read_text())
    finding = "SWE1-02: SWR-006 [tx_complete_callback] names the wrong callback"
    C.release(dst, task["id"], [finding])
    kept = json.loads(C._keep_path(dst, task["id"]).read_text())
    assert kept["release_findings"]["tx_complete_callback"] == [finding]
    assert "receive_blocking" in kept["kept"]
    draft = {**rec, "doc": {**rec["doc"], "requirements": rec["doc"]["requirements"][:1]}}
    monkeypatch.setattr(F, "validate_task", lambda *_: ["conflicting draft and preserved requirement"])
    merged = C.merge_kept(dst, task, draft, F.context(dst))
    assert merged["status"] == "INVALID"
    assert merged["errors"] == ["conflicting draft and preserved requirement"]


def test_the_inspection_publishes_its_pass_requirements(pair):  # noqa: F811
    from forge_factory.common import sha256_file
    from forge_factory.governance import inventory as GI
    from forge_factory.lrtx import carry_store as CS
    from forge_factory.lrtx import swe1_quality as Q

    src, _dst = pair
    passed = {k: v for k, v in Q.verdicts(src).items() if v.get("passed") is True}
    store, dep = CS.Store(), sha256_file(src / GI.OUT)
    assert passed and store.orders_for("SWE.1", dep) == [SRC]
    tk, sha = next(iter(passed))
    hit = store.find("SWE.1", tk, dep_sha=dep)
    assert hit["source_order"] == SRC and hit["verdicts"]["IQ"] == "PASS"


def test_a_rerun_whose_named_source_is_gone_finds_the_validated_run_in_the_store(tmp_path, monkeypatch, pair):  # noqa: F811
    from forge_factory.lrtx import swe1_carry as C

    src, _dst = pair
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-GONE"]}
    other = prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F021-ONLY-GONE")
    p, meta = C.source(other)
    assert p == src and meta["source_work_order"] == SRC and meta["via"] == "validated-item store"


def test_another_inventory_finds_nothing_in_the_store(tmp_path, monkeypatch, pair):  # noqa: F811
    from forge_factory.governance import inventory as GI
    from forge_factory.lrtx import swe1_carry as C

    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2", "carry_from": ["WO-F020-GONE"]}
    other = prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F021-OTHER-INPUTS")
    inv = json.loads((other / GI.OUT).read_text())
    inv["module"] = inv["module"] + "-changed"
    (other / GI.OUT).write_text(json.dumps(inv))
    p, meta = C.source(other)
    assert p is None and "WO-F020-GONE:NOT_AVAILABLE" in meta["reason"]
