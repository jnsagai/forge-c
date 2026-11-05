"""CAPA-087 (run WO-F014-SWE2-IWDG-20261101-01, Omniverse2, 2026-11-01): under the high-allowance policy the SWE.1
inspector failed SWE1-04 five times with reworded findings; stuck detection compared exact findings and never fired.
Owner 2026-11-01: the same item failing 3 times stops the phase (STUCK). Owner change 2026-11-02: only when the same
finding repeats (test_same_finding_stuck.py); the fixtures below repeat one finding near-verbatim ("wording <n>")."""
from __future__ import annotations

import json

from forge_factory import development_execution as D
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture


def _ins(ws_, n, failed, at="9999-01-01T00:00:0{}Z"):
    st = Store(ws_)
    bl = st.latest_baseline("SWE.1")
    d = ws_ / "inspection/SWE.1"
    d.mkdir(parents=True, exist_ok=True)
    items = {"SWE1-03": {"verdict": "PASS"}, "SWE1-04": {"verdict": "PASS"}, "SWE1-05": {"verdict": "PASS"}}
    for k in failed:
        items[k] = {"verdict": "FAIL"}
    rec = {"inspection_id": f"INS-SWE.1-{n:03d}", "baseline_id": bl["baseline_id"], "baseline_hash": bl["baseline_hash"],
           "verdict": "FAIL" if failed else "PASS", "items": items, "recorded_at": at.format(n),
           "findings": [{"item": k, "detail": f"wording {n}"} for k in failed]}
    (d / f"INS-SWE.1-{n:03d}.json").write_text(json.dumps(rec))


def test_the_same_item_failing_three_times_with_a_near_verbatim_finding_is_found(ws1):  # noqa: F811
    _ins(ws1, 1, ["SWE1-04"])
    _ins(ws1, 2, ["SWE1-04", "SWE1-05"])
    assert gate.repeated_failed_item(Store(ws1), "SWE.1") is None  # two failures: still repaired
    _ins(ws1, 3, ["SWE1-04"])
    assert gate.repeated_failed_item(Store(ws1), "SWE.1") == "SWE1-04"


def test_different_items_or_a_pass_in_between_are_not_stuck(ws1):  # noqa: F811
    _ins(ws1, 1, ["SWE1-03"])
    _ins(ws1, 2, ["SWE1-04"])
    _ins(ws1, 3, ["SWE1-04"])
    assert gate.repeated_failed_item(Store(ws1), "SWE.1") is None
    _ins(ws1, 4, [])
    _ins(ws1, 5, ["SWE1-04"])
    assert gate.repeated_failed_item(Store(ws1), "SWE.1") is None


def test_the_high_allowance_route_blocks_on_the_third_same_item_failure(ws1):  # noqa: F811
    m = json.loads((ws1 / ".forge-run/manifest.json").read_text())
    m["purpose"] = "ASPICE_ONLY"
    m["development_execution"] = D.binding(D.HIGH, "ASPICE_ONLY")
    (ws1 / ".forge-run/manifest.json").write_text(json.dumps(m))
    for n in (1, 2):
        _ins(ws1, n, ["SWE1-04"])
        assert gate.step_route(Store(ws1), "SWE.1") == 0  # rework granted
    _ins(ws1, 3, ["SWE1-04"])
    assert gate.step_route(Store(ws1), "SWE.1") == 1
    route = [json.loads(x) for x in (ws1 / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()
             if '"step": "route"' in x][-1]
    assert route["gate"]["decision"] == "BLOCKED" and "SAME_ITEM_FAILED_3X:SWE1-04" in route["gate"]["reason"]
