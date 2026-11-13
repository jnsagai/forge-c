"""Owner 2026-11-13 ("go ahead with 1, 2 and 3"), autonomy items 1 and 2 - found by the L48 incident: the UART order
failed its delivery build four times at launch (math.h missing in the owner-lane toolchain), the lineage stopped with
SAME_ISSUE_EXCEEDED_3, and only a hand-made series bump restarted it after the environment was fixed.

1. Before ANY placement (first, retry, relaunch) the line checks the order's inputs, now including the delivery build
   (brownfield.delivery.precheck): a compile failure is an INPUT_GAP held with its compiler message - no launch, no
   strike. A check that cannot run (source unreadable, no compiler) is UNVERIFIED and never holds the line.
2. A stopped lineage whose strikes were all pre-run input/environment failures is released by the line itself once the
   same checks pass again (CAUSE_GONE), once per lineage block, logged with its evidence. A new deployed revision
   already rebinds every lineage block (the campaign names the revision), so no second rule is needed for that."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

import json
import os
from pathlib import Path

from forge_factory.afo import lineage_release as LR
from forge_factory.afo import line_orders as LO
from forge_factory.brownfield import delivery as BD
from test_line_conductor_m3 import X, drive, env, grant, lin, lineage, placer, write_campaign  # noqa: F401

SPEC = {"layer": "LL+HAL", "delivery": {"build": {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True}}}


# ---- 1: the delivery precheck -----------------------------------------------------------------------------------------
def test_precheck_is_not_applicable_without_a_delivery_or_for_a_provided_ll_hal():
    assert BD.precheck({"layer": "LL"}, Path("."))["status"] == "NOT_APPLICABLE"
    hal = {"layer": "HAL", "delivery": {"provided_ll": True}}
    assert BD.precheck(hal, Path("."))["reason"] == "BUILDS_AGAINST_A_PROVIDED_LL"


def test_precheck_maps_the_build_and_never_turns_its_own_failure_into_a_gap(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(BD, "_collect", lambda d, ex: ([], {"software/hal/x.c": b"int x;"}, [], [], []))

    def build(files, style, defines, secure):
        seen["path"] = os.environ["PATH"]
        return {"status": seen.get("want", "FAIL"), "command": ["arm-none-eabi-gcc", "-c"], "exit_code": 1,
                "log": "x.c:1: fatal error: math.h: No such file or directory", "log_sha256": "0" * 64}
    monkeypatch.setattr(BD, "build_check", build)
    before = os.environ["PATH"]
    r = BD.precheck(SPEC, tmp_path, toolchain_bin=tmp_path / "bin")
    assert r["status"] == "FAIL" and "math.h" in r["log_tail"] and r["command"] == ["arm-none-eabi-gcc"]
    assert seen["path"].startswith(str(tmp_path / "bin")) and os.environ["PATH"] == before  # restored
    seen["want"] = "PASS"
    assert BD.precheck(SPEC, tmp_path)["status"] == "PASS"
    seen["want"] = "NOT_RUN"  # no compiler: the check could not run
    assert BD.precheck(SPEC, tmp_path)["status"] == "UNVERIFIED"
    monkeypatch.setattr(BD, "_collect", lambda d, ex: (["DELIVERY_SOURCE_UNREADABLE:x"], {}, [], [], []))
    assert BD.precheck(SPEC, tmp_path)["status"] == "UNVERIFIED"


def test_the_delivery_gap_is_cached_on_pass_and_rechecked_after_a_failure(monkeypatch, tmp_path):
    calls = []
    want = {"status": "FAIL"}
    monkeypatch.setattr(BD, "precheck", lambda spec, ex, toolchain_bin=None: (calls.append(1), dict(
        want, log_tail="fatal error: math.h"))[1])
    cache: dict = {}
    k = ("rev", "ex-u")
    assert LO.delivery_gap(cache, k, SPEC, tmp_path, now=100.0, detail_dir=tmp_path / "gaps") == "DELIVERY_BUILD"
    detail = json.loads((tmp_path / "gaps/ex-u.json").read_text())
    assert detail["code"] == "DELIVERY_BUILD" and "math.h" in detail["log_tail"]
    assert LO.delivery_gap(cache, k, SPEC, tmp_path, now=200.0, detail_dir=tmp_path / "gaps") == "DELIVERY_BUILD"
    assert len(calls) == 1  # within the recheck interval
    want["status"] = "PASS"
    assert LO.delivery_gap(cache, k, SPEC, tmp_path, now=100.0 + LO.DELIVERY_RECHECK_S + 1,
                           detail_dir=tmp_path / "gaps") is None
    assert not (tmp_path / "gaps/ex-u.json").exists()  # a resolved gap leaves no stale detail
    LO.delivery_gap(cache, k, SPEC, tmp_path, now=10_000.0, detail_dir=tmp_path / "gaps")
    assert len(calls) == 2  # a PASS stays cached
    want["status"] = "UNVERIFIED"
    assert LO.delivery_gap({}, k, SPEC, tmp_path, now=1.0, detail_dir=tmp_path / "gaps") is None


def test_a_retry_is_held_on_an_input_gap_and_placed_once_it_is_filled(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", phases=["SWE.1"])])
    grant(env)
    line = env["line"]
    pl = placer(env)
    first = "WO-F014-SWE1-CRCL-20261103-L30"
    drive(env, pl, {first: X}, cycles=1)  # the first attempt is placed and fails
    assert [x["wo"] for x in line.launched] == [first]
    gap = ["DELIVERY_BUILD"]
    line.input_gaps = lambda sha, ex, purpose: list(gap)
    outs = drive(env, pl, cycles=3)
    v = lin(outs[-1], "crc-ll")
    assert (v["state"], v["reason"]) == ("WAITING", "INPUT_GAP:DELIVERY_BUILD:ex-crc-ll")
    assert [x["wo"] for x in line.launched] == [first] and v["strikes"]["count"] == 1  # no launch, no strike
    gap.clear()
    drive(env, pl, cycles=3, until=lambda o: len(line.launched) == 2)
    assert line.launched[1]["wo"].startswith(first) and line.launched[1]["wo"] != first


# ---- 2: a stopped lineage is released when its pre-run cause is gone ---------------------------------------------------
def _stopped(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", phases=["SWE.1"])])
    grant(env)
    pl = placer(env)
    sw = [f"WO-F014-SWE1-CRCL-20261103-L30{s}" for s in ("", "B", "C", "D")]
    outs = drive(env, pl, {w: X for w in sw}, cycles=8)
    v = lin(outs[-1], "crc-ll")
    assert (v["state"], v["reason"]) == ("ESCALATED", "SAME_ISSUE_EXCEEDED_3")
    return pl, sw


def _pre_run(wo):
    return {"status": "BLOCKED", "stage": "delivery_intake", "issues": ["DELIVERY_BUILD_FAIL"]}


def test_a_stop_caused_by_a_pre_run_gap_is_released_once_the_checks_pass(env):
    line = env["line"]
    pl, sw = _stopped(env)
    line.releases = LR.Releases(env["tmp"] / "releases.jsonl")
    line.launch_cause = _pre_run
    line.input_gaps = lambda sha, ex, purpose: ["DELIVERY_BUILD"]  # still broken: stays stopped
    outs = drive(env, pl, cycles=3)
    assert lin(outs[-1], "crc-ll")["state"] == "ESCALATED" and len(line.launched) == 4
    line.input_gaps = lambda sha, ex, purpose: []  # the environment was fixed
    outs = drive(env, pl, cycles=6, until=lambda o: lin(o, "crc-ll")["state"] == "DONE")
    assert lin(outs[-1], "crc-ll")["state"] == "DONE" and len(line.launched) == 5
    rows = [json.loads(x) for x in (env["tmp"] / "releases.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["rule"] == LR.CAUSE_GONE and rows[0]["lineage"].endswith("crc-ll")
    assert rows[0]["evidence"]["attempts"] == sw and rows[0]["evidence"]["causes"][sw[0]]["stage"] == "delivery_intake"


def test_a_stop_from_run_failures_is_not_released(env):
    line = env["line"]
    pl, _sw = _stopped(env)
    line.releases = LR.Releases(env["tmp"] / "releases.jsonl")
    line.launch_cause = lambda wo: None  # the runs started: no pre-run cause
    line.input_gaps = lambda sha, ex, purpose: []
    outs = drive(env, pl, cycles=4)
    assert lin(outs[-1], "crc-ll")["state"] == "ESCALATED" and len(line.launched) == 4
    assert not (env["tmp"] / "releases.jsonl").exists()


def test_a_released_lineage_that_fails_again_stays_stopped(env):
    line = env["line"]
    pl, sw = _stopped(env)
    line.releases = LR.Releases(env["tmp"] / "releases.jsonl")
    line.launch_cause = _pre_run
    line.input_gaps = lambda sha, ex, purpose: []
    more = [f"WO-F014-SWE1-CRCL-20261103-L30{s}" for s in ("E", "F", "G", "H", "I")]
    outs = drive(env, pl, {w: X for w in more}, cycles=14)
    assert lin(outs[-1], "crc-ll")["state"] == "ESCALATED"
    launched = [x["wo"] for x in line.launched]
    assert launched[:4] == sw and len(launched) == 8  # one release, four more strikes, stopped for good
    assert len((env["tmp"] / "releases.jsonl").read_text().splitlines()) == 1


def test_launch_cause_reads_the_attempt_launch_log(tmp_path):
    d = tmp_path / ".launch/WO-A/attempt-1"
    d.mkdir(parents=True)
    (d / "workorder-launch.log").write_text('noise\n{"work_order": "WO-A", "status": "BLOCKED", '
                                           '"stage": "delivery_intake", "issues": ["DELIVERY_BUILD_FAIL"]}\n')
    c = LR.launch_cause(tmp_path, "WO-A")
    assert c == {"status": "BLOCKED", "stage": "delivery_intake", "issues": ["DELIVERY_BUILD_FAIL"]}
    assert LR.pre_run(c) and not LR.pre_run({"status": "BLOCKED", "stage": "swe1", "issues": ["X"]})
    assert LR.launch_cause(tmp_path, "WO-NONE") is None
