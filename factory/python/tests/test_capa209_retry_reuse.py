"""CAPA-209 (owner 2026-11-09 "implement the 3 points that could make it faster"): SPI LL L41N passed 38 of 40
requirements in phase 1 and ended BLOCKED on an input gap; its retry L41O started SWE.1 from scratch, re-authoring every
task and re-inspecting every requirement. A retry of the first phase now names the failed attempt (retry_of); the work
order records it (fresh_recovery_from kind LINE_RETRY) so an author task whose packet is identical is revalidated and
reused (visit.inherited_task), and a requirement whose phase-1 inspection packet is identical keeps its PASS verdict.
Everything else - changed tasks, failed verdicts, the set inspection, baselines and gates - runs again."""
# ruff: noqa: F811 - shared pytest fixtures are imported from their home modules
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory.afo import line_launcher as LLA
from forge_factory.afo import line_orders as LO
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.line_recovery_product import order_arguments
from forge_factory.common import sha256_file
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1_quality as Q
from test_f018_phase1 import MODEL, _finding, _model, assembled  # noqa: F401
from test_line_conductor_m3 import X, drive, env, grant, lineage, placer, write_campaign  # noqa: F401
from test_lrtx_swe1 import ws  # noqa: F401


# ---- the line names the failed attempt of the first phase -------------------------------------------------------------
def test_a_first_phase_retry_names_the_failed_attempt_and_later_phases_do_not(env):
    write_campaign(env, [lineage("crc-ll", "CRCL", "20261103-L30", phases=["SWE.1", "SWE.2"])])
    grant(env)
    sw1 = "WO-F014-SWE1-CRCL-20261103-L30"
    drive(env, placer(env), {sw1: X, "WO-F014-SWE2-CRCL-20261103-L30B": X}, cycles=8)
    launched = env["line"].launched
    first = [x for x in launched if x["wo"].startswith("WO-F014-SWE1-")]
    assert first[0]["wo"] == sw1 and "--retry-of" not in first[0]
    assert first[1]["wo"] == sw1 + "B" and first[1]["--retry-of"] == sw1
    spec = json.loads((LO.supervisor_dir() / "line-orders" / f"{sw1}B.json").read_text())
    assert spec["kind"] == "RETRY" and spec["retry_of"] == sw1 and spec["resume_from"] is None
    assert not [x for x in launched if x["wo"].startswith("WO-F014-SWE2-") and "--retry-of" in x]
    start = json.loads((LO.supervisor_dir() / "line-orders" / f"{sw1}.json").read_text())
    assert "retry_of" not in start  # orders that are not first-phase retries keep their digest


def test_the_owner_lane_envelope_takes_only_a_same_lineage_same_phase_retry_source():
    spi = [w for w, s in D.ORDER_SCOPE.items() if s[:2] == ("spi-ll", "SWE.1")]
    tim = next(w for w, s in D.ORDER_SCOPE.items() if s[:2] == ("tim-ll", "SWE.1"))
    spi2 = next(w for w, s in D.ORDER_SCOPE.items() if s[:2] == ("spi-ll", "SWE.2"))
    o = {"wo": spi[1], "kind": "RETRY", "resume_from": None, "retry_of": spi[0]}
    assert D._retry_shape(o, "spi-ll", "SWE.1") and D._retry_shape({**o, "retry_of": None}, "spi-ll", "SWE.1")
    for bad in ({"retry_of": tim}, {"retry_of": spi2}, {"retry_of": spi[1]}, {"kind": "CHAIN"},
                {"resume_from": spi2}, {"retry_of": "WO-NOT-AN-ORDER"}):
        assert not D._retry_shape({**o, **bad}, "spi-ll", "SWE.1"), bad


