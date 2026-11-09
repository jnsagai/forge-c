"""CAPA-207: the line holds a ladder step whose inputs are not ready (INPUT_GAP:<code>:<example>) - both a first
placement and a queued retry - and launches it once a deployed revision fills the gap."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

from test_f019_ladder_walk import ladder
from test_line_conductor_m3 import drive, env, lin, placer  # noqa: F401


def test_a_step_with_an_input_gap_is_held_and_launches_once_filled(env):
    ladder(env)
    line = env["line"]
    gap = {"ex-crc-hal": ["CPU_TIMING_BUDGET"]}
    line.input_gaps = lambda sha, ex, purpose: list(gap.get(ex, []))
    pl = placer(env)
    outs = drive(env, pl, cycles=60, until=lambda o: lin(o, "crc-ll")["state"] == "DONE"
                 and (lin(o, "crc-hal")["reason"] or "").startswith("INPUT_GAP"))
    o = outs[-1]
    assert (lin(o, "crc-hal")["state"], lin(o, "crc-hal")["reason"]) == ("WAITING",
                                                                         "INPUT_GAP:CPU_TIMING_BUDGET:ex-crc-hal")
    assert not [x for x in line.launched if "CRCHAL" in x["wo"]]
    gap.clear()
    drive(env, pl, cycles=5, until=lambda o: any("CRCHAL" in x["wo"] for x in line.launched))
    assert [x for x in line.launched if "CRCHAL" in x["wo"]]


def test_without_the_check_the_line_behaves_as_before(env):
    ladder(env)
    assert not hasattr(env["line"], "input_gaps")
    outs = drive(env, placer(env), cycles=30, until=lambda o: lin(o, "crc-ll")["state"] == "DONE")
    assert lin(outs[-1], "crc-ll")["state"] == "DONE"
