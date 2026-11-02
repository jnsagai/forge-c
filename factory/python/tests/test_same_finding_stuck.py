"""Owner change 2026-11-02 (cloud comparison line): an item is STUCK only when the SAME finding repeats on it.

Runs WO-F014-CMP-SWE1-RCC-20261102-06, -IWDG-20261102-05 and -CRCL-20261102-06 stopped BLOCKED STUCK
SAME_ITEM_FAILED_3X:SWE1-02 although each round's SWE1-02 finding was a different issue the author had fixed. The test
data are the full finding texts of the last three inspection rounds of those runs (and of three runs whose finding
really repeated), copied from the Forge-C inspection records."""
from __future__ import annotations

import json
from pathlib import Path

from forge_factory import development_execution as D
from forge_factory.inspection import finding_identity as FI
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture

DATA = json.loads((Path(__file__).parent / "fixtures/cloud-stuck-rounds-20261102.json").read_text())


def _incident(wo: str, item: str) -> dict:
    return next(i for i in DATA["incidents"] if i["work_order"] == wo and i["item"] == item)


def _rounds(inc: dict) -> list[list[str]]:
    return [r["findings"] for r in inc["rounds"]]


def test_the_incident_rounds_classify_as_the_owner_expects():
    assert {i["expected"] for i in DATA["incidents"]} == {"SAME", "DIFFERENT"}
    for inc in DATA["incidents"]:
        alive = FI.persisting(_rounds(inc))
        assert bool(alive) == (inc["expected"] == "SAME"), (inc["work_order"], inc["item"], alive[:1])


def test_moving_target_runs_are_progress():
    for wo in ("WO-F014-CMP-SWE1-RCC-20261102-06", "WO-F014-CMP-SWE1-IWDG-20261102-05",
               "WO-F014-CMP-SWE1-CRCL-20261102-06"):
        assert FI.persisting(_rounds(_incident(wo, "SWE1-02"))) == [], wo


def test_rcc06_preservation_findings_on_other_requirements_are_different_findings():
    r = _rounds(_incident("WO-F014-CMP-SWE1-RCC-20261102-06", "SWE1-02"))
    serialization, rcc_cr, others = r[0][1], r[1][0], r[2][0]
    assert "SWR-653" in serialization and "RCC_CR" in rcc_cr and "SWR-016" in others
    assert not FI.same_finding(serialization, rcc_cr)
    assert not FI.same_finding(rcc_cr, others)
    # the APB3 scope finding really did repeat from round 1 to round 2 (and was gone in round 3)
    assert FI.same_finding(r[0][4], r[1][3])


def test_a_verbatim_or_near_verbatim_repeat_is_the_same_finding():
    text = _rounds(_incident("WO-F014-CMP-SWE1-RCC-20261102-06", "SWE1-02"))[1][2]
    assert FI.same_finding(text, text)
    assert FI.same_finding(text, "Major - SWE1-02: " + text)  # severity and item labels do not count
    assert FI.same_finding(text, text.replace("SWR-660", "SWR-656"))  # renumbered, otherwise verbatim
    assert FI.same_finding(text, text.replace("therefore lacks", "still lacks"))
    assert FI.persisting([[text], [text.replace("SWR-660", "SWR-661")], [text]]) == [text]


def test_disjoint_requirements_are_not_matched_by_wording_alone():
    trace = _rounds(_incident("WO-F014-CMP-SWE1-IWDG-20261102-02", "SWE1-01"))[0]
    assert "SWR-001" in trace[0] and "SWR-005" in trace[1]
    assert not FI.same_finding(trace[0], trace[1])  # same kind of defect, another requirement
    m = FI.compare(trace[0], trace[1])
    assert m["location_compatible"] is False and m["sequence"] < FI.NEAR_VERBATIM


def test_a_round_without_finding_text_keeps_the_item_only_rule():
    assert FI.persisting([[], [], []]) == [""]
    assert FI.persisting([["the CPU budget is missing"], [], ["the CPU budget is missing"]]) == [
        "the CPU budget is missing"]
    assert FI.persisting([["the CPU budget is missing"], ["SWR-004 lacks a reset value"]]) == []


def _ins(ws_, n, items: dict[str, list[str]]):
    st = Store(ws_)
    bl = st.latest_baseline("SWE.1")
    d = ws_ / "inspection/SWE.1"
    d.mkdir(parents=True, exist_ok=True)
    rec_items = {"SWE1-03": {"verdict": "PASS"}, "SWE1-04": {"verdict": "PASS"}}
    for k, texts in items.items():
        rec_items[k] = {"verdict": "FAIL", "findings": texts}
    rec = {"inspection_id": f"INS-SWE.1-{n:03d}", "baseline_id": bl["baseline_id"], "baseline_hash": bl["baseline_hash"],
           "verdict": "FAIL" if items else "PASS", "items": rec_items, "recorded_at": f"9999-01-01T00:00:{n:02d}Z",
           "findings": [{"id": k, "detail": t[0][:200]} for k, t in items.items()]}
    (d / f"INS-SWE.1-{n:03d}.json").write_text(json.dumps(rec))