def test_the_launcher_and_the_durable_launch_bind_the_retry_source():
    o = LLA.Order(wo="WO-F014-SWE1-SPIL-20261107-L41O", rev="a" * 40, example="0011l-st-cube-spi-swe1-gen",
                  profile="p", model="m", stop_after="SWE.1", retry_of="WO-F014-SWE1-SPIL-20261107-L41N")
    o.validate()
    a = o.workorder_args()
    assert a[a.index("--retry-of") + 1] == "WO-F014-SWE1-SPIL-20261107-L41N"
    assert order_arguments(o)["retry_of"] == "WO-F014-SWE1-SPIL-20261107-L41N"
    plain = LLA.Order(wo="WO-F014-SWE1-SPIL-20261107-L41N", rev="a" * 40, example="e", profile="p", model="m")
    assert "retry_of" not in order_arguments(plain) and "retry_of" not in plain.view()
    with pytest.raises(LLA.LaunchError, match="retry_of"):
        LLA.Order(wo="WO-A-123", rev="a" * 40, example="e", profile="p", model="m", retry_of="bad").validate()


def test_a_line_retry_needs_its_source():
    from forge_factory import workorder as W

    with pytest.raises(ValueError, match="LINE_RETRY_SOURCE_REQUIRED"):
        W.run(W.REPO_ROOT / "examples/0009a-iwdg-ll", "WO-T-NO-SOURCE", False, line_retry=True)


# ---- phase-1 verdicts of identical inspection packets are kept --------------------------------------------------------
def _retry_copy(src, kind="LINE_RETRY"):
    dst = src.parents[1] / "WO-T-IWDG-LL-R" / "workspace"
    shutil.copytree(src, dst, symlinks=True)
    shutil.rmtree(dst / ".forge-run/lrtx/SWE.1/phase1")
    man = json.loads((dst / ".forge-run/manifest.json").read_text())
    man["work_order"] = "WO-T-IWDG-LL-R"
    man["fresh_recovery_from"] = {"work_order": "WO-T-IWDG-LL", "kind": kind, "revalidate_author_tasks": True,
                                  "source_manifest_sha256": sha256_file(src / ".forge-run/manifest.json")}
    (dst / ".forge-run/manifest.json").write_text(json.dumps(man))
    return dst


def test_a_retry_keeps_the_passed_verdicts_of_identical_packets_and_rejudges_the_rest(assembled, monkeypatch):
    src = assembled
    flag = {"prescaler": lambda r: [_finding()]}  # the source failed this one
    monkeypatch.setattr(S, "call", _model(src, [], flag))
    assert Q.iq_inspect(src, MODEL)["status"] == "PASS"
    passed = {v["key"] for v in Q.verdicts(src).values() if v["passed"]}
    assert passed and "prescaler" not in passed
    dst = _retry_copy(src)
    calls = []
    monkeypatch.setattr(S, "call", _model(dst, calls))
    assert Q.iq_inspect(dst, MODEL)["status"] == "PASS"
    assert [p["task"].rsplit(":", 1)[1] for p in calls if p["task"].startswith("iq:")] == ["prescaler"]
    got = Q.verdicts(dst).values()
    inherited = {v["key"] for v in got if v.get("inherited_from")}
    assert inherited == passed and all(v["inherited_from"]["source_work_order"] == "WO-T-IWDG-LL" for v in got
                                       if v.get("inherited_from"))


def test_no_verdict_is_kept_without_a_line_retry_or_with_a_changed_source(assembled, monkeypatch):
    src = assembled
    monkeypatch.setattr(S, "call", _model(src, []))
    assert Q.iq_inspect(src, MODEL)["status"] == "PASS"
    n = len(Q.requirements(src))
    for kind in ("FRESH_REVALIDATION", "LINE_RETRY"):
        dst = _retry_copy(src, kind)
        if kind == "LINE_RETRY":  # the source manifest changed after the retry was bound
            (src / ".forge-run/manifest.json").write_text((src / ".forge-run/manifest.json").read_text() + " ")
        calls = []
        monkeypatch.setattr(S, "call", _model(dst, calls))
        assert Q.iq_inspect(dst, MODEL)["status"] == "PASS"
        assert len([p for p in calls if p["task"].startswith("iq:")]) == n, kind
        shutil.rmtree(dst.parent)
