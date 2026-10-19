"""SLO evidence (owner 2026-10-17: SLO reduced to 10 runs per cohort): readiness groups packaged attempts by cohort AND
recorded factory revision; >= min_n attempts gives a measured baseline with a Wilson interval, never an attainment."""
from forge_factory.reliability import readiness as RD


def _att(i, rev="70ccc9e", done=True, ck="driver_class=LL|mode=FULL", finished="2026-10-17T00:00:00Z"):
    return {"attempt_id": f"WO-X-r{i}", "cohort_key": ck, "revision": rev, "revision_basis": "recorded_at_launch",
            "finished": finished, "completed": done}


def test_baseline_measured_only_with_enough_attempts_on_one_revision(monkeypatch):
    atts = [_att(i, done=i % 5 != 0) for i in range(1, 11)] + [_att(99, rev="other")]
    monkeypatch.setattr("forge_factory.reliability.metrics.attempts", lambda: atts)
    out = RD.slo_evidence(10, [])
    assert out["status"] == "BASELINE_MEASURED" and out["attainment"].startswith("NOT_EVALUATED")
    [m] = out["measured_cohorts"]
    assert (m["n"], m["completed"], m["factory_revision"]) == (10, 8, "70ccc9e")
    assert m["wilson95"][0] < 0.8 < m["wilson95"][1]
    assert RD.slo_evidence(11, [])["status"] == "NOT_DEMONSTRATED"  # other revisions never pool


def test_unfinished_and_excluded_attempts_do_not_count(monkeypatch):
    atts = [_att(i) for i in range(1, 10)] + [_att(10, finished=None), _att(98)]
    monkeypatch.setattr("forge_factory.reliability.metrics.attempts", lambda: atts)
    monkeypatch.setattr(RD, "_read", lambda rel: {"excluded": {"WO-X-r98": "owner stop"}} if "exclusions" in rel else None)
    assert RD.slo_evidence(10, [])["status"] == "NOT_DEMONSTRATED"
