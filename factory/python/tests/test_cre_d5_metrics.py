"""CRE D5 (CRE-T030..T034): unit semantics, Wilson/zero-failure bounds, SPC calibration, batch=incremental,
cohort-safe growth comparison (AT-027..AT-031)."""
import copy
import random

import pytest
from forge_factory.common import canonical_json, sha256_bytes
from forge_factory.reliability import metrics as M
from forge_factory.reliability.policy import Policy, issues_of, load
from forge_factory.reliability.store import CREStore

COH = {"driver_class": "RCC", "target": "CM55", "model": "m", "code_model": "-", "provider": "p", "mode": "FULL"}


def att(aid, order, started, completed, first=None, cohort=COH, revision="UNKNOWN"):
    ck = "|".join(f"{k}={v}" for k, v in cohort.items())
    return {"attempt_id": aid, "order_id": order, "started": started, "finished": None, "cohort": cohort,
            "cohort_key": ck, "revision": revision, "revision_basis": "x", "completed": completed,
            "phases_passed": [], "first_inspection": first or {}, "author_visits": {"SWE.3": 1},
            "package_status": "BLOCKED"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return CREStore(tmp_path / "m.sqlite3"), load()


def by_id(rep, mid, cohort=None):
    return [m for m in rep["measurements"] if m["metric_id"] == mid and (cohort is None or m["cohort_key"] == cohort)]


# ---- CRE-T030 / AT-027 -------------------------------------------------------------------------------------------
def test_retries_never_raise_first_pass_or_order_counts(env):
    store, pol = env
    atts = [att("WO-1", "WO-1", "2026-10-16T01:00:00.000000Z", False, {"SWE.3": "REWORK"}),
            att("WO-1-r1", "WO-1", "2026-10-16T02:00:00.000000Z", False, {"SWE.3": "REWORK"}),
            att("WO-1-r2", "WO-1", "2026-10-16T03:00:00.000000Z", False, {"SWE.3": "REWORK"}),
            att("WO-1-r3", "WO-1", "2026-10-16T04:00:00.000000Z", True, {"SWE.3": "PASS"}),
            att("WO-2", "WO-2", "2026-10-16T05:00:00.000000Z", True, {"SWE.3": "PASS"})]
    rep = M.compute(store, pol, atts, now="2026-10-16T06:00:00.000000Z")
    [r01] = by_id(rep, "CRE-R01")
    assert (r01["numerator"], r01["denominator"]) == (1, 2)  # one of two ORDERS succeeded on its first attempt
    [r10] = by_id(rep, "CRE-R10-SWE.3")
    assert (r10["numerator"], r10["denominator"]) == (2, 5)  # attempt-level, labelled distinctly from K01
    [r07] = by_id(rep, "CRE-R07")
    assert r07["status"] == "NOT_APPLICABLE"  # no READY package: no cost per accepted package
    assert {m["metric_id"] for m in rep["measurements"]} >= {"CRE-R01", "CRE-R02", "CRE-R03", "CRE-R05", "CRE-R06",
                                                             "CRE-R08", "CRE-R09", "K16", "K17"}


# ---- CRE-T031 / AT-028 -------------------------------------------------------------------------------------------
def test_small_samples_never_claim_100_percent(env):
    _, pol = env
    m = M.measurement("CRE-R09", "c", "2026-10-16T00:00:00Z", "2026-10-16T01:00:00Z", 5, 5, policy=pol)
    assert m["value"] == 1.0 and m["ci_lower"] < 0.6 and m["ci_upper"] == 1.0
    assert "n=5" in m["quality_notes"] and any("not 100% reliability" in n for n in m["quality_notes"])
    assert 0.0098 < M.zero_failure_upper(300) < 0.0100 and abs(M.zero_failure_upper(300) - 3 / 300) < 0.0003
    z = M.measurement("CRE-R05", "c", "2026-10-16T00:00:00Z", "2026-10-16T01:00:00Z", None, None, policy=pol)
    assert z["status"] == "NOT_COMPUTABLE" and z["value"] is None and z["ci_lower"] is None
    lo, hi = M.wilson(4, 30)
    assert round(lo, 3) == 0.053 and round(hi, 3) == 0.297


# ---- CRE-T032 / AT-029 -------------------------------------------------------------------------------------------
def enabled_policy():
    d = copy.deepcopy(load().data)
    d["statistics"]["p_chart_enabled_after_calibration"] = True
    d["statistics"]["ewma_enabled_after_calibration"] = True
    assert issues_of(d) == []
    return Policy(d, sha256_bytes(canonical_json(d)), "test")


def test_spc_needs_a_frozen_calibration_and_only_emits_diagnostics(env):
    store, pol = env
    samples = [(f"g{i}", d, 10) for i, d in enumerate([1, 2, 1, 9, 1])]
    assert M.p_chart(pol, samples, None)["status"] == "INSUFFICIENT_BASELINE"
    assert M.ewma(pol, [0.1, 0.2], {"mean": 0.1, "sd": 0.05})["status"] == "INSUFFICIENT_BASELINE"  # policy off
    on = enabled_policy()
    assert M.p_chart(on, samples, {"pbar": 0.15, "samples": 10, "frozen_at": "x"})["status"] == "INSUFFICIENT_BASELINE"
    chart = M.p_chart(on, samples, {"pbar": 0.15, "samples": 40, "frozen_at": "2026-10-16T00:00:00Z"})
    assert chart["status"] == "MEASURED" and chart["signals"] == ["g3"]
    assert M.ewma(on, [0.1] * 5 + [0.9] * 3, {"mean": 0.1, "sd": 0.05})["signals"]
    before = load().sha256
    assert M.emit_spc_signals(store, on, "p:test", chart["signals"]) == 1
    [ev] = store.events("cre.spc_signal")
    assert ev["payload"]["action"] == "DIAGNOSTIC_ONLY" and load().sha256 == before  # no auto-tuning of policy


# ---- CRE-T033 / AT-030 -------------------------------------------------------------------------------------------
def test_batch_replay_and_incremental_aggregation_are_identical(env, tmp_path):
    store, pol = env
    atts = [att(f"A{i}", "WO-1", f"2026-10-16T0{i}:00:00.000000Z", i % 3 == 0) for i in range(9)]
    a = M.compute(store, pol, atts, now="2026-10-16T12:00:00.000000Z")
    b = M.compute(store, pol, list(reversed(atts)), now="2026-10-16T12:00:00.000000Z")
    assert canonical_json(a) == canonical_json(b)  # same event set + policy => identical metrics
    inc = M.IncrementalR09()
    stream = atts + atts[:4]
    random.Random(3).shuffle(stream)
    for x in stream:  # reordered, duplicated delivery
        inc.add(x)
    [r09] = by_id(a, "CRE-R09")
    assert inc.counts() == {r09["cohort_key"]: (r09["numerator"], r09["denominator"])}
    assert M.cloud_tokens(atts[0], tmp_path / "no-meter.jsonl") == {"status": "UNKNOWN"}  # missing => UNKNOWN, not 0


# ---- CRE-T034 / AT-031 -------------------------------------------------------------------------------------------
def test_comparisons_refuse_unlike_cohorts_and_report_uncertainty(env):
    _, pol = env
    other = {**COH, "model": "other", "mode": "RESUMED"}
    assert M.comparable(COH, other) == ["model", "mode"]
    assert M.comparable(COH, {**COH, "mode": "RESUMED"}, {"ignore_keys": ["mode"]}) == []
    head = __import__("subprocess").run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                         cwd=M.REPO_ROOT).stdout.strip()
    old = __import__("subprocess").run(["git", "rev-parse", "HEAD~20"], capture_output=True, text=True,
                                        cwd=M.REPO_ROOT).stdout.strip()
    atts = ([att(f"p{i}", "o", "2026-10-15T00:00:00Z", False, revision=old) for i in range(6)] +
            [att(f"q{i}", "o", "2026-10-16T00:00:00Z", True, revision=head) for i in range(2)] +
            [att(f"x{i}", "o", "2026-10-16T00:00:00Z", True, cohort=other, revision=head) for i in range(9)])
    r = M.growth_report(pol, atts, COH, "HEAD~10")
    assert r["excluded_other_cohorts"] == 9 and (r["pre"]["n"], r["post"]["n"]) == (6, 2)
    assert r["verdict"] == "IMPROVEMENT_SUPPORTED" or r["verdict"] == "NO_SIGNIFICANT_DIFFERENCE"
    small = M.growth_report(pol, atts[:6] + atts[6:7], COH, "HEAD~10")
    assert small["verdict"] == "NO_SIGNIFICANT_DIFFERENCE"  # 0/6 vs 1/1: intervals overlap, no claim
