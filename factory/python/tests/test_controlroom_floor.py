"""CR-T008/CR-T009: live floor - andon derivation from recorded gate decisions, schema, stable content hash."""
import json
from datetime import datetime

from controlroom_fixtures import CFG, FakeProbe, append, inspect, passed, rejected, route, ts, workspace
from forge_factory.common import REPO_ROOT
from forge_factory.controlroom.floor import Floor, GateLogReader
from jsonschema import Draft202012Validator

SCHEMA = json.loads((REPO_ROOT / "specs/007-kpi-control-room/contracts/floor-snapshot.schema.json").read_text())
NOW = datetime.fromisoformat("2026-10-19T12:30:00+00:00").timestamp()


def _floor(tmp_path, probe=None):
    return Floor(root=tmp_path, probe=probe or FakeProbe(last_ts=ts(149)))


def _st(snap, sid):
    return next(s for s in snap["stations"] if s["station_id"] == sid)


def _u(snap, wo):
    return next(u for u in snap["units"] if u["work_order"] == wo)


def test_running_unit_moves_station_after_a_pass(tmp_path):
    ws = workspace(tmp_path, "WO-A-r1", [*passed("SWE.1", 1)])
    f = _floor(tmp_path)
    s = f.snapshot(CFG, now=NOW)
    assert _u(s, "WO-A-r1")["station"] == "SWE.2" and _u(s, "WO-A-r1")["status"] == "RUNNING"
    assert _st(s, "SWE.2")["andon"] == "RUNNING" and _st(s, "SWE.1")["andon"] == "IDLE"
    assert s["factory_status"] == "PRODUCING"
    append(ws, *passed("SWE.2", 10))
    s2 = f.snapshot(CFG, now=NOW)
    assert _u(s2, "WO-A-r1")["station"] == "SWE.3" and s2["content_hash"] != s["content_hash"]


def test_rework_shows_amber_with_the_recorded_reason(tmp_path):
    workspace(tmp_path, "WO-B-r1", [*passed("SWE.1", 1), rejected("SWE.2", 5), route("SWE.2", 6)])
    s = _floor(tmp_path).snapshot(CFG, now=NOW)
    st = _st(s, "SWE.2")
    assert st["andon"] == "REWORK" and st["reason"] == "NO_BASELINE" and s["factory_status"] == "ATTENTION"
    assert st["evidence"] == ["WO-B-r1/.forge-run/gates/gate-log.jsonl#L4"]
    assert _u(s, "WO-B-r1")["rework_cycles"]["SWE.2"] == 1


def test_author_rejection_reason_is_the_issue_code(tmp_path):
    workspace(tmp_path, "WO-C-r1", [rejected("SWE.1", 2)])
    s = _floor(tmp_path).snapshot(CFG, now=NOW)
    assert _st(s, "SWE.1")["reason"] == "author REJECTED: CONTRACT_SWR_NOT_COVERED"


def test_blocked_in_progress_is_red_and_stops_the_factory(tmp_path):
    workspace(tmp_path, "WO-D-r1", [*passed("SWE.1", 1), *passed("SWE.2", 5), *passed("SWE.3", 9),
                                    inspect("SWE.4", 20, "REWORK"),
                                    route("SWE.4", 30, "BLOCKED", "rework budget exhausted (3 failed cycles)")])
    s = _floor(tmp_path).snapshot(CFG, now=NOW)
    st = _st(s, "SWE.4")
    assert st["andon"] == "BLOCKED" and st["reason"] == "rework budget exhausted (3 failed cycles)"
    assert s["factory_status"] == "STOPPED" and st["units"] == ["WO-D-r1"]


def test_governor_budget_exhaustion_is_blocked(tmp_path):
    workspace(tmp_path, "WO-E-r1", [{"phase": "SWE.1", "step": "governor", "result": "TOKEN_BUDGET_EXHAUSTED",
                                     "ts": ts(3)}])
    assert _st(_floor(tmp_path).snapshot(CFG, now=NOW), "SWE.1")["andon"] == "BLOCKED"


