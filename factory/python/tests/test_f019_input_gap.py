"""Feature 019 (owner 2026-11-09: "Omniverse fully responsible to prepare all the inputs for the run"): a ladder step
whose work-order spec does not exist is held as INPUT_GAP and blocks the later steps; it starts once the spec exists."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

from test_f019_ladder_walk import ladder
from test_line_conductor_m3 import drive, env, lin, placer  # noqa: F401


def test_a_missing_spec_holds_the_step_and_every_later_step(env):
    ladder(env)
    line = env["line"]
    missing = {"ex-crc-hal"}
    real = line.spec_quality
    line.spec_quality = lambda sha, ex: (False, None) if ex in missing else real(sha, ex)
    pl = placer(env)
    outs = drive(env, pl, cycles=60, until=lambda o: lin(o, "crc-ll")["state"] == "DONE"
                 and (lin(o, "crc-hal")["reason"] or "").startswith("INPUT_GAP"))
    o = outs[-1]
    assert (lin(o, "crc-hal")["state"], lin(o, "crc-hal")["reason"]) == ("WAITING", "INPUT_GAP:WORKORDER_SPEC:ex-crc-hal")
    assert lin(o, "wwdg-ll")["reason"] == "AFTER:crc-hal:SWE.6:PASS"
    assert not [x for x in line.launched if "CRCHAL" in x["wo"] or "WWDGL" in x["wo"]]
    missing.clear()  # the onboarding stage delivered the spec in a deployed revision
    drive(env, pl, cycles=5, until=lambda o: any("CRCHAL" in x["wo"] for x in line.launched))
    hal = [x for x in line.launched if "CRCHAL" in x["wo"]]
    assert hal and hal[0]["--provided-from"] == "WO-F014-SWE6-CRCL-20261109-L1"