def _high(ws_):
    m = json.loads((ws_ / ".forge-run/manifest.json").read_text())
    m["purpose"] = "ASPICE_ONLY"
    m["development_execution"] = D.binding(D.HIGH, "ASPICE_ONLY")
    (ws_ / ".forge-run/manifest.json").write_text(json.dumps(m))


def _last_route(ws_):
    return [json.loads(x) for x in (ws_ / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()
            if '"step": "route"' in x][-1]["gate"]


def test_the_route_keeps_repairing_a_moving_target_and_blocks_a_repeated_finding(ws1):  # noqa: F811
    _high(ws1)
    rounds = _rounds(_incident("WO-F014-CMP-SWE1-RCC-20261102-06", "SWE1-02"))
    for n, texts in enumerate(rounds, 1):
        _ins(ws1, n, {"SWE1-02": texts})
        assert gate.step_route(Store(ws1), "SWE.1") == 0, n  # each round a different finding: progress
    assert gate.repeated_failed_item(Store(ws1), "SWE.1") is None
    last = rounds[-1][0]
    assert "used by SWR-649" in last
    # rounds 3, 4, 5 repeat one finding near-verbatim (a new wording each round, as on a re-frozen baseline)
    _ins(ws1, 4, {"SWE1-02": [last.replace("used by SWR-649", "of SWR-649")]})
    assert gate.step_route(Store(ws1), "SWE.1") == 0
    _ins(ws1, 5, {"SWE1-02": [last.replace("SWR-649", "SWR-650")]})
    assert gate.step_route(Store(ws1), "SWE.1") == 1
    route = _last_route(ws1)
    assert route["decision"] == "BLOCKED" and "SAME_ITEM_FAILED_3X:SWE1-02" in route["reason"]
    assert route["repeated_finding"]["SWE1-02"].startswith(last[:60])


def test_the_phase_repair_bound_still_ends_a_moving_target(ws1):  # noqa: F811
    _high(ws1)
    rounds = _rounds(_incident("WO-F014-CMP-SWE1-IWDG-20261102-05", "SWE1-02"))
    _ins(ws1, 1, {"SWE1-02": rounds[0]})
    _ins(ws1, 2, {"SWE1-02": rounds[1]})
    with D.phase_state(ws1, "SWE.1") as state:  # 999 of the policy's 1000 phase repair passes already used
        state["phase_reworks"] = D.selected(ws1)["max_phase_repair_passes"] - 1
    _ins(ws1, 3, {"SWE1-02": rounds[2]})
    assert gate.step_route(Store(ws1), "SWE.1") == 0  # the last pass is granted (different finding)
    _ins(ws1, 4, {"SWE1-02": rounds[0]})
    assert gate.step_route(Store(ws1), "SWE.1") == 1  # still a different finding, but the bound is reached
    route = _last_route(ws1)
    assert route["decision"] == "BLOCKED" and "development repair exhausted" in route["reason"]


def _moving_rounds() -> list[list[str]]:
    """Six rounds of SWE1-02 findings, each a different issue (IWDG-05 then CRCL-06 incident rounds)."""
    return (_rounds(_incident("WO-F014-CMP-SWE1-IWDG-20261102-05", "SWE1-02"))
            + _rounds(_incident("WO-F014-CMP-SWE1-CRCL-20261102-06", "SWE1-02")))


def test_a_moving_target_is_capped_at_six_consecutive_failures_of_the_item(ws1):  # noqa: F811
    _high(ws1)
    rounds = _moving_rounds()
    assert gate.MOVING_TARGET_LIMIT == 6 and len(rounds) == 6
    for n, texts in enumerate(rounds[:5], 1):
        _ins(ws1, n, {"SWE1-02": texts})
        assert gate.step_route(Store(ws1), "SWE.1") == 0, n  # five rounds of different findings still continue
    assert gate.moving_target_items(Store(ws1), "SWE.1") == {}
    _ins(ws1, 6, {"SWE1-02": rounds[5]})
    assert gate.step_route(Store(ws1), "SWE.1") == 1
    route = _last_route(ws1)
    assert route["decision"] == "BLOCKED" and "STUCK: ITEM_FAILED_6X_MOVING_TARGET:SWE1-02;" in route["reason"]
    summary = route["moving_target_rounds"]["SWE1-02"]
    assert [s["inspection_id"] for s in summary] == [f"INS-SWE.1-{n:03d}" for n in range(1, 7)]
    assert [s["findings"] for s in summary] == [len(t) for t in rounds]
    assert all(s["first"] == t[0][:200] for s, t in zip(summary, rounds, strict=True))
    assert "repeated_finding" not in route


def test_a_pass_of_the_item_restarts_the_moving_target_count(ws1):  # noqa: F811
    _high(ws1)
    rounds = _moving_rounds()
    for n, texts in enumerate(rounds[:3], 1):
        _ins(ws1, n, {"SWE1-02": texts})
    _ins(ws1, 4, {"SWE1-03": ["SWE1-03 only: failure handling is not specified."]})
    for n, texts in enumerate(rounds[3:], 5):
        _ins(ws1, n, {"SWE1-02": texts})
    _ins(ws1, 8, {"SWE1-02": rounds[0]})
    assert gate.moving_target_items(Store(ws1), "SWE.1") == {}  # SWE1-02 failed only the last 4 in a row