def test_shipped_units_are_listed_at_shipping_and_blocked_scrap_keeps_its_cause(tmp_path):
    all_six = [x for i, p in enumerate(["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]) for x in passed(p, i * 10)]
    workspace(tmp_path, "WO-F-r1", all_six, package="READY_FOR_OFFLINE_REVIEW")
    workspace(tmp_path, "WO-G-r1", [*passed("SWE.1", 1), route("SWE.2", 9, "BLOCKED", "rework budget exhausted")],
              package="BLOCKED")
    s = _floor(tmp_path).snapshot(CFG, now=NOW)
    assert _u(s, "WO-F-r1")["status"] == "READY" and _u(s, "WO-F-r1")["station"] == "SHIPPING"
    g = _u(s, "WO-G-r1")
    assert g["status"] == "BLOCKED" and g["reason"] == "SWE.2: rework budget exhausted"
    assert _st(s, "SHIPPING")["andon"] == "IDLE"            # shipped units are output/scrap, not a stopped station
    assert {r["work_order"] for r in _st(s, "SHIPPING")["recent"]} == {"WO-F-r1", "WO-G-r1"}
    assert [r["work_order"] for r in _st(s, "SWE.2")["recent"]] == ["WO-G-r1"]
    assert s["factory_status"] == "NO_WIP"


def test_run_ended_without_package_is_stopped(tmp_path):
    workspace(tmp_path, "WO-H-r1", [rejected("SWE.3", 5)], run_id="RUN-H")
    s = _floor(tmp_path, FakeProbe({"RUN-H": "failed"}, ts(10))).snapshot(CFG, now=NOW)
    u = _u(s, "WO-H-r1")
    assert u["status"] == "STOPPED" and u["reason"] == "run failed, no package"
    assert _st(s, "SWE.3")["andon"] == "BLOCKED" and s["factory_status"] == "STOPPED"


def test_retries_are_attempts_of_one_order_and_first_pass_is_immutable(tmp_path):
    workspace(tmp_path, "WO-I-r2", [inspect("SWE.1", 1, "REWORK"), route("SWE.1", 2), *passed("SWE.1", 3)])
    u = _u(_floor(tmp_path).snapshot(CFG, now=NOW), "WO-I-r2")
    assert u["order_id"] == "WO-I" and u["first_pass"]["SWE.1"] == "FAIL" and u["station"] == "SWE.2"


def test_elapsed_time_grows_live_and_freezes_at_shipping(tmp_path):
    workspace(tmp_path, "WO-J-r1", [*passed("SWE.1", 1)], created="2026-10-19T10:00:00Z")
    f = _floor(tmp_path)
    assert _u(f.snapshot(CFG, now=NOW), "WO-J-r1")["elapsed_s"] == 9000.0
    assert _u(f.snapshot(CFG, now=NOW + 60), "WO-J-r1")["elapsed_s"] == 9060.0


def test_stale_only_when_something_runs_and_data_is_old(tmp_path):
    workspace(tmp_path, "WO-K-r1", [*passed("SWE.1", 1)])
    import os

    gl = tmp_path / "WO-K-r1/workspace/.forge-run/gates/gate-log.jsonl"
    for p in (gl, gl.parents[1] / "manifest.json"):
        os.utime(p, (NOW - 3600, NOW - 3600))
    s = _floor(tmp_path, FakeProbe(last_ts=None)).snapshot(CFG, now=NOW)
    assert s["stale"] is True and s["data_age_s"] == 3600.0
    empty = Floor(root=tmp_path / "none", probe=FakeProbe()).snapshot(CFG, now=NOW)
    assert empty["stale"] is False and empty["factory_status"] == "NO_WIP" and empty["data_age_s"] is None
    assert all(st["andon"] == "IDLE" for st in empty["stations"])


def test_violation_overrides_every_other_status(tmp_path):
    workspace(tmp_path, "WO-L-r1", [*passed("SWE.1", 1)])
    assert _floor(tmp_path).snapshot(CFG, now=NOW, violations_open=1)["factory_status"] == "VIOLATION"


def test_snapshots_validate_and_hash_is_stable(tmp_path):
    workspace(tmp_path, "WO-M-r1", [*passed("SWE.1", 1), rejected("SWE.2", 4), route("SWE.2", 5)])
    workspace(tmp_path, "WO-N-r1", [*passed("SWE.1", 1)], package="BLOCKED")
    f = _floor(tmp_path)
    a, b = f.snapshot(CFG, now=NOW), f.snapshot(CFG, now=NOW + 5)
    assert not list(Draft202012Validator(SCHEMA).iter_errors(a))
    assert a["content_hash"] == b["content_hash"]                 # time passing alone is not a floor change


def test_reader_is_incremental_and_waits_for_a_partial_line(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps({"step": "author"}) + "\n" + '{"step": "insp')
    r = GateLogReader()
    assert [x["step"] for x in r.rows(p)] == ["author"]
    with p.open("a") as fh:
        fh.write('ect"}\n')
    assert [(x["step"], x["_line"]) for x in r.rows(p)] == [("author", 1), ("inspect", 2)]
    assert len(r.rows(p)) == 2                                    # re-reading adds nothing (idempotent)
