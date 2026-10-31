"""Owner decision 2026-10-26 ("Advisory + calibrate", refined: the model tries its best first): with the local
profile's structured.advisory_continue, a phase whose whole bounded ladder is exhausted (rework budget, progress
extensions, stall detection) and that has a frozen baseline continues to the next phase; its unresolved findings and
attempt record are registered for the end-of-run human review. The release rule is unchanged."""
import json
import re

import pytest
from forge_factory.inspection import gate as G
from forge_factory.inspection.engine import Store
from test_rework_progress_extension import _ins, _rej, _route, _ws


@pytest.fixture()
def advisory(monkeypatch):
    monkeypatch.setattr(G, "advisory_enabled", lambda ws: True)
    monkeypatch.setattr(Store, "latest_baseline", lambda self, phase: {"baseline_id": "BL-SWE.4-003",
                                                                       "baseline_hash": "x"})


def _exhaust(ws):
    for n in (1, 2, 3):  # findings grow every cycle: no progress extension
        _ins(ws, n, *[(f"SWE4-0{k}", f"UT-00{k} is vacuous") for k in range(1, n + 2)])


def test_an_exhausted_ladder_continues_with_its_gap_and_attempts_registered(tmp_path, advisory):
    ws = _ws(tmp_path)
    _exhaust(ws)
    rc, g = _route(ws)
    assert rc == 1 and g["decision"] == "ADVISORY_CONTINUE" and "registered for human review" in g["reason"]
    assert g["progress_extension"]["progress"] is False  # the extension was evaluated first, and refused
    rec = [json.loads(x) for x in (ws / g["advisory_ref"]).read_text().splitlines()][-1]
    assert rec["phase"] == "SWE.4" and rec["baseline_id"] == "BL-SWE.4-003"
    assert [f["id"] for f in rec["unresolved_findings"]] == ["SWE4-01", "SWE4-02", "SWE4-03", "SWE4-04"]
    att = rec["attempts"]
    assert att["failed_cycles"] == 3 and att["budget"] == 3 and len(att["history"]) == 3
    assert G.step_advisory(Store(ws), "SWE.4") == 0  # the advisory node continues the run
    ladder = {r["rung"]: r for r in att["ladder"]}  # every rung says what it did; none is implied
    assert list(ladder) == ["rework_with_findings", "progress_extension", "validated_lessons", "capa_retrieval",
                            "diagnosis_repair", "stall_detection"]
    assert ladder["capa_retrieval"]["status"] in ("NONE_MATCHING", "UNKNOWN")  # no CAPA links this fixture's failures
    assert ladder["rework_with_findings"]["failed_cycles"] == 3 and ladder["progress_extension"]["status"] == "REFUSED"
    assert ladder["validated_lessons"]["status"] == "NONE_QUALIFIED"
    assert ladder["diagnosis_repair"]["status"] == "UNAVAILABLE"  # a plain local run has no recovery path


def test_the_lessons_rung_names_the_lessons_this_phase_was_given(tmp_path, advisory, monkeypatch):
    from forge_factory.knowledge.store import LessonStore

    monkeypatch.setattr(LessonStore, "exposures", lambda self, run_id, phase=None:
                        ["lesson-0123456789ab"] if (run_id, phase) == ("WO-A", "SWE.4") else [])
    ws = _ws(tmp_path)
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    (ws / ".forge-run/manifest.json").write_text(json.dumps({**m, "work_order": "WO-A"}))
    _exhaust(ws)
    rc, g = _route(ws)
    rec = [json.loads(x) for x in (ws / g["advisory_ref"]).read_text().splitlines()][-1]
    rung = next(r for r in rec["attempts"]["ladder"] if r["rung"] == "validated_lessons")
    assert rung == {"rung": "validated_lessons", "status": "EXPOSED", "lesson_ids": ["lesson-0123456789ab"]}


def test_without_the_flag_or_a_frozen_baseline_the_phase_still_blocks(tmp_path, monkeypatch):
    ws = _ws(tmp_path)
    _exhaust(ws)
    rc, g = _route(ws)  # flag off (no local profile): unchanged behaviour
    assert rc == 1 and g["decision"] == "BLOCKED" and G.step_advisory(Store(ws), "SWE.4") == 1
    ws2 = _ws(tmp_path / "b")
    for n in (1, 2, 3):
        _rej(ws2, n, "ARCH:NO_INTERFACES")  # stuck at the author gate: nothing frozen to build on
    monkeypatch.setattr(G, "advisory_enabled", lambda ws: True)
    monkeypatch.setattr(Store, "latest_baseline", lambda self, phase: None)
    rc, g = _route(ws2)
    assert rc == 1 and g["decision"] == "BLOCKED" and not (ws2 / ".forge-run/advisory").exists()


