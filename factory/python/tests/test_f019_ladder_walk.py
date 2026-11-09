"""Feature 019 (owner 2026-11-09: "implement first the low level driver, then the whole driver for the same model"):
the line walks the ladder by itself - LL, then the HAL on it, then the next peripheral's LL - one step at a time."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

from test_line_conductor_m3 import drive, env, grant, lin, lineage, placer, write_campaign  # noqa: F401

STEP = ("RUNNING", "LAUNCHING", "QUEUED", "CHAINED")


def dep(lid):
    return {"lineage": lid, "phase": "SWE.6", "verdict": "PASS"}


def ladder(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261109-L1", priority=50),
                         lineage("crc-hal", "CRCHAL", "20261109-L2", priority=49, depends_on=dep("crc-ll")),
                         lineage("wwdg-ll", "WWDGL", "20261109-L3", priority=48, after=dep("crc-hal"))])
    grant(env)


def names(tag, series):
    return [f"WO-F014-SWE{n}-{tag}-{series}" for n in range(1, 7)]


def test_the_line_walks_the_ladder_one_step_at_a_time(env):
    ladder(env)
    pl = placer(env)
    first = pl.cycle()
    assert (lin(first, "wwdg-ll")["state"], lin(first, "wwdg-ll")["reason"]) == ("WAITING", "AFTER:crc-hal:SWE.6:PASS")
    outs = [first] + drive(env, pl, cycles=120, until=lambda o: lin(o, "wwdg-ll")["state"] == "DONE")
    assert lin(outs[-1], "wwdg-ll")["state"] == "DONE"
    ll, hal, ww = names("CRCL", "20261109-L1"), names("CRCHAL", "20261109-L2"), names("WWDGL", "20261109-L3")
    launched = env["line"].launched
    assert [x["wo"] for x in launched] == ll + hal + ww
    assert [x.get("--provided-from") for x in launched] == [None] * 6 + [ll[-1]] * 6 + [None] * 6
    for o in outs:  # never two ladder steps at once
        assert sum(lin(o, x)["state"] in STEP for x in ("crc-ll", "crc-hal", "wwdg-ll")) <= 1


def test_a_lineage_grown_from_one_phase_continues_from_its_passed_phase(env):
    write_campaign(env, [lineage("wwdg-ll", "WWDGL", "20261109-L44", phases=["SWE.1"])])
    grant(env)
    drive(env, placer(env), cycles=20, until=lambda o: lin(o, "wwdg-ll")["state"] == "DONE")
    swe1 = "WO-F014-SWE1-WWDGL-20261109-L44"
    assert [x["wo"] for x in env["line"].launched] == [swe1]
    write_campaign(env, [lineage("wwdg-ll", "WWDGL", "20261109-L44")])  # the six phases (L44F case)
    drive(env, placer(env), cycles=5, until=lambda o: len(env["line"].launched) >= 2)
    nxt = env["line"].launched[1]
    assert nxt["wo"] == "WO-F014-SWE2-WWDGL-20261109-L44" and nxt["--resume-from"] == swe1
    assert [x["wo"] for x in env["line"].launched].count(swe1) == 1  # SWE.1 never rerun


def test_the_swe1_stage_walks_ll_hal_on_a_verified_ll_then_the_next_ll(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261109-L1", priority=50, phases=["SWE.1"]),
                         lineage("crc-hal", "CRCHAL", "20261109-L2", priority=49, phases=["SWE.1"],
                                 provided_from="WO-F014-SWE6-CRCL-20261103-L24",
                                 after={"lineage": "crc-ll", "phase": "SWE.1", "verdict": "PASS"}),
                         lineage("wwdg-ll", "WWDGL", "20261109-L3", priority=48, phases=["SWE.1"],
                                 after={"lineage": "crc-hal", "phase": "SWE.1", "verdict": "PASS"})])
    grant(env)
    outs = drive(env, placer(env), cycles=40, until=lambda o: lin(o, "wwdg-ll")["state"] == "DONE")
    launched = env["line"].launched
    assert [x["wo"] for x in launched] == ["WO-F014-SWE1-CRCL-20261109-L1", "WO-F014-SWE1-CRCHAL-20261109-L2",
                                           "WO-F014-SWE1-WWDGL-20261109-L3"]
    assert [x.get("--provided-from") for x in launched] == [None, "WO-F014-SWE6-CRCL-20261103-L24", None]
    for o in outs:
        assert sum(lin(o, x)["state"] in STEP for x in ("crc-ll", "crc-hal", "wwdg-ll")) <= 1