def test_a_progressing_phase_keeps_its_extension_before_any_advisory_continue(tmp_path, advisory):
    ws = _ws(tmp_path)
    _rej(ws, 1, "UNIT:SWR_NOT_REFINED:SWR-013", "UNIT:SWR_NOT_REFINED:SWR-014")
    _rej(ws, 2, "UNIT:SWR_NOT_REFINED:SWR-014", "UNIT:SWR_NOT_REFINED:SWR-015")
    _rej(ws, 3, "UNIT:SWR_NOT_REFINED:SWR-015")
    rc, g = _route(ws)  # the ladder is not exhausted while the phase measurably progresses
    assert rc == 0 and g["decision"] != "ADVISORY_CONTINUE" and g["progress_extension"]["progress"] is True


def test_the_advisory_node_is_wired_only_in_the_advisory_profile_graph():
    from forge_factory.workflow.builder import build

    base, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg")
    st = {"phases": [], "inspect_phases": [], "reinspect": False, "model": "m"}
    plain, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured=st)
    g, _ = build("WO-X", layer="LL", trace=True, peripheral="iwdg", structured={**st, "advisory": True})
    node = re.compile(r"\bswe\d_advisory\b")  # node names only: paths in the graph may contain the test's name
    assert not node.search(base) and not node.search(plain)
    for n in range(1, 7):
        nxt = "release_manager" if n == 6 else None
        assert f"  swe{n}_route -> swe{n}_advisory\n" in g and f"  swe{n}_route -> upstream_swe1\n" in base
        assert f"  swe{n}_advisory -> upstream_swe1\n" in g
        succ = [x for x in g.splitlines() if x.startswith(f"  swe{n}_advisory -> ") and "outcome=succeeded" in x]
        assert len(succ) == 1 and (nxt is None or f"-> {nxt} " in succ[0])
        assert "--step advisory" in g


def test_the_package_carries_the_register_and_the_release_rule_is_unchanged(tmp_path):
    from forge_factory.release import finalize as F

    ws = tmp_path / "ws"
    (ws / ".forge-run/advisory").mkdir(parents=True)
    (ws / ".forge-run/advisory/SWE.2.jsonl").write_text(json.dumps({"phase": "SWE.2", "unresolved_findings": []}) + "\n")
    (ws / ".forge-run/advisory/SWE.1.jsonl").write_text(json.dumps({"phase": "SWE.1", "unresolved_findings": []}) + "\n")
    assert [e["phase"] for e in F.advisory_register(ws)] == ["SWE.1", "SWE.2"]
    assert F.advisory_register(tmp_path / "none") == []


def test_the_capa_rung_names_the_capas_linked_to_this_phases_failure_fingerprints(tmp_path, monkeypatch):
    from forge_factory.reliability import capa, observe

    monkeypatch.setattr(observe, "from_workspace", lambda ws: [{"phase": "SWE.4", "fingerprint": "cfp1-aaa"},
                                                               {"phase": "SWE.3", "fingerprint": "cfp1-bbb"}])

    class Reg:
        def __init__(self, *a):
            pass

        def all(self):
            return [{"capa_id": "CAPA-070", "state": "OPEN"}, {"capa_id": "CAPA-071", "state": "CLOSED"}]

        def links(self, capa_id, kind=None):
            return {"CAPA-070": ["cfp1-aaa"], "CAPA-071": ["cfp1-bbb"]}[capa_id]

    monkeypatch.setattr(capa, "CapaRegistry", Reg)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    r = G.capa_rung(tmp_path, "SWE.4")
    assert r == {"rung": "capa_retrieval", "status": "MATCHED", "capas": [{"capa_id": "CAPA-070", "state": "OPEN"}],
                 "fingerprints": ["cfp1-aaa"]}
    assert G.capa_rung(tmp_path, "SWE.1")["status"] == "NONE_MATCHING"
